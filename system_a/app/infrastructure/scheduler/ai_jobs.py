"""
AI background jobs.

Registers two scheduled jobs:
  1. outage_detection_job  — every 2 minutes, detects grid outages from telemetry.
  2. (future) insight_prefetch_job — on the hour, pre-warms AI insight cache.

Both jobs are stateless: all state is held in Redis or PostgreSQL.
"""
import logging
from typing import List, Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def register_ai_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register AI-related background jobs with the APScheduler instance."""
    scheduler.add_job(
        outage_detection_job,
        IntervalTrigger(minutes=2),
        id="outage_detection",
        name="Grid outage detection (every 2 min)",
        replace_existing=True,
        max_instances=1,          # never run two cycles concurrently
        misfire_grace_time=30,    # skip if more than 30s late
    )
    logger.info("Registered AI background job: outage_detection (every 2 minutes)")


# =============================================================================
# Outage detection job
# =============================================================================

async def outage_detection_job() -> None:
    """
    Detect grid outages for all online sites.

    Runs every 2 minutes. For each site that has at least one device registered,
    reads live Redis telemetry and updates the grid_outages table.

    Failures for individual sites are swallowed — they are logged but do not
    abort the cycle for other sites.

    A Redis distributed lock (TTL 90s) ensures only one of the 4 uvicorn
    workers actually executes the cycle per tick — the others skip silently.
    """
    import redis.asyncio as aioredis
    from ...config import settings

    redis = aioredis.from_url(settings.redis.url)
    lock_key = "scheduler:lock:outage_detection"
    lock_ttl = 90  # seconds — slightly less than the 2-min interval

    acquired = await redis.set(lock_key, "1", nx=True, ex=lock_ttl)
    await redis.aclose()
    if not acquired:
        return  # another worker is already running this cycle

    logger.debug("[outage_job] Starting outage detection cycle")

    try:
        sites = await _fetch_all_sites_with_serials()
    except Exception as exc:
        logger.error("[outage_job] Failed to fetch site list: %s", exc, exc_info=True)
        return

    if not sites:
        logger.debug("[outage_job] No sites found — skipping detection cycle")
        return

    try:
        from ...infrastructure.database.connection import DatabaseManager
        from ...infrastructure.cache.telemetry_cache import TelemetryCacheReader
        from ...application.services.outage_detection_service import OutageDetectionService

        session_factory = DatabaseManager.get_session_factory()
        cache_reader = TelemetryCacheReader()
        service = OutageDetectionService(
            telemetry_cache=cache_reader,
            session_factory=session_factory,
        )

        await service.run_detection_cycle(sites)

        logger.debug(
            "[outage_job] Detection cycle complete — %d sites checked", len(sites)
        )

    except Exception as exc:
        logger.error(
            "[outage_job] Outage detection cycle failed: %s", exc, exc_info=True
        )


async def _fetch_all_sites_with_serials() -> List[Dict]:
    """
    Return a list of dicts suitable for OutageDetectionService.run_detection_cycle().

    Each dict has:
        site_id:        str  (UUID)
        device_serials: list[str]
    """
    from ...infrastructure.database.connection import DatabaseManager
    from sqlalchemy import text

    session_factory = DatabaseManager.get_session_factory()
    async with session_factory() as session:
        # Single query: join sites → devices, group by site
        rows = await session.execute(
            text(
                """
                SELECT
                    s.id::text            AS site_id,
                    array_agg(d.serial_number) AS serials
                FROM sites s
                JOIN devices d ON d.site_id = s.id
                WHERE d.serial_number IS NOT NULL
                GROUP BY s.id
                """
            )
        )
        result = rows.fetchall()

    return [
        {
            "site_id": row.site_id,
            "device_serials": [s for s in row.serials if s],
        }
        for row in result
        if row.serials
    ]
