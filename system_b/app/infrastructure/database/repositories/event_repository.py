"""
Repository for device events in System B.

Handles event storage and queries in TimescaleDB hypertable.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, delete, func, and_, text, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.telemetry_model import DeviceEventsModel
from ....domain.entities.event import DeviceEvent, EventType, EventSeverity

logger = logging.getLogger(__name__)


class EventRepository:
    """
    Repository for device events.

    Events are stored in a TimescaleDB hypertable for efficient
    time-series queries.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # Create Operations
    # =========================================================================

    async def create(self, event: DeviceEvent) -> DeviceEvent:
        """
        Create a new device event.

        Args:
            event: DeviceEvent entity to create.

        Returns:
            Created DeviceEvent entity.
        """
        model = DeviceEventsModel(
            time=event.time,
            device_id=event.device_id,
            site_id=event.site_id,
            event_type=event.event_type.value if isinstance(event.event_type, EventType) else event.event_type,
            event_code=event.event_code,
            severity=event.severity.value if isinstance(event.severity, EventSeverity) else event.severity,
            message=event.message,
            details=event.details,
            acknowledged=event.acknowledged,
            acknowledged_at=event.acknowledged_at,
            acknowledged_by=event.acknowledged_by,
        )

        self._session.add(model)
        await self._session.flush()

        logger.debug(
            f"Created event for device {event.device_id}: "
            f"{event.event_type} ({event.severity})"
        )

        return event

    async def create_batch(self, events: List[DeviceEvent]) -> int:
        """
        Create multiple events efficiently.

        Args:
            events: List of DeviceEvent entities.

        Returns:
            Number of events created.
        """
        if not events:
            return 0

        values = []
        for event in events:
            values.append({
                "time": event.time,
                "device_id": event.device_id,
                "site_id": event.site_id,
                "event_type": event.event_type.value if isinstance(event.event_type, EventType) else event.event_type,
                "event_code": event.event_code,
                "severity": event.severity.value if isinstance(event.severity, EventSeverity) else event.severity,
                "message": event.message,
                "details": event.details,
                "acknowledged": event.acknowledged,
            })

        # Use upsert to handle duplicate keys (time, device_id, event_type)
        stmt = pg_insert(DeviceEventsModel).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["time", "device_id", "event_type"],
            set_={
                "event_code": stmt.excluded.event_code,
                "message": stmt.excluded.message,
                "details": stmt.excluded.details,
            }
        )

        await self._session.execute(stmt)

        return len(values)

    # =========================================================================
    # Query Operations
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
        conditions = [DeviceEventsModel.device_id == device_id]

        if start_time:
            conditions.append(DeviceEventsModel.time >= start_time)
        if end_time:
            conditions.append(DeviceEventsModel.time <= end_time)
        if event_types:
            conditions.append(
                DeviceEventsModel.event_type.in_([t.value for t in event_types])
            )
        if severities:
            conditions.append(
                DeviceEventsModel.severity.in_([s.value for s in severities])
            )
        if unacknowledged_only:
            conditions.append(DeviceEventsModel.acknowledged == False)

        query = (
            select(DeviceEventsModel)
            .where(and_(*conditions))
            .order_by(desc(DeviceEventsModel.time))
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

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
        conditions = [DeviceEventsModel.site_id == site_id]

        if start_time:
            conditions.append(DeviceEventsModel.time >= start_time)
        if end_time:
            conditions.append(DeviceEventsModel.time <= end_time)
        if event_types:
            conditions.append(
                DeviceEventsModel.event_type.in_([t.value for t in event_types])
            )
        if severities:
            conditions.append(
                DeviceEventsModel.severity.in_([s.value for s in severities])
            )
        if device_ids:
            conditions.append(DeviceEventsModel.device_id.in_(device_ids))
        if unacknowledged_only:
            conditions.append(DeviceEventsModel.acknowledged == False)

        query = (
            select(DeviceEventsModel)
            .where(and_(*conditions))
            .order_by(desc(DeviceEventsModel.time))
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

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
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        conditions = [
            DeviceEventsModel.time >= since,
            DeviceEventsModel.severity.in_([
                EventSeverity.ERROR.value,
                EventSeverity.CRITICAL.value,
            ]),
        ]

        if device_id:
            conditions.append(DeviceEventsModel.device_id == device_id)
        if site_id:
            conditions.append(DeviceEventsModel.site_id == site_id)

        query = (
            select(DeviceEventsModel)
            .where(and_(*conditions))
            .order_by(desc(DeviceEventsModel.time))
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

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
        conditions = [DeviceEventsModel.acknowledged == False]

        if site_id:
            conditions.append(DeviceEventsModel.site_id == site_id)
        if severities:
            conditions.append(
                DeviceEventsModel.severity.in_([s.value for s in severities])
            )

        query = (
            select(DeviceEventsModel)
            .where(and_(*conditions))
            .order_by(
                # Order by severity (critical first), then time
                desc(DeviceEventsModel.severity == EventSeverity.CRITICAL.value),
                desc(DeviceEventsModel.severity == EventSeverity.ERROR.value),
                desc(DeviceEventsModel.time),
            )
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

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
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceEventsModel)
            .where(
                and_(
                    DeviceEventsModel.device_id == device_id,
                    DeviceEventsModel.time == event_time,
                    DeviceEventsModel.event_type == event_type.value,
                )
            )
            .values(
                acknowledged=True,
                acknowledged_at=now,
                acknowledged_by=acknowledged_by,
            )
        )

        result = await self._session.execute(stmt)
        return result.rowcount > 0

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
        now = datetime.now(timezone.utc)

        conditions = [
            DeviceEventsModel.device_id == device_id,
            DeviceEventsModel.acknowledged == False,
        ]

        if event_types:
            conditions.append(
                DeviceEventsModel.event_type.in_([t.value for t in event_types])
            )
        if before_time:
            conditions.append(DeviceEventsModel.time <= before_time)

        stmt = (
            update(DeviceEventsModel)
            .where(and_(*conditions))
            .values(
                acknowledged=True,
                acknowledged_at=now,
                acknowledged_by=acknowledged_by,
            )
        )

        result = await self._session.execute(stmt)
        return result.rowcount

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
        now = datetime.now(timezone.utc)

        conditions = [
            DeviceEventsModel.site_id == site_id,
            DeviceEventsModel.acknowledged == False,
        ]

        if severities:
            conditions.append(
                DeviceEventsModel.severity.in_([s.value for s in severities])
            )

        stmt = (
            update(DeviceEventsModel)
            .where(and_(*conditions))
            .values(
                acknowledged=True,
                acknowledged_at=now,
                acknowledged_by=acknowledged_by,
            )
        )

        result = await self._session.execute(stmt)
        return result.rowcount

    # =========================================================================
    # Aggregation Operations
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
        conditions = []

        if device_id:
            conditions.append(DeviceEventsModel.device_id == device_id)
        if site_id:
            conditions.append(DeviceEventsModel.site_id == site_id)
        if start_time:
            conditions.append(DeviceEventsModel.time >= start_time)
        if end_time:
            conditions.append(DeviceEventsModel.time <= end_time)

        query = select(
            DeviceEventsModel.event_type,
            DeviceEventsModel.severity,
            func.count().label("count"),
        ).group_by(
            DeviceEventsModel.event_type,
            DeviceEventsModel.severity,
        )

        if conditions:
            query = query.where(and_(*conditions))

        result = await self._session.execute(query)
        rows = result.all()

        # Build nested dict
        counts: Dict[str, Dict[str, int]] = {}
        for row in rows:
            if row.event_type not in counts:
                counts[row.event_type] = {}
            counts[row.event_type][row.severity] = row.count

        return counts

    async def get_event_timeline(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "1 hour",
    ) -> List[Dict[str, Any]]:
        """
        Get event counts over time using TimescaleDB time_bucket.

        Args:
            site_id: Site UUID.
            start_time: Start of time range.
            end_time: End of time range.
            bucket_interval: PostgreSQL interval string.

        Returns:
            List of dicts with bucket and counts by severity.
        """
        query = text("""
            SELECT
                time_bucket(:interval, time) AS bucket,
                severity,
                COUNT(*) AS count
            FROM device_events
            WHERE site_id = :site_id
              AND time >= :start_time
              AND time < :end_time
            GROUP BY bucket, severity
            ORDER BY bucket
        """)

        result = await self._session.execute(
            query,
            {
                "interval": bucket_interval,
                "site_id": str(site_id),
                "start_time": start_time,
                "end_time": end_time,
            }
        )

        # Aggregate by bucket
        buckets: Dict[datetime, Dict[str, int]] = {}
        for row in result:
            if row.bucket not in buckets:
                buckets[row.bucket] = {"info": 0, "warning": 0, "error": 0, "critical": 0}
            buckets[row.bucket][row.severity] = row.count

        return [
            {"bucket": bucket, **counts}
            for bucket, counts in sorted(buckets.items())
        ]

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
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = (
            select(
                DeviceEventsModel.device_id,
                func.count().label("error_count"),
                func.max(DeviceEventsModel.time).label("last_error"),
            )
            .where(
                and_(
                    DeviceEventsModel.site_id == site_id,
                    DeviceEventsModel.time >= since,
                    DeviceEventsModel.severity.in_([
                        EventSeverity.ERROR.value,
                        EventSeverity.CRITICAL.value,
                    ]),
                )
            )
            .group_by(DeviceEventsModel.device_id)
            .order_by(desc(func.count()))
            .limit(limit)
        )

        result = await self._session.execute(query)
        rows = result.all()

        return [
            {
                "device_id": row.device_id,
                "error_count": row.error_count,
                "last_error": row.last_error,
            }
            for row in rows
        ]

    # =========================================================================
    # Cleanup Operations
    # =========================================================================

    async def delete_old_events(
        self,
        older_than: datetime,
        device_id: Optional[UUID] = None,
        keep_unacknowledged: bool = True,
    ) -> int:
        """
        Delete old events from the database.

        Args:
            older_than: Delete events before this time.
            device_id: Optional device filter.
            keep_unacknowledged: Don't delete unacknowledged events.

        Returns:
            Number of events deleted.
        """
        conditions = [DeviceEventsModel.time < older_than]

        if device_id:
            conditions.append(DeviceEventsModel.device_id == device_id)
        if keep_unacknowledged:
            conditions.append(DeviceEventsModel.acknowledged == True)

        stmt = delete(DeviceEventsModel).where(and_(*conditions))
        result = await self._session.execute(stmt)

        count = result.rowcount
        if count > 0:
            logger.info(f"Deleted {count} old events")

        return count

    # =========================================================================
    # Statistics
    # =========================================================================

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
        conditions = []

        if site_id:
            conditions.append(DeviceEventsModel.site_id == site_id)
        if device_id:
            conditions.append(DeviceEventsModel.device_id == device_id)

        # Total count
        count_query = select(func.count())
        if conditions:
            count_query = count_query.where(and_(*conditions))
        count_result = await self._session.execute(count_query.select_from(DeviceEventsModel))
        total_count = count_result.scalar() or 0

        # Unacknowledged count
        unack_conditions = conditions + [DeviceEventsModel.acknowledged == False]
        unack_query = select(func.count()).select_from(DeviceEventsModel).where(and_(*unack_conditions))
        unack_result = await self._session.execute(unack_query)
        unack_count = unack_result.scalar() or 0

        # Recent errors (last 24h)
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        error_conditions = conditions + [
            DeviceEventsModel.time >= yesterday,
            DeviceEventsModel.severity.in_([
                EventSeverity.ERROR.value,
                EventSeverity.CRITICAL.value,
            ]),
        ]
        error_query = select(func.count()).select_from(DeviceEventsModel).where(and_(*error_conditions))
        error_result = await self._session.execute(error_query)
        recent_errors = error_result.scalar() or 0

        # Time range
        range_query = select(
            func.min(DeviceEventsModel.time).label("first_event"),
            func.max(DeviceEventsModel.time).label("last_event"),
        )
        if conditions:
            range_query = range_query.where(and_(*conditions))
        range_result = await self._session.execute(range_query.select_from(DeviceEventsModel))
        range_row = range_result.one()

        return {
            "total_events": total_count,
            "unacknowledged_events": unack_count,
            "recent_errors_24h": recent_errors,
            "first_event": range_row.first_event,
            "last_event": range_row.last_event,
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _model_to_entity(self, model: DeviceEventsModel) -> DeviceEvent:
        """Convert SQLAlchemy model to domain entity."""
        return DeviceEvent(
            time=model.time,
            device_id=model.device_id,
            site_id=model.site_id,
            event_type=EventType(model.event_type) if model.event_type else EventType.STATUS_CHANGE,
            severity=EventSeverity(model.severity) if model.severity else EventSeverity.INFO,
            event_code=model.event_code,
            message=model.message,
            details=model.details,
            acknowledged=model.acknowledged,
            acknowledged_at=model.acknowledged_at,
            acknowledged_by=model.acknowledged_by,
        )
