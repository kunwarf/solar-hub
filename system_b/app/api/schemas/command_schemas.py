"""
Pydantic schemas for command API endpoints.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


class CommandCreateRequest(BaseModel):
    """Request to create a device command."""
    device_id: UUID
    site_id: UUID
    command_type: str = Field(..., min_length=1, max_length=100)
    command_params: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[datetime] = None
    expires_in_minutes: int = Field(default=60, ge=1, le=1440)
    priority: int = Field(default=5, ge=1, le=10)


class CommandResponse(BaseModel):
    """Response for command information."""
    id: UUID
    device_id: UUID
    site_id: UUID
    command_type: str
    command_params: Optional[Dict[str, Any]] = None
    status: str
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int
    priority: int
    created_at: datetime

    class Config:
        from_attributes = True


class CommandListResponse(BaseModel):
    """Response for command list."""
    commands: List[CommandResponse]
    total: int


class CommandResultRequest(BaseModel):
    """Request to report command result."""
    command_id: UUID
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class CommandStatsResponse(BaseModel):
    """Response for command statistics."""
    by_status: Dict[str, int]
    total_commands: int
    pending_commands: int
    success_rate: float
    active_waiters: int
