"""
Device-related test data factories.
"""
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4

import factory


class DeviceFactory(factory.Factory):
    """
    Factory for creating device data dictionaries.

    Usage:
        device = DeviceFactory()
        device = DeviceFactory(device_type="meter")
        devices = DeviceFactory.build_batch(10)
    """

    class Meta:
        model = dict

    device_id = factory.LazyFunction(uuid4)
    site_id = factory.LazyFunction(uuid4)
    organization_id = factory.LazyFunction(uuid4)
    device_type = factory.Iterator(["inverter", "meter", "battery", "weather_station"])
    serial_number = factory.Sequence(lambda n: f"DEVICE{n:06d}")
    protocol = factory.LazyAttribute(
        lambda o: {
            "inverter": "modbus_tcp",
            "meter": "modbus_tcp",
            "battery": "command",
            "weather_station": "modbus_tcp",
        }.get(o.device_type, "modbus_tcp")
    )
    connection_status = "disconnected"
    polling_interval_seconds = 60

    @factory.lazy_attribute
    def connection_config(self) -> Dict[str, Any]:
        base_port = random.randint(8500, 8600)
        return {
            "host": "127.0.0.1",
            "port": base_port,
            "unit_id": 1,
            "timeout": 10.0,
        }


class DeviceRegistryFactory(factory.Factory):
    """
    Factory for creating device registry entries (database model format).
    """

    class Meta:
        model = dict

    device_id = factory.LazyFunction(uuid4)
    site_id = factory.LazyFunction(uuid4)
    organization_id = factory.LazyFunction(uuid4)
    device_type = "inverter"
    serial_number = factory.Sequence(lambda n: f"INV{n:06d}")
    auth_token_hash = None
    token_expires_at = None
    connection_status = "disconnected"
    last_connected_at = None
    last_disconnected_at = None
    reconnect_count = 0
    protocol = "modbus_tcp"
    connection_config = factory.LazyFunction(
        lambda: {"host": "127.0.0.1", "port": 8502, "unit_id": 1}
    )
    polling_interval_seconds = 60
    last_polled_at = None
    next_poll_at = None
    metadata = factory.LazyFunction(dict)
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = None
    synced_at = None


class ConnectedDeviceFactory(DeviceFactory):
    """Factory for devices in connected state."""

    connection_status = "connected"
    last_connected_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class PowdriveInverterFactory(DeviceFactory):
    """Factory for Powdrive hybrid inverter devices."""

    device_type = "inverter"
    protocol = "modbus_tcp"
    serial_number = factory.Sequence(lambda n: f"PD12K{n:05d}")

    @factory.lazy_attribute
    def metadata(self) -> Dict[str, Any]:
        return {
            "manufacturer": "Powdrive",
            "model": "PD12K",
            "firmware_version": "1.2.3",
            "rated_power_w": 12000,
            "battery_capacity_wh": 25600,
        }


class IAMMeterFactory(DeviceFactory):
    """Factory for IAMMeter devices."""

    device_type = "meter"
    protocol = "modbus_tcp"
    serial_number = factory.Sequence(lambda n: f"IAM{n:06d}")

    @factory.lazy_attribute
    def metadata(self) -> Dict[str, Any]:
        return {
            "manufacturer": "IAMMeter",
            "model": "WEM3080T",
            "phases": 3,
        }


class PytesBatteryFactory(DeviceFactory):
    """Factory for Pytes battery devices."""

    device_type = "battery"
    protocol = "command"
    serial_number = factory.Sequence(lambda n: f"PYTES{n:05d}")

    @factory.lazy_attribute
    def connection_config(self) -> Dict[str, Any]:
        return {
            "host": "127.0.0.1",
            "port": random.randint(8600, 8700),
            "timeout": 10.0,
        }

    @factory.lazy_attribute
    def metadata(self) -> Dict[str, Any]:
        return {
            "manufacturer": "Pytes",
            "model": "E-Box-48100R",
            "capacity_wh": 5120,
            "nominal_voltage": 48.0,
        }
