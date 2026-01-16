"""
Shared pytest fixtures for System B tests.

Provides fixtures for:
- Database sessions (async SQLAlchemy)
- Redis mock (fakeredis)
- API client (httpx)
- Device simulators
- Test data factories
"""
import asyncio
import os
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

# Test environment configuration
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/system_b_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")


# ============================================================================
# Core Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def mock_db_session():
    """
    Mock database session for unit tests.

    Returns an AsyncMock that can be configured per test.
    """
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.refresh = AsyncMock()

    yield session


@pytest_asyncio.fixture
async def db_session():
    """
    Real database session for integration tests.

    Requires running PostgreSQL with TimescaleDB.
    Creates tables before test and drops after.
    """
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from app.infrastructure.database.models import Base

        database_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://test:test@localhost:5433/system_b_test"
        )

        engine = create_async_engine(database_url, echo=False)

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create session
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with async_session() as session:
            yield session

        # Cleanup - drop tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()

    except Exception as e:
        pytest.skip(f"Database not available: {e}")


# ============================================================================
# Redis Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def mock_redis():
    """
    Mock Redis client for unit tests.

    Uses fakeredis for realistic Redis behavior.
    """
    try:
        import fakeredis.aioredis

        redis = fakeredis.aioredis.FakeRedis()
        yield redis
        await redis.flushall()
        await redis.aclose()

    except ImportError:
        # Fallback to simple mock
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.xadd = AsyncMock(return_value="1-0")
        redis.xread = AsyncMock(return_value=[])
        yield redis


@pytest_asyncio.fixture
async def redis_client():
    """
    Real Redis client for integration tests.

    Requires running Redis server.
    """
    try:
        import redis.asyncio as redis

        redis_url = os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0")
        client = redis.from_url(redis_url)

        # Test connection
        await client.ping()

        yield client

        await client.flushdb()
        await client.aclose()

    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


# ============================================================================
# API Client Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def api_client(mock_db_session, mock_redis):
    """
    Test API client for unit tests.

    Uses mocked dependencies.
    """
    try:
        import httpx
        from fastapi.testclient import TestClient

        # Import app lazily to allow mocking
        from app.main import app
        from app.api.dependencies import get_db_session, get_redis_client

        # Override dependencies
        app.dependency_overrides[get_db_session] = lambda: mock_db_session
        app.dependency_overrides[get_redis_client] = lambda: mock_redis

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            yield client

        # Clear overrides
        app.dependency_overrides.clear()

    except ImportError as e:
        pytest.skip(f"API dependencies not available: {e}")


@pytest_asyncio.fixture
async def integration_api_client(db_session, redis_client):
    """
    Test API client for integration tests.

    Uses real database and Redis.
    """
    try:
        import httpx

        from app.main import app
        from app.api.dependencies import get_db_session, get_redis_client

        app.dependency_overrides[get_db_session] = lambda: db_session
        app.dependency_overrides[get_redis_client] = lambda: redis_client

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            yield client

        app.dependency_overrides.clear()

    except ImportError as e:
        pytest.skip(f"API dependencies not available: {e}")


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def sample_device_id() -> UUID:
    """Generate a sample device ID."""
    return uuid4()


@pytest.fixture
def sample_site_id() -> UUID:
    """Generate a sample site ID."""
    return uuid4()


@pytest.fixture
def sample_organization_id() -> UUID:
    """Generate a sample organization ID."""
    return uuid4()


@pytest.fixture
def sample_device_data(sample_device_id, sample_site_id, sample_organization_id) -> Dict[str, Any]:
    """Sample device registration data."""
    return {
        "device_id": sample_device_id,
        "site_id": sample_site_id,
        "organization_id": sample_organization_id,
        "device_type": "inverter",
        "serial_number": f"TEST{uuid4().hex[:8].upper()}",
        "protocol": "modbus_tcp",
        "connection_config": {
            "host": "127.0.0.1",
            "port": 502,
            "unit_id": 1
        },
        "polling_interval_seconds": 60,
    }


@pytest.fixture
def sample_telemetry_data(sample_device_id, sample_site_id) -> Dict[str, Any]:
    """Sample telemetry data."""
    return {
        "device_id": sample_device_id,
        "site_id": sample_site_id,
        "timestamp": datetime.now(timezone.utc),
        "metrics": {
            "battery_soc_pct": 75.0,
            "pv_power_w": 3500,
            "battery_power_w": 1200,
            "grid_power_w": -500,
            "load_power_w": 4200,
        },
        "source": "modbus",
    }


@pytest.fixture
def sample_command_data(sample_device_id, sample_site_id) -> Dict[str, Any]:
    """Sample command data."""
    return {
        "command_id": uuid4(),
        "device_id": sample_device_id,
        "site_id": sample_site_id,
        "command_type": "set_battery_mode",
        "command_params": {
            "mode": "charge",
            "power_limit": 3000
        },
        "priority": 5,
    }


@pytest.fixture
def sample_event_data(sample_device_id, sample_site_id) -> Dict[str, Any]:
    """Sample event data."""
    return {
        "device_id": sample_device_id,
        "site_id": sample_site_id,
        "event_type": "warning",
        "event_code": "LOW_BATTERY",
        "severity": "warning",
        "message": "Battery SOC below 20%",
        "details": {"soc": 18.5},
        "timestamp": datetime.now(timezone.utc),
    }


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture
def mock_telemetry_repository():
    """Mock telemetry repository."""
    repo = AsyncMock()
    repo.ingest_batch = AsyncMock(return_value=10)
    repo.get_latest_readings = AsyncMock(return_value={})
    repo.get_time_range = AsyncMock(return_value=[])
    repo.get_time_bucket_aggregates = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_device_repository():
    """Mock device repository."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_serial = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.update_connection_status = AsyncMock()
    repo.generate_auth_token = AsyncMock(return_value="test_token")
    repo.validate_auth_token = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_command_repository():
    """Mock command repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_pending_for_device = AsyncMock(return_value=[])
    repo.claim_pending_command = AsyncMock(return_value=None)
    repo.mark_completed = AsyncMock()
    repo.mark_failed = AsyncMock()
    return repo


@pytest.fixture
def mock_event_repository():
    """Mock event repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_device_events = AsyncMock(return_value=[])
    repo.acknowledge_event = AsyncMock()
    repo.get_event_timeline = AsyncMock(return_value=[])
    return repo


# ============================================================================
# Simulator Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def simulator_manager():
    """
    Device simulator manager for E2E tests.

    Provides virtual devices that respond to Modbus/command requests.
    """
    try:
        from tests.simulators.simulator_manager import SimulatorManager

        manager = SimulatorManager()
        yield manager
        await manager.stop_all()

    except ImportError:
        pytest.skip("Simulator module not available")


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def freeze_time():
    """
    Fixture for freezing time in tests.

    Usage:
        def test_something(freeze_time):
            with freeze_time("2026-01-15 12:00:00"):
                # time is frozen
    """
    try:
        from freezegun import freeze_time as _freeze_time
        return _freeze_time
    except ImportError:
        pytest.skip("freezegun not installed")


@pytest.fixture
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"
