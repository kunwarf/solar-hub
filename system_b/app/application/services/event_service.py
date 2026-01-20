"""
Event Service for System B.

Handles device event creation, queries, and acknowledgment.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from ...domain.entities.event import DeviceEvent, EventType, EventSeverity
from ...infrastructure.database.repositories import EventRepository

logger = logging.getLogger(__name__)


class EventService:
    """
    Application service for device event management.

    Coordinates event creation, queries, acknowledgment, and analytics.
    """

    def __init__(
        self,
        event_repo: EventRepository,
    ):
        self._event_repo = event_repo

    # =========================================================================
    # Event Creation
    # =========================================================================

    async def create_event(
        self,
        device_id: UUID,
        site_id: UUID,
        event_type: EventType,
        severity: EventSeverity = EventSeverity.INFO,
        event_code: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> DeviceEvent:
        """
        Create a new device event.

        Args:
            device_id: Device UUID.
            site_id: Site UUID.
            event_type: Type of event.
            severity: Event severity level.
            event_code: Optional event code.
            message: Optional event message.
            details: Optional event details.

        Returns:
            Created DeviceEvent entity.
        """
        event = DeviceEvent(
            time=datetime.now(timezone.utc),
            device_id=device_id,
            site_id=site_id,
            event_type=event_type,
            severity=severity,
            event_code=event_code,
            message=message,
            details=details,
        )

        created = await self._event_repo.create(event)

        logger.info(
            f"Created event for device {device_id}: "
            f"{event_type.value} ({severity.value})"
        )

        return created

    async def create_connection_event(
        self,
        device_id: UUID,
        site_id: UUID,
        connected: bool,
        details: Optional[Dict[str, Any]] = None,
    ) -> DeviceEvent:
        """
        Create a connection/disconnection event.

        Args:
            device_id: Device UUID.
            site_id: Site UUID.
            connected: True if connected, False if disconnected.
            details: Optional connection details.

        Returns:
            Created DeviceEvent entity.
        """
        event = DeviceEvent.create_connection_event(
            device_id=device_id,
            site_id=site_id,
            connected=connected,
            details=details,
        )
        return await self._event_repo.create(event)

    async def create_error_event(
        self,
        device_id: UUID,
        site_id: UUID,
        error_code: str,
        message: str,
        severity: EventSeverity = EventSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
    ) -> DeviceEvent:
        """
        Create an error event.

        Args:
            device_id: Device UUID.
            site_id: Site UUID.
            error_code: Error code.
            message: Error message.
            severity: Event severity level.
            details: Optional error details.

        Returns:
            Created DeviceEvent entity.
        """
        event = DeviceEvent.create_error_event(
            device_id=device_id,
            site_id=site_id,
            error_code=error_code,
            message=message,
            severity=severity,
            details=details,
        )
        return await self._event_repo.create(event)

    async def create_status_change_event(
        self,
        device_id: UUID,
        site_id: UUID,
        old_status: str,
        new_status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> DeviceEvent:
        """
        Create a status change event.

        Args:
            device_id: Device UUID.
            site_id: Site UUID.
            old_status: Previous status.
            new_status: New status.
            details: Optional status change details.

        Returns:
            Created DeviceEvent entity.
        """
        event = DeviceEvent.create_status_change_event(
            device_id=device_id,
            site_id=site_id,
            old_status=old_status,
            new_status=new_status,
            details=details,
        )
        return await self._event_repo.create(event)

    async def create_batch(self, events: List[DeviceEvent]) -> int:
        """
        Create multiple events efficiently.

        Args:
            events: List of DeviceEvent entities.

        Returns:
            Number of events created.
        """
        return await self._event_repo.create_batch(events)

    # =========================================================================
    # Event Queries
    # =========================================================================

    async def get_device_events(
        self,
        device_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[EventType]] = None,
        severities: Optional[List[EventSeverity]] = None,
        unacknowledged_only: bool = False,
        limit: int = 100,
    ) -> List[DeviceEvent]:
        """
        Get events for a device with filters.

        Args:
            device_id: Device UUID.
            start_time: Filter from this time.
            end_time: Filter to this time.
            event_types: Filter by event types.
            severities: Filter by severities.
            unacknowledged_only: Only return unacknowledged events.
            limit: Maximum events to return.

        Returns:
            List of DeviceEvent entities.
        """
        return await self._event_repo.get_device_events(
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            event_types=event_types,
            severities=severities,
            unacknowledged_only=unacknowledged_only,
            limit=limit,
        )

    async def get_site_events(
        self,
        site_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[EventType]] = None,
        severities: Optional[List[EventSeverity]] = None,
        device_ids: Optional[List[UUID]] = None,
        unacknowledged_only: bool = False,
        limit: int = 500,
    ) -> List[DeviceEvent]:
        """
        Get events for all devices at a site.

        Args:
            site_id: Site UUID.
            start_time: Filter from this time.
            end_time: Filter to this time.
            event_types: Filter by event types.
            severities: Filter by severities.
            device_ids: Filter by specific devices.
            unacknowledged_only: Only return unacknowledged events.
            limit: Maximum events to return.

        Returns:
            List of DeviceEvent entities.
        """
        return await self._event_repo.get_site_events(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            event_types=event_types,
            severities=severities,
            device_ids=device_ids,
            unacknowledged_only=unacknowledged_only,
            limit=limit,
        )

    async def get_recent_errors(
        self,
        device_id: Optional[UUID] = None,
        site_id: Optional[UUID] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> List[DeviceEvent]:
        """
        Get recent error events.

        Args:
            device_id: Optional device filter.
            site_id: Optional site filter.
            hours: Lookback period in hours.
            limit: Maximum events to return.

        Returns:
            List of error DeviceEvent entities.
        """
        return await self._event_repo.get_recent_errors(
            device_id=device_id,
            site_id=site_id,
            hours=hours,
            limit=limit,
        )

    async def get_unacknowledged_events(
        self,
        site_id: Optional[UUID] = None,
        severities: Optional[List[EventSeverity]] = None,
        limit: int = 100,
    ) -> List[DeviceEvent]:
        """
        Get unacknowledged events requiring attention.

        Args:
            site_id: Optional site filter.
            severities: Filter by severities.
            limit: Maximum events to return.

        Returns:
            List of unacknowledged DeviceEvent entities.
        """
        return await self._event_repo.get_unacknowledged_events(
            site_id=site_id,
            severities=severities,
            limit=limit,
        )

    # =========================================================================
    # Acknowledgment Operations
    # =========================================================================

    async def acknowledge_event(
        self,
        device_id: UUID,
        event_time: datetime,
        event_type: EventType,
        acknowledged_by: UUID,
    ) -> bool:
        """
        Acknowledge an event.

        Args:
            device_id: Device UUID.
            event_time: Event timestamp.
            event_type: Event type.
            acknowledged_by: User UUID acknowledging the event.

        Returns:
            True if acknowledged, False if not found.
        """
        result = await self._event_repo.acknowledge_event(
            device_id=device_id,
            event_time=event_time,
            event_type=event_type,
            acknowledged_by=acknowledged_by,
        )

        if result:
            logger.info(
                f"Event acknowledged: device={device_id}, "
                f"type={event_type.value}, by={acknowledged_by}"
            )

        return result

    async def acknowledge_device_events(
        self,
        device_id: UUID,
        acknowledged_by: UUID,
        event_types: Optional[List[EventType]] = None,
        before_time: Optional[datetime] = None,
    ) -> int:
        """
        Acknowledge all events for a device.

        Args:
            device_id: Device UUID.
            acknowledged_by: User UUID acknowledging.
            event_types: Optional filter by event types.
            before_time: Optional time cutoff.

        Returns:
            Number of events acknowledged.
        """
        count = await self._event_repo.acknowledge_device_events(
            device_id=device_id,
            acknowledged_by=acknowledged_by,
            event_types=event_types,
            before_time=before_time,
        )

        if count > 0:
            logger.info(f"Acknowledged {count} events for device {device_id}")

        return count

    async def acknowledge_site_events(
        self,
        site_id: UUID,
        acknowledged_by: UUID,
        severities: Optional[List[EventSeverity]] = None,
    ) -> int:
        """
        Acknowledge all events for a site.

        Args:
            site_id: Site UUID.
            acknowledged_by: User UUID acknowledging.
            severities: Optional filter by severities.

        Returns:
            Number of events acknowledged.
        """
        count = await self._event_repo.acknowledge_site_events(
            site_id=site_id,
            acknowledged_by=acknowledged_by,
            severities=severities,
        )

        if count > 0:
            logger.info(f"Acknowledged {count} events for site {site_id}")

        return count

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_event_counts(
        self,
        device_id: Optional[UUID] = None,
        site_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, int]]:
        """
        Get event counts by type and severity.

        Args:
            device_id: Optional device filter.
            site_id: Optional site filter.
            start_time: Filter from this time.
            end_time: Filter to this time.

        Returns:
            Nested dict: {event_type: {severity: count}}.
        """
        return await self._event_repo.get_event_counts(
            device_id=device_id,
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

    async def get_event_timeline(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "1 hour",
    ) -> List[Dict[str, Any]]:
        """
        Get event counts over time.

        Args:
            site_id: Site UUID.
            start_time: Start of time range.
            end_time: End of time range.
            bucket_interval: PostgreSQL interval string.

        Returns:
            List of dicts with bucket and counts by severity.
        """
        return await self._event_repo.get_event_timeline(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            bucket_interval=bucket_interval,
        )

    async def get_top_error_devices(
        self,
        site_id: UUID,
        hours: int = 24,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get devices with the most errors.

        Args:
            site_id: Site UUID.
            hours: Lookback period in hours.
            limit: Maximum devices to return.

        Returns:
            List of dicts with device_id and error counts.
        """
        return await self._event_repo.get_top_error_devices(
            site_id=site_id,
            hours=hours,
            limit=limit,
        )

    async def get_event_stats(
        self,
        site_id: Optional[UUID] = None,
        device_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get event statistics.

        Args:
            site_id: Optional site filter.
            device_id: Optional device filter.

        Returns:
            Dict with event statistics.
        """
        return await self._event_repo.get_event_stats(
            site_id=site_id,
            device_id=device_id,
        )

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def cleanup_old_events(
        self,
        retention_days: int = 90,
        device_id: Optional[UUID] = None,
        keep_unacknowledged: bool = True,
    ) -> int:
        """
        Clean up old events.

        Args:
            retention_days: Delete events older than this.
            device_id: Optional device filter.
            keep_unacknowledged: Don't delete unacknowledged events.

        Returns:
            Number of events deleted.
        """
        older_than = datetime.now(timezone.utc) - timedelta(days=retention_days)

        count = await self._event_repo.delete_old_events(
            older_than=older_than,
            device_id=device_id,
            keep_unacknowledged=keep_unacknowledged,
        )

        if count > 0:
            logger.info(f"Cleaned up {count} old events")

        return count
