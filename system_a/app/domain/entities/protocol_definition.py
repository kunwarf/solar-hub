"""
Protocol Definition domain entity and related value objects.

Defines device communication protocols for adapter configuration.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from .base import Entity, utc_now
from .device import DeviceType, ProtocolType


@dataclass(frozen=True)
class IdentificationConfig:
    """
    Configuration for device identification (value object).

    Defines how to identify a device during discovery.
    """
    register: Optional[int] = None          # Modbus register address
    size: int = 1                           # Number of registers to read
    expected_values: List[int] = field(default_factory=list)  # Valid values
    command: Optional[str] = None           # For command-based protocols
    expected_response: Optional[str] = None # Expected response pattern
    timeout: float = 5.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'register': self.register,
            'size': self.size,
            'expected_values': self.expected_values,
            'command': self.command,
            'expected_response': self.expected_response,
            'timeout': self.timeout
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IdentificationConfig':
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            register=data.get('register'),
            size=data.get('size', 1),
            expected_values=data.get('expected_values', []),
            command=data.get('command'),
            expected_response=data.get('expected_response'),
            timeout=data.get('timeout', 5.0)
        )


@dataclass(frozen=True)
class SerialNumberConfig:
    """
    Configuration for extracting device serial number (value object).
    """
    register: Optional[int] = None          # Modbus register address
    size: int = 5                           # Number of registers
    encoding: str = 'ascii'                 # ascii, hex, or raw
    command: Optional[str] = None           # For command-based protocols
    parse_regex: Optional[str] = None       # Regex to extract serial

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'register': self.register,
            'size': self.size,
            'encoding': self.encoding,
            'command': self.command,
            'parse_regex': self.parse_regex
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SerialNumberConfig':
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            register=data.get('register'),
            size=data.get('size', 5),
            encoding=data.get('encoding', 'ascii'),
            command=data.get('command'),
            parse_regex=data.get('parse_regex')
        )


@dataclass(frozen=True)
class PollingConfig:
    """
    Configuration for telemetry polling (value object).
    """
    default_interval: int = 10              # Seconds between polls
    timeout: float = 5.0                    # Poll timeout
    max_consecutive_failures: int = 5       # Failures before offline

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'default_interval': self.default_interval,
            'timeout': self.timeout,
            'max_consecutive_failures': self.max_consecutive_failures
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PollingConfig':
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            default_interval=data.get('default_interval', 10),
            timeout=data.get('timeout', 5.0),
            max_consecutive_failures=data.get('max_consecutive_failures', 5)
        )


@dataclass(frozen=True)
class ModbusConfig:
    """
    Modbus-specific configuration (value object).
    """
    unit_id: int = 1
    timeout: float = 5.0
    retries: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'unit_id': self.unit_id,
            'timeout': self.timeout,
            'retries': self.retries
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModbusConfig':
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            unit_id=data.get('unit_id', 1),
            timeout=data.get('timeout', 5.0),
            retries=data.get('retries', 3)
        )


@dataclass(frozen=True)
class CommandConfig:
    """
    Command-based protocol configuration (value object).
    """
    line_ending: str = '\r\n'
    response_timeout: float = 5.0
    command_delay: float = 0.1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'line_ending': self.line_ending,
            'response_timeout': self.response_timeout,
            'command_delay': self.command_delay
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandConfig':
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            line_ending=data.get('line_ending', '\r\n'),
            response_timeout=data.get('response_timeout', 5.0),
            command_delay=data.get('command_delay', 0.1)
        )


@dataclass
class ProtocolDefinition(Entity):
    """
    Protocol Definition entity.

    Defines how to communicate with a specific type of device,
    including identification, serial number extraction, and polling configuration.
    """
    protocol_id: str = ""                   # Unique string identifier (e.g., "powdrive")
    name: str = ""                          # Human-readable name
    description: Optional[str] = None
    device_type: DeviceType = DeviceType.INVERTER
    protocol_type: ProtocolType = ProtocolType.MODBUS_TCP
    priority: int = 100                     # Lower = higher priority
    manufacturer: Optional[str] = None
    model_pattern: Optional[str] = None     # Regex for model matching
    adapter_class: str = ""                 # Full Python class path
    register_map_file: Optional[str] = None

    # Configuration objects
    identification_config: Optional[IdentificationConfig] = None
    serial_number_config: Optional[SerialNumberConfig] = None
    polling_config: Optional[PollingConfig] = None
    modbus_config: Optional[ModbusConfig] = None
    command_config: Optional[CommandConfig] = None
    default_connection_config: Optional[Dict[str, Any]] = None

    # Metadata
    is_active: bool = True
    is_system: bool = False                 # True for YAML-defined protocols

    version: int = 1

    @classmethod
    def create(
        cls,
        protocol_id: str,
        name: str,
        device_type: DeviceType,
        protocol_type: ProtocolType,
        adapter_class: str,
        description: Optional[str] = None,
        priority: int = 100,
        manufacturer: Optional[str] = None,
        model_pattern: Optional[str] = None,
        register_map_file: Optional[str] = None,
        identification_config: Optional[IdentificationConfig] = None,
        serial_number_config: Optional[SerialNumberConfig] = None,
        polling_config: Optional[PollingConfig] = None,
        modbus_config: Optional[ModbusConfig] = None,
        command_config: Optional[CommandConfig] = None,
        default_connection_config: Optional[Dict[str, Any]] = None,
        is_system: bool = False
    ) -> 'ProtocolDefinition':
        """Factory method to create a new protocol definition."""
        return cls(
            id=uuid4(),
            protocol_id=protocol_id,
            name=name,
            description=description,
            device_type=device_type,
            protocol_type=protocol_type,
            priority=priority,
            manufacturer=manufacturer,
            model_pattern=model_pattern,
            adapter_class=adapter_class,
            register_map_file=register_map_file,
            identification_config=identification_config,
            serial_number_config=serial_number_config,
            polling_config=polling_config,
            modbus_config=modbus_config,
            command_config=command_config,
            default_connection_config=default_connection_config,
            is_active=True,
            is_system=is_system,
            created_at=utc_now(),
            version=1
        )

    def update(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        manufacturer: Optional[str] = None,
        model_pattern: Optional[str] = None,
        adapter_class: Optional[str] = None,
        register_map_file: Optional[str] = None,
        identification_config: Optional[IdentificationConfig] = None,
        serial_number_config: Optional[SerialNumberConfig] = None,
        polling_config: Optional[PollingConfig] = None,
        modbus_config: Optional[ModbusConfig] = None,
        command_config: Optional[CommandConfig] = None,
        default_connection_config: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> None:
        """Update protocol definition fields."""
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if priority is not None:
            self.priority = priority
        if manufacturer is not None:
            self.manufacturer = manufacturer
        if model_pattern is not None:
            self.model_pattern = model_pattern
        if adapter_class is not None:
            self.adapter_class = adapter_class
        if register_map_file is not None:
            self.register_map_file = register_map_file
        if identification_config is not None:
            self.identification_config = identification_config
        if serial_number_config is not None:
            self.serial_number_config = serial_number_config
        if polling_config is not None:
            self.polling_config = polling_config
        if modbus_config is not None:
            self.modbus_config = modbus_config
        if command_config is not None:
            self.command_config = command_config
        if default_connection_config is not None:
            self.default_connection_config = default_connection_config
        if is_active is not None:
            self.is_active = is_active

        self.mark_updated()
        self.version += 1

    def deactivate(self) -> None:
        """Deactivate the protocol definition."""
        self.is_active = False
        self.mark_updated()

    def activate(self) -> None:
        """Activate the protocol definition."""
        self.is_active = True
        self.mark_updated()
