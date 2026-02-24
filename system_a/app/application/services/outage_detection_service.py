"""
Outage Detection Service.

Runs as a background job (every 2 minutes via APScheduler).
Reads Redis telemetry for every online site, detects grid on/off transitions,
and writes records to the grid_outages table.

Detection logic:
  - Grid is DOWN when: grid_power_w is 0 AND working_mode indicates off-grid
    OR grid_power_w is 0 AND battery is discharging AND pv_power_w > 0
  - Grid is UP  when: grid_power_w != 0 (positive import or negative export)

State is kept in Redis keys (TTL=10min) to survive service restarts:
  outage_state:{site_id}  →  "active:{outage_id}:{started_at_iso}" | "grid_up"
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Pakistan Standard Time
_PKT = timezone(timedelta(hours=5))

# Redis key pattern for outage state
_STATE_KEY = "outage_state:{site_id}"
_STATE_TTL  = 700      # 10 minutes + buffer — refreshed every poll cycle

# Thresholds
_GRID_ZERO_THRESHOLD_W = 10     # below this is considered "no grid" (noise filter)
_MIN_OUTAGE_MINUTES    = 2      # ignore flickers shorter than this


class OutageDetectionService:
    """
    Detects and records grid outage events from live telemetry.

    Designed to run as a periodic background task.  It is stateless between
    calls — all transient state is stored in Redis so the scheduler can be
    restarted without losing open outage records.
    """

    def __init__(
        self,
        telemetry_cache,       # TelemetryCacheReader
        session_factory,       # async_sessionmaker[AsyncSession]
    ) -> None:
        self._cache = telemetry_cache
        self._session_factory = session_factory

    # =========================================================================
    # Public entry point (called by scheduler)
    # =========================================================================

    async def run_detection_cycle(
        self,
        sites: List[Dict],   # [{site_id, device_serials: [...]}]
    ) -> None:
        """
        Check every site and update outage records.

        Called every 2 minutes by the APScheduler job.
        Each site is processed independently; failures for one site do not
        affect others.
        """
        for site in sites:
            try:
                await self._check_site(
                    site_id=UUID(site["site_id"]),
                    device_serials=site["device_serials"],
                )
            except Exception as exc:
                logger.warning(
                    "[outage] Error checking site=%s: %s",
                    site["site_id"], exc, exc_info=True,
                )

    # =========================================================================
    # Per-site logic
    # =========================================================================

    async def _check_site(
        self,
        site_id: UUID,
        device_serials: List[str],
    ) -> None:
        """Detect grid state for a site and write events to DB."""
        grid_on, primary_serial = await self._detect_grid_state(device_serials)
        state_key = _STATE_KEY.format(site_id=site_id)

        redis = None
        try:
            from ...infrastructure.cache.redis_manager import RedisManager
            redis = await RedisManager.get_client()
            current_state = await redis.get(state_key)
        except Exception:
            current_state = None

        if redis is None:
            # Redis unavailable — skip state tracking to avoid false outage events
            return

        now = datetime.now(timezone.utc)

        if grid_on:
            # Grid is UP
            if current_state and current_state.startswith("active:"):
                # Outage just ended — close it
                await self._close_outage(state_key, current_state, now, redis)
                logger.info("[outage] site=%s grid RESTORED at %s UTC", site_id, now.isoformat())
            else:
                # Normal — grid was already up
                await redis.setex(state_key, _STATE_TTL, "grid_up")
        else:
            # Grid is DOWN
            if not current_state or current_state == "grid_up":
                # New outage starting
                outage_id = await self._open_outage(
                    site_id, primary_serial, now
                )
                state_val = f"active:{outage_id}:{now.isoformat()}"
                await redis.setex(state_key, _STATE_TTL, state_val)
                logger.info(
                    "[outage] site=%s grid DOWN — new outage %s started at %s UTC",
                    site_id, outage_id, now.isoformat(),
                )
            else:
                # Outage already active — just refresh TTL
                await redis.setex(state_key, _STATE_TTL, current_state)

    async def _detect_grid_state(
        self,
        device_serials: List[str],
    ) -> tuple[bool, Optional[str]]:
        """
        Return (grid_is_on, primary_serial) from telemetry.

        Uses the first device with valid telemetry.
        Grid is considered ON if |grid_power_w| > threshold.
        """
        for serial in device_serials:
            telemetry = await self._cache.get_telemetry(serial)
            if not telemetry:
                continue

            power = telemetry.get("power", {})
            grid_w = float(power.get("grid_w", 0) or 0)

            # Grid is up if there is measurable grid power (import or export)
            grid_on = abs(grid_w) > _GRID_ZERO_THRESHOLD_W
            return grid_on, serial

        # No telemetry available — assume grid is up to avoid false positives
        return True, None

    async def _open_outage(
        self,
        site_id: UUID,
        detected_by_serial: Optional[str],
        started_at: datetime,
    ) -> str:
        """Insert a new outage row and return the outage UUID string."""
        from ...domain.entities.ai_entities import GridOutage
        from ...infrastructure.database.unit_of_work import SQLAlchemyUnitOfWork

        now_pkt = started_at.astimezone(_PKT)
        outage = GridOutage(
            id=uuid4(),
            site_id=site_id,
            started_at=started_at,
            day_of_week=now_pkt.weekday(),
            week_of_year=int(now_pkt.strftime("%W")),
            month_pkt=now_pkt.month,
            started_hour_pkt=now_pkt.hour,
            detected_by_serial=detected_by_serial,
        )

        async with self._session_factory() as session:
            from ...infrastructure.database.repositories.ai_repository import (
                SQLAlchemyGridOutageRepository,
            )
            repo = SQLAlchemyGridOutageRepository(session)
            saved = await repo.add(outage)
            await session.commit()
            return str(saved.id)

    async def _close_outage(
        self,
        state_key: str,
        state_val: str,
        ended_at: datetime,
        redis,
    ) -> None:
        """
        Update an existing outage row with its end time and duration.

        Ignores outages shorter than _MIN_OUTAGE_MINUTES (flickering).
        """
        try:
            # state_val format: "active:{uuid}:{iso_start}"
            parts = state_val.split(":", 2)
            outage_id = UUID(parts[1])
            started_at = datetime.fromisoformat(parts[2])
        except (IndexError, ValueError) as exc:
            logger.warning("[outage] Could not parse state_val %r: %s", state_val, exc)
            await redis.setex(state_key, _STATE_TTL, "grid_up")
            return

        duration_min = int((ended_at - started_at).total_seconds() / 60)
        if duration_min < _MIN_OUTAGE_MINUTES:
            # Flicker — delete the outage row
            logger.debug("[outage] Ignoring %dmin flicker (outage %s)", duration_min, outage_id)
            await self._delete_outage(outage_id)
        else:
            from ...domain.entities.ai_entities import GridOutage
            # Build a minimal domain object to carry the closing data
            now_pkt = ended_at.astimezone(_PKT)
            dummy = GridOutage(
                id=outage_id,
                site_id=uuid4(),          # not used in update
                started_at=started_at,
                day_of_week=0, week_of_year=0, month_pkt=0,
                started_hour_pkt=0,
                ended_at=ended_at,
                ended_hour_pkt=now_pkt.hour,
                duration_minutes=duration_min,
            )
            await self._update_outage_end(dummy)

        await redis.setex(state_key, _STATE_TTL, "grid_up")

    async def _update_outage_end(self, outage) -> None:
        async with self._session_factory() as session:
            from ...infrastructure.database.repositories.ai_repository import (
                SQLAlchemyGridOutageRepository,
            )
            repo = SQLAlchemyGridOutageRepository(session)
            await repo.close_outage(outage)
            await session.commit()

    async def _delete_outage(self, outage_id: UUID) -> None:
        async with self._session_factory() as session:
            from sqlalchemy import delete
            from ...infrastructure.database.models.ai_models import GridOutageModel
            await session.execute(
                delete(GridOutageModel).where(GridOutageModel.id == outage_id)
            )
            await session.commit()
