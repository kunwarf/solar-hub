"""
Redis Streams utilities for System B (Telemetry).

Provides stream-based message queuing for telemetry ingestion and processing.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple

import redis.asyncio as redis

from ...config import get_settings

settings = get_settings()


@dataclass
class StreamMessage:
    """Represents a message from a Redis stream."""
    stream: str
    message_id: str
    data: Dict[str, Any]
    timestamp: datetime

    @classmethod
    def from_raw(cls, stream: str, message_id: str, fields: Dict[str, str]) -> 'StreamMessage':
        """Create from raw Redis response."""
        # Parse timestamp from message ID (format: timestamp-sequence)
        ts_ms = int(message_id.split('-')[0])
        timestamp = datetime.fromtimestamp(ts_ms / 1000)

        # Deserialize data field
        data = json.loads(fields.get('data', '{}'))

        return cls(
            stream=stream,
            message_id=message_id,
            data=data,
            timestamp=timestamp
        )


class RedisStreamManager:
    """
    Manages Redis connections for stream operations.
    """

    _client: Optional[redis.Redis] = None

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
    async def close(cls) -> None:
        """Close Redis connection."""
        if cls._client is not None:
            await cls._client.close()
            cls._client = None


class StreamProducer:
    """
    Produces messages to Redis streams.

    Optimized for high-throughput telemetry ingestion.
    """

    def __init__(self, stream_name: str, max_len: Optional[int] = None):
        self.stream_name = stream_name
        self.max_len = max_len or settings.redis.stream_max_len

    async def add(
        self,
        data: Dict[str, Any],
        message_id: str = '*'
    ) -> str:
        """
        Add message to stream.

        Args:
            data: Message data
            message_id: Message ID (* for auto-generate)

        Returns:
            Generated message ID
        """
        client = await RedisStreamManager.get_client()

        # Serialize data
        fields = {'data': json.dumps(data, default=str)}

        return await client.xadd(
            self.stream_name,
            fields,
            id=message_id,
            maxlen=self.max_len,
            approximate=True  # Use ~ for better performance
        )

    async def add_batch(self, messages: List[Dict[str, Any]]) -> List[str]:
        """
        Add multiple messages using pipeline.

        Args:
            messages: List of message data dicts

        Returns:
            List of generated message IDs
        """
        client = await RedisStreamManager.get_client()
        pipe = client.pipeline()

        for data in messages:
            fields = {'data': json.dumps(data, default=str)}
            pipe.xadd(
                self.stream_name,
                fields,
                id='*',
                maxlen=self.max_len,
                approximate=True
            )

        return await pipe.execute()


class StreamConsumer:
    """
    Consumes messages from Redis streams.

    Supports consumer groups for distributed processing.
    """

    def __init__(
        self,
        stream_name: str,
        group_name: str,
        consumer_name: str
    ):
        self.stream_name = stream_name
        self.group_name = group_name
        self.consumer_name = consumer_name
        self._running = False

    async def ensure_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        client = await RedisStreamManager.get_client()
        try:
            await client.xgroup_create(
                self.stream_name,
                self.group_name,
                id='0',
                mkstream=True
            )
        except redis.ResponseError as e:
            if 'BUSYGROUP' not in str(e):
                raise

    async def read(
        self,
        count: int = 10,
        block: int = 5000
    ) -> List[StreamMessage]:
        """
        Read messages from stream.

        Args:
            count: Maximum messages to read
            block: Block time in milliseconds (0 for no blocking)

        Returns:
            List of stream messages
        """
        client = await RedisStreamManager.get_client()

        response = await client.xreadgroup(
            self.group_name,
            self.consumer_name,
            {self.stream_name: '>'},
            count=count,
            block=block
        )

        messages = []
        if response:
            for stream_name, stream_messages in response:
                for message_id, fields in stream_messages:
                    msg = StreamMessage.from_raw(stream_name, message_id, fields)
                    messages.append(msg)

        return messages

    async def read_pending(self, count: int = 10) -> List[StreamMessage]:
        """
        Read pending (unacknowledged) messages.

        Useful for recovering from failures.
        """
        client = await RedisStreamManager.get_client()

        response = await client.xreadgroup(
            self.group_name,
            self.consumer_name,
            {self.stream_name: '0'},
            count=count
        )

        messages = []
        if response:
            for stream_name, stream_messages in response:
                for message_id, fields in stream_messages:
                    if fields:  # Skip empty (deleted) messages
                        msg = StreamMessage.from_raw(stream_name, message_id, fields)
                        messages.append(msg)

        return messages

    async def ack(self, message_id: str) -> int:
        """Acknowledge message as processed."""
        client = await RedisStreamManager.get_client()
        return await client.xack(self.stream_name, self.group_name, message_id)

    async def ack_batch(self, message_ids: List[str]) -> int:
        """Acknowledge multiple messages."""
        if not message_ids:
            return 0
        client = await RedisStreamManager.get_client()
        return await client.xack(self.stream_name, self.group_name, *message_ids)

    async def process(
        self,
        handler: Callable[[StreamMessage], Any],
        count: int = 10,
        block: int = 5000
    ) -> int:
        """
        Process messages with handler.

        Args:
            handler: Async function to process each message
            count: Messages per batch
            block: Block time in ms

        Returns:
            Number of messages processed
        """
        messages = await self.read(count=count, block=block)
        processed = 0

        for msg in messages:
            try:
                await handler(msg)
                await self.ack(msg.message_id)
                processed += 1
            except Exception as e:
                # Log error but don't ack - message will be reprocessed
                print(f"Error processing message {msg.message_id}: {e}")

        return processed

    async def run_forever(
        self,
        handler: Callable[[StreamMessage], Any],
        count: int = 10,
        block: int = 5000
    ) -> None:
        """
        Continuously process messages.

        Call stop() to gracefully shut down.
        """
        await self.ensure_group()
        self._running = True

        # First, process any pending messages
        while self._running:
            pending = await self.read_pending(count=count)
            if not pending:
                break
            for msg in pending:
                try:
                    await handler(msg)
                    await self.ack(msg.message_id)
                except Exception as e:
                    print(f"Error processing pending message {msg.message_id}: {e}")

        # Then, process new messages
        while self._running:
            try:
                await self.process(handler, count=count, block=block)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in consumer loop: {e}")
                await asyncio.sleep(1)

    def stop(self) -> None:
        """Signal consumer to stop."""
        self._running = False


class PubSubManager:
    """
    Redis pub/sub for real-time notifications.
    """

    @staticmethod
    async def publish(channel: str, message: Any) -> int:
        """Publish message to channel."""
        client = await RedisStreamManager.get_client()
        serialized = json.dumps(message, default=str)
        return await client.publish(channel, serialized)

    @staticmethod
    @asynccontextmanager
    async def subscribe(*channels: str) -> AsyncGenerator:
        """Subscribe to channels."""
        client = await RedisStreamManager.get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(*channels)
        try:
            yield pubsub
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()


# Pre-configured stream names
TELEMETRY_STREAM = 'telemetry_ingestion'
ALERT_STREAM = 'alert_evaluation'
NOTIFICATION_STREAM = 'notifications'
COMMAND_STREAM = 'device_commands'


# Convenience producers
telemetry_producer = StreamProducer(TELEMETRY_STREAM)
alert_producer = StreamProducer(ALERT_STREAM)
notification_producer = StreamProducer(NOTIFICATION_STREAM)
command_producer = StreamProducer(COMMAND_STREAM)


async def health_check() -> bool:
    """Check Redis connectivity."""
    try:
        client = await RedisStreamManager.get_client()
        return await client.ping()
    except Exception:
        return False


async def get_stream_info(stream_name: str) -> Dict[str, Any]:
    """Get information about a stream."""
    client = await RedisStreamManager.get_client()
    info = await client.xinfo_stream(stream_name)
    return {
        'length': info['length'],
        'first_entry': info['first-entry'],
        'last_entry': info['last-entry'],
        'groups': await client.xinfo_groups(stream_name)
    }
