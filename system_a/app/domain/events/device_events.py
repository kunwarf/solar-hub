"""
Device domain events.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from .base import DomainEvent


@dataclass
class DeviceRegistered(DomainEvent):
    """Event raised when a new device is registered."""
    device_id: UUID
    site_id: UUID
    organization_id: UUID
    device_type: str
    serial_number: str

    @property
    def event_type(self) -> str:
        return "device.registered"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id),
            'site_id': str(self.site_id),
            'organization_id': str(self.organization_id),
            'device_type': self.device_type,
            'serial_number': self.serial_number
        }


@dataclass
class DeviceUpdated(DomainEvent):
    """Event raised when device details are updated."""
    device_id: UUID

    @property
    def event_type(self) -> str:
        return "device.updated"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id)
        }


@dataclass
class DeviceConnectionConfigured(DomainEvent):
    """Event raised when device connection is configured."""
    device_id: UUID
    protocol: str

    @property
    def event_type(self) -> str:
        return "device.connection_configured"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id),
            'protocol': self.protocol
        }


@dataclass
class DeviceOnline(DomainEvent):
    """Event raised when device comes online."""
    device_id: UUID

    @property
    def event_type(self) -> str:
        return "device.online"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id)
        }


@dataclass
class DeviceOffline(DomainEvent):
    """Event raised when device goes offline."""
    device_id: UUID

    @property
    def event_type(self) -> str:
        return "device.offline"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id)
        }


@dataclass
class DeviceError(DomainEvent):
    """Event raised when device reports an error."""
    device_id: UUID
    error_message: str
    error_code: Optional[str] = None

    @property
    def event_type(self) -> str:
        return "device.error"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id),
            'error_message': self.error_message,
            'error_code': self.error_code
        }


@dataclass
class DeviceErrorCleared(DomainEvent):
    """Event raised when device error is cleared."""
    device_id: UUID

    @property
    def event_type(self) -> str:
        return "device.error_cleared"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id)
        }


@dataclass
class DeviceMaintenanceStarted(DomainEvent):
    """Event raised when device enters maintenance mode."""
    device_id: UUID
    reason: str
    started_by: UUID

    @property
    def event_type(self) -> str:
        return "device.maintenance_started"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id),
            'reason': self.reason,
            'started_by': str(self.started_by)
        }


@dataclass
class DeviceMaintenanceEnded(DomainEvent):
    """Event raised when device exits maintenance mode."""
    device_id: UUID
    ended_by: UUID

    @property
    def event_type(self) -> str:
        return "device.maintenance_ended"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id),
            'ended_by': str(self.ended_by)
        }


@dataclass
class DeviceDecommissioned(DomainEvent):
    """Event raised when device is permanently decommissioned."""
    device_id: UUID
    site_id: UUID
    reason: str
    decommissioned_by: UUID

    @property
    def event_type(self) -> str:
        return "device.decommissioned"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'device_id': str(self.device_id),
            'site_id': str(self.site_id),
            'reason': self.reason,
            'decommissioned_by': str(self.decommissioned_by)
        }
