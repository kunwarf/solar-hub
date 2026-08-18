"""
Energy spike guard for the HA MQTT publisher.

Home Assistant's Energy dashboard is driven by long-term statistics computed
from `total_increasing` and `total` sensors.  A single implausible reading
(e.g. a lifetime-total counter accidentally landing on a daily-total sensor,
or a Modbus mis-read returning a garbage value) turns into a huge hourly
delta that HA records as real energy consumption / production.  Once written,
the spike stays in HA's statistics database and makes the whole day
unusable in the dashboard.

This module rejects any energy reading that:
  * exceeds an absolute plausibility ceiling for its metric class, or
  * jumps by more than a plausible delta from the previous accepted value.

The "previous accepted value" is stored in Redis with a 24 h TTL so the
guard survives publisher restarts.  When a reading is rejected we return
the last accepted value instead of `None`, so HA sees a flat line rather
than a gap (a gap becomes a "reset" in HA's `total_increasing` logic and
can itself cause bad statistics).

Thresholds are deliberately generous — the guard should never reject a real
reading, only obvious garbage.  For residential/light-commercial installs a
single day cannot exceed 500 kWh on any channel, and no channel can change
by more than 200 kWh between publish cycles (that would require > 24 MW of
instantaneous power).  Adjust `_TODAY_CEILING_KWH` / `_MAX_DELTA_KWH` if you
onboard genuinely industrial sites.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Any daily counter above this is impossible for the systems we support and
# is treated as garbage.  Residential daily max is < 200 kWh; we allow 2.5×
# headroom for commercial rooftops.
_TODAY_CEILING_KWH = 500.0

# Total (lifetime) counters legitimately grow forever.  Use a very loose
# ceiling only to catch obviously bogus U32 overflow values.
_TOTAL_CEILING_KWH = 10_000_000.0

# Maximum plausible change between two consecutive publish cycles (30 s by
# default).  A 200 kWh jump in 30 s implies 24 MW — not possible on any of
# our devices.  Applies to both daily and total counters.
_MAX_DELTA_KWH = 200.0

# Redis key template.  Kept short — key size matters at scale.
_LAST_GOOD_KEY = "ha:guard:{serial}:{metric}"

# Retention for last-good values.  24 h is enough to cover the longest
# expected offline window (overnight) without letting truly stale values
# hang around forever.
_LAST_GOOD_TTL = 86400

# Metrics we guard.  Any state-payload key not in this set is passed through
# unchanged (power, temperature, voltage, etc. have their own natural limits).
TODAY_METRICS = frozenset({
    "pv_energy_today_kwh",
    "grid_import_today_kwh",
    "grid_export_today_kwh",
    "load_energy_today_kwh",
    "battery_charge_today_kwh",
    "battery_discharge_today_kwh",
})

TOTAL_METRICS = frozenset({
    "pv_energy_total_kwh",
    "grid_import_total_kwh",
    "grid_export_total_kwh",
    "load_energy_total_kwh",
    "battery_charge_total_kwh",
    "battery_discharge_total_kwh",
})

GUARDED_METRICS = TODAY_METRICS | TOTAL_METRICS


class EnergySpikeGuard:
    """
    Rejects implausible energy readings before they reach Home Assistant.

    Redis-backed so the last-good value survives publisher restarts.  If
    Redis is unavailable the guard degrades to absolute-ceiling checks only
    (no per-metric delta memory).
    """

    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    async def sanitize(self, serial: str, state: Dict[str, Optional[float]]) -> None:
        """
        Sanitize `state` in-place.

        For each guarded metric key: if the value is implausible, replace it
        with the last accepted value (or drop to None if we have no history).
        Otherwise persist it as the new last-good value.
        """
        for metric, value in list(state.items()):
            if metric not in GUARDED_METRICS or value is None:
                continue
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue

            last_good = await self._get_last_good(serial, metric)
            if self._is_implausible(metric, v, last_good):
                logger.warning(
                    "[spike_guard] Rejected %s=%.2f for %s (last_good=%s) — "
                    "value out of range, replacing with last good",
                    metric, v, serial, last_good,
                )
                state[metric] = last_good  # None or previous value; either way not the spike
                continue

            await self._set_last_good(serial, metric, v)

    # ------------------------------------------------------------------
    # Guard logic
    # ------------------------------------------------------------------

    @staticmethod
    def _is_implausible(metric: str, value: float, last_good: Optional[float]) -> bool:
        # Negative energy is always bogus.
        if value < 0:
            return True

        # Absolute ceiling per metric class.
        if metric in TODAY_METRICS and value > _TODAY_CEILING_KWH:
            return True
        if metric in TOTAL_METRICS and value > _TOTAL_CEILING_KWH:
            return True

        # Delta check only fires when we have a baseline.
        if last_good is not None:
            # For today counters HA also treats a drop as a valid midnight
            # reset, so we only reject upward spikes.  For total counters a
            # drop is always suspicious (lifetime should only grow), but a
            # legitimate device replacement would drop to 0 — we let that
            # through and rely on HA's `state_class: total` semantics to
            # avoid counting it as consumption.
            if value - last_good > _MAX_DELTA_KWH:
                return True

        return False

    # ------------------------------------------------------------------
    # Redis-backed last-good store
    # ------------------------------------------------------------------

    async def _get_last_good(self, serial: str, metric: str) -> Optional[float]:
        try:
            raw = await self._redis.get(_LAST_GOOD_KEY.format(serial=serial, metric=metric))
        except Exception as exc:
            logger.debug("[spike_guard] Redis GET failed for %s/%s: %s", serial, metric, exc)
            return None
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    async def _set_last_good(self, serial: str, metric: str, value: float) -> None:
        try:
            await self._redis.setex(
                _LAST_GOOD_KEY.format(serial=serial, metric=metric),
                _LAST_GOOD_TTL,
                str(value),
            )
        except Exception as exc:
            logger.debug("[spike_guard] Redis SETEX failed for %s/%s: %s", serial, metric, exc)
