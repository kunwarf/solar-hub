"""
Device state tracking.

Tracks the state of connected devices including connection info,
protocol, polling status, and telemetry history.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID


class DeviceStatus(str, Enum):
    """Device online status."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    INITIALIZING = "initializing"


@dataclass
class PollResult:
    """Result of a telemetry poll."""
    timestamp: datetime
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class DeviceState:
    """
    Complete state for a connected device.

    Tracks all information needed to manage the device including
    connection, protocol, polling, and telemetry status.
    """
    # Identity
    device_id: UUID
    serial_number: str
    protocol_id: str
    device_type: str

    # Connection
    connection_id: UUID
    remote_addr: str

    # Status
    status: DeviceStatus = DeviceStatus.INITIALIZING
    status_message: Optional[str] = None

    # Timestamps
    connected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    identified_at: Optional[datetime] = None
    last_poll: Optional[datetime] = None
    last_successful_poll: Optional[datetime] = None
    last_error: Optional[datetime] = None

    # Polling metrics
    poll_interval: int = 10  # seconds
    consecutive_failures: int = 0
    total_polls: int = 0
    successful_polls: int = 0
    failed_polls: int = 0

    # Last telemetry data
    last_telemetry: Optional[Dict[str, Any]] = None

    # Recent poll history (circular buffer)
    poll_history: List[PollResult] = field(default_factory=list)
    max_history_size: int = 100

    # Device metadata from identification
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    firmware_version: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def record_poll(
        self,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> None:
        """
        Record a poll result.

        Args:
            success: Whether the poll succeeded.
            data: Telemetry data if successful.
            error: Error message if failed.
            duration_ms: Poll duration in milliseconds.
        """
        now = datetime.now(timezone.utc)

        result = PollResult(
            timestamp=now,
            success=success,
            data=data,
            error=error,
            duration_ms=duration_ms,
        )

        # Update counters
        self.total_polls += 1
        self.last_poll = now

        if success:
            self.successful_polls += 1
            self.last_successful_poll = now
            self.consecutive_failures = 0
            self.last_telemetry = data
            self.status = DeviceStatus.ONLINE
            self.status_message = None
        else:
            self.failed_polls += 1
            self.consecutive_failures += 1
            self.last_error = now
            self.status_message = error

        # Add to history (circular buffer)
        self.poll_history.append(result)
        if len(self.poll_history) > self.max_history_size:
            self.poll_history.pop(0)

    def mark_online(self) -> None:
        """Mark device as online."""
        self.status = DeviceStatus.ONLINE
        self.status_message = None

    def mark_offline(self, reason: Optional[str] = None) -> None:
        """Mark device as offline."""
        self.status = DeviceStatus.OFFLINE
        self.status_message = reason or "Device offline"

    def mark_error(self, error: str) -> None:
        """Mark device as having an error."""
        self.status = DeviceStatus.ERROR
        self.status_message = error
        self.last_error = datetime.now(timezone.utc)

    @property
    def is_online(self) -> bool:
        """Check if device is online."""
        return self.status == DeviceStatus.ONLINE

    @property
    def uptime_seconds(self) -> float:
        """Get device uptime in seconds."""
        return (datetime.now(timezone.utc) - self.connected_at).total_seconds()

    @property
    def idle_seconds(self) -> float:
        """Get seconds since last successful poll."""
        if self.last_successful_poll:
            return (
                datetime.now(timezone.utc) - self.last_successful_poll
            ).total_seconds()
        return self.uptime_seconds

    @property
    def success_rate(self) -> float:
        """Get poll success rate as percentage."""
        if self.total_polls == 0:
            return 0.0
        return (self.successful_polls / self.total_polls) * 100

    @property
    def avg_poll_duration_ms(self) -> float:
        """Get average poll duration from recent history."""
        successful = [r for r in self.poll_history if r.success]
        if not successful:
            return 0.0
        return sum(r.duration_ms for r in successful) / len(successful)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "device_id": str(self.device_id),
            "serial_number": self.serial_number,
            "protocol_id": self.protocol_id,
            "device_type": self.device_type,
            "connection_id": str(self.connection_id),
            "remote_addr": self.remote_addr,
            "status": self.status.value,
            "status_message": self.status_message,
            "connected_at": self.connected_at.isoformat(),
            "identified_at": (
                self.identified_at.isoformat() if self.identified_at else None
            ),
            "last_poll": self.last_poll.isoformat() if self.last_poll else None,
            "last_successful_poll": (
                self.last_successful_poll.isoformat()
                if self.last_successful_poll
                else None
            ),
            "last_error": (
                self.last_error.isoformat() if self.last_error else None
            ),
            "poll_interval": self.poll_interval,
            "consecutive_failures": self.consecutive_failures,
            "total_polls": self.total_polls,
            "successful_polls": self.successful_polls,
            "failed_polls": self.failed_polls,
            "success_rate": round(self.success_rate, 2),
            "uptime_seconds": round(self.uptime_seconds, 1),
            "idle_seconds": round(self.idle_seconds, 1),
            "model": self.model,
            "manufacturer": self.manufacturer,
        }

    def __repr__(self) -> str:
        return (
            f"DeviceState("
            f"id={self.device_id}, "
            f"serial={self.serial_number}, "
            f"status={self.status.value})"
        )
