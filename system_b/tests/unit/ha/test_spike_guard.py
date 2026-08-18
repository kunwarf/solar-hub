"""
Unit tests for EnergySpikeGuard.

The guard's job is to keep HA long-term statistics clean: reject implausible
energy readings before they get published to the MQTT state topic, while
never rejecting a legitimate value.
"""
import pytest

from system_b.device_server.ha.spike_guard import (
    EnergySpikeGuard,
    _MAX_DELTA_KWH,
    _TODAY_CEILING_KWH,
    _TOTAL_CEILING_KWH,
)


class FakeRedis:
    """Minimal in-memory Redis stub covering get/setex only."""

    def __init__(self, initial=None):
        self._store = dict(initial or {})
        self.setex_calls = []
        self.get_should_raise = False

    async def get(self, key):
        if self.get_should_raise:
            raise RuntimeError("redis unavailable")
        return self._store.get(key)

    async def setex(self, key, ttl, value):
        self.setex_calls.append((key, ttl, value))
        self._store[key] = str(value)


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.fixture
def guard(redis):
    return EnergySpikeGuard(redis)


# ---------------------------------------------------------------------------
# Absolute ceilings
# ---------------------------------------------------------------------------

class TestAbsoluteCeilings:
    async def test_today_value_above_ceiling_is_dropped(self, guard):
        state = {"pv_energy_today_kwh": _TODAY_CEILING_KWH + 1.0}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] is None  # no baseline → dropped to None

    async def test_today_value_at_ceiling_is_allowed(self, guard):
        state = {"pv_energy_today_kwh": _TODAY_CEILING_KWH}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] == _TODAY_CEILING_KWH

    async def test_typical_daily_value_is_allowed(self, guard):
        state = {"pv_energy_today_kwh": 88.4}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] == 88.4

    async def test_total_value_below_ceiling_is_allowed(self, guard):
        state = {"pv_energy_total_kwh": 20_377.92}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_total_kwh"] == 20_377.92

    async def test_total_value_above_ceiling_is_dropped(self, guard):
        state = {"pv_energy_total_kwh": _TOTAL_CEILING_KWH + 1.0}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_total_kwh"] is None

    async def test_negative_energy_is_dropped(self, guard):
        state = {"grid_import_today_kwh": -5.0}
        await guard.sanitize("SN1", state)
        assert state["grid_import_today_kwh"] is None


# ---------------------------------------------------------------------------
# Delta guard
# ---------------------------------------------------------------------------

class TestDeltaGuard:
    async def test_first_ever_reading_within_ceiling_is_accepted(self, guard):
        state = {"pv_energy_today_kwh": 5.2}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] == 5.2

    async def test_small_step_after_baseline_is_accepted(self, guard, redis):
        # First reading establishes baseline
        await guard.sanitize("SN1", {"pv_energy_today_kwh": 5.2})
        # Second reading: small increment — should pass
        state = {"pv_energy_today_kwh": 5.9}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] == 5.9

    async def test_huge_jump_is_rejected_and_last_good_returned(self, guard):
        # Baseline: 5.2 kWh this morning
        await guard.sanitize("SN1", {"pv_energy_today_kwh": 5.2})
        # Bogus reading: 20,377.92 kWh (a lifetime total landing on the daily sensor)
        state = {"pv_energy_today_kwh": 20_377.92}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] == 5.2  # last good returned

    async def test_delta_exactly_at_limit_is_allowed(self, guard):
        await guard.sanitize("SN1", {"pv_energy_total_kwh": 20_000.0})
        state = {"pv_energy_total_kwh": 20_000.0 + _MAX_DELTA_KWH}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_total_kwh"] == 20_000.0 + _MAX_DELTA_KWH

    async def test_delta_above_limit_on_total_counter_is_rejected(self, guard):
        # Baseline lifetime = 20,000 kWh
        await guard.sanitize("SN1", {"pv_energy_total_kwh": 20_000.0})
        # Reconnect after outage: device reports 20,377.92 in one publish cycle.
        # Delta = 377.92 > 200 kWh limit → reject.
        state = {"pv_energy_total_kwh": 20_377.92}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_total_kwh"] == 20_000.0  # rolled back to last good

    async def test_midnight_reset_on_daily_counter_is_allowed(self, guard):
        # Yesterday ended at 88 kWh — HA saw the reset itself; today starts at 0.
        # A DROP is fine — the guard only rejects upward spikes.
        await guard.sanitize("SN1", {"pv_energy_today_kwh": 88.0})
        state = {"pv_energy_today_kwh": 0.1}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] == 0.1


# ---------------------------------------------------------------------------
# Non-guarded fields are passed through unchanged
# ---------------------------------------------------------------------------

class TestPassThrough:
    async def test_power_field_is_never_touched(self, guard):
        # 500,000 W is nonsense but power isn't in GUARDED_METRICS
        state = {"pv_power_w": 500_000.0}
        await guard.sanitize("SN1", state)
        assert state["pv_power_w"] == 500_000.0

    async def test_none_energy_value_is_left_none(self, guard):
        state = {"pv_energy_today_kwh": None}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] is None

    async def test_non_numeric_energy_value_is_left_untouched(self, guard):
        state = {"pv_energy_today_kwh": "not-a-number"}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] == "not-a-number"


# ---------------------------------------------------------------------------
# Cross-device / cross-metric isolation
# ---------------------------------------------------------------------------

class TestIsolation:
    async def test_baselines_are_per_serial(self, guard):
        # SN1's high reading shouldn't influence SN2's guard
        await guard.sanitize("SN1", {"pv_energy_today_kwh": 100.0})
        state = {"pv_energy_today_kwh": 5.0}
        await guard.sanitize("SN2", state)
        assert state["pv_energy_today_kwh"] == 5.0

    async def test_baselines_are_per_metric(self, guard):
        # PV baseline shouldn't influence grid baseline
        await guard.sanitize("SN1", {"pv_energy_today_kwh": 88.0})
        state = {"grid_import_today_kwh": 2.0}
        await guard.sanitize("SN1", state)
        assert state["grid_import_today_kwh"] == 2.0


# ---------------------------------------------------------------------------
# Redis failure modes
# ---------------------------------------------------------------------------

class TestRedisFailure:
    async def test_get_failure_still_applies_absolute_ceiling(self, guard, redis):
        redis.get_should_raise = True
        # Spike above ceiling should still be dropped even without last-good memory
        state = {"pv_energy_today_kwh": _TODAY_CEILING_KWH + 100.0}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] is None

    async def test_get_failure_lets_reasonable_values_through(self, guard, redis):
        redis.get_should_raise = True
        state = {"pv_energy_today_kwh": 42.0}
        await guard.sanitize("SN1", state)
        assert state["pv_energy_today_kwh"] == 42.0


# ---------------------------------------------------------------------------
# Baseline is actually persisted
# ---------------------------------------------------------------------------

class TestPersistence:
    async def test_accepted_value_becomes_new_baseline(self, guard, redis):
        await guard.sanitize("SN1", {"pv_energy_today_kwh": 10.0})
        setex_call = next(
            c for c in redis.setex_calls
            if "pv_energy_today_kwh" in c[0]
        )
        key, ttl, value = setex_call
        assert value == "10.0"
        assert ttl == 86400

    async def test_rejected_value_does_not_update_baseline(self, guard, redis):
        # Baseline 5
        await guard.sanitize("SN1", {"pv_energy_today_kwh": 5.0})
        setex_before = len(redis.setex_calls)
        # Bogus 20,000
        await guard.sanitize("SN1", {"pv_energy_today_kwh": 20_000.0})
        # No new setex should have happened for the spiky metric
        new_calls = redis.setex_calls[setex_before:]
        assert not any("pv_energy_today_kwh" in c[0] for c in new_calls)
