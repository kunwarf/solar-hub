"""
Last-known value cache for the HA MQTT publisher.

Motivation: Home Assistant treats a `null` state as "Unavailable" — the
sensor tile shows a dash, statistics accumulate gaps, and the Energy
dashboard's baseline charts break wherever we skip a value.  Before this
cache existed, any transient blip in the source pipeline (Modbus register
missing, adapter returning a partial dict, Redis cache write skew) meant
one or more sensors would flap to Unavailable and back, even though the
device itself was healthy.

This helper solves that by:

  1. Filling any None value in the outgoing state payload with the
     last non-None value we published for the same (serial, metric).
  2. Falling back to a metric-appropriate zero if we've never seen the
     metric before (first publish after boot).
  3. Persisting each published value in Redis with a 24 h TTL so a
     publisher restart doesn't clear the memory.

Interaction with the availability topic: this cache does NOT hide genuine
outages.  When the source device is stale (`age_seconds > 300`) the
publisher sends availability=offline and returns early WITHOUT touching
the state topic.  HA then marks the entity Unavailable regardless of
whatever state we published earlier.  So users still see accurate offline
state for real outages, while brief transient dips (a single missed poll,
a Redis-cache race) become invisible.

Interaction with EnergySpikeGuard: the spike guard runs BEFORE this cache
in the publish pipeline.  If the guard drops a spike, the metric becomes
None, and this cache then substitutes the last-known.  End result: HA
sees the last accepted value, not the spike, not a null.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


_LAST_KEY = "ha:lastpub:{serial}:{metric}"
_LAST_TTL = 86400  # 24 h — survives publisher restart, doesn't linger forever

# Metrics whose zero-value default is a reasonable first-boot substitute.
# Power in watts and cumulative energy in kWh are legitimately zero at
# various points in the day (nighttime, midnight rollover, first daylight)
# so publishing 0 is semantically correct and users see continuous data
# rather than Unavailable flapping.
_ZERO_OK_METRICS = frozenset({
    # ── Live power ──────────────────────────────────────────────
    "pv_power_w",
    "grid_power_w",
    "load_power_w",
    "battery_power_w",
    # ── Energy today (starts at 0 each day) ─────────────────────
    "pv_energy_today_kwh",
    "grid_import_today_kwh",
    "grid_export_today_kwh",
    "load_energy_today_kwh",
    "battery_charge_today_kwh",
    "battery_discharge_today_kwh",
    # ── Energy total (lifetime) ─────────────────────────────────
    # A brand-new install genuinely has 0 lifetime kWh, so 0 is a
    # reasonable first-boot default.  From then on the last-known
    # takes over and preserves the accumulator.
    "pv_energy_total_kwh",
    "grid_import_total_kwh",
    "grid_export_total_kwh",
    "load_energy_total_kwh",
    "battery_charge_total_kwh",
    "battery_discharge_total_kwh",
})

# Metadata fields we should not cache/inject — they're static per publish
# and would only add noise if we cached them.
_SKIP_METRICS = frozenset({
    "last_reset_epoch",
})


class LastKnownCache:
    """
    Per-(serial, metric) last-known-value store backed by Redis.

    Not thread-safe on its own but individual Redis pipelines are, and the
    publisher only calls fill_and_update() from one asyncio task at a time
    per device.
    """

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def fill_and_update(
        self, serial: str, state: Dict[str, Optional[float]]
    ) -> None:
        """
        Fill None values in `state` from the last-known cache, and update
        the cache with the non-None values so the next publish can use
        them.  Mutates `state` in-place.

        Order matters — we FILL before we UPDATE, so a None value that
        got replaced by a last-known does NOT overwrite that last-known
        with itself (a no-op that would still cost a Redis roundtrip).
        """
        # Split into (missing, present) so we can fetch all misses in one
        # mget round-trip.
        missing = [k for k, v in state.items() if v is None and k not in _SKIP_METRICS]
        present = [k for k, v in state.items() if v is not None and k not in _SKIP_METRICS]

        # Fill missing values from cache
        if missing:
            keys = [_LAST_KEY.format(serial=serial, metric=m) for m in missing]
            try:
                cached = await self._redis.mget(*keys)
            except Exception as exc:
                logger.debug("[last_known] mget failed for %s: %s", serial, exc)
                cached = [None] * len(keys)

            for metric, raw in zip(missing, cached):
                if raw is not None:
                    # Restore from cache.  Try float first for numeric
                    # values; some metrics like cycle_count are int.
                    try:
                        state[metric] = float(raw)
                    except (TypeError, ValueError):
                        state[metric] = raw
                elif metric in _ZERO_OK_METRICS:
                    # First-boot: no cache, but zero is semantically correct
                    # for this metric class.
                    state[metric] = 0.0
                # else: leave as None — HA will show Unavailable, which is
                # honest for opaque metrics we have no way to guess (SOC,
                # voltage, temperature, cycle count).  Once the device
                # publishes a real value even once, the cache takes over
                # and the sensor never goes Unavailable again for a
                # transient miss.

        # Update cache with present values.  Use a pipeline so all setex
        # calls fly out in one round-trip.
        if present:
            try:
                pipe = self._redis.pipeline()
                for metric in present:
                    pipe.setex(
                        _LAST_KEY.format(serial=serial, metric=metric),
                        _LAST_TTL,
                        str(state[metric]),
                    )
                await pipe.execute()
            except Exception as exc:
                logger.debug(
                    "[last_known] pipeline setex failed for %s: %s",
                    serial, exc,
                )
