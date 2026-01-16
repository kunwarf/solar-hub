"""
Pydantic schemas for device API endpoints.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    """Request to register a device."""
    device_id: UUID
    site_id: UUID
    organization_id: UUID
    device_type: str
    serial_number: str = Field(..., min_length=1, max_length=100)
    protocol: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    polling_interval_seconds: int = Field(default=60, ge=5, le=3600)
    metadata: Optional[Dict[str, Any]] = None


class DeviceSyncRequest(BaseModel):
    """Request to sync device from System A."""
    id: UUID
    site_id: UUID
    organization_id: UUID
    device_type: str
    serial_number: str
    protocol: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    polling_interval_seconds: int = 60
    metadata: Optional[Dict[str, Any]] = None


class DeviceUpdateRequest(BaseModel):
    """Request to update device properties."""
    protocol: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    polling_interval_seconds: Optional[int] = Field(default=None, ge=5, le=3600)
    metadata: Optional[Dict[str, Any]] = None


class DeviceResponse(BaseModel):
    """Response for device information."""
    device_id: UUID
    site_id: UUID
    organization_id: UUID
    device_type: str
    serial_number: str
    protocol: Optional[str] = None
    connection_status: str
    is_connected: bool
    last_connected_at: Optional[datetime] = None
    last_polled_at: Optional[datetime] = None
    polling_interval_seconds: int
    reconnect_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class DeviceSessionResponse(BaseModel):
    """Response for active device session."""
    session_id: str
    connected_at: datetime
    last_activity_at: datetime
    client_address: Optional[str] = None


class DeviceSummaryResponse(BaseModel):
    """Response for device summary."""
    device_id: UUID
    site_id: UUID
    organization_id: UUID
    device_type: str
    serial_number: str
    protocol: Optional[str] = None
    connection_status: str
    is_connected: bool
    last_connected_at: Optional[datetime] = None
    last_polled_at: Optional[datetime] = None
    polling_interval_seconds: int
    reconnect_count: int
    session: Optional[DeviceSessionResponse] = None


class DeviceListResponse(BaseModel):
    """Response for device list."""
    devices: List[DeviceResponse]
    total: int


class ConnectionStatsResponse(BaseModel):
    """Response for connection statistics."""
    by_status: Dict[str, int]
    by_type: Dict[str, int]
    total_devices: int
    active_sessions: int


class DeviceAuthRequest(BaseModel):
    """Request for device authentication."""
    serial_number: str
    token: str


class DeviceAuthResponse(BaseModel):
    """Response for device authentication."""
    success: bool
    device_id: Optional[UUID] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class DeviceTokenResponse(BaseModel):
    """Response for token generation."""
    device_id: UUID
    token: str
    expires_at: datetime
