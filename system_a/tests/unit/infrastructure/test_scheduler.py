"""
Unit tests for the telemetry sync scheduler.
"""
import pytest
from unittest.mock import patch, AsyncMock

from system_a.app.infrastructure.scheduler.scheduler import (
    get_scheduler,
    start_scheduler,
    stop_scheduler,
)


class TestScheduler:
    """Tests for scheduler lifecycle."""

    def test_get_scheduler_returns_singleton(self):
        """Scheduler should be a singleton."""
        import system_a.app.infrastructure.scheduler.scheduler as mod
        mod._scheduler = None  # Reset

        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

        mod._scheduler = None  # Cleanup

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """Scheduler should start and stop without errors."""
        import system_a.app.infrastructure.scheduler.scheduler as mod
        mod._scheduler = None  # Reset

        await start_scheduler()
        scheduler = get_scheduler()
        assert scheduler.running

        await stop_scheduler()
        assert mod._scheduler is None

    def test_jobs_are_registered(self):
        """All three sync jobs should be registered."""
        import system_a.app.infrastructure.scheduler.scheduler as mod
        mod._scheduler = None

        scheduler = get_scheduler()

        from system_a.app.infrastructure.scheduler.jobs import register_jobs
        register_jobs(scheduler)

        job_ids = [job.id for job in scheduler.get_jobs()]
        assert "sync_hourly" in job_ids
        assert "sync_daily" in job_ids
        assert "sync_monthly" in job_ids

        mod._scheduler = None  # Cleanup
