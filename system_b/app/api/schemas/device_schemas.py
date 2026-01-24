"""
Pydantic schemas for device API endpoints.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class DeviceRegisterRequest(BaseModel):
    """Request to register a device (with site_id - for System A sync)."""
    site_id: UUID
    device_type: str
    serial_number: str = Field(..., min_length=1, max_length=100)
    protocol_id: Optional[str] = None
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    capabilities: Optional[List[str]] = None
    device_metadata: Optional[Dict[str, Any]] = None


class DeviceSelfRegisterRequest(BaseModel):
    """
    Request for device self-registration (ESP logger registration).

    This is used when an ESP device connects and registers itself.
    The device starts in 'orphan' state until claimed by a user.
    """
    serial_number: str = Field(..., min_length=1, max_length=100, description="Unique device serial number")
    device_type: str = Field(..., description="Device type: inverter, battery, or meter")
    firmware_version: Optional[str] = Field(None, max_length=50, description="ESP firmware version")
    manufacturer: Optional[str] = Field(None, max_length=100, description="Device manufacturer (e.g., Solis, Growatt)")
    protocol: Optional[str] = Field(None, max_length=50, description="Communication protocol (e.g., modbus_tcp)")
    model: Optional[str] = Field(None, max_length=100, description="Device model")
    capabilities: Optional[Dict[str, Any]] = Field(None, description="Device capabilities metadata")


class DeviceSelfRegisterResponse(BaseModel):
    """Response for device self-registration."""
    status: str = Field(..., description="'success' for both new and reconnecting devices")
    device_id: UUID = Field(..., description="Device UUID (generated for new devices)")
    message: str = Field(..., description="Human-readable message")
    polling_interval_ms: int = Field(default=5000, description="Recommended polling interval in milliseconds")
    is_claimed: bool = Field(default=False, description="Whether device is claimed by a user")

    model_config = ConfigDict(from_attributes=True)


class DeviceClaimRequest(BaseModel):
    """Request to claim an orphan device."""
    owner_id: UUID = Field(..., description="User UUID who is claiming the device")
    site_id: UUID = Field(..., description="Site UUID to attach the device to")
    organization_id: UUID = Field(..., description="Organization UUID")


class DeviceClaimResponse(BaseModel):
    """Response for device claim operation."""
    success: bool
    message: str
    device: Optional["DeviceFullResponse"] = None

    model_config = ConfigDict(from_attributes=True)


class DeviceFullResponse(BaseModel):
    """Full device response with all fields."""
    id: UUID
    serial_number: str
    device_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    protocol: Optional[str] = None
    status: str = "orphan"
    owner_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    connection_status: str = "disconnected"
    last_connected_at: Optional[datetime] = None
    last_telemetry_at: Optional[datetime] = None
    capabilities: Optional[Dict[str, Any]] = None
    polling_interval_seconds: int = 60
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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


# ============================================================================
# Serial Number Schemas
# ============================================================================


class SerialNumberGenerateRequest(BaseModel):
    """Request to generate serial numbers."""
    device_type: str = Field(
        default="inverter",
        description="Device type: inverter, battery, meter, gateway, sensor, weather_station, other"
    )
    hardware_revision: str = Field(
        default="01",
        min_length=1,
        max_length=2,
        description="Hardware revision code (e.g., '01', '02')"
    )
    count: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Number of serial numbers to generate (max 100)"
    )


class SerialNumberGenerateResponse(BaseModel):
    """Response with generated serial numbers."""
    serial_numbers: List[str] = Field(..., description="List of generated serial numbers")
    formatted: List[str] = Field(..., description="Serial numbers formatted with dashes")
    count: int = Field(..., description="Number of serial numbers generated")
    device_type: str = Field(..., description="Device type code")


class SerialNumberValidateRequest(BaseModel):
    """Request to validate a serial number."""
    serial_number: str = Field(..., min_length=1, max_length=20, description="Serial number to validate")


class SerialNumberValidateResponse(BaseModel):
    """Response for serial number validation."""
    serial_number: str = Field(..., description="Normalized serial number (uppercase, no dashes)")
    is_valid: bool = Field(..., description="Whether the serial number is valid")
    error: Optional[str] = Field(None, description="Error message if invalid")
    formatted: Optional[str] = Field(None, description="Formatted serial number with dashes")
    manufacturer_code: Optional[str] = Field(None, description="Manufacturer code (2 chars)")
    hardware_revision: Optional[str] = Field(None, description="Hardware revision (2 chars)")
    device_type_code: Optional[str] = Field(None, description="Device type code (2 chars)")
    device_type: Optional[str] = Field(None, description="Device type name")


class SerialNumberBatchValidateRequest(BaseModel):
    """Request to validate multiple serial numbers."""
    serial_numbers: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of serial numbers to validate"
    )


class SerialNumberBatchValidateResponse(BaseModel):
    """Response for batch serial number validation."""
    results: List[SerialNumberValidateResponse] = Field(..., description="Validation results")
    valid_count: int = Field(..., description="Number of valid serial numbers")
    invalid_count: int = Field(..., description="Number of invalid serial numbers")
