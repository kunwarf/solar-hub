"""
Tools and utilities for System B.

Includes:
- DeviceSimulator: HTTP-based device simulator (sends telemetry via REST API)
- ModbusDeviceSimulator: Modbus TCP slave simulator (responds to server Modbus requests)
"""
from .device_simulator import DeviceSimulator, MultiDeviceSimulator
from .modbus_device_simulator import ModbusDeviceSimulator, MultiModbusSimulator

__all__ = [
    "DeviceSimulator",
    "MultiDeviceSimulator",
    "ModbusDeviceSimulator",
    "MultiModbusSimulator",
]
