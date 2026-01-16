"""
Device event entities for System B.

Events capture significant device occurrences for monitoring and alerting.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID


class EventType(str, Enum):
    """Types of device events."""
    STATUS_CHANGE = "status_change"
    ERROR = "error"
    WARNING = "warning"
    CONNECTION = "connection"
    COMMAND = "command"
    FIRMWARE = "firmware"
    CONFIGURATION = "configuration"


class EventSeverity(str, Enum):
    """Event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DeviceEvent:
    """
    A significant device event.

    Events are stored in TimescaleDB hypertable for time-series analysis.
    """
    time: datetime
    device_id: UUID
    site_id: UUID
    event_type: EventType
    severity: EventSeverity = EventSeverity.INFO
    event_code: Optional[str] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None

    def acknowledge(self, user_id: UUID) -> None:
        """Acknowledge this event."""
        self.acknowledged = True
        self.acknowledged_at = datetime.utcnow()
        self.acknowledged_by = user_id

    @classmethod
    def create_connection_event(
        cls,
        device_id: UUID,
        site_id: UUID,
        connected: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> "DeviceEvent":
        """Factory method for connection events."""
        return cls(
            time=datetime.utcnow(),
            device_id=device_id,
            site_id=site_id,
            event_type=EventType.CONNECTION,
            severity=EventSeverity.INFO,
            event_code="connected" if connected else "disconnected",
            message=f"Device {'connected' if connected else 'disconnected'}",
            details=details
        )

    @classmethod
    def create_error_event(
        cls,
        device_id: UUID,
        site_id: UUID,
        error_code: str,
        message: str,
        severity: EventSeverity = EventSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None
    ) -> "DeviceEvent":
        """Factory method for error events."""
        return cls(
            time=datetime.utcnow(),
            device_id=device_id,
            site_id=site_id,
            event_type=EventType.ERROR,
            severity=severity,
            event_code=error_code,
            message=message,
            details=details
        )

    @classmethod
    def create_status_change_event(
        cls,
        device_id: UUID,
        site_id: UUID,
        old_status: str,
        new_status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> "DeviceEvent":
        """Factory method for status change events."""
        return cls(
            time=datetime.utcnow(),
            device_id=device_id,
            site_id=site_id,
            event_type=EventType.STATUS_CHANGE,
            severity=EventSeverity.INFO,
            event_code=new_status,
            message=f"Status changed from {old_status} to {new_status}",
            details=details or {"old_status": old_status, "new_status": new_status}
        )
