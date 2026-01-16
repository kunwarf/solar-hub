"""
Stream service classes for System B.

Integrates Redis streams with workers for distributed processing.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from .redis_streams import (
    StreamProducer,
    StreamConsumer,
    StreamMessage,
    RedisStreamManager,
    TELEMETRY_STREAM,
    COMMAND_STREAM,
    ALERT_STREAM,
    NOTIFICATION_STREAM,
)

logger = logging.getLogger(__name__)


class TelemetryStreamService:
    """
    Service for telemetry stream processing.

    Provides high-level interface for publishing and consuming
    telemetry data through Redis streams.
    """

    def __init__(
        self,
        consumer_group: str = "telemetry_processors",
        consumer_name: Optional[str] = None,
    ):
        """
        Initialize the telemetry stream service.

        Args:
            consumer_group: Consumer group name.
            consumer_name: Unique consumer name (auto-generated if not provided).
        """
        self.producer = StreamProducer(TELEMETRY_STREAM)
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"consumer_{datetime.now().timestamp()}"

        self._consumer: Optional[StreamConsumer] = None
        self._running = False

        # Handlers
        self._on_telemetry: Optional[Callable] = None

        # Stats
        self._messages_published = 0
        self._messages_consumed = 0
        self._last_publish_time: Optional[datetime] = None
        self._last_consume_time: Optional[datetime] = None

    async def publish_telemetry(
        self,
        device_id: UUID,
        site_id: UUID,
        metrics: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        source: str = "device",
    ) -> str:
        """
        Publish telemetry data to stream.

        Args:
            device_id: Device ID.
            site_id: Site ID.
            metrics: Telemetry metrics.
            timestamp: Telemetry timestamp.
            source: Data source.

        Returns:
            Message ID.
        """
        data = {
            "device_id": str(device_id),
            "site_id": str(site_id),
            "metrics": metrics,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "source": source,
        }

        message_id = await self.producer.add(data)
        self._messages_published += 1
        self._last_publish_time = datetime.now(timezone.utc)

        logger.debug(f"Published telemetry for device {device_id}: {message_id}")
        return message_id

    async def publish_batch(
        self,
        telemetry_batch: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Publish batch of telemetry data.

        Args:
            telemetry_batch: List of telemetry data dictionaries.

        Returns:
            List of message IDs.
        """
        # Ensure all entries have proper format
        formatted_batch = []
        for item in telemetry_batch:
            formatted = {
                "device_id": str(item.get("device_id")),
                "site_id": str(item.get("site_id")),
                "metrics": item.get("metrics", {}),
                "timestamp": item.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "source": item.get("source", "device"),
            }
            formatted_batch.append(formatted)

        message_ids = await self.producer.add_batch(formatted_batch)
        self._messages_published += len(message_ids)
        self._last_publish_time = datetime.now(timezone.utc)

        logger.debug(f"Published batch of {len(message_ids)} telemetry messages")
        return message_ids

    def set_telemetry_handler(self, handler: Callable) -> None:
        """Set handler for processing telemetry messages."""
        self._on_telemetry = handler

    async def start_consumer(
        self,
        batch_size: int = 10,
        block_ms: int = 5000,
    ) -> None:
        """
        Start consuming telemetry messages.

        Args:
            batch_size: Messages per batch.
            block_ms: Block time in milliseconds.
        """
        if self._running:
            logger.warning("Consumer already running")
            return

        self._consumer = StreamConsumer(
            TELEMETRY_STREAM,
            self.consumer_group,
            self.consumer_name,
        )

        await self._consumer.ensure_group()
        self._running = True

        logger.info(f"Started telemetry stream consumer: {self.consumer_name}")

        # Process in background
        asyncio.create_task(
            self._consume_loop(batch_size, block_ms),
            name="telemetry_stream_consumer",
        )

    async def stop_consumer(self) -> None:
        """Stop the consumer."""
        self._running = False
        if self._consumer:
            self._consumer.stop()

        logger.info("Stopped telemetry stream consumer")

    async def _consume_loop(self, batch_size: int, block_ms: int) -> None:
        """Internal consume loop."""
        while self._running:
            try:
                messages = await self._consumer.read(count=batch_size, block=block_ms)

                for msg in messages:
                    try:
                        await self._process_message(msg)
                        await self._consumer.ack(msg.message_id)
                        self._messages_consumed += 1
                        self._last_consume_time = datetime.now(timezone.utc)
                    except Exception as e:
                        logger.error(f"Error processing telemetry message: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telemetry consume loop: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, msg: StreamMessage) -> None:
        """Process a single telemetry message."""
        if not self._on_telemetry:
            return

        data = msg.data
        await self._on_telemetry(
            device_id=UUID(data["device_id"]),
            site_id=UUID(data["site_id"]),
            metrics=data["metrics"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "device"),
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "running": self._running,
            "consumer_name": self.consumer_name,
            "consumer_group": self.consumer_group,
            "messages_published": self._messages_published,
            "messages_consumed": self._messages_consumed,
            "last_publish_time": self._last_publish_time.isoformat() if self._last_publish_time else None,
            "last_consume_time": self._last_consume_time.isoformat() if self._last_consume_time else None,
        }


class CommandStreamService:
    """
    Service for command stream processing.

    Handles device command distribution through Redis streams.
    """

    def __init__(
        self,
        consumer_group: str = "command_executors",
        consumer_name: Optional[str] = None,
    ):
        """
        Initialize the command stream service.

        Args:
            consumer_group: Consumer group name.
            consumer_name: Unique consumer name.
        """
        self.producer = StreamProducer(COMMAND_STREAM)
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"executor_{datetime.now().timestamp()}"

        self._consumer: Optional[StreamConsumer] = None
        self._running = False

        # Handlers
        self._on_command: Optional[Callable] = None
        self._on_result: Optional[Callable] = None

        # Stats
        self._commands_published = 0
        self._commands_processed = 0

    async def publish_command(
        self,
        command_id: UUID,
        device_id: UUID,
        site_id: UUID,
        command_type: str,
        command_params: Optional[Dict[str, Any]] = None,
        priority: int = 5,
    ) -> str:
        """
        Publish a command to the stream.

        Args:
            command_id: Command ID.
            device_id: Target device ID.
            site_id: Site ID.
            command_type: Command type.
            command_params: Command parameters.
            priority: Command priority.

        Returns:
            Message ID.
        """
        data = {
            "command_id": str(command_id),
            "device_id": str(device_id),
            "site_id": str(site_id),
            "command_type": command_type,
            "command_params": command_params or {},
            "priority": priority,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }

        message_id = await self.producer.add(data)
        self._commands_published += 1

        logger.debug(f"Published command {command_id} for device {device_id}")
        return message_id

    async def publish_result(
        self,
        command_id: UUID,
        device_id: UUID,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> str:
        """
        Publish command result.

        Args:
            command_id: Command ID.
            device_id: Device ID.
            success: Whether command succeeded.
            result: Result data.
            error_message: Error message if failed.

        Returns:
            Message ID.
        """
        result_producer = StreamProducer(f"{COMMAND_STREAM}_results")

        data = {
            "command_id": str(command_id),
            "device_id": str(device_id),
            "success": success,
            "result": result,
            "error_message": error_message,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        return await result_producer.add(data)

    def set_command_handler(self, handler: Callable) -> None:
        """Set handler for processing commands."""
        self._on_command = handler

    def set_result_handler(self, handler: Callable) -> None:
        """Set handler for processing results."""
        self._on_result = handler

    async def start_consumer(
        self,
        batch_size: int = 5,
        block_ms: int = 1000,
    ) -> None:
        """Start consuming commands."""
        if self._running:
            return

        self._consumer = StreamConsumer(
            COMMAND_STREAM,
            self.consumer_group,
            self.consumer_name,
        )

        await self._consumer.ensure_group()
        self._running = True

        logger.info(f"Started command stream consumer: {self.consumer_name}")

        asyncio.create_task(
            self._consume_loop(batch_size, block_ms),
            name="command_stream_consumer",
        )

    async def stop_consumer(self) -> None:
        """Stop the consumer."""
        self._running = False
        if self._consumer:
            self._consumer.stop()

    async def _consume_loop(self, batch_size: int, block_ms: int) -> None:
        """Internal consume loop."""
        while self._running:
            try:
                messages = await self._consumer.read(count=batch_size, block=block_ms)

                for msg in messages:
                    try:
                        await self._process_command(msg)
                        await self._consumer.ack(msg.message_id)
                        self._commands_processed += 1
                    except Exception as e:
                        logger.error(f"Error processing command message: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in command consume loop: {e}")
                await asyncio.sleep(1)

    async def _process_command(self, msg: StreamMessage) -> None:
        """Process a single command message."""
        if not self._on_command:
            return

        data = msg.data
        await self._on_command(
            command_id=UUID(data["command_id"]),
            device_id=UUID(data["device_id"]),
            site_id=UUID(data["site_id"]),
            command_type=data["command_type"],
            command_params=data.get("command_params", {}),
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "running": self._running,
            "consumer_name": self.consumer_name,
            "commands_published": self._commands_published,
            "commands_processed": self._commands_processed,
        }


class AlertStreamService:
    """
    Service for alert evaluation stream.

    Publishes telemetry data for alert evaluation.
    """

    def __init__(self):
        """Initialize the alert stream service."""
        self.producer = StreamProducer(ALERT_STREAM)
        self._alerts_published = 0

    async def publish_for_evaluation(
        self,
        device_id: UUID,
        site_id: UUID,
        metric_name: str,
        metric_value: float,
        timestamp: datetime,
    ) -> str:
        """
        Publish metric for alert evaluation.

        Args:
            device_id: Device ID.
            site_id: Site ID.
            metric_name: Metric name.
            metric_value: Metric value.
            timestamp: Timestamp.

        Returns:
            Message ID.
        """
        data = {
            "device_id": str(device_id),
            "site_id": str(site_id),
            "metric_name": metric_name,
            "metric_value": metric_value,
            "timestamp": timestamp.isoformat(),
        }

        message_id = await self.producer.add(data)
        self._alerts_published += 1
        return message_id

    async def publish_batch_for_evaluation(
        self,
        telemetry_data: List[Dict[str, Any]],
    ) -> List[str]:
        """Publish batch of metrics for alert evaluation."""
        formatted = [
            {
                "device_id": str(item.get("device_id")),
                "site_id": str(item.get("site_id")),
                "metric_name": item.get("metric_name"),
                "metric_value": item.get("metric_value"),
                "timestamp": item.get("timestamp", datetime.now(timezone.utc)).isoformat(),
            }
            for item in telemetry_data
        ]
        return await self.producer.add_batch(formatted)


class NotificationStreamService:
    """
    Service for notification stream.

    Handles notification delivery through Redis streams.
    """

    def __init__(
        self,
        consumer_group: str = "notification_senders",
        consumer_name: Optional[str] = None,
    ):
        """Initialize the notification stream service."""
        self.producer = StreamProducer(NOTIFICATION_STREAM)
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name or f"sender_{datetime.now().timestamp()}"

        self._consumer: Optional[StreamConsumer] = None
        self._running = False
        self._on_notification: Optional[Callable] = None

    async def publish_notification(
        self,
        notification_type: str,
        recipients: List[str],
        subject: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
    ) -> str:
        """
        Publish a notification.

        Args:
            notification_type: Type (email, sms, push, webhook).
            recipients: List of recipients.
            subject: Notification subject.
            body: Notification body.
            data: Additional data.
            priority: Priority level.

        Returns:
            Message ID.
        """
        notification_data = {
            "type": notification_type,
            "recipients": recipients,
            "subject": subject,
            "body": body,
            "data": data or {},
            "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        return await self.producer.add(notification_data)

    def set_notification_handler(self, handler: Callable) -> None:
        """Set handler for sending notifications."""
        self._on_notification = handler

    async def start_consumer(self, batch_size: int = 10, block_ms: int = 5000) -> None:
        """Start consuming notifications."""
        if self._running:
            return

        self._consumer = StreamConsumer(
            NOTIFICATION_STREAM,
            self.consumer_group,
            self.consumer_name,
        )

        await self._consumer.ensure_group()
        self._running = True

        asyncio.create_task(
            self._consume_loop(batch_size, block_ms),
            name="notification_stream_consumer",
        )

    async def stop_consumer(self) -> None:
        """Stop the consumer."""
        self._running = False
        if self._consumer:
            self._consumer.stop()

    async def _consume_loop(self, batch_size: int, block_ms: int) -> None:
        """Internal consume loop."""
        while self._running:
            try:
                messages = await self._consumer.read(count=batch_size, block=block_ms)

                for msg in messages:
                    try:
                        if self._on_notification:
                            await self._on_notification(msg.data)
                        await self._consumer.ack(msg.message_id)
                    except Exception as e:
                        logger.error(f"Error processing notification: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in notification consume loop: {e}")
                await asyncio.sleep(1)


# Service singletons
telemetry_stream_service = TelemetryStreamService()
command_stream_service = CommandStreamService()
alert_stream_service = AlertStreamService()
notification_stream_service = NotificationStreamService()


async def shutdown_all_streams() -> None:
    """Shutdown all stream services."""
    await telemetry_stream_service.stop_consumer()
    await command_stream_service.stop_consumer()
    await notification_stream_service.stop_consumer()
    await RedisStreamManager.close()
