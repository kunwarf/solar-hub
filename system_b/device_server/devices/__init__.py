"""
Device management module.

Provides device state tracking, adapter creation, and device lifecycle management.
"""
from .device_state import DeviceState, DeviceStatus, PollResult
from .adapter_factory import (
    AdapterFactory,
    TCPModbusAdapter,
    TCPCommandAdapter,
)
from .device_manager import DeviceManager

__all__ = [
    "DeviceState",
    "DeviceStatus",
    "PollResult",
    "AdapterFactory",
    "TCPModbusAdapter",
    "TCPCommandAdapter",
    "DeviceManager",
]
