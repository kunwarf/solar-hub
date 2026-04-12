"""
Unit tests for scheduler/jobs/registry.py.

Verifies that register_all_jobs() registers exactly the expected jobs
with the correct triggers and IDs, without touching a real database or Redis.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_scheduler():
    """Return an AsyncIOScheduler with add_job mocked (no DB/Redis needed)."""
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.add_job = MagicMock()
    return scheduler


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_register_all_jobs_registers_three_jobs(mock_scheduler):
    """register_all_jobs() should register exactly 3 jobs."""
    with (
        patch("app.infrastructure.scheduler.billing_jobs.daily_billing_job", AsyncMock()),
        patch("app.infrastructure.scheduler.billing_jobs.cycle_settlement_check_job", AsyncMock()),
        patch("app.infrastructure.scheduler.ai_jobs.outage_detection_job", AsyncMock()),
    ):
        from scheduler.jobs.registry import register_all_jobs
        register_all_jobs(mock_scheduler, redis_url="redis://localhost/0")

    assert mock_scheduler.add_job.call_count == 3


def test_daily_billing_job_registered_with_cron_trigger(mock_scheduler):
    """daily_billing job must use a CronTrigger."""
    with (
        patch("app.infrastructure.scheduler.billing_jobs.daily_billing_job", AsyncMock()),
        patch("app.infrastructure.scheduler.billing_jobs.cycle_settlement_check_job", AsyncMock()),
        patch("app.infrastructure.scheduler.ai_jobs.outage_detection_job", AsyncMock()),
    ):
        from scheduler.jobs.registry import register_all_jobs
        register_all_jobs(mock_scheduler, redis_url="redis://localhost/0")

    calls = mock_scheduler.add_job.call_args_list
    # First call is daily_billing
    billing_call = calls[0]
    trigger = billing_call.args[1] if len(billing_call.args) > 1 else billing_call.kwargs.get("trigger")
    assert isinstance(trigger, CronTrigger), "daily_billing must use CronTrigger"


def test_daily_billing_job_id(mock_scheduler):
    """daily_billing must be registered with id='daily_billing'."""
    with (
        patch("app.infrastructure.scheduler.billing_jobs.daily_billing_job", AsyncMock()),
        patch("app.infrastructure.scheduler.billing_jobs.cycle_settlement_check_job", AsyncMock()),
        patch("app.infrastructure.scheduler.ai_jobs.outage_detection_job", AsyncMock()),
    ):
        from scheduler.jobs.registry import register_all_jobs
        register_all_jobs(mock_scheduler, redis_url="redis://localhost/0")

    calls = mock_scheduler.add_job.call_args_list
    billing_call = calls[0]
    job_id = billing_call.kwargs.get("id")
    assert job_id == "daily_billing"


def test_outage_detection_registered_with_interval_trigger(mock_scheduler):
    """outage_detection must use an IntervalTrigger."""
    with (
        patch("app.infrastructure.scheduler.billing_jobs.daily_billing_job", AsyncMock()),
        patch("app.infrastructure.scheduler.billing_jobs.cycle_settlement_check_job", AsyncMock()),
        patch("app.infrastructure.scheduler.ai_jobs.outage_detection_job", AsyncMock()),
    ):
        from scheduler.jobs.registry import register_all_jobs
        register_all_jobs(mock_scheduler, redis_url="redis://localhost/0")

    calls = mock_scheduler.add_job.call_args_list
    # Third call is outage_detection
    outage_call = calls[2]
    trigger = outage_call.args[1] if len(outage_call.args) > 1 else outage_call.kwargs.get("trigger")
    assert isinstance(trigger, IntervalTrigger), "outage_detection must use IntervalTrigger"


def test_outage_detection_job_id(mock_scheduler):
    """outage_detection must be registered with id='outage_detection'."""
    with (
        patch("app.infrastructure.scheduler.billing_jobs.daily_billing_job", AsyncMock()),
        patch("app.infrastructure.scheduler.billing_jobs.cycle_settlement_check_job", AsyncMock()),
        patch("app.infrastructure.scheduler.ai_jobs.outage_detection_job", AsyncMock()),
    ):
        from scheduler.jobs.registry import register_all_jobs
        register_all_jobs(mock_scheduler, redis_url="redis://localhost/0")

    calls = mock_scheduler.add_job.call_args_list
    outage_call = calls[2]
    job_id = outage_call.kwargs.get("id")
    assert job_id == "outage_detection"


def test_all_jobs_have_replace_existing(mock_scheduler):
    """All jobs must use replace_existing=True for clean restarts."""
    with (
        patch("app.infrastructure.scheduler.billing_jobs.daily_billing_job", AsyncMock()),
        patch("app.infrastructure.scheduler.billing_jobs.cycle_settlement_check_job", AsyncMock()),
        patch("app.infrastructure.scheduler.ai_jobs.outage_detection_job", AsyncMock()),
    ):
        from scheduler.jobs.registry import register_all_jobs
        register_all_jobs(mock_scheduler, redis_url="redis://localhost/0")

    for call in mock_scheduler.add_job.call_args_list:
        assert call.kwargs.get("replace_existing") is True, (
            f"Job '{call.kwargs.get('id')}' must set replace_existing=True"
        )
