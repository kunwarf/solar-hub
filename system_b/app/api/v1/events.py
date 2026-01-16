"""
Event API endpoints for System B.

Handles device events, alerts, and acknowledgments.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db_session
from ..schemas import (
    EventCreateRequest,
    EventResponse,
    EventListResponse,
    EventAcknowledgeRequest,
    EventBulkAcknowledgeRequest,
    EventCountsResponse,
    EventTimelinePoint,
    EventTimelineResponse,
    EventStatsResponse,
    TopErrorDeviceResponse,
)
from ...infrastructure.database.repositories import EventRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
    description="Create a new device event.",
)
async def create_event(
    request: EventCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> EventResponse:
    """
    Create a new device event.
    """
    event_repo = EventRepository(session)

    try:
        event = await event_repo.create(
            device_id=request.device_id,
            site_id=request.site_id,
            event_type=request.event_type,
            severity=request.severity,
            event_code=request.event_code,
            message=request.message,
            details=request.details,
        )

        return EventResponse(
            time=event.time,
            device_id=event.device_id,
            site_id=event.site_id,
            event_type=event.event_type,
            severity=event.severity,
            event_code=event.event_code,
            message=event.message,
            details=event.details,
            acknowledged=event.acknowledged,
            acknowledged_at=event.acknowledged_at,
            acknowledged_by=event.acknowledged_by,
        )
    except Exception as e:
        logger.error(f"Failed to create event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create event",
        )


@router.get(
    "/device/{device_id}",
    response_model=EventListResponse,
    summary="Get device events",
    description="Get events for a device.",
)
async def get_device_events(
    device_id: UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    event_types: Optional[List[str]] = Query(default=None),
    severities: Optional[List[str]] = Query(default=None),
    acknowledged: Optional[bool] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> EventListResponse:
    """
    Get events for a device.
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc) - timedelta(days=7)
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    event_repo = EventRepository(session)

    events = await event_repo.get_device_events(
        device_id=device_id,
        start_time=start_time,
        end_time=end_time,
        event_types=event_types,
        severities=severities,
        acknowledged=acknowledged,
        limit=limit,
        offset=offset,
    )

    total = await event_repo.count_device_events(
        device_id=device_id,
        start_time=start_time,
        end_time=end_time,
        event_types=event_types,
        severities=severities,
        acknowledged=acknowledged,
    )

    return EventListResponse(
        events=[
            EventResponse(
                time=e.time,
                device_id=e.device_id,
                site_id=e.site_id,
                event_type=e.event_type,
                severity=e.severity,
                event_code=e.event_code,
                message=e.message,
                details=e.details,
                acknowledged=e.acknowledged,
                acknowledged_at=e.acknowledged_at,
                acknowledged_by=e.acknowledged_by,
            )
            for e in events
        ],
        total=total,
    )


@router.get(
    "/site/{site_id}",
    response_model=EventListResponse,
    summary="Get site events",
    description="Get events for all devices at a site.",
)
async def get_site_events(
    site_id: UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    device_ids: Optional[List[UUID]] = Query(default=None),
    event_types: Optional[List[str]] = Query(default=None),
    severities: Optional[List[str]] = Query(default=None),
    acknowledged: Optional[bool] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> EventListResponse:
    """
    Get events for a site.
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc) - timedelta(days=7)
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    event_repo = EventRepository(session)

    events = await event_repo.get_site_events(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        device_ids=device_ids,
        event_types=event_types,
        severities=severities,
        acknowledged=acknowledged,
        limit=limit,
        offset=offset,
    )

    total = await event_repo.count_site_events(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        device_ids=device_ids,
        event_types=event_types,
        severities=severities,
        acknowledged=acknowledged,
    )

    return EventListResponse(
        events=[
            EventResponse(
                time=e.time,
                device_id=e.device_id,
                site_id=e.site_id,
                event_type=e.event_type,
                severity=e.severity,
                event_code=e.event_code,
                message=e.message,
                details=e.details,
                acknowledged=e.acknowledged,
                acknowledged_at=e.acknowledged_at,
                acknowledged_by=e.acknowledged_by,
            )
            for e in events
        ],
        total=total,
    )


@router.post(
    "/acknowledge",
    summary="Acknowledge an event",
    description="Acknowledge a specific event.",
)
async def acknowledge_event(
    request: EventAcknowledgeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Acknowledge a specific event.
    """
    event_repo = EventRepository(session)

    success = await event_repo.acknowledge_event(
        device_id=request.device_id,
        event_time=request.event_time,
        event_type=request.event_type,
        acknowledged_by=request.acknowledged_by,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found or already acknowledged",
        )

    return {"success": True}


@router.post(
    "/acknowledge-bulk",
    summary="Acknowledge multiple events",
    description="Acknowledge multiple events matching criteria.",
)
async def acknowledge_events_bulk(
    request: EventBulkAcknowledgeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Acknowledge multiple events.
    """
    event_repo = EventRepository(session)

    count = await event_repo.acknowledge_events_bulk(
        device_id=request.device_id,
        site_id=request.site_id,
        event_types=request.event_types,
        severities=request.severities,
        before_time=request.before_time,
        acknowledged_by=request.acknowledged_by,
    )

    return {"acknowledged_count": count}


@router.get(
    "/counts/{site_id}",
    response_model=EventCountsResponse,
    summary="Get event counts",
    description="Get event counts by type and severity.",
)
async def get_event_counts(
    site_id: UUID,
    hours: int = Query(default=24, ge=1, le=168),
    session: AsyncSession = Depends(get_db_session),
) -> EventCountsResponse:
    """
    Get event counts grouped by type and severity.
    """
    event_repo = EventRepository(session)

    counts = await event_repo.get_event_counts(site_id, hours)

    return EventCountsResponse(counts=counts)


@router.get(
    "/timeline/{site_id}",
    response_model=EventTimelineResponse,
    summary="Get event timeline",
    description="Get event counts over time for charting.",
)
async def get_event_timeline(
    site_id: UUID,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    bucket_interval: str = Query(default="1 hour"),
    session: AsyncSession = Depends(get_db_session),
) -> EventTimelineResponse:
    """
    Get event timeline for charting.
    """
    if start_time is None:
        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    event_repo = EventRepository(session)

    timeline = await event_repo.get_event_timeline(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        bucket_interval=bucket_interval,
    )

    return EventTimelineResponse(
        timeline=[
            EventTimelinePoint(
                bucket=datetime.fromisoformat(t["bucket"]) if isinstance(t["bucket"], str) else t["bucket"],
                info=t.get("info", 0),
                warning=t.get("warning", 0),
                error=t.get("error", 0),
                critical=t.get("critical", 0),
            )
            for t in timeline
        ]
    )


@router.get(
    "/stats/{site_id}",
    response_model=EventStatsResponse,
    summary="Get event statistics",
    description="Get event statistics for a site.",
)
async def get_event_stats(
    site_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> EventStatsResponse:
    """
    Get event statistics for a site.
    """
    event_repo = EventRepository(session)

    stats = await event_repo.get_event_stats(site_id)

    return EventStatsResponse(
        total_events=stats.get("total_events", 0),
        unacknowledged_events=stats.get("unacknowledged_events", 0),
        recent_errors_24h=stats.get("recent_errors_24h", 0),
        first_event=stats.get("first_event"),
        last_event=stats.get("last_event"),
    )


@router.get(
    "/top-errors/{site_id}",
    response_model=List[TopErrorDeviceResponse],
    summary="Get top error devices",
    description="Get devices with most errors.",
)
async def get_top_error_devices(
    site_id: UUID,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=10, le=50),
    session: AsyncSession = Depends(get_db_session),
) -> List[TopErrorDeviceResponse]:
    """
    Get devices with most errors.
    """
    event_repo = EventRepository(session)

    devices = await event_repo.get_top_error_devices(site_id, hours, limit)

    return [
        TopErrorDeviceResponse(
            device_id=d["device_id"],
            error_count=d["error_count"],
            last_error=d["last_error"],
        )
        for d in devices
    ]


@router.get(
    "/unacknowledged/{site_id}",
    response_model=EventListResponse,
    summary="Get unacknowledged events",
    description="Get all unacknowledged events for a site.",
)
async def get_unacknowledged_events(
    site_id: UUID,
    severities: Optional[List[str]] = Query(default=None),
    limit: int = Query(default=100, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> EventListResponse:
    """
    Get unacknowledged events for a site.
    """
    event_repo = EventRepository(session)

    events = await event_repo.get_unacknowledged_events(
        site_id=site_id,
        severities=severities,
        limit=limit,
    )

    return EventListResponse(
        events=[
            EventResponse(
                time=e.time,
                device_id=e.device_id,
                site_id=e.site_id,
                event_type=e.event_type,
                severity=e.severity,
                event_code=e.event_code,
                message=e.message,
                details=e.details,
                acknowledged=e.acknowledged,
                acknowledged_at=e.acknowledged_at,
                acknowledged_by=e.acknowledged_by,
            )
            for e in events
        ],
        total=len(events),
    )


@router.get(
    "/recent-critical/{site_id}",
    response_model=EventListResponse,
    summary="Get recent critical events",
    description="Get recent critical and error events.",
)
async def get_recent_critical_events(
    site_id: UUID,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> EventListResponse:
    """
    Get recent critical and error events.
    """
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    end_time = datetime.now(timezone.utc)

    event_repo = EventRepository(session)

    events = await event_repo.get_site_events(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        severities=["critical", "error"],
        limit=limit,
    )

    return EventListResponse(
        events=[
            EventResponse(
                time=e.time,
                device_id=e.device_id,
                site_id=e.site_id,
                event_type=e.event_type,
                severity=e.severity,
                event_code=e.event_code,
                message=e.message,
                details=e.details,
                acknowledged=e.acknowledged,
                acknowledged_at=e.acknowledged_at,
                acknowledged_by=e.acknowledged_by,
            )
            for e in events
        ],
        total=len(events),
    )
