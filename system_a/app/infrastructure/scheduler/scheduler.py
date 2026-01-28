"""
APScheduler lifecycle management.

Provides async scheduler for periodic telemetry sync jobs.
"""
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Karachi")
    return _scheduler


async def start_scheduler() -> None:
    """Start the scheduler with registered jobs."""
    scheduler = get_scheduler()

    from .jobs import register_jobs
    register_jobs(scheduler)

    scheduler.start()
    logger.info("Telemetry sync scheduler started")


async def stop_scheduler() -> None:
    """Shut down the scheduler."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Telemetry sync scheduler stopped")
    _scheduler = None
