"""
Solar Hub Standalone Scheduler Service — entry point.

Usage:
    python -m scheduler

Requires PYTHONPATH to include the system_a/ directory so that
System A's modules (app.config, app.infrastructure.*) are importable.
This is set automatically by the systemd unit file.

Health check: curl http://127.0.0.1:8002/health
"""
import asyncio
import logging
import os
import signal
import sys

# ---------------------------------------------------------------------------
# Logging setup (before any other imports that might log)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("scheduler")

# ---------------------------------------------------------------------------
# APScheduler
# ---------------------------------------------------------------------------
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

# ---------------------------------------------------------------------------
# System A settings (resolved via PYTHONPATH=.../system_a)
# ---------------------------------------------------------------------------
from scheduler.config import settings
from scheduler.jobs.registry import register_all_jobs
from scheduler.health import start_health_server


async def main() -> None:
    """Start the scheduler and health server, run until SIGTERM/SIGINT."""

    logger.info("Solar Hub Scheduler Service starting")
    logger.info("DB: %s (pool_size=%d)", settings.database.url, settings.database.pool_size)
    logger.info("Redis: %s", settings.redis.url)

    # Warm up System A's database connection pool.
    # DatabaseManager is lazy — calling get_session_factory() triggers engine creation.
    from app.infrastructure.database.connection import DatabaseManager
    DatabaseManager.get_session_factory()
    logger.info("Database connection pool initialised")

    # Warm up Redis (lazy — first call creates the client).
    from app.infrastructure.cache.redis_cache import RedisManager
    await RedisManager.get_client()
    logger.info("Redis client initialised")

    # ── APScheduler ──────────────────────────────────────────────────────────
    scheduler = AsyncIOScheduler(
        jobstores={
            # PostgreSQL job store: persists job state so missed jobs replay
            # after restarts (misfire_grace_time handles the replay window).
            "default": SQLAlchemyJobStore(url=settings.database.sync_url),
        },
        executors={
            "default": AsyncIOExecutor(),
        },
        job_defaults={
            "misfire_grace_time": 12 * 3600,  # replay jobs missed within 12 hours
            "coalesce": True,                  # merge multiple missed fires into one
            "max_instances": 1,                # never run the same job concurrently
        },
        timezone="Asia/Karachi",
    )

    register_all_jobs(scheduler, redis_url=settings.redis.url)
    scheduler.start()
    logger.info("APScheduler started with PostgreSQL job store")

    # ── Health server ─────────────────────────────────────────────────────────
    health_port = int(os.environ.get("SCHEDULER_HEALTH_PORT", "8002"))
    health_runner = await start_health_server(scheduler, port=health_port)

    # ── Signal handling ───────────────────────────────────────────────────────
    shutdown_event = asyncio.Event()

    def _handle_signal(sig_name: str) -> None:
        logger.info("Received %s — initiating graceful shutdown", sig_name)
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig.name)

    logger.info("Scheduler service running. Press Ctrl+C or send SIGTERM to stop.")
    await shutdown_event.wait()

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down scheduler service")
    scheduler.shutdown(wait=False)
    await health_runner.cleanup()
    await DatabaseManager.close()
    await RedisManager.close()
    logger.info("Scheduler service stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
