"""
Regression tests for PollingScheduler._poll_loop offline-recovery behaviour.

Prior to the fix in this PR, once a device hit `max_consecutive_failures`
the poll loop `break`ed and stopped polling that device until the TCP
connection dropped and the ESP32 re-handshaked.  Same devices ended up
on the offline list day after day.  Production log evidence: on
faisal-home the top 6 offenders each showed up 6 times in one week's
polling-manager.log, always with `Too many poll failures (5)`.

The scheduler must now:

  * mark the device offline exactly once when the threshold is first
    crossed (fires the callback for HA / dashboards);
  * KEEP RUNNING the poll loop, with the existing exponential backoff
    stretching the poll interval;
  * fire the on_device_online callback and reset the offline flag as
    soon as any subsequent poll succeeds — so recovery is automatic.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from system_b.device_server.devices.device_state import (
    DeviceState,
    DeviceStatus,
)
from system_b.device_server.polling.scheduler import PollingScheduler


def _make_state(interval: int = 0) -> DeviceState:
    return DeviceState(
        device_id=uuid4(),
        serial_number="SH01TEST00000001",
        protocol_id="senergy",
        device_type="inverter",
        connection_id=uuid4(),
        remote_addr="127.0.0.1:12345",
        poll_interval=interval,
    )


def _make_scheduler(device_state: DeviceState):
    """Build a scheduler wired to a fake device_manager + fake collector."""
    from system_b.device_server.config import DeviceServerSettings

    settings = DeviceServerSettings()
    # Speed up backoff for the test — keep the min/max tight.
    settings.polling.min_interval = 0
    settings.polling.max_interval = 1
    settings.polling.max_consecutive_failures = 3
    settings.polling.failure_backoff = False   # keep interval predictable

    device_manager = MagicMock()
    device_manager.get_device.return_value = device_state
    device_manager.mark_device_offline = AsyncMock()

    scheduler = PollingScheduler(device_manager=device_manager, settings=settings)
    scheduler.collector = MagicMock()
    scheduler.processor = MagicMock()
    scheduler.processor.process.return_value = {"ok": True}
    return scheduler, device_manager


class TestPollLoopSurvivesOfflineBurst:
    """
    Simulate the production pattern: N consecutive Modbus failures push
    consecutive_failures over the threshold, then subsequent polls
    succeed.  The loop must continue running through the failure burst
    and auto-recover on the first success.
    """

    @pytest.mark.asyncio
    async def test_loop_does_not_break_when_threshold_crossed(self):
        state = _make_state()
        scheduler, dm = _make_scheduler(state)
        scheduler._running = True

        offline_cb = AsyncMock()
        online_cb = AsyncMock()
        telemetry_cb = AsyncMock()
        scheduler.set_on_device_offline(offline_cb)
        scheduler.set_on_device_online(online_cb)
        scheduler.set_on_telemetry(telemetry_cb)

        # Sequence: 4 failures (pushes past threshold=3), then 3 successes.
        # collector.collect returns (success, telemetry, error).
        outcomes = [
            (False, None, "modbus timeout"),
            (False, None, "modbus timeout"),
            (False, None, "modbus timeout"),
            (False, None, "modbus timeout"),
            (True, {"pv_power_w": 4200}, None),
            (True, {"pv_power_w": 4300}, None),
            (True, {"pv_power_w": 4400}, None),
        ]
        idx = {"i": 0}

        async def fake_collect(_device_id):
            i = idx["i"]
            idx["i"] += 1
            success, tel, err = outcomes[i] if i < len(outcomes) else (True, {}, None)
            # Mirror what the real collector does — update DeviceState too.
            state.record_poll(success=success, data=tel, error=err)
            return success, tel, err

        scheduler.collector.collect = AsyncMock(side_effect=fake_collect)

        # poll_interval=0 makes the loop's wait_for timeout immediately, so
        # real wallclock never has to advance for the test to drain outcomes.
        # We poll idx["i"] with real sleep() slices (not asyncio.sleep(0),
        # which just yields once) so the poll loop actually runs.
        async def loop_and_stop():
            task = asyncio.create_task(scheduler._poll_loop(state.device_id))
            deadline = 0
            while idx["i"] < len(outcomes) and deadline < 200:
                await asyncio.sleep(0.005)
                deadline += 1
            scheduler._running = False
            scheduler._shutdown_event.set()
            await asyncio.wait_for(task, timeout=2.0)

        await loop_and_stop()

        # ---- Assertions ----------------------------------------------------

        # 1. The loop drained every outcome — no early break.
        assert idx["i"] >= len(outcomes), (
            f"poll loop broke early after {idx['i']} outcomes "
            f"— expected {len(outcomes)}"
        )

        # 2. Offline callback fired exactly once (when threshold first hit),
        #    not repeatedly for every failure past it.
        assert offline_cb.call_count == 1, (
            f"expected offline callback to fire once, got {offline_cb.call_count}"
        )

        # 3. Recovery callback fired exactly once (on the first success after
        #    the offline event).
        assert online_cb.call_count == 1, (
            f"expected online callback to fire once, got {online_cb.call_count}"
        )

        # 4. Telemetry callback fired for each successful poll after recovery.
        assert telemetry_cb.call_count == 3, (
            f"expected 3 telemetry callbacks, got {telemetry_cb.call_count}"
        )

        # 5. DeviceState reflects final ONLINE status with consecutive_failures reset.
        assert state.status == DeviceStatus.ONLINE
        assert state.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_offline_callback_not_refired_while_still_failing(self):
        """
        Consecutive failures beyond the threshold must NOT keep firing the
        offline callback every cycle — that would spam Redis writes and
        log noise.
        """
        state = _make_state()
        scheduler, _ = _make_scheduler(state)
        scheduler._running = True

        offline_cb = AsyncMock()
        scheduler.set_on_device_offline(offline_cb)

        # 8 straight failures — well past the 3-failure threshold.
        outcomes = [(False, None, "err")] * 8
        idx = {"i": 0}

        async def fake_collect(_device_id):
            i = idx["i"]
            idx["i"] += 1
            success, tel, err = outcomes[i] if i < len(outcomes) else (False, None, "err")
            state.record_poll(success=success, data=tel, error=err)
            return success, tel, err

        scheduler.collector.collect = AsyncMock(side_effect=fake_collect)

        task = asyncio.create_task(scheduler._poll_loop(state.device_id))
        deadline = 0
        while idx["i"] < len(outcomes) and deadline < 200:
            await asyncio.sleep(0.005)
            deadline += 1
        scheduler._running = False
        scheduler._shutdown_event.set()
        await asyncio.wait_for(task, timeout=2.0)

        # 8 failures, but offline callback only fires once.
        assert idx["i"] >= 8
        assert offline_cb.call_count == 1

    @pytest.mark.asyncio
    async def test_flap_offline_online_offline_fires_callbacks_twice(self):
        """
        A device that recovers then dies again must fire offline once,
        online once, offline again — never once online resets, the guard.
        """
        state = _make_state()
        scheduler, _ = _make_scheduler(state)
        scheduler._running = True

        offline_cb = AsyncMock()
        online_cb = AsyncMock()
        scheduler.set_on_device_offline(offline_cb)
        scheduler.set_on_device_online(online_cb)

        # Fail x4 → succeed x2 → fail x4 again.
        outcomes = (
            [(False, None, "err")] * 4
            + [(True, {"pv_power_w": 1000}, None)] * 2
            + [(False, None, "err")] * 4
        )
        idx = {"i": 0}

        async def fake_collect(_device_id):
            i = idx["i"]
            idx["i"] += 1
            success, tel, err = outcomes[i] if i < len(outcomes) else (True, {}, None)
            state.record_poll(success=success, data=tel, error=err)
            return success, tel, err

        scheduler.collector.collect = AsyncMock(side_effect=fake_collect)

        task = asyncio.create_task(scheduler._poll_loop(state.device_id))
        deadline = 0
        while idx["i"] < len(outcomes) and deadline < 400:
            await asyncio.sleep(0.005)
            deadline += 1
        scheduler._running = False
        scheduler._shutdown_event.set()
        await asyncio.wait_for(task, timeout=2.0)

        assert offline_cb.call_count == 2, (
            f"expected 2 offline fires (initial + relapse), got {offline_cb.call_count}"
        )
        assert online_cb.call_count == 1, (
            f"expected 1 online fire (mid-sequence recovery), got {online_cb.call_count}"
        )
