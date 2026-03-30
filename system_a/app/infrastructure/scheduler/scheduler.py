"""
APScheduler lifecycle management.

Uses a PostgreSQL job store so missed jobs are persisted and replayed on
restart (e.g. after a deployment or OOM kill). Without this, in-memory-only
scheduling silently drops any job that was supposed to run while the process
was down.
"""
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        from ...config import settings

        jobstores = {
            "default": SQLAlchemyJobStore(url=settings.database.sync_url),
        }
        executors = {
            "default": AsyncIOExecutor(),
        }
        job_defaults = {
            # Allow a job to run up to 12 hours late (covers server restarts,
            # brief downtime). Without this APScheduler drops missed fires.
            "misfire_grace_time": 12 * 3600,
            # Don't run multiple instances of the same job concurrently.
            "coalesce": True,
            "max_instances": 1,
        }
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="Asia/Karachi",
        )
    return _scheduler


async def start_scheduler() -> None:
    """Start the scheduler with registered jobs."""
    scheduler = get_scheduler()

    from .jobs import register_jobs
    register_jobs(scheduler)

    scheduler.start()
    logger.info("Scheduler started (PostgreSQL job store)")


async def stop_scheduler() -> None:
    """Shut down the scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None
