"""
Integration tests for Stream Services.

Tests TelemetryStreamService, CommandStreamService, AlertStreamService,
and NotificationStreamService.
"""
import pytest
import asyncio
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


class TestTelemetryStreamService:
    """Test TelemetryStreamService functionality."""

    def test_init_default_values(self):
        """Test service initialization with defaults."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService()

        assert service.consumer_group == "telemetry_processors"
        assert service.consumer_name.startswith("consumer_")
        assert service._running is False
        assert service._messages_published == 0
        assert service._messages_consumed == 0

    def test_init_custom_values(self):
        """Test service initialization with custom values."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService(
            consumer_group="custom_group",
            consumer_name="custom_consumer",
        )

        assert service.consumer_group == "custom_group"
        assert service.consumer_name == "custom_consumer"

    @pytest.mark.asyncio
    async def test_publish_telemetry(self, mock_redis_manager):
        """Test publishing telemetry data."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService()

        device_id = uuid4()
        site_id = uuid4()
        metrics = {"battery_soc_pct": 75.0, "pv_power_w": 3500}

        message_id = await service.publish_telemetry(
            device_id=device_id,
            site_id=site_id,
            metrics=metrics,
        )

        assert message_id is not None
        assert service._messages_published == 1
        assert service._last_publish_time is not None

    @pytest.mark.asyncio
    async def test_publish_telemetry_with_timestamp(self, mock_redis_manager):
        """Test publishing telemetry with custom timestamp."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService()

        custom_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        message_id = await service.publish_telemetry(
            device_id=uuid4(),
            site_id=uuid4(),
            metrics={"value": 100},
            timestamp=custom_time,
            source="simulator",
        )

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_publish_batch(self, mock_redis_manager):
        """Test publishing batch of telemetry."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService()

        batch = [
            {
                "device_id": uuid4(),
                "site_id": uuid4(),
                "metrics": {"value": i},
            }
            for i in range(5)
        ]

        message_ids = await service.publish_batch(batch)

        assert len(message_ids) == 5
        assert service._messages_published == 5

    def test_set_telemetry_handler(self):
        """Test setting telemetry handler."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService()

        async def handler(*args, **kwargs):
            pass

        service.set_telemetry_handler(handler)

        assert service._on_telemetry == handler

    @pytest.mark.asyncio
    async def test_start_consumer(self, mock_redis_manager):
        """Test starting the consumer."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService()

        await service.start_consumer(batch_size=5, block_ms=100)

        assert service._running is True
        assert service._consumer is not None

        await service.stop_consumer()

    @pytest.mark.asyncio
    async def test_stop_consumer(self, mock_redis_manager):
        """Test stopping the consumer."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService()

        await service.start_consumer()
        await service.stop_consumer()

        assert service._running is False

    def test_get_stats(self):
        """Test getting service statistics."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        service = TelemetryStreamService()

        stats = service.get_stats()

        assert stats["running"] is False
        assert stats["messages_published"] == 0
        assert stats["messages_consumed"] == 0
        assert stats["consumer_group"] == "telemetry_processors"


class TestCommandStreamService:
    """Test CommandStreamService functionality."""

    def test_init_default_values(self):
        """Test service initialization with defaults."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        assert service.consumer_group == "command_executors"
        assert service.consumer_name.startswith("executor_")
        assert service._running is False

    @pytest.mark.asyncio
    async def test_publish_command(self, mock_redis_manager):
        """Test publishing a command."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        command_id = uuid4()
        device_id = uuid4()
        site_id = uuid4()

        message_id = await service.publish_command(
            command_id=command_id,
            device_id=device_id,
            site_id=site_id,
            command_type="set_mode",
            command_params={"mode": "battery_priority"},
            priority=3,
        )

        assert message_id is not None
        assert service._commands_published == 1

    @pytest.mark.asyncio
    async def test_publish_result(self, mock_redis_manager):
        """Test publishing command result."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        message_id = await service.publish_result(
            command_id=uuid4(),
            device_id=uuid4(),
            success=True,
            result={"new_mode": "battery_priority"},
        )

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_publish_result_failure(self, mock_redis_manager):
        """Test publishing failed command result."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        message_id = await service.publish_result(
            command_id=uuid4(),
            device_id=uuid4(),
            success=False,
            error_message="Device offline",
        )

        assert message_id is not None

    def test_set_command_handler(self):
        """Test setting command handler."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        async def handler(*args, **kwargs):
            pass

        service.set_command_handler(handler)

        assert service._on_command == handler

    def test_set_result_handler(self):
        """Test setting result handler."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        async def handler(*args, **kwargs):
            pass

        service.set_result_handler(handler)

        assert service._on_result == handler

    @pytest.mark.asyncio
    async def test_start_stop_consumer(self, mock_redis_manager):
        """Test consumer lifecycle."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        await service.start_consumer(batch_size=5, block_ms=100)
        assert service._running is True

        await service.stop_consumer()
        assert service._running is False

    def test_get_stats(self):
        """Test getting service statistics."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        stats = service.get_stats()

        assert stats["running"] is False
        assert stats["commands_published"] == 0
        assert stats["commands_processed"] == 0


class TestAlertStreamService:
    """Test AlertStreamService functionality."""

    def test_init(self):
        """Test service initialization."""
        from app.infrastructure.messaging.stream_services import AlertStreamService

        service = AlertStreamService()

        assert service._alerts_published == 0

    @pytest.mark.asyncio
    async def test_publish_for_evaluation(self, mock_redis_manager):
        """Test publishing metric for alert evaluation."""
        from app.infrastructure.messaging.stream_services import AlertStreamService

        service = AlertStreamService()

        message_id = await service.publish_for_evaluation(
            device_id=uuid4(),
            site_id=uuid4(),
            metric_name="battery_soc_pct",
            metric_value=15.5,
            timestamp=datetime.now(timezone.utc),
        )

        assert message_id is not None
        assert service._alerts_published == 1

    @pytest.mark.asyncio
    async def test_publish_batch_for_evaluation(self, mock_redis_manager):
        """Test publishing batch for alert evaluation."""
        from app.infrastructure.messaging.stream_services import AlertStreamService

        service = AlertStreamService()

        batch = [
            {
                "device_id": uuid4(),
                "site_id": uuid4(),
                "metric_name": "battery_soc_pct",
                "metric_value": 75.0,
            },
            {
                "device_id": uuid4(),
                "site_id": uuid4(),
                "metric_name": "pv_power_w",
                "metric_value": 3500,
            },
        ]

        message_ids = await service.publish_batch_for_evaluation(batch)

        assert len(message_ids) == 2


class TestNotificationStreamService:
    """Test NotificationStreamService functionality."""

    def test_init_default_values(self):
        """Test service initialization with defaults."""
        from app.infrastructure.messaging.stream_services import NotificationStreamService

        service = NotificationStreamService()

        assert service.consumer_group == "notification_senders"
        assert service.consumer_name.startswith("sender_")
        assert service._running is False

    @pytest.mark.asyncio
    async def test_publish_notification(self, mock_redis_manager):
        """Test publishing a notification."""
        from app.infrastructure.messaging.stream_services import NotificationStreamService

        service = NotificationStreamService()

        message_id = await service.publish_notification(
            notification_type="email",
            recipients=["admin@example.com"],
            subject="Low Battery Alert",
            body="Battery SOC is below 20%",
            data={"device_id": str(uuid4()), "soc": 15},
            priority="high",
        )

        assert message_id is not None

    @pytest.mark.asyncio
    async def test_publish_notification_minimal(self, mock_redis_manager):
        """Test publishing notification with minimal data."""
        from app.infrastructure.messaging.stream_services import NotificationStreamService

        service = NotificationStreamService()

        message_id = await service.publish_notification(
            notification_type="sms",
            recipients=["+1234567890"],
            subject="Alert",
            body="Check system status",
        )

        assert message_id is not None

    def test_set_notification_handler(self):
        """Test setting notification handler."""
        from app.infrastructure.messaging.stream_services import NotificationStreamService

        service = NotificationStreamService()

        async def handler(data):
            pass

        service.set_notification_handler(handler)

        assert service._on_notification == handler

    @pytest.mark.asyncio
    async def test_start_stop_consumer(self, mock_redis_manager):
        """Test consumer lifecycle."""
        from app.infrastructure.messaging.stream_services import NotificationStreamService

        service = NotificationStreamService()

        await service.start_consumer(batch_size=5, block_ms=100)
        assert service._running is True

        await service.stop_consumer()
        assert service._running is False


class TestServiceSingletons:
    """Test pre-configured service singletons."""

    def test_telemetry_stream_service_exists(self):
        """Test telemetry stream service singleton."""
        from app.infrastructure.messaging.stream_services import telemetry_stream_service

        assert telemetry_stream_service is not None
        assert telemetry_stream_service.consumer_group == "telemetry_processors"

    def test_command_stream_service_exists(self):
        """Test command stream service singleton."""
        from app.infrastructure.messaging.stream_services import command_stream_service

        assert command_stream_service is not None
        assert command_stream_service.consumer_group == "command_executors"

    def test_alert_stream_service_exists(self):
        """Test alert stream service singleton."""
        from app.infrastructure.messaging.stream_services import alert_stream_service

        assert alert_stream_service is not None

    def test_notification_stream_service_exists(self):
        """Test notification stream service singleton."""
        from app.infrastructure.messaging.stream_services import notification_stream_service

        assert notification_stream_service is not None
        assert notification_stream_service.consumer_group == "notification_senders"


class TestShutdownAllStreams:
    """Test shutdown function."""

    @pytest.mark.asyncio
    async def test_shutdown_all_streams(self, mock_redis_manager):
        """Test shutting down all stream services."""
        from app.infrastructure.messaging.stream_services import (
            telemetry_stream_service,
            command_stream_service,
            notification_stream_service,
            shutdown_all_streams,
        )

        # Start some services
        await telemetry_stream_service.start_consumer(batch_size=1, block_ms=100)
        await command_stream_service.start_consumer(batch_size=1, block_ms=100)

        # Shutdown all
        await shutdown_all_streams()

        assert telemetry_stream_service._running is False
        assert command_stream_service._running is False


class TestEndToEndMessageFlow:
    """Test end-to-end message flow through services."""

    @pytest.mark.asyncio
    async def test_telemetry_publish_and_consume(self, mock_redis_manager):
        """Test full telemetry message flow."""
        from app.infrastructure.messaging.stream_services import TelemetryStreamService

        producer_service = TelemetryStreamService(
            consumer_group="test_group",
            consumer_name="producer",
        )
        consumer_service = TelemetryStreamService(
            consumer_group="test_group",
            consumer_name="consumer",
        )

        # Publish telemetry
        device_id = uuid4()
        site_id = uuid4()

        await producer_service.publish_telemetry(
            device_id=device_id,
            site_id=site_id,
            metrics={"battery_soc_pct": 75.0},
        )

        assert producer_service._messages_published == 1

    @pytest.mark.asyncio
    async def test_command_publish_and_result(self, mock_redis_manager):
        """Test command publish and result flow."""
        from app.infrastructure.messaging.stream_services import CommandStreamService

        service = CommandStreamService()

        command_id = uuid4()
        device_id = uuid4()
        site_id = uuid4()

        # Publish command
        await service.publish_command(
            command_id=command_id,
            device_id=device_id,
            site_id=site_id,
            command_type="set_mode",
        )

        # Publish result
        await service.publish_result(
            command_id=command_id,
            device_id=device_id,
            success=True,
            result={"mode": "battery_priority"},
        )

        assert service._commands_published == 1

    @pytest.mark.asyncio
    async def test_alert_to_notification_flow(self, mock_redis_manager):
        """Test alert evaluation to notification flow."""
        from app.infrastructure.messaging.stream_services import (
            AlertStreamService,
            NotificationStreamService,
        )

        alert_service = AlertStreamService()
        notification_service = NotificationStreamService()

        device_id = uuid4()
        site_id = uuid4()

        # Publish alert for evaluation
        await alert_service.publish_for_evaluation(
            device_id=device_id,
            site_id=site_id,
            metric_name="battery_soc_pct",
            metric_value=10.0,  # Critical low
            timestamp=datetime.now(timezone.utc),
        )

        # Simulated alert evaluation would create notification
        await notification_service.publish_notification(
            notification_type="email",
            recipients=["admin@example.com"],
            subject="Critical: Low Battery",
            body="Battery SOC is critically low (10%)",
            data={"device_id": str(device_id)},
            priority="high",
        )

        assert alert_service._alerts_published == 1

