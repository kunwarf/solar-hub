"""
Auto-discovery module for scanning networks and identifying solar devices.

This module provides:
- Network scanning with configurable IP ranges and ports
- Device identification using registered protocols
- Progress tracking for long-running scans
- Background task support for API integration
"""
from .discovery_result import (
    DiscoveryResult,
    DiscoveredDevice,
    ScanProgress,
    ScanStatus,
)
from .network_scanner import NetworkScanner, ScanConfig
from .discovery_service import DiscoveryService

__all__ = [
    "DiscoveryResult",
    "DiscoveredDevice",
    "ScanProgress",
    "ScanStatus",
    "NetworkScanner",
    "ScanConfig",
    "DiscoveryService",
]
