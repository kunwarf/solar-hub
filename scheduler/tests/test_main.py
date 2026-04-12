"""
Unit tests for scheduler/__main__.py lifecycle.

Tests startup, graceful shutdown, and signal handling without requiring
a real database, Redis, or APScheduler PostgreSQL job store.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_scheduler():
    s = MagicMock()
    s.running = False
    s.start = MagicMock()
    s.shutdown = MagicMock()
    s.get_jobs = MagicMock(return_value=[])
    return s


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_starts_on_main():
    """main() should start the APScheduler and health server."""
    mock_scheduler = _make_mock_scheduler()

    with (
        patch("scheduler.__main__.AsyncIOScheduler", return_value=mock_scheduler),
        patch("scheduler.__main__.SQLAlchemyJobStore"),
        patch("scheduler.__main__.AsyncIOExecutor"),
        patch("scheduler.__main__.register_all_jobs"),
        patch("scheduler.__main__.start_health_server", new_callable=AsyncMock) as mock_health,
        patch("scheduler.__main__.DatabaseManager") as mock_db,
        patch("scheduler.__main__.RedisManager") as mock_redis,
        patch("scheduler.__main__.settings") as mock_settings,
        # Immediately trigger shutdown so main() doesn't hang
        patch("asyncio.Event") as mock_event_cls,
    ):
        mock_settings.database.url = "postgresql+asyncpg://user:pass@localhost/db"
        mock_settings.database.pool_size = 5
        mock_settings.database.sync_url = "postgresql://user:pass@localhost/db"
        mock_settings.redis.url = "redis://localhost:6379/0"

        mock_event = AsyncMock()
        mock_event.wait = AsyncMock(return_value=None)
        mock_event_cls.return_value = mock_event

        mock_redis.get_client = AsyncMock()
        mock_health.return_value = AsyncMock(cleanup=AsyncMock())
        mock_db.close = AsyncMock()
        mock_redis.close = AsyncMock()

        from scheduler.__main__ import main
        await main()

    mock_scheduler.start.assert_called_once()
    mock_health.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_shuts_down_gracefully():
    """main() should call scheduler.shutdown() and cleanup on exit."""
    mock_scheduler = _make_mock_scheduler()
    mock_runner = AsyncMock()
    mock_runner.cleanup = AsyncMock()

    with (
        patch("scheduler.__main__.AsyncIOScheduler", return_value=mock_scheduler),
        patch("scheduler.__main__.SQLAlchemyJobStore"),
        patch("scheduler.__main__.AsyncIOExecutor"),
        patch("scheduler.__main__.register_all_jobs"),
        patch("scheduler.__main__.start_health_server", new_callable=AsyncMock, return_value=mock_runner),
        patch("scheduler.__main__.DatabaseManager") as mock_db,
        patch("scheduler.__main__.RedisManager") as mock_redis,
        patch("scheduler.__main__.settings") as mock_settings,
        patch("asyncio.Event") as mock_event_cls,
    ):
        mock_settings.database.url = "postgresql+asyncpg://user:pass@localhost/db"
        mock_settings.database.pool_size = 5
        mock_settings.database.sync_url = "postgresql://user:pass@localhost/db"
        mock_settings.redis.url = "redis://localhost:6379/0"

        mock_event = AsyncMock()
        mock_event.wait = AsyncMock(return_value=None)
        mock_event_cls.return_value = mock_event

        mock_redis.get_client = AsyncMock()
        mock_db.close = AsyncMock()
        mock_redis.close = AsyncMock()

        from scheduler.__main__ import main
        await main()

    mock_scheduler.shutdown.assert_called_once_with(wait=False)
    mock_runner.cleanup.assert_called_once()
    mock_db.close.assert_called_once()
    mock_redis.close.assert_called_once()


@pytest.mark.asyncio
async def test_register_all_jobs_called_with_redis_url():
    """register_all_jobs() must receive the Redis URL from settings."""
    mock_scheduler = _make_mock_scheduler()
    register_mock = MagicMock()

    with (
        patch("scheduler.__main__.AsyncIOScheduler", return_value=mock_scheduler),
        patch("scheduler.__main__.SQLAlchemyJobStore"),
        patch("scheduler.__main__.AsyncIOExecutor"),
        patch("scheduler.__main__.register_all_jobs", register_mock),
        patch("scheduler.__main__.start_health_server", new_callable=AsyncMock, return_value=AsyncMock(cleanup=AsyncMock())),
        patch("scheduler.__main__.DatabaseManager") as mock_db,
        patch("scheduler.__main__.RedisManager") as mock_redis,
        patch("scheduler.__main__.settings") as mock_settings,
        patch("asyncio.Event") as mock_event_cls,
    ):
        mock_settings.database.url = "postgresql+asyncpg://user:pass@localhost/db"
        mock_settings.database.pool_size = 5
        mock_settings.database.sync_url = "postgresql://user:pass@localhost/db"
        mock_settings.redis.url = "redis://localhost:6379/1"

        mock_event = AsyncMock()
        mock_event.wait = AsyncMock(return_value=None)
        mock_event_cls.return_value = mock_event

        mock_redis.get_client = AsyncMock()
        mock_db.close = AsyncMock()
        mock_redis.close = AsyncMock()

        from scheduler.__main__ import main
        await main()

    register_mock.assert_called_once_with(mock_scheduler, redis_url="redis://localhost:6379/1")
