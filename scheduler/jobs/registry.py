"""
Job registration for the standalone scheduler service.

Imports job functions directly from System A's package (no code duplication)
and wraps billing jobs with Redis distributed locks for horizontal scaling.

The outage_detection_job already has its own internal Redis lock, so it is
registered without an additional wrapper.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from scheduler.lock import with_redis_lock

logger = logging.getLogger(__name__)


def register_all_jobs(scheduler: AsyncIOScheduler, redis_url: str) -> None:
    """
    Register all Solar Hub scheduled jobs.

    Args:
        scheduler:  The APScheduler AsyncIOScheduler instance.
        redis_url:  Redis URL used for distributed locks.
    """
    # Lazy imports — System A modules are only resolvable when PYTHONPATH includes system_a/
    from app.infrastructure.scheduler.billing_jobs import (
        daily_billing_job,
        cycle_settlement_check_job,
    )
    from app.infrastructure.scheduler.ai_jobs import outage_detection_job

    # ── Daily billing ─────────────────────────────────────────────────────────
    # Lock TTL = 23 hours. Job runs once per day, execution takes ~30 seconds.
    # Lock prevents a second scheduler instance from double-billing on the same day.
    scheduler.add_job(
        with_redis_lock(redis_url, "daily_billing", ttl_seconds=23 * 3600)(daily_billing_job),
        CronTrigger(hour=0, minute=30, timezone="Asia/Karachi"),
        id="daily_billing",
        name="Daily billing computation",
        replace_existing=True,
    )

    # ── Cycle settlement check ────────────────────────────────────────────────
    # Lock TTL = 28 days. Job runs on the 15th of each month.
    scheduler.add_job(
        with_redis_lock(
            redis_url, "cycle_settlement_check", ttl_seconds=28 * 86400
        )(cycle_settlement_check_job),
        CronTrigger(day=15, hour=1, minute=0, timezone="Asia/Karachi"),
        id="cycle_settlement_check",
        name="Billing cycle settlement check",
        replace_existing=True,
    )

    # ── Outage detection ──────────────────────────────────────────────────────
    # Already has its own internal Redis lock (scheduler:lock:outage_detection, TTL 90s).
    # Registered without an extra wrapper.
    scheduler.add_job(
        outage_detection_job,
        IntervalTrigger(minutes=2),
        id="outage_detection",
        name="Grid outage detection (every 2 min)",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=30,
    )

    logger.info(
        "Registered %d scheduler jobs: daily_billing, cycle_settlement_check, outage_detection",
        3,
    )
