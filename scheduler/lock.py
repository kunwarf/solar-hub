"""
Redis distributed lock for horizontal scaling.

Wraps job functions with a SETNX lock so that when multiple scheduler
instances are running, only one executes each job per cycle.
"""
import functools
import logging
from typing import Callable

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


def with_redis_lock(redis_url: str, job_id: str, ttl_seconds: int) -> Callable:
    """
    Decorator factory: acquire a Redis SETNX lock before executing a job.

    If the lock is already held by another scheduler instance, the job is
    skipped silently for this cycle.

    Args:
        redis_url:    Redis connection URL (e.g. redis://localhost:6379/0)
        job_id:       Unique job identifier — becomes part of the lock key
        ttl_seconds:  Lock TTL. Should be shorter than the job interval but
                      longer than the expected execution time. On expiry the
                      lock is released automatically even if the process dies.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            client = aioredis.from_url(redis_url)
            try:
                key = f"scheduler:lock:{job_id}"
                acquired = await client.set(key, "1", nx=True, ex=ttl_seconds)
                if not acquired:
                    logger.debug(
                        "Lock '%s' held by another scheduler instance — skipping this cycle",
                        job_id,
                    )
                    return
                logger.debug("Lock '%s' acquired (TTL=%ds)", job_id, ttl_seconds)
                return await func(*args, **kwargs)
            finally:
                await client.aclose()
        return wrapper
    return decorator
