"""
Protocol definitions for device communication.

Defines dataclasses for protocol configuration including
identification, polling, and communication settings.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class DeviceType(str, Enum):
    """Supported device types."""
    INVERTER = "inverter"
    METER = "meter"
    BATTERY = "battery"
    LOGGER = "logger"
    UNKNOWN = "unknown"


class ProtocolType(str, Enum):
    """Communication protocol types."""
    MODBUS_TCP = "modbus_tcp"
    MODBUS_RTU = "modbus_rtu"
    COMMAND = "command"  # Text command-based (e.g., Pytes)
    BLE = "ble"  # Bluetooth Low Energy


@dataclass
class IdentificationConfig:
    """
    Configuration for device identification.

    Defines how to identify a device by reading specific registers
    or sending identification commands.
    """
    # For Modbus-based identification
    register: Optional[int] = None
    size: int = 1
    expected_values: List[int] = field(default_factory=list)

    # For command-based identification (e.g., Pytes, JK-BMS)
    command: Optional[str] = None
    expected_response: Optional[str] = None

    # Timeout for identification attempt
    timeout: float = 5.0

    def is_modbus_based(self) -> bool:
        """Check if this identification uses Modbus."""
        return self.register is not None

    def is_command_based(self) -> bool:
        """Check if this identification uses commands."""
        return self.command is not None


@dataclass
class SerialNumberConfig:
    """
    Configuration for reading device serial number.

    Used after successful identification to extract unique device ID.
    """
    # For Modbus-based serial number
    register: Optional[int] = None
    size: int = 8
    encoding: str = "ascii"

    # For command-based serial number
    command: Optional[str] = None
    parse_regex: Optional[str] = None


@dataclass
class PollingConfig:
    """Configuration for telemetry polling."""
    default_interval: int = 10  # seconds
    min_interval: int = 5
    max_interval: int = 300
    timeout: float = 5.0
    max_consecutive_failures: int = 5
    retry_delay: float = 1.0


@dataclass
class ModbusConfig:
    """Modbus-specific configuration."""
    unit_id: int = 1
    timeout: float = 5.0
    retries: int = 3
    retry_delay: float = 0.5

    # For RTU
    baudrate: int = 9600
    parity: str = "N"
    stopbits: int = 1
    bytesize: int = 8


@dataclass
class CommandConfig:
    """Command-based protocol configuration (e.g., Pytes battery)."""
    line_ending: str = "\r\n"
    response_timeout: float = 5.0
    command_delay: float = 0.1  # Delay between commands


@dataclass
class ProtocolDefinition:
    """
    Complete protocol definition for a device type.

    Contains all configuration needed to identify, connect to,
    and poll data from a device.
    """
    # Basic info
    protocol_id: str
    name: str
    device_type: DeviceType
    protocol_type: ProtocolType
    priority: int = 100  # Lower = try first

    # Register map file path (relative to register_maps directory)
    register_map_file: Optional[str] = None

    # Identification
    identification: IdentificationConfig = field(
        default_factory=IdentificationConfig
    )

    # Serial number extraction
    serial_number: SerialNumberConfig = field(
        default_factory=SerialNumberConfig
    )

    # Polling configuration
    polling: PollingConfig = field(default_factory=PollingConfig)

    # Protocol-specific config
    modbus: Optional[ModbusConfig] = None
    command: Optional[CommandConfig] = None

    # Adapter class name (for dynamic loading)
    adapter_class: Optional[str] = None

    # Additional metadata
    manufacturer: Optional[str] = None
    model_pattern: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        """Validate and set defaults."""
        if isinstance(self.device_type, str):
            self.device_type = DeviceType(self.device_type)
        if isinstance(self.protocol_type, str):
            self.protocol_type = ProtocolType(self.protocol_type)

        # Ensure appropriate config exists for protocol type
        if self.protocol_type in (ProtocolType.MODBUS_TCP, ProtocolType.MODBUS_RTU):
            if self.modbus is None:
                self.modbus = ModbusConfig()
        elif self.protocol_type == ProtocolType.COMMAND:
            if self.command is None:
                self.command = CommandConfig()

    def get_register_map_path(self, base_path: Path) -> Optional[Path]:
        """Get full path to register map file."""
        if self.register_map_file:
            return base_path / self.register_map_file
        return None

    def matches_identification(self, value: int) -> bool:
        """Check if a value matches expected identification values."""
        return value in self.identification.expected_values

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "protocol_id": self.protocol_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "protocol_type": self.protocol_type.value,
            "priority": self.priority,
            "register_map_file": self.register_map_file,
            "manufacturer": self.manufacturer,
            "model_pattern": self.model_pattern,
            "description": self.description,
        }
