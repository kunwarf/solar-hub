"""
Device command entities for System B.

Commands represent remote control operations sent to devices.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from .base import Entity


class CommandStatus(str, Enum):
    """Command execution status."""
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class CommandType(str, Enum):
    """Standard command types."""
    SET_POWER_LIMIT = "set_power_limit"
    RESTART = "restart"
    UPDATE_FIRMWARE = "update_firmware"
    SET_TIME = "set_time"
    CLEAR_ERRORS = "clear_errors"
    ENABLE_EXPORT = "enable_export"
    DISABLE_EXPORT = "disable_export"
    SET_BATTERY_MODE = "set_battery_mode"
    SET_CHARGE_LIMIT = "set_charge_limit"
    SET_DISCHARGE_LIMIT = "set_discharge_limit"
    READ_REGISTERS = "read_registers"
    WRITE_REGISTERS = "write_registers"
    CUSTOM = "custom"


@dataclass
class DeviceCommand(Entity):
    """
    A command to be sent to a device.

    Commands are queued and processed by device communication workers.
    """
    device_id: UUID
    site_id: UUID
    command_type: str  # Using str to allow custom command types
    command_params: Optional[Dict[str, Any]] = None

    # Status tracking
    status: CommandStatus = CommandStatus.PENDING

    # Timing
    scheduled_at: Optional[datetime] = None  # For scheduled commands
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # Result
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    # Audit
    created_by: Optional[UUID] = None
    priority: int = 5  # 1=highest, 10=lowest

    def __post_init__(self):
        # Set default expiration if not provided
        if self.expires_at is None:
            self.expires_at = datetime.utcnow() + timedelta(hours=1)

    def mark_sent(self) -> None:
        """Mark command as sent to device."""
        self.status = CommandStatus.SENT
        self.sent_at = datetime.utcnow()

    def mark_acknowledged(self) -> None:
        """Mark command as acknowledged by device."""
        self.status = CommandStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.utcnow()

    def mark_completed(self, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark command as successfully completed."""
        self.status = CommandStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result = result

    def mark_failed(self, error_message: str) -> None:
        """Mark command as failed."""
        self.status = CommandStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message

    def mark_timeout(self) -> None:
        """Mark command as timed out."""
        self.status = CommandStatus.TIMEOUT
        self.completed_at = datetime.utcnow()
        self.error_message = "Command timed out"

    def cancel(self) -> None:
        """Cancel the command."""
        self.status = CommandStatus.CANCELLED
        self.completed_at = datetime.utcnow()

    def can_retry(self) -> bool:
        """Check if command can be retried."""
        return (
            self.status in (CommandStatus.FAILED, CommandStatus.TIMEOUT)
            and self.retry_count < self.max_retries
            and not self.is_expired()
        )

    def retry(self) -> None:
        """Increment retry count and reset status for retry."""
        if not self.can_retry():
            raise ValueError("Command cannot be retried")
        self.retry_count += 1
        self.status = CommandStatus.PENDING
        self.sent_at = None
        self.acknowledged_at = None
        self.completed_at = None
        self.error_message = None

    def is_expired(self) -> bool:
        """Check if command has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_pending(self) -> bool:
        """Check if command is pending execution."""
        return self.status == CommandStatus.PENDING

    def is_completed(self) -> bool:
        """Check if command is in a terminal state."""
        return self.status in (
            CommandStatus.COMPLETED,
            CommandStatus.FAILED,
            CommandStatus.TIMEOUT,
            CommandStatus.CANCELLED
        )

    @classmethod
    def create_power_limit_command(
        cls,
        device_id: UUID,
        site_id: UUID,
        limit_kw: float,
        created_by: Optional[UUID] = None
    ) -> "DeviceCommand":
        """Factory method for power limit command."""
        return cls(
            device_id=device_id,
            site_id=site_id,
            command_type=CommandType.SET_POWER_LIMIT.value,
            command_params={"limit_kw": limit_kw},
            created_by=created_by
        )

    @classmethod
    def create_restart_command(
        cls,
        device_id: UUID,
        site_id: UUID,
        created_by: Optional[UUID] = None
    ) -> "DeviceCommand":
        """Factory method for restart command."""
        return cls(
            device_id=device_id,
            site_id=site_id,
            command_type=CommandType.RESTART.value,
            command_params={},
            created_by=created_by,
            priority=3  # Higher priority for restart
        )


@dataclass
class CommandResult:
    """
    Result of command execution.
    """
    command_id: UUID
    device_id: UUID
    success: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
