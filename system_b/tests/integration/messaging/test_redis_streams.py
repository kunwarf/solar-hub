"""
Integration tests for Redis Streams utilities.

Tests StreamProducer, StreamConsumer, and PubSubManager.
"""
import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import fakeredis.aioredis


@pytest.fixture
def fake_redis():
    """Create fake Redis client."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_redis_manager(fake_redis):
    """Mock the RedisStreamManager to use fake Redis."""
    with patch(
        "app.infrastructure.messaging.redis_streams.RedisStreamManager.get_client",
        return_value=fake_redis
    ):
        yield fake_redis


class TestStreamMessage:
    """Test StreamMessage dataclass."""

    def test_from_raw_parses_correctly(self):
        """Test parsing raw Redis message."""
        from app.infrastructure.messaging.redis_streams import StreamMessage

        stream = "test_stream"
        message_id = "1704067200000-0"  # 2024-01-01 00:00:00 UTC
        fields = {"data": json.dumps({"key": "value"})}

        msg = StreamMessage.from_raw(stream, message_id, fields)

        assert msg.stream == stream
        assert msg.message_id == message_id
        assert msg.data == {"key": "value"}
        assert msg.timestamp.year == 2024

    def test_from_raw_handles_empty_data(self):
        """Test parsing message with empty data."""
        from app.infrastructure.messaging.redis_streams import StreamMessage

        msg = StreamMessage.from_raw("stream", "1704067200000-0", {})

        assert msg.data == {}


class TestStreamProducer:
    """Test StreamProducer functionality."""

    @pytest.mark.asyncio
    async def test_add_message(self, mock_redis_manager):
        """Test adding a single message."""
        from app.infrastructure.messaging.redis_streams import StreamProducer

        producer = StreamProducer("test_stream", max_len=1000)

        message_id = await producer.add({"key": "value"})

        assert message_id is not None
        assert "-" in message_id

    @pytest.mark.asyncio
    async def test_add_message_with_custom_id(self, mock_redis_manager):
        """Test adding message with specific ID."""
        from app.infrastructure.messaging.redis_streams import StreamProducer

        producer = StreamProducer("test_stream")

        # Using * for auto-generate
        message_id = await producer.add({"key": "value"}, message_id="*")

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_add_batch(self, mock_redis_manager):
        """Test adding multiple messages in batch."""
        from app.infrastructure.messaging.redis_streams import StreamProducer

        producer = StreamProducer("test_stream")

        messages = [
            {"device_id": str(uuid4()), "value": i}
            for i in range(5)
        ]

        message_ids = await producer.add_batch(messages)

        assert len(message_ids) == 5
        for mid in message_ids:
            assert "-" in mid

    @pytest.mark.asyncio
    async def test_add_complex_data(self, mock_redis_manager):
        """Test adding message with complex data types."""
        from app.infrastructure.messaging.redis_streams import StreamProducer

        producer = StreamProducer("test_stream")

        data = {
            "device_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc),
            "metrics": {
                "battery_soc": 75.5,
                "power": 3500,
            },
            "nested": {"level1": {"level2": "value"}},
        }

        message_id = await producer.add(data)

        assert message_id is not None


class TestStreamConsumer:
    """Test StreamConsumer functionality."""

    @pytest.mark.asyncio
    async def test_ensure_group_creates_group(self, mock_redis_manager):
        """Test consumer group creation."""
        from app.infrastructure.messaging.redis_streams import StreamConsumer

        consumer = StreamConsumer(
            "test_stream",
            "test_group",
            "consumer_1",
        )

        # Should not raise
        await consumer.ensure_group()

    @pytest.mark.asyncio
    async def test_ensure_group_handles_existing(self, mock_redis_manager):
        """Test handling of existing group."""
        from app.infrastructure.messaging.redis_streams import StreamConsumer

        consumer = StreamConsumer(
            "test_stream",
            "test_group",
            "consumer_1",
        )

        # Create twice - second should not raise
        await consumer.ensure_group()
        await consumer.ensure_group()

    @pytest.mark.asyncio
    async def test_read_messages(self, mock_redis_manager, fake_redis):
        """Test reading messages from stream."""
        from app.infrastructure.messaging.redis_streams import (
            StreamProducer,
            StreamConsumer,
        )

        # Add messages first
        producer = StreamProducer("test_stream")
        await producer.add({"key": "value1"})
        await producer.add({"key": "value2"})

        # Create consumer and read
        consumer = StreamConsumer(
            "test_stream",
            "test_group",
            "consumer_1",
        )
        await consumer.ensure_group()

        messages = await consumer.read(count=10, block=100)

        assert len(messages) == 2
        assert messages[0].data["key"] == "value1"
        assert messages[1].data["key"] == "value2"

    @pytest.mark.asyncio
    async def test_ack_message(self, mock_redis_manager, fake_redis):
        """Test acknowledging messages."""
        from app.infrastructure.messaging.redis_streams import (
            StreamProducer,
            StreamConsumer,
        )

        producer = StreamProducer("test_stream")
        await producer.add({"key": "value"})

        consumer = StreamConsumer(
            "test_stream",
            "test_group",
            "consumer_1",
        )
        await consumer.ensure_group()

        messages = await consumer.read(count=1, block=100)
        assert len(messages) == 1

        # Acknowledge the message
        result = await consumer.ack(messages[0].message_id)
        assert result >= 0

    @pytest.mark.asyncio
    async def test_ack_batch(self, mock_redis_manager, fake_redis):
        """Test batch acknowledgment."""
        from app.infrastructure.messaging.redis_streams import (
            StreamProducer,
            StreamConsumer,
        )

        producer = StreamProducer("test_stream")
        for i in range(3):
            await producer.add({"key": f"value{i}"})

        consumer = StreamConsumer(
            "test_stream",
            "test_group",
            "consumer_1",
        )
        await consumer.ensure_group()

        messages = await consumer.read(count=10, block=100)
        message_ids = [m.message_id for m in messages]

        result = await consumer.ack_batch(message_ids)
        assert result >= 0

    @pytest.mark.asyncio
    async def test_process_with_handler(self, mock_redis_manager, fake_redis):
        """Test processing messages with handler."""
        from app.infrastructure.messaging.redis_streams import (
            StreamProducer,
            StreamConsumer,
        )

        producer = StreamProducer("test_stream")
        await producer.add({"key": "value1"})
        await producer.add({"key": "value2"})

        consumer = StreamConsumer(
            "test_stream",
            "test_group",
            "consumer_1",
        )
        await consumer.ensure_group()

        processed = []

        async def handler(msg):
            processed.append(msg.data)

        count = await consumer.process(handler, count=10, block=100)

        assert count == 2
        assert len(processed) == 2

    @pytest.mark.asyncio
    async def test_process_handles_errors(self, mock_redis_manager, fake_redis):
        """Test error handling in process."""
        from app.infrastructure.messaging.redis_streams import (
            StreamProducer,
            StreamConsumer,
        )

        producer = StreamProducer("test_stream")
        await producer.add({"key": "value1"})
        await producer.add({"key": "value2"})

        consumer = StreamConsumer(
            "test_stream",
            "test_group",
            "consumer_1",
        )
        await consumer.ensure_group()

        call_count = 0

        async def failing_handler(msg):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Test error")

        # Should process second message even if first fails
        count = await consumer.process(failing_handler, count=10, block=100)

        # Only the second message was successful
        assert count == 1
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_stop_consumer(self, mock_redis_manager):
        """Test stopping consumer."""
        from app.infrastructure.messaging.redis_streams import StreamConsumer

        consumer = StreamConsumer(
            "test_stream",
            "test_group",
            "consumer_1",
        )

        assert consumer._running is False
        consumer.stop()
        assert consumer._running is False


class TestPubSubManager:
    """Test PubSubManager functionality."""

    @pytest.mark.asyncio
    async def test_publish(self, mock_redis_manager):
        """Test publishing to channel."""
        from app.infrastructure.messaging.redis_streams import PubSubManager

        result = await PubSubManager.publish("test_channel", {"key": "value"})

        # Returns number of subscribers (0 in test)
        assert result >= 0

    @pytest.mark.asyncio
    async def test_publish_complex_data(self, mock_redis_manager):
        """Test publishing complex data types."""
        from app.infrastructure.messaging.redis_streams import PubSubManager

        data = {
            "timestamp": datetime.now(timezone.utc),
            "nested": {"key": [1, 2, 3]},
        }

        result = await PubSubManager.publish("test_channel", data)
        assert result >= 0


class TestHealthCheck:
    """Test health check function."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_redis_manager):
        """Test successful health check."""
        from app.infrastructure.messaging.redis_streams import health_check

        result = await health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check with connection failure."""
        from app.infrastructure.messaging.redis_streams import health_check

        with patch(
            "app.infrastructure.messaging.redis_streams.RedisStreamManager.get_client",
            side_effect=Exception("Connection failed"),
        ):
            result = await health_check()

        assert result is False


class TestStreamInfo:
    """Test stream info retrieval."""

    @pytest.mark.asyncio
    async def test_get_stream_info(self, mock_redis_manager, fake_redis):
        """Test getting stream information."""
        from app.infrastructure.messaging.redis_streams import (
            StreamProducer,
            get_stream_info,
        )

        # Add some messages
        producer = StreamProducer("test_stream")
        await producer.add({"key": "value1"})
        await producer.add({"key": "value2"})

        info = await get_stream_info("test_stream")

        assert "length" in info
        assert info["length"] == 2


class TestConvenienceProducers:
    """Test pre-configured producers."""

    @pytest.mark.asyncio
    async def test_telemetry_producer(self, mock_redis_manager):
        """Test telemetry producer."""
        from app.infrastructure.messaging.redis_streams import telemetry_producer

        message_id = await telemetry_producer.add({
            "device_id": str(uuid4()),
            "metrics": {"battery_soc": 75.0},
        })

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_alert_producer(self, mock_redis_manager):
        """Test alert producer."""
        from app.infrastructure.messaging.redis_streams import alert_producer

        message_id = await alert_producer.add({
            "device_id": str(uuid4()),
            "alert_type": "low_battery",
        })

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_command_producer(self, mock_redis_manager):
        """Test command producer."""
        from app.infrastructure.messaging.redis_streams import command_producer

        message_id = await command_producer.add({
            "command_id": str(uuid4()),
            "command_type": "set_mode",
        })

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_notification_producer(self, mock_redis_manager):
        """Test notification producer."""
        from app.infrastructure.messaging.redis_streams import notification_producer

        message_id = await notification_producer.add({
            "type": "email",
            "recipients": ["test@example.com"],
        })

        assert message_id is not None

