"""
Device domain entities for System B.

Lightweight device information for telemetry collection.
Main device registry is in System A.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from .base import Entity
from .telemetry import DeviceType, ConnectionStatus


@dataclass
class DeviceRegistry(Entity):
    """
    Lightweight device registry for System B.

    Contains only the information needed for telemetry collection.
    Full device details are stored in System A.
    """
    device_id: UUID  # Same as Entity.id but explicit
    site_id: UUID
    organization_id: UUID
    device_type: DeviceType
    serial_number: str

    # Authentication
    auth_token_hash: Optional[str] = None
    token_expires_at: Optional[datetime] = None

    # Connection state
    connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_connected_at: Optional[datetime] = None
    last_disconnected_at: Optional[datetime] = None
    reconnect_count: int = 0

    # Protocol configuration (cached from System A)
    protocol: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None

    # Polling configuration
    polling_interval_seconds: int = 60
    last_polled_at: Optional[datetime] = None
    next_poll_at: Optional[datetime] = None

    # Metadata
    metadata: Optional[Dict[str, Any]] = None

    # Sync tracking
    synced_at: Optional[datetime] = None

    def __post_init__(self):
        # Ensure device_id matches id
        if hasattr(self, 'id'):
            self.device_id = self.id

    def mark_connected(self) -> None:
        """Mark device as connected."""
        self.connection_status = ConnectionStatus.CONNECTED
        self.last_connected_at = datetime.utcnow()
        self.reconnect_count += 1

    def mark_disconnected(self) -> None:
        """Mark device as disconnected."""
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.last_disconnected_at = datetime.utcnow()

    def mark_error(self) -> None:
        """Mark device as in error state."""
        self.connection_status = ConnectionStatus.ERROR

    def is_connected(self) -> bool:
        """Check if device is currently connected."""
        return self.connection_status == ConnectionStatus.CONNECTED

    def needs_polling(self) -> bool:
        """Check if device needs to be polled."""
        if not self.is_connected():
            return False
        if self.next_poll_at is None:
            return True
        return datetime.utcnow() >= self.next_poll_at

    def update_poll_time(self) -> None:
        """Update last polled time and calculate next poll."""
        from datetime import timedelta
        self.last_polled_at = datetime.utcnow()
        self.next_poll_at = self.last_polled_at + timedelta(seconds=self.polling_interval_seconds)


@dataclass
class DeviceSession:
    """
    Active device session for connection management.
    """
    device_id: UUID
    session_id: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    protocol: Optional[str] = None
    client_address: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.utcnow()

    def is_stale(self, timeout_seconds: int = 300) -> bool:
        """Check if session is stale (no activity for timeout period)."""
        from datetime import timedelta
        return datetime.utcnow() - self.last_activity_at > timedelta(seconds=timeout_seconds)
