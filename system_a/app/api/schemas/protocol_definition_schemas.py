"""
Pydantic schemas for protocol definition endpoints.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class IdentificationConfigSchema(BaseModel):
    """Configuration for device identification."""
    register: Optional[int] = Field(None, description="Modbus register address for identification")
    size: int = Field(default=1, ge=1, le=100, description="Number of registers to read")
    expected_values: List[int] = Field(default_factory=list, description="Valid identification values")
    command: Optional[str] = Field(None, description="Command for command-based protocols")
    expected_response: Optional[str] = Field(None, description="Expected response pattern")
    timeout: float = Field(default=5.0, ge=0.1, le=60.0, description="Identification timeout in seconds")


class SerialNumberConfigSchema(BaseModel):
    """Configuration for extracting device serial number."""
    register: Optional[int] = Field(None, description="Modbus register address for serial")
    size: int = Field(default=5, ge=1, le=50, description="Number of registers")
    encoding: str = Field(default="ascii", description="Encoding: ascii, hex, or raw")
    command: Optional[str] = Field(None, description="Command for command-based protocols")
    parse_regex: Optional[str] = Field(None, description="Regex to extract serial number")

    @field_validator('encoding')
    @classmethod
    def validate_encoding(cls, v: str) -> str:
        valid = ['ascii', 'hex', 'raw']
        if v.lower() not in valid:
            raise ValueError(f'Encoding must be one of: {", ".join(valid)}')
        return v.lower()


class PollingConfigSchema(BaseModel):
    """Configuration for telemetry polling."""
    default_interval: int = Field(default=10, ge=1, le=3600, description="Seconds between polls")
    timeout: float = Field(default=5.0, ge=0.1, le=60.0, description="Poll timeout in seconds")
    max_consecutive_failures: int = Field(default=5, ge=1, le=100, description="Failures before offline")


class ModbusConfigSchema(BaseModel):
    """Modbus-specific configuration."""
    unit_id: int = Field(default=1, ge=0, le=255, description="Modbus unit ID")
    timeout: float = Field(default=5.0, ge=0.1, le=60.0, description="Request timeout")
    retries: int = Field(default=3, ge=0, le=10, description="Number of retries")


class CommandConfigSchema(BaseModel):
    """Command-based protocol configuration."""
    line_ending: str = Field(default="\r\n", description="Line ending for commands")
    response_timeout: float = Field(default=5.0, ge=0.1, le=60.0, description="Response timeout")
    command_delay: float = Field(default=0.1, ge=0.0, le=10.0, description="Delay between commands")


class ProtocolDefinitionCreate(BaseModel):
    """Request to create a protocol definition."""
    protocol_id: str = Field(..., min_length=1, max_length=100, description="Unique protocol identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Human-readable name")
    description: Optional[str] = Field(None, max_length=2000)
    device_type: str = Field(..., description="Device type (inverter, meter, battery, etc.)")
    protocol_type: str = Field(..., description="Protocol type (modbus_tcp, modbus_rtu, mqtt, etc.)")
    priority: int = Field(default=100, ge=0, le=1000, description="Priority order (lower = higher priority)")
    manufacturer: Optional[str] = Field(None, max_length=100)
    model_pattern: Optional[str] = Field(None, max_length=200, description="Regex for model matching")
    adapter_class: str = Field(..., min_length=1, max_length=200, description="Python adapter class path")
    register_map_file: Optional[str] = Field(None, max_length=200, description="JSON register map file")
    identification_config: Optional[IdentificationConfigSchema] = None
    serial_number_config: Optional[SerialNumberConfigSchema] = None
    polling_config: Optional[PollingConfigSchema] = None
    modbus_config: Optional[ModbusConfigSchema] = None
    command_config: Optional[CommandConfigSchema] = None
    default_connection_config: Optional[Dict[str, Any]] = None

    @field_validator('device_type')
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        valid_types = ['inverter', 'meter', 'battery', 'weather_station', 'sensor', 'gateway', 'other']
        if v.lower() not in valid_types:
            raise ValueError(f'Device type must be one of: {", ".join(valid_types)}')
        return v.lower()

    @field_validator('protocol_type')
    @classmethod
    def validate_protocol_type(cls, v: str) -> str:
        valid_protocols = ['modbus_tcp', 'modbus_rtu', 'mqtt', 'http', 'https', 'custom']
        if v.lower() not in valid_protocols:
            raise ValueError(f'Protocol type must be one of: {", ".join(valid_protocols)}')
        return v.lower()

    @field_validator('protocol_id')
    @classmethod
    def validate_protocol_id(cls, v: str) -> str:
        # Only allow alphanumeric, underscore, and hyphen
        import re
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError('Protocol ID must start with a letter and contain only alphanumeric, underscore, or hyphen')
        return v.lower()


class ProtocolDefinitionUpdate(BaseModel):
    """Request to update a protocol definition."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    priority: Optional[int] = Field(None, ge=0, le=1000)
    manufacturer: Optional[str] = Field(None, max_length=100)
    model_pattern: Optional[str] = Field(None, max_length=200)
    adapter_class: Optional[str] = Field(None, min_length=1, max_length=200)
    register_map_file: Optional[str] = Field(None, max_length=200)
    identification_config: Optional[IdentificationConfigSchema] = None
    serial_number_config: Optional[SerialNumberConfigSchema] = None
    polling_config: Optional[PollingConfigSchema] = None
    modbus_config: Optional[ModbusConfigSchema] = None
    command_config: Optional[CommandConfigSchema] = None
    default_connection_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProtocolDefinitionResponse(BaseModel):
    """Protocol definition response."""
    id: UUID
    protocol_id: str
    name: str
    description: Optional[str]
    device_type: str
    protocol_type: str
    priority: int
    manufacturer: Optional[str]
    model_pattern: Optional[str]
    adapter_class: str
    register_map_file: Optional[str]
    identification_config: Optional[Dict[str, Any]]
    serial_number_config: Optional[Dict[str, Any]]
    polling_config: Optional[Dict[str, Any]]
    modbus_config: Optional[Dict[str, Any]]
    command_config: Optional[Dict[str, Any]]
    default_connection_config: Optional[Dict[str, Any]]
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProtocolDefinitionListResponse(BaseModel):
    """Paginated list of protocol definitions."""
    items: List[ProtocolDefinitionResponse]
    total: int
    limit: int
    offset: int
