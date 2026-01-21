"""
Pydantic schemas for device API endpoints.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class DeviceRegisterRequest(BaseModel):
    """Request to register a device."""
    site_id: UUID
    device_type: str
    serial_number: str = Field(..., min_length=1, max_length=100)
    protocol_id: Optional[str] = None
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    device_metadata: Optional[Dict[str, Any]] = None


class DeviceSyncRequest(BaseModel):
    """Request to sync device from System A."""
    site_id: UUID
    device_type: str
    serial_number: str
    protocol_id: Optional[str] = None
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    device_metadata: Optional[Dict[str, Any]] = None


class DeviceUpdateRequest(BaseModel):
    """Request to update device properties."""
    protocol: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    polling_interval_seconds: Optional[int] = Field(default=None, ge=5, le=3600)
    metadata: Optional[Dict[str, Any]] = None


class DeviceResponse(BaseModel):
    """Response for device information."""
    id: UUID
    site_id: UUID
    device_type: str
    serial_number: str
    protocol_id: Optional[str] = None
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    connection_status: str
    last_seen: Optional[datetime] = None
    capabilities: Optional[List[str]] = None
    device_metadata: Optional[Dict[str, Any]] = None
    is_active: bool = True
    created_at: datetime
    newly_registered: bool = True  # True if device was just created, False if already existed

    model_config = ConfigDict(from_attributes=True)


class DeviceSessionResponse(BaseModel):
    """Response for active device session."""
    device_id: UUID
    session_id: Optional[str] = None
    connected_at: Optional[datetime] = None
    ip_address: Optional[str] = None


class DeviceSummaryResponse(BaseModel):
    """Response for device summary."""
    id: UUID
    site_id: UUID
    device_type: str
    serial_number: str
    connection_status: str
    last_seen: Optional[datetime] = None
    is_active: bool = True


class DeviceListResponse(BaseModel):
    """Response for device list."""
    devices: List[DeviceSummaryResponse]
    total: int


class ConnectionStatsResponse(BaseModel):
    """Response for connection statistics."""
    total_devices: int
    online: int
    offline: int
    error: int = 0
    never_connected: int = 0


class DeviceAuthRequest(BaseModel):
    """Request for device authentication."""
    device_id: UUID
    token: str


class DeviceAuthResponse(BaseModel):
    """Response for device authentication."""
    authenticated: bool
    device_id: Optional[UUID] = None
    session_token: Optional[str] = None
    expires_at: Optional[datetime] = None


class DeviceTokenResponse(BaseModel):
    """Response for token generation."""
    device_id: UUID
    token: str
    expires_in_days: int
