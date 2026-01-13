"""
Redis cache and pub/sub utilities for System A.

Provides caching, pub/sub messaging, and distributed locking.
"""
import json
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncGenerator, Callable, Optional, TypeVar, Union

import redis.asyncio as redis
from redis.asyncio.client import PubSub

from ...config import get_settings

settings = get_settings()

T = TypeVar('T')


class RedisManager:
    """
    Manages Redis connections for caching and pub/sub.
    """

    _client: Optional[redis.Redis] = None
    _pubsub_client: Optional[redis.Redis] = None

    @classmethod
    async def get_client(cls) -> redis.Redis:
        """Get or create the Redis client."""
        if cls._client is None:
            cls._client = redis.from_url(
                settings.redis.url,
                encoding='utf-8',
                decode_responses=True,
            )
        return cls._client

    @classmethod
    async def get_pubsub_client(cls) -> redis.Redis:
        """Get a separate client for pub/sub (avoids blocking main client)."""
        if cls._pubsub_client is None:
            cls._pubsub_client = redis.from_url(
                settings.redis.url,
                encoding='utf-8',
                decode_responses=True,
            )
        return cls._pubsub_client

    @classmethod
    async def close(cls) -> None:
        """Close all Redis connections."""
        if cls._client is not None:
            await cls._client.close()
            cls._client = None
        if cls._pubsub_client is not None:
            await cls._pubsub_client.close()
            cls._pubsub_client = None


class Cache:
    """
    High-level caching interface.
    """

    def __init__(self, prefix: str = "cache"):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Build cache key with prefix."""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        client = await RedisManager.get_client()
        value = await client.get(self._key(key))
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None

    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[Union[int, timedelta]] = None
    ) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            expire: Expiration time in seconds or timedelta
        """
        client = await RedisManager.get_client()
        serialized = json.dumps(value, default=str)

        if expire is not None:
            if isinstance(expire, timedelta):
                expire = int(expire.total_seconds())
            await client.setex(self._key(key), expire, serialized)
        else:
            await client.set(self._key(key), serialized)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        client = await RedisManager.get_client()
        await client.delete(self._key(key))

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        client = await RedisManager.get_client()
        keys = await client.keys(self._key(pattern))
        if keys:
            return await client.delete(*keys)
        return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        client = await RedisManager.get_client()
        return await client.exists(self._key(key)) > 0

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        client = await RedisManager.get_client()
        return await client.incrby(self._key(key), amount)

    async def expire(self, key: str, seconds: int) -> None:
        """Set expiration on existing key."""
        client = await RedisManager.get_client()
        await client.expire(self._key(key), seconds)

    async def ttl(self, key: str) -> int:
        """Get time-to-live for key in seconds."""
        client = await RedisManager.get_client()
        return await client.ttl(self._key(key))

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        expire: Optional[Union[int, timedelta]] = None
    ) -> Any:
        """
        Get from cache or compute and set.

        Args:
            key: Cache key
            factory: Callable to compute value if not cached
            expire: Expiration time
        """
        value = await self.get(key)
        if value is None:
            value = await factory() if callable(factory) else factory
            await self.set(key, value, expire)
        return value


class PubSubManager:
    """
    Redis pub/sub message handling.
    """

    @staticmethod
    async def publish(channel: str, message: Any) -> int:
        """
        Publish message to channel.

        Args:
            channel: Channel name
            message: Message to publish (will be JSON serialized)

        Returns:
            Number of subscribers that received the message
        """
        client = await RedisManager.get_client()
        serialized = json.dumps(message, default=str)
        return await client.publish(channel, serialized)

    @staticmethod
    @asynccontextmanager
    async def subscribe(*channels: str) -> AsyncGenerator[PubSub, None]:
        """
        Subscribe to channels.

        Usage:
            async with PubSubManager.subscribe('channel1', 'channel2') as pubsub:
                async for message in pubsub.listen():
                    if message['type'] == 'message':
                        data = json.loads(message['data'])
                        # process data
        """
        client = await RedisManager.get_pubsub_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(*channels)
        try:
            yield pubsub
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()

    @staticmethod
    @asynccontextmanager
    async def psubscribe(*patterns: str) -> AsyncGenerator[PubSub, None]:
        """Subscribe to channel patterns."""
        client = await RedisManager.get_pubsub_client()
        pubsub = client.pubsub()
        await pubsub.psubscribe(*patterns)
        try:
            yield pubsub
        finally:
            await pubsub.punsubscribe(*patterns)
            await pubsub.close()


class DistributedLock:
    """
    Distributed lock using Redis.

    Implements a simple lock mechanism for coordinating across instances.
    """

    def __init__(
        self,
        name: str,
        timeout: int = 30,
        blocking: bool = True,
        blocking_timeout: Optional[int] = None
    ):
        self.name = f"lock:{name}"
        self.timeout = timeout
        self.blocking = blocking
        self.blocking_timeout = blocking_timeout
        self._lock: Optional[redis.lock.Lock] = None

    async def acquire(self) -> bool:
        """Acquire the lock."""
        client = await RedisManager.get_client()
        self._lock = client.lock(
            self.name,
            timeout=self.timeout,
            blocking=self.blocking,
            blocking_timeout=self.blocking_timeout
        )
        return await self._lock.acquire()

    async def release(self) -> None:
        """Release the lock."""
        if self._lock is not None:
            await self._lock.release()
            self._lock = None

    async def __aenter__(self) -> 'DistributedLock':
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.release()


class RateLimiter:
    """
    Rate limiter using Redis sliding window.
    """

    def __init__(
        self,
        key_prefix: str,
        max_requests: int,
        window_seconds: int
    ):
        self.key_prefix = key_prefix
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _key(self, identifier: str) -> str:
        return f"ratelimit:{self.key_prefix}:{identifier}"

    async def is_allowed(self, identifier: str) -> tuple[bool, int]:
        """
        Check if request is allowed.

        Args:
            identifier: Unique identifier (e.g., user_id, IP)

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        client = await RedisManager.get_client()
        key = self._key(identifier)

        current = await client.incr(key)
        if current == 1:
            await client.expire(key, self.window_seconds)

        remaining = max(0, self.max_requests - current)
        allowed = current <= self.max_requests

        return allowed, remaining

    async def reset(self, identifier: str) -> None:
        """Reset rate limit for identifier."""
        client = await RedisManager.get_client()
        await client.delete(self._key(identifier))


# Convenience instances
cache = Cache(prefix="solar_hub")
site_cache = Cache(prefix="site")
user_cache = Cache(prefix="user")
dashboard_cache = Cache(prefix="dashboard")


async def health_check() -> bool:
    """Check Redis connectivity."""
    try:
        client = await RedisManager.get_client()
        return await client.ping()
    except Exception:
        return False
