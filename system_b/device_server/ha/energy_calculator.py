"""
Battery energy calculator for the HA MQTT publisher.

For battery devices that lack hardware energy counters (JK BMS, Pylontech, …)
this module provides two complementary strategies:

  Today's energy  — Redis accumulator: each publish cycle we integrate
                    power_w × elapsed_seconds and increment a date-keyed
                    Redis counter.  The key expires after 2 days so old
                    entries are cleaned up automatically.

  Total energy    — TimescaleDB query: sum all historical charge/discharge
                    energy from device_telemetry using a window-function
                    integration (power × time between consecutive rows).
                    Result is cached in Redis for 1 hour.

Both strategies are transparent to the publisher — call get_energy() and
get back (charge_today_kwh, discharge_today_kwh, charge_total_kwh,
discharge_total_kwh).  Any value that cannot be computed is returned as None
so the HA state payload keeps that sensor as null / Unknown.
"""
import asyncio
import logging
from datetime import date
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Redis key templates
_TODAY_CHARGE_KEY    = "ha:batt:{serial}:{date}:charge_kwh"
_TODAY_DISCHARGE_KEY = "ha:batt:{serial}:{date}:discharge_kwh"
_TOTAL_CHARGE_KEY    = "ha:batt:{serial}:total_charge_kwh"
_TOTAL_DISCHARGE_KEY = "ha:batt:{serial}:total_discharge_kwh"

_TODAY_TTL = 86400 * 2   # 2 days — covers midnight rollover
_TOTAL_TTL = 3600        # Refresh total energy from DB every hour


class BatteryEnergyCalculator:
    """
    Calculates and caches charge/discharge energy for battery devices.

    Thread-safe for asyncio use.  Create one instance shared across all
    publisher workers (pass the same instance; it is stateless beyond the
    Redis/DB connections it holds).
    """

    def __init__(self, redis_client, db_url: Optional[str] = None) -> None:
        self._redis = redis_client
        self._db_url = db_url          # plain postgresql:// URL for asyncpg
        self._db_pool = None
        self._db_lock = asyncio.Lock()

    async def get_energy(
        self,
        serial: str,
        power_w: Optional[float],
        interval_sec: float,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        Return (charge_today_kwh, discharge_today_kwh,
                charge_total_kwh,   discharge_total_kwh).

        Any unavailable value is None.

        Args:
            serial:       Device serial number.
            power_w:      Current battery power (W).
                          Positive = charging, negative = discharging.
            interval_sec: Seconds elapsed since the last publish cycle.
        """
        charge_today, discharge_today = await self._accumulate_today(
            serial, power_w, interval_sec
        )
        charge_total, discharge_total = await self._get_total(serial)
        return charge_today, discharge_today, charge_total, discharge_total

    # ------------------------------------------------------------------
    # Today (Redis accumulator)
    # ------------------------------------------------------------------

    async def _accumulate_today(
        self,
        serial: str,
        power_w: Optional[float],
        interval_sec: float,
    ) -> Tuple[Optional[float], Optional[float]]:
        today = date.today().isoformat()
        charge_key    = _TODAY_CHARGE_KEY.format(serial=serial, date=today)
        discharge_key = _TODAY_DISCHARGE_KEY.format(serial=serial, date=today)

        if power_w is not None and interval_sec > 0:
            # kWh = W × s / 3_600_000
            delta_kwh = abs(power_w) * interval_sec / 3_600_000.0
            if power_w > 0:
                await self._redis.incrbyfloat(charge_key, delta_kwh)
                await self._redis.expire(charge_key, _TODAY_TTL)
            elif power_w < 0:
                await self._redis.incrbyfloat(discharge_key, delta_kwh)
                await self._redis.expire(discharge_key, _TODAY_TTL)

        try:
            charge    = await self._redis.get(charge_key)
            discharge = await self._redis.get(discharge_key)
            return (
                round(float(charge),    3) if charge    else 0.0,
                round(float(discharge), 3) if discharge else 0.0,
            )
        except Exception as exc:
            logger.debug("[energy_calc] Redis read failed for %s: %s", serial, exc)
            return None, None

    # ------------------------------------------------------------------
    # Total (TimescaleDB + Redis cache)
    # ------------------------------------------------------------------

    async def _get_total(
        self, serial: str
    ) -> Tuple[Optional[float], Optional[float]]:
        charge_key    = _TOTAL_CHARGE_KEY.format(serial=serial)
        discharge_key = _TOTAL_DISCHARGE_KEY.format(serial=serial)

        try:
            charge    = await self._redis.get(charge_key)
            discharge = await self._redis.get(discharge_key)
            if charge is not None and discharge is not None:
                return float(charge), float(discharge)
        except Exception:
            pass

        if not self._db_url:
            return None, None

        try:
            charge_kwh, discharge_kwh = await self._query_db_total(serial)
            await self._redis.setex(charge_key,    _TOTAL_TTL, str(charge_kwh))
            await self._redis.setex(discharge_key, _TOTAL_TTL, str(discharge_kwh))
            return charge_kwh, discharge_kwh
        except Exception as exc:
            logger.warning("[energy_calc] DB total query failed for %s: %s", serial, exc)
            return None, None

    async def _query_db_total(self, serial: str) -> Tuple[float, float]:
        """
        Sum all historical charge/discharge energy from device_telemetry.

        Uses LEAD() to compute the time interval between consecutive rows
        and multiplies by power to get energy (kWh).  Gaps longer than
        5 minutes are excluded so offline periods don't inflate totals.

        Both JK BMS ('power' field) and other batteries ('battery_power_w')
        are handled via COALESCE.
        """
        import asyncpg

        async with self._db_lock:
            if self._db_pool is None:
                self._db_pool = await asyncpg.create_pool(
                    self._db_url, min_size=1, max_size=2,
                    command_timeout=30,
                )

        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COALESCE(SUM(GREATEST(power_w, 0) * interval_secs) / 3600000.0, 0)
                        AS charge_kwh,
                    COALESCE(SUM(GREATEST(-power_w, 0) * interval_secs) / 3600000.0, 0)
                        AS discharge_kwh
                FROM (
                    SELECT
                        COALESCE(
                            (data->>'power')::float,
                            (data->>'battery_power_w')::float
                        ) AS power_w,
                        EXTRACT(EPOCH FROM (
                            LEAD(time) OVER (ORDER BY time) - time
                        )) AS interval_secs
                    FROM device_telemetry
                    WHERE serial_number = $1
                      AND device_type   = 'battery'
                      AND (data ? 'power' OR data ? 'battery_power_w')
                ) t
                WHERE power_w       IS NOT NULL
                  AND interval_secs IS NOT NULL
                  AND interval_secs BETWEEN 1 AND 300
                """,
                serial,
            )

        if row:
            return round(float(row["charge_kwh"]), 3), round(float(row["discharge_kwh"]), 3)
        return 0.0, 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the asyncpg pool if one was opened."""
        async with self._db_lock:
            if self._db_pool is not None:
                await self._db_pool.close()
                self._db_pool = None
