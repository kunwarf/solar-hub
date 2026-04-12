"""
Unit tests for scheduler/health.py.

Tests the health check and job trigger endpoints using aiohttp's test client.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scheduler.health import _health_handler, _list_jobs_handler, _trigger_job_handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_job(job_id: str, name: str, next_run: datetime | None = None):
    job = MagicMock()
    job.id = job_id
    job.name = name
    job.next_run_time = next_run or datetime(2026, 4, 11, 0, 30, tzinfo=timezone.utc)
    job.trigger = MagicMock(__str__=lambda self: "cron[hour=0, minute=30]")
    job.max_instances = 1
    job.misfire_grace_time = 43200
    job.coalesce = True
    return job


def _make_app(scheduler: AsyncIOScheduler) -> web.Application:
    app = web.Application()
    app["scheduler"] = scheduler
    app.router.add_get("/health", _health_handler)
    app.router.add_get("/jobs", _list_jobs_handler)
    app.router.add_post("/jobs/{job_id}/trigger", _trigger_job_handler)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_running_returns_healthy(aiohttp_client):
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.running = True
    scheduler.get_jobs.return_value = [
        _make_mock_job("daily_billing", "Daily billing computation"),
    ]

    client = await aiohttp_client(_make_app(scheduler))
    resp = await client.get("/health")

    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "healthy"
    assert data["running"] is True
    assert data["jobs_count"] == 1


@pytest.mark.asyncio
async def test_health_not_running_returns_unhealthy(aiohttp_client):
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.running = False
    scheduler.get_jobs.return_value = []

    client = await aiohttp_client(_make_app(scheduler))
    resp = await client.get("/health")

    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "unhealthy"
    assert data["running"] is False


@pytest.mark.asyncio
async def test_health_includes_all_jobs(aiohttp_client):
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.running = True
    scheduler.get_jobs.return_value = [
        _make_mock_job("daily_billing", "Daily billing"),
        _make_mock_job("outage_detection", "Outage detection"),
    ]

    client = await aiohttp_client(_make_app(scheduler))
    resp = await client.get("/health")
    data = await resp.json()

    assert data["jobs_count"] == 2
    ids = [j["id"] for j in data["jobs"]]
    assert "daily_billing" in ids
    assert "outage_detection" in ids


@pytest.mark.asyncio
async def test_trigger_known_job_returns_success(aiohttp_client):
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.running = True
    mock_job = _make_mock_job("daily_billing", "Daily billing computation")
    scheduler.get_job.return_value = mock_job

    client = await aiohttp_client(_make_app(scheduler))
    resp = await client.post("/jobs/daily_billing/trigger")

    assert resp.status == 200
    data = await resp.json()
    assert data["success"] is True
    assert data["job_id"] == "daily_billing"
    mock_job.modify.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_unknown_job_returns_404(aiohttp_client):
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.running = True
    scheduler.get_job.return_value = None

    client = await aiohttp_client(_make_app(scheduler))
    resp = await client.post("/jobs/nonexistent_job/trigger")

    assert resp.status == 404
    data = await resp.json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_trigger_when_scheduler_stopped_returns_400(aiohttp_client):
    scheduler = MagicMock(spec=AsyncIOScheduler)
    scheduler.running = False

    client = await aiohttp_client(_make_app(scheduler))
    resp = await client.post("/jobs/daily_billing/trigger")

    assert resp.status == 400
    data = await resp.json()
    assert data["success"] is False
    assert "not running" in data["message"].lower()
