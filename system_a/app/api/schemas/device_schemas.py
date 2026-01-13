"""
Pydantic schemas for device endpoints.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ConnectionConfigSchema(BaseModel):
    """Device connection configuration."""
    protocol: str = Field(..., description="Communication protocol (modbus, mqtt, http)")
    host: Optional[str] = Field(None, description="Host address for network protocols")
    port: Optional[int] = Field(None, description="Port number")
    slave_id: Optional[int] = Field(None, description="Modbus slave ID")
    mqtt_topic: Optional[str] = Field(None, description="MQTT topic for device")
    api_endpoint: Optional[str] = Field(None, description="HTTP API endpoint")
    auth_token: Optional[str] = Field(None, description="Authentication token")
    polling_interval_seconds: int = Field(default=30, ge=5, le=3600)
    timeout_seconds: int = Field(default=10, ge=1, le=60)

    @field_validator('protocol')
    @classmethod
    def validate_protocol(cls, v: str) -> str:
        valid_protocols = ['modbus_tcp', 'modbus_rtu', 'mqtt', 'http', 'custom']
        if v.lower() not in valid_protocols:
            raise ValueError(f'Protocol must be one of: {", ".join(valid_protocols)}')
        return v.lower()


class DeviceMetricsSchema(BaseModel):
    """Real-time device metrics."""
    power_output_kw: Optional[float] = None
    energy_today_kwh: Optional[float] = None
    energy_total_kwh: Optional[float] = None
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    frequency_hz: Optional[float] = None
    temperature_c: Optional[float] = None
    battery_soc_percent: Optional[float] = None
    grid_power_kw: Optional[float] = None
    pv_power_kw: Optional[float] = None
    last_updated: Optional[datetime] = None


class DeviceCreate(BaseModel):
    """Request to create/register a device."""
    site_id: UUID
    device_type: str = Field(..., description="Device type (inverter, meter, battery, etc.)")
    manufacturer: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    serial_number: str = Field(..., min_length=1, max_length=100)
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    connection_config: ConnectionConfigSchema
    metadata: Optional[Dict[str, Any]] = None

    @field_validator('device_type')
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        valid_types = ['inverter', 'meter', 'battery', 'weather_station', 'sensor', 'gateway', 'other']
        if v.lower() not in valid_types:
            raise ValueError(f'Device type must be one of: {", ".join(valid_types)}')
        return v.lower()

    @field_validator('serial_number')
    @classmethod
    def validate_serial(cls, v: str) -> str:
        return v.strip().upper()


class DeviceUpdate(BaseModel):
    """Request to update a device."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    connection_config: Optional[ConnectionConfigSchema] = None
    metadata: Optional[Dict[str, Any]] = None


class DeviceResponse(BaseModel):
    """Device response."""
    id: UUID
    site_id: UUID
    organization_id: UUID
    device_type: str
    manufacturer: str
    model: str
    serial_number: str
    name: str
    description: Optional[str]
    status: str
    protocol: str
    firmware_version: Optional[str]
    last_seen_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DeviceDetailResponse(DeviceResponse):
    """Detailed device response with config and metrics."""
    connection_config: ConnectionConfigSchema
    latest_metrics: Optional[DeviceMetricsSchema]
    metadata: Optional[Dict[str, Any]]
    total_messages_received: int = 0
    total_errors: int = 0
    uptime_percentage: float = 0.0


class DeviceListResponse(BaseModel):
    """Paginated list of devices."""
    items: List[DeviceResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DeviceStatusUpdate(BaseModel):
    """Request to update device status."""
    status: str = Field(..., description="New status")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid_statuses = ['online', 'offline', 'maintenance', 'error']
        if v.lower() not in valid_statuses:
            raise ValueError(f'Status must be one of: {", ".join(valid_statuses)}')
        return v.lower()


class DeviceCommandRequest(BaseModel):
    """Request to send command to device."""
    command: str = Field(..., description="Command to send")
    parameters: Optional[Dict[str, Any]] = None


class DeviceCommandResponse(BaseModel):
    """Response from device command."""
    command_id: UUID
    device_id: UUID
    command: str
    status: str
    sent_at: datetime
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class DeviceSummaryResponse(BaseModel):
    """Device summary for lists."""
    id: UUID
    name: str
    device_type: str
    status: str
    last_seen_at: Optional[datetime]
    current_power_kw: Optional[float] = None
