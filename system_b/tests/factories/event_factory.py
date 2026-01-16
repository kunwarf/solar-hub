"""
Event-related test data factories.
"""
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from uuid import uuid4

import factory


class EventFactory(factory.Factory):
    """
    Factory for creating device event data dictionaries.

    Usage:
        event = EventFactory()
        event = EventFactory(event_type="fault", severity="critical")
    """

    class Meta:
        model = dict

    event_id = factory.LazyFunction(uuid4)
    device_id = factory.LazyFunction(uuid4)
    site_id = factory.LazyFunction(uuid4)
    timestamp = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    event_type = factory.Iterator([
        "connection",
        "disconnection",
        "warning",
        "fault",
        "info",
        "command_result",
    ])
    severity = factory.LazyAttribute(
        lambda o: {
            "connection": "info",
            "disconnection": "warning",
            "warning": "warning",
            "fault": "critical",
            "info": "info",
            "command_result": "info",
        }.get(o.event_type, "info")
    )
    acknowledged = False
    acknowledged_at = None
    acknowledged_by = None

    @factory.lazy_attribute
    def event_code(self) -> str:
        codes_by_type = {
            "connection": "DEVICE_CONNECTED",
            "disconnection": "DEVICE_DISCONNECTED",
            "warning": random.choice([
                "LOW_BATTERY",
                "HIGH_TEMPERATURE",
                "GRID_VOLTAGE_HIGH",
                "GRID_VOLTAGE_LOW",
            ]),
            "fault": random.choice([
                "INVERTER_FAULT",
                "BATTERY_FAULT",
                "GRID_FAULT",
                "OVERCURRENT",
            ]),
            "info": random.choice([
                "FIRMWARE_UPDATED",
                "CONFIG_CHANGED",
                "CALIBRATION_COMPLETE",
            ]),
            "command_result": "COMMAND_EXECUTED",
        }
        return codes_by_type.get(self.event_type, "UNKNOWN")

    @factory.lazy_attribute
    def message(self) -> str:
        messages_by_code = {
            "DEVICE_CONNECTED": "Device connected to system",
            "DEVICE_DISCONNECTED": "Device disconnected from system",
            "LOW_BATTERY": "Battery SOC below threshold",
            "HIGH_TEMPERATURE": "Device temperature exceeds limit",
            "GRID_VOLTAGE_HIGH": "Grid voltage above acceptable range",
            "GRID_VOLTAGE_LOW": "Grid voltage below acceptable range",
            "INVERTER_FAULT": "Inverter reported fault condition",
            "BATTERY_FAULT": "Battery reported fault condition",
            "GRID_FAULT": "Grid fault detected",
            "OVERCURRENT": "Overcurrent protection triggered",
            "FIRMWARE_UPDATED": "Device firmware updated successfully",
            "CONFIG_CHANGED": "Device configuration changed",
            "CALIBRATION_COMPLETE": "Device calibration complete",
            "COMMAND_EXECUTED": "Command executed successfully",
        }
        return messages_by_code.get(self.event_code, "Unknown event")

    @factory.lazy_attribute
    def details(self) -> Dict[str, Any]:
        details_by_code = {
            "LOW_BATTERY": {"soc_pct": random.uniform(5, 20)},
            "HIGH_TEMPERATURE": {"temperature_c": random.uniform(45, 60)},
            "GRID_VOLTAGE_HIGH": {"voltage_v": random.uniform(255, 270)},
            "GRID_VOLTAGE_LOW": {"voltage_v": random.uniform(180, 200)},
            "INVERTER_FAULT": {"fault_code": random.randint(1, 50)},
            "BATTERY_FAULT": {"fault_code": random.randint(1, 20)},
            "OVERCURRENT": {"current_a": random.uniform(60, 80)},
        }
        return details_by_code.get(self.event_code, {})


class ConnectionEventFactory(EventFactory):
    """Factory for device connection events."""

    event_type = "connection"
    event_code = "DEVICE_CONNECTED"
    severity = "info"
    message = "Device connected to system"

    @factory.lazy_attribute
    def details(self) -> Dict[str, Any]:
        return {
            "protocol": "modbus_tcp",
            "address": "192.168.1.100:502",
        }


class DisconnectionEventFactory(EventFactory):
    """Factory for device disconnection events."""

    event_type = "disconnection"
    event_code = "DEVICE_DISCONNECTED"
    severity = "warning"
    message = "Device disconnected from system"

    @factory.lazy_attribute
    def details(self) -> Dict[str, Any]:
        return {
            "reason": random.choice([
                "timeout",
                "connection_reset",
                "device_shutdown",
            ]),
            "last_seen": (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(),
        }


class WarningEventFactory(EventFactory):
    """Factory for warning events."""

    event_type = "warning"
    severity = "warning"


class FaultEventFactory(EventFactory):
    """Factory for fault events."""

    event_type = "fault"
    severity = "critical"


class AcknowledgedEventFactory(EventFactory):
    """Factory for acknowledged events."""

    acknowledged = True
    acknowledged_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    acknowledged_by = factory.LazyFunction(uuid4)


class EventTimelineFactory:
    """
    Factory for creating event timelines.

    Usage:
        timeline = EventTimelineFactory.create_timeline(
            device_id=uuid,
            site_id=uuid,
            duration_hours=24
        )
    """

    @staticmethod
    def create_timeline(
        device_id,
        site_id,
        duration_hours: int = 24,
        events_per_hour: float = 0.5,
    ):
        """
        Create a timeline of events.

        Args:
            device_id: Device ID for all events.
            site_id: Site ID for all events.
            duration_hours: Duration of timeline.
            events_per_hour: Average events per hour.

        Returns:
            List of event dictionaries sorted by timestamp.
        """
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=duration_hours)

        events = []
        total_events = int(duration_hours * events_per_hour)

        for _ in range(total_events):
            # Random timestamp within range
            offset_seconds = random.randint(0, duration_hours * 3600)
            timestamp = start_time + timedelta(seconds=offset_seconds)

            event = EventFactory(
                device_id=device_id,
                site_id=site_id,
                timestamp=timestamp,
            )
            events.append(event)

        # Sort by timestamp
        events.sort(key=lambda e: e["timestamp"])

        return events
