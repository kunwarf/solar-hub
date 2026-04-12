"""
Unit tests for scheduler/lock.py.

Tests Redis distributed lock acquisition and skip behaviour using a
fakeredis in-memory backend so no real Redis is needed.
"""
import asyncio
import pytest
import fakeredis.aioredis as fakeredis

from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# Helper: patch aioredis.from_url to return a fakeredis instance
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_redis():
    """Return a fresh fakeredis server for each test."""
    return fakeredis.FakeRedis()


async def _make_fake_redis(url: str):
    return fakeredis.FakeRedis()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lock_acquired_and_job_runs():
    """When no lock exists, the wrapped job executes and the lock key is set."""
    calls = []

    async def my_job():
        calls.append(1)

    fake = fakeredis.FakeRedis()

    with patch("scheduler.lock.aioredis.from_url", return_value=fake):
        from scheduler.lock import with_redis_lock
        wrapped = with_redis_lock("redis://localhost/0", "test_job", ttl_seconds=60)(my_job)
        await wrapped()

    assert calls == [1], "Job should have run once"
    # Lock key should exist in Redis
    assert await fake.exists("scheduler:lock:test_job"), "Lock key should be set after execution"


@pytest.mark.asyncio
async def test_lock_held_skips_job():
    """When the lock already exists, the wrapped job is skipped."""
    calls = []

    async def my_job():
        calls.append(1)

    fake = fakeredis.FakeRedis()
    # Pre-set the lock key so acquisition fails
    await fake.set("scheduler:lock:test_job", "1", ex=60)

    with patch("scheduler.lock.aioredis.from_url", return_value=fake):
        from scheduler.lock import with_redis_lock
        wrapped = with_redis_lock("redis://localhost/0", "test_job", ttl_seconds=60)(my_job)
        await wrapped()

    assert calls == [], "Job should NOT have run when lock is held"


@pytest.mark.asyncio
async def test_lock_released_on_job_error():
    """Even when the job raises, the Redis client is closed (no connection leak)."""
    close_called = []

    async def my_job():
        raise RuntimeError("boom")

    fake = fakeredis.FakeRedis()

    original_aclose = fake.aclose

    async def tracking_aclose():
        close_called.append(1)
        await original_aclose()

    fake.aclose = tracking_aclose

    with patch("scheduler.lock.aioredis.from_url", return_value=fake):
        from scheduler.lock import with_redis_lock
        wrapped = with_redis_lock("redis://localhost/0", "test_job", ttl_seconds=60)(my_job)
        with pytest.raises(RuntimeError, match="boom"):
            await wrapped()

    assert close_called == [1], "aclose() must be called even when job raises"


@pytest.mark.asyncio
async def test_lock_key_naming():
    """Lock key is prefixed with scheduler:lock: and uses the provided job_id."""
    async def my_job():
        pass

    fake = fakeredis.FakeRedis()

    with patch("scheduler.lock.aioredis.from_url", return_value=fake):
        from scheduler.lock import with_redis_lock
        wrapped = with_redis_lock("redis://localhost/0", "my_unique_job", ttl_seconds=10)(my_job)
        await wrapped()

    assert await fake.exists("scheduler:lock:my_unique_job")
    assert not await fake.exists("scheduler:lock:other_job")


@pytest.mark.asyncio
async def test_lock_ttl_set_correctly():
    """Lock key is created with the specified TTL."""
    async def my_job():
        pass

    fake = fakeredis.FakeRedis()

    with patch("scheduler.lock.aioredis.from_url", return_value=fake):
        from scheduler.lock import with_redis_lock
        wrapped = with_redis_lock("redis://localhost/0", "ttl_job", ttl_seconds=300)(my_job)
        await wrapped()

    ttl = await fake.ttl("scheduler:lock:ttl_job")
    assert 0 < ttl <= 300, f"TTL should be ≤300, got {ttl}"


@pytest.mark.asyncio
async def test_concurrent_instances_only_one_runs():
    """Simulate two scheduler instances racing — only the first should run the job."""
    calls = []

    async def my_job():
        calls.append(1)

    fake = fakeredis.FakeRedis()

    with patch("scheduler.lock.aioredis.from_url", return_value=fake):
        from scheduler.lock import with_redis_lock
        wrapped = with_redis_lock("redis://localhost/0", "race_job", ttl_seconds=60)(my_job)
        # Run both "instances" concurrently
        await asyncio.gather(wrapped(), wrapped())

    assert len(calls) == 1, "Exactly one instance should have run the job"
