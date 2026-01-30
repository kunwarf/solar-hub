"""
Protocol definitions and registry for device communication.
"""
from .definitions import (
    DeviceType,
    ProtocolType,
    IdentificationConfig,
    SerialNumberConfig,
    PollingConfig,
    ModbusConfig,
    CommandConfig,
    ProtocolDefinition,
)
from .registry import ProtocolRegistry, get_protocol_registry, set_protocol_registry
from .loader import ProtocolLoader

__all__ = [
    "DeviceType",
    "ProtocolType",
    "IdentificationConfig",
    "SerialNumberConfig",
    "PollingConfig",
    "ModbusConfig",
    "CommandConfig",
    "ProtocolDefinition",
    "ProtocolRegistry",
    "ProtocolLoader",
    "get_protocol_registry",
    "set_protocol_registry",
]
