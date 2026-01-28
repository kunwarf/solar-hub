"""
Integration test configuration for System A.

Provides fixtures that require real external services (database, Redis).
These tests are skipped when services are unavailable.
"""
import asyncio
import os

import pytest


def pytest_collection_modifyitems(items):
    """Auto-mark all integration tests."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def integration_db_url():
    """Get integration test database URL."""
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/solar_hub_test",
    )


@pytest.fixture(scope="session")
def integration_redis_url():
    """Get integration test Redis URL."""
    return os.environ.get(
        "TEST_REDIS_URL",
        "redis://localhost:6379/2",
    )


@pytest.fixture
async def integration_db_session(integration_db_url):
    """
    Create a real async database session for integration tests.

    Requires PostgreSQL to be running. Skips if unavailable.
    """
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        engine = create_async_engine(integration_db_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            yield session
            await session.rollback()

        await engine.dispose()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture
async def integration_redis_client(integration_redis_url):
    """
    Create a real Redis client for integration tests.

    Requires Redis to be running. Skips if unavailable.
    """
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(integration_redis_url, decode_responses=True)
        await client.ping()
        yield client
        await client.aclose()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
