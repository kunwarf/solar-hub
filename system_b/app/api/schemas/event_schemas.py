"""
Pydantic schemas for event API endpoints.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


class EventCreateRequest(BaseModel):
    """Request to create a device event."""
    device_id: UUID
    site_id: UUID
    event_type: str
    severity: str = Field(default="info")
    event_code: Optional[str] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class EventResponse(BaseModel):
    """Response for event information."""
    time: datetime
    device_id: UUID
    site_id: UUID
    event_type: str
    severity: str
    event_code: Optional[str] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Response for event list."""
    events: List[EventResponse]
    total: int


class EventAcknowledgeRequest(BaseModel):
    """Request to acknowledge an event."""
    device_id: UUID
    event_time: datetime
    event_type: str
    acknowledged_by: UUID


class EventBulkAcknowledgeRequest(BaseModel):
    """Request to acknowledge multiple events."""
    device_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    event_types: Optional[List[str]] = None
    severities: Optional[List[str]] = None
    before_time: Optional[datetime] = None
    acknowledged_by: UUID


class EventCountsResponse(BaseModel):
    """Response for event counts."""
    counts: Dict[str, Dict[str, int]]


class EventTimelinePoint(BaseModel):
    """Single point in event timeline."""
    bucket: datetime
    info: int = 0
    warning: int = 0
    error: int = 0
    critical: int = 0


class EventTimelineResponse(BaseModel):
    """Response for event timeline."""
    timeline: List[EventTimelinePoint]


class EventStatsResponse(BaseModel):
    """Response for event statistics."""
    total_events: int
    unacknowledged_events: int
    recent_errors_24h: int
    first_event: Optional[datetime] = None
    last_event: Optional[datetime] = None


class TopErrorDeviceResponse(BaseModel):
    """Response for top error device."""
    device_id: UUID
    error_count: int
    last_error: datetime
