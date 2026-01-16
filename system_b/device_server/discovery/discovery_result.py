"""
Data classes for discovery results.

Provides structured data types for representing discovered devices,
scan progress, and overall discovery results.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class ScanStatus(str, Enum):
    """Status of a discovery scan."""
    PENDING = "pending"
    SCANNING = "scanning"
    IDENTIFYING = "identifying"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class DiscoveredDevice:
    """Information about a discovered device."""

    # Discovery info
    ip_address: str
    port: int

    # Identification results (if successfully identified)
    protocol_id: Optional[str] = None
    serial_number: Optional[str] = None
    device_type: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    firmware_version: Optional[str] = None

    # Connection info
    is_identified: bool = False
    response_time_ms: float = 0.0

    # Extra data from identification
    extra_data: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "ip_address": self.ip_address,
            "port": self.port,
            "protocol_id": self.protocol_id,
            "serial_number": self.serial_number,
            "device_type": self.device_type,
            "model": self.model,
            "manufacturer": self.manufacturer,
            "firmware_version": self.firmware_version,
            "is_identified": self.is_identified,
            "response_time_ms": self.response_time_ms,
            "extra_data": self.extra_data,
            "discovered_at": self.discovered_at.isoformat(),
        }


@dataclass
class ScanProgress:
    """Progress tracking for a discovery scan."""

    # Progress counters
    total_hosts: int = 0
    scanned_hosts: int = 0
    responsive_hosts: int = 0
    identified_devices: int = 0
    failed_identifications: int = 0

    # Current operation
    current_ip: Optional[str] = None
    current_port: Optional[int] = None
    current_status: ScanStatus = ScanStatus.PENDING

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_remaining_seconds: Optional[float] = None

    # Messages
    status_message: str = ""
    last_error: Optional[str] = None

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_hosts == 0:
            return 0.0
        return (self.scanned_hosts / self.total_hosts) * 100

    @property
    def is_running(self) -> bool:
        """Check if scan is currently running."""
        return self.current_status in (ScanStatus.SCANNING, ScanStatus.IDENTIFYING)

    @property
    def is_complete(self) -> bool:
        """Check if scan is complete."""
        return self.current_status in (
            ScanStatus.COMPLETED,
            ScanStatus.CANCELLED,
            ScanStatus.FAILED,
        )

    @property
    def elapsed_seconds(self) -> float:
        """Calculate elapsed time in seconds."""
        if not self.started_at:
            return 0.0
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_hosts": self.total_hosts,
            "scanned_hosts": self.scanned_hosts,
            "responsive_hosts": self.responsive_hosts,
            "identified_devices": self.identified_devices,
            "failed_identifications": self.failed_identifications,
            "progress_percent": round(self.progress_percent, 1),
            "current_ip": self.current_ip,
            "current_port": self.current_port,
            "current_status": self.current_status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "estimated_remaining_seconds": (
                round(self.estimated_remaining_seconds, 1)
                if self.estimated_remaining_seconds else None
            ),
            "status_message": self.status_message,
            "last_error": self.last_error,
        }


@dataclass
class DiscoveryResult:
    """Complete result of a discovery scan."""

    # Scan identification
    scan_id: UUID = field(default_factory=uuid4)

    # Scan parameters
    network: str = ""
    ports: List[int] = field(default_factory=list)
    site_id: Optional[UUID] = None

    # Results
    devices: List[DiscoveredDevice] = field(default_factory=list)
    progress: ScanProgress = field(default_factory=ScanProgress)

    @property
    def identified_devices(self) -> List[DiscoveredDevice]:
        """Get only successfully identified devices."""
        return [d for d in self.devices if d.is_identified]

    @property
    def unidentified_hosts(self) -> List[DiscoveredDevice]:
        """Get responsive but unidentified hosts."""
        return [d for d in self.devices if not d.is_identified]

    def add_device(self, device: DiscoveredDevice) -> None:
        """Add a discovered device to results."""
        self.devices.append(device)
        if device.is_identified:
            self.progress.identified_devices += 1
        else:
            self.progress.failed_identifications += 1

    def get_by_serial(self, serial_number: str) -> Optional[DiscoveredDevice]:
        """Find device by serial number."""
        for device in self.devices:
            if device.serial_number == serial_number:
                return device
        return None

    def get_by_ip(self, ip_address: str) -> List[DiscoveredDevice]:
        """Find devices by IP address (may be multiple on different ports)."""
        return [d for d in self.devices if d.ip_address == ip_address]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scan_id": str(self.scan_id),
            "network": self.network,
            "ports": self.ports,
            "site_id": str(self.site_id) if self.site_id else None,
            "devices": [d.to_dict() for d in self.devices],
            "progress": self.progress.to_dict(),
            "summary": {
                "total_devices": len(self.devices),
                "identified_devices": len(self.identified_devices),
                "unidentified_hosts": len(self.unidentified_hosts),
            },
        }
