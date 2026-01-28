"""
Root test configuration for System A.

Provides shared fixtures for all test types (unit, integration, e2e).
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

# Set test environment before any app imports
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/solar_hub_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", '["http://localhost:5173","http://localhost:3000"]')


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =========================================================================
# Sample Data Fixtures
# =========================================================================

@pytest.fixture
def sample_site_id() -> UUID:
    return UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def sample_device_id() -> UUID:
    return UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def sample_device_id_2() -> UUID:
    return UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture
def sample_org_id() -> UUID:
    return UUID("44444444-4444-4444-4444-444444444444")


@pytest.fixture
def sample_user_id() -> UUID:
    return UUID("55555555-5555-5555-5555-555555555555")


@pytest.fixture
def sample_serial_number() -> str:
    return "SH01IN2406130092"


@pytest.fixture
def sample_timestamp() -> datetime:
    return datetime(2026, 1, 28, 12, 0, 0, tzinfo=timezone.utc)


# =========================================================================
# Mock Fixtures
# =========================================================================

@pytest.fixture
def mock_db_session():
    """Mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_system_b_client():
    """Mock SystemBClient with telemetry methods."""
    client = AsyncMock()
    client.get_device_aggregates = AsyncMock(return_value=[])
    client.get_site_telemetry = AsyncMock(return_value=[])
    client.get_site_power_chart = AsyncMock(return_value=[])
    client.get_device_latest = AsyncMock(return_value=None)
    client.get_device_by_serial = AsyncMock(return_value=None)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_telemetry_repository():
    """Mock telemetry repository."""
    repo = AsyncMock()
    repo.upsert_hourly_summary = AsyncMock()
    repo.upsert_daily_summary = AsyncMock()
    repo.upsert_monthly_summary = AsyncMock()
    repo.aggregate_hourly_to_daily = AsyncMock(return_value={})
    repo.aggregate_daily_to_monthly = AsyncMock(return_value={})
    repo.get_today_energy = AsyncMock(return_value={
        "energy_generated_kwh": 0.0,
        "energy_consumed_kwh": 0.0,
        "energy_exported_kwh": 0.0,
        "energy_imported_kwh": 0.0,
        "peak_power_kw": 0.0,
    })
    repo.get_this_month_energy = AsyncMock(return_value=0.0)
    repo.get_hourly_summaries = AsyncMock(return_value=[])
    repo.get_daily_summaries = AsyncMock(return_value=[])
    repo.get_monthly_summaries = AsyncMock(return_value=[])
    repo.get_monthly_summary = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_site_repository():
    """Mock site repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_organization_id = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_device_repository():
    """Mock device repository."""
    repo = AsyncMock()
    repo.get_by_site_id = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def sample_aggregate_response() -> list:
    """Sample aggregated telemetry data as returned by System B API."""
    return [
        {
            "bucket": "2026-01-28T10:00:00+00:00",
            "avg": 5200.5,
            "min": 3100.0,
            "max": 7400.0,
            "first": 3100.0,
            "last": 7400.0,
            "delta": 4300.0,
            "sample_count": 60,
            "quality_percent": 98.5,
        },
        {
            "bucket": "2026-01-28T11:00:00+00:00",
            "avg": 8100.0,
            "min": 7000.0,
            "max": 9200.0,
            "first": 7000.0,
            "last": 9200.0,
            "delta": 2200.0,
            "sample_count": 60,
            "quality_percent": 100.0,
        },
    ]


@pytest.fixture
def sample_latest_response(sample_device_id) -> Dict[str, Any]:
    """Sample latest telemetry response from System B API."""
    return {
        "device_id": str(sample_device_id),
        "readings": {
            "pv_power_w": {
                "value": 5234.0,
                "timestamp": "2026-01-28T12:48:07+00:00",
                "quality": "good",
            },
            "battery_soc_pct": {
                "value": 98.0,
                "timestamp": "2026-01-28T12:48:07+00:00",
                "quality": "good",
            },
        },
    }
