"""
Pydantic schemas for discovery endpoints.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
import ipaddress


class ScanNetworkRequest(BaseModel):
    """Request to start a network discovery scan."""

    network: str = Field(
        ...,
        description="Network in CIDR notation (e.g., '192.168.1.0/24')",
        examples=["192.168.1.0/24", "10.0.0.0/16"],
    )
    ports: List[int] = Field(
        default=[502, 8502],
        description="Ports to scan for Modbus/device connections",
    )
    site_id: Optional[UUID] = Field(
        default=None,
        description="Site ID to associate discovered devices with",
    )
    max_concurrent: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum concurrent connections",
    )
    connect_timeout: float = Field(
        default=2.0,
        ge=0.1,
        le=30.0,
        description="TCP connection timeout in seconds",
    )
    identify_timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Device identification timeout in seconds",
    )
    run_in_background: bool = Field(
        default=False,
        description="Run scan in background and return immediately",
    )

    @field_validator("network")
    @classmethod
    def validate_network(cls, v: str) -> str:
        """Validate network CIDR notation."""
        try:
            network = ipaddress.ip_network(v, strict=False)
            # Limit scan size to prevent abuse
            if network.num_addresses > 65536:
                raise ValueError(
                    f"Network too large: {network.num_addresses} addresses. "
                    f"Maximum allowed is 65536 (/16 network)."
                )
            return str(network)
        except ValueError as e:
            raise ValueError(f"Invalid network specification: {e}")

    @field_validator("ports")
    @classmethod
    def validate_ports(cls, v: List[int]) -> List[int]:
        """Validate port list."""
        if not v:
            return [502, 8502]  # Default Modbus ports
        if len(v) > 10:
            raise ValueError("Maximum 10 ports allowed per scan")
        for port in v:
            if not (1 <= port <= 65535):
                raise ValueError(f"Invalid port number: {port}")
        return list(set(v))  # Deduplicate


class ScanHostRequest(BaseModel):
    """Request to scan a specific host."""

    ip_address: str = Field(
        ...,
        description="IP address to scan",
    )
    ports: List[int] = Field(
        default=[502, 8502],
        description="Ports to check",
    )
    site_id: Optional[UUID] = Field(
        default=None,
        description="Site ID to associate discovered devices with",
    )

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        """Validate IP address."""
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid IP address: {v}")


class DiscoveredDeviceResponse(BaseModel):
    """Response for a discovered device."""

    ip_address: str
    port: int
    protocol_id: Optional[str] = None
    serial_number: Optional[str] = None
    device_type: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    firmware_version: Optional[str] = None
    is_identified: bool = False
    response_time_ms: float = 0.0
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    discovered_at: datetime

    class Config:
        from_attributes = True


class ScanProgressResponse(BaseModel):
    """Response for scan progress."""

    total_hosts: int = 0
    scanned_hosts: int = 0
    responsive_hosts: int = 0
    identified_devices: int = 0
    failed_identifications: int = 0
    progress_percent: float = 0.0
    current_ip: Optional[str] = None
    current_port: Optional[int] = None
    current_status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: Optional[float] = None
    status_message: str = ""
    last_error: Optional[str] = None

    class Config:
        from_attributes = True


class DiscoveryResultResponse(BaseModel):
    """Response for discovery scan results."""

    scan_id: UUID
    network: str
    ports: List[int]
    site_id: Optional[UUID] = None
    devices: List[DiscoveredDeviceResponse]
    progress: ScanProgressResponse
    summary: Dict[str, int]

    class Config:
        from_attributes = True


class ScanStatusResponse(BaseModel):
    """Response for scan status check."""

    scan_id: UUID
    is_running: bool
    is_complete: bool
    progress: ScanProgressResponse
    device_count: int

    class Config:
        from_attributes = True


class StartScanResponse(BaseModel):
    """Response when starting a background scan."""

    scan_id: UUID
    message: str
    status: str = "started"


class DiscoverySummaryResponse(BaseModel):
    """Response with summary of all active scans."""

    active_scans: int
    total_devices_found: int
    scans: List[ScanStatusResponse]
