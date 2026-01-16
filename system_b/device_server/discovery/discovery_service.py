"""
Discovery service for orchestrating network scans and device identification.

Coordinates the network scanner and device prober to discover and
identify solar devices on local networks.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set
from uuid import UUID, uuid4

from .discovery_result import (
    DiscoveredDevice,
    DiscoveryResult,
    ScanProgress,
    ScanStatus,
)
from .network_scanner import NetworkScanner, ScanConfig, ScanResult
from ..connection.tcp_connection import TCPConnection
from ..identification.prober import DeviceProber
from ..protocols.registry import ProtocolRegistry

logger = logging.getLogger(__name__)


class DiscoveryService:
    """
    Service for discovering and identifying solar devices on networks.

    Coordinates network scanning and device identification:
    1. Scans IP ranges for responsive hosts
    2. Attempts to identify devices using registered protocols
    3. Tracks progress and results for API integration

    Supports:
    - Background scanning with progress callbacks
    - Deduplication by serial number
    - Configurable concurrency and timeouts
    """

    def __init__(
        self,
        protocol_registry: ProtocolRegistry,
        prober: Optional[DeviceProber] = None,
    ):
        """
        Initialize the discovery service.

        Args:
            protocol_registry: Registry of device protocols.
            prober: Device prober for identification.
                Created from registry if not provided.
        """
        self.registry = protocol_registry
        self.prober = prober or DeviceProber(protocol_registry)

        # Active scans
        self._active_scans: Dict[UUID, DiscoveryResult] = {}
        self._scan_tasks: Dict[UUID, asyncio.Task] = {}

        # Known devices (for deduplication across scans)
        self._known_serials: Set[str] = set()

    async def scan_network(
        self,
        network: str,
        ports: Optional[List[int]] = None,
        site_id: Optional[UUID] = None,
        max_concurrent: int = 50,
        connect_timeout: float = 2.0,
        identify_timeout: float = 10.0,
        progress_callback: Optional[Callable[[ScanProgress], None]] = None,
        register_callback: Optional[Callable[[DiscoveredDevice], None]] = None,
    ) -> DiscoveryResult:
        """
        Scan a network range and identify devices.

        Args:
            network: Network in CIDR notation (e.g., "192.168.1.0/24").
            ports: Ports to scan. Defaults to [502, 8502].
            site_id: Optional site ID for registered devices.
            max_concurrent: Maximum concurrent connections.
            connect_timeout: TCP connection timeout in seconds.
            identify_timeout: Device identification timeout in seconds.
            progress_callback: Called with progress updates.
            register_callback: Called when a device is identified.

        Returns:
            DiscoveryResult with all discovered devices.
        """
        # Create scan result
        result = DiscoveryResult(
            scan_id=uuid4(),
            network=network,
            ports=ports or [502, 8502],
            site_id=site_id,
        )

        # Track this scan
        self._active_scans[result.scan_id] = result

        # Create scanner config
        config = ScanConfig(
            network=network,
            ports=result.ports,
            max_concurrent=max_concurrent,
            connect_timeout=connect_timeout,
        )
        scanner = NetworkScanner(config)

        # Initialize progress
        result.progress = ScanProgress(
            current_status=ScanStatus.SCANNING,
            started_at=datetime.now(timezone.utc),
            status_message="Starting network scan...",
        )

        # Calculate total hosts for progress
        try:
            import ipaddress
            net = ipaddress.ip_network(network, strict=False)
            result.progress.total_hosts = len(list(net.hosts())) * len(result.ports)
        except ValueError:
            result.progress.total_hosts = 0

        if progress_callback:
            progress_callback(result.progress)

        try:
            # Phase 1: Network scan
            logger.info(f"Starting discovery scan {result.scan_id} on {network}")
            responsive_hosts: List[ScanResult] = []

            def update_scan_progress(scanned: int, total: int, ip: str, port: int):
                result.progress.scanned_hosts = scanned
                result.progress.current_ip = ip
                result.progress.current_port = port
                result.progress.status_message = f"Scanning {ip}:{port}"

                # Estimate remaining time
                if scanned > 0:
                    elapsed = result.progress.elapsed_seconds
                    rate = scanned / elapsed if elapsed > 0 else 1
                    remaining = (total - scanned) / rate if rate > 0 else 0
                    result.progress.estimated_remaining_seconds = remaining

                if progress_callback:
                    progress_callback(result.progress)

            async for scan_result in scanner.scan(progress_callback=update_scan_progress):
                responsive_hosts.append(scan_result)
                result.progress.responsive_hosts += 1
                logger.debug(
                    f"Found responsive host: {scan_result.ip}:{scan_result.port} "
                    f"(response: {scan_result.response_time_ms:.1f}ms)"
                )

            logger.info(
                f"Scan found {len(responsive_hosts)} responsive hosts"
            )

            # Phase 2: Device identification
            result.progress.current_status = ScanStatus.IDENTIFYING
            result.progress.status_message = "Identifying devices..."
            if progress_callback:
                progress_callback(result.progress)

            # Process responsive hosts with concurrency limit
            semaphore = asyncio.Semaphore(min(max_concurrent, 10))

            async def identify_host(scan_result: ScanResult) -> Optional[DiscoveredDevice]:
                async with semaphore:
                    return await self._identify_device(
                        scan_result.ip,
                        scan_result.port,
                        scan_result.response_time_ms,
                        identify_timeout,
                    )

            # Create identification tasks
            tasks = [
                asyncio.create_task(identify_host(sr))
                for sr in responsive_hosts
            ]

            # Process results
            for task in asyncio.as_completed(tasks):
                try:
                    device = await task
                    if device:
                        # Check for duplicate serial numbers
                        if device.serial_number:
                            if device.serial_number in self._known_serials:
                                logger.debug(
                                    f"Skipping duplicate device: {device.serial_number}"
                                )
                                continue
                            self._known_serials.add(device.serial_number)

                        result.add_device(device)

                        result.progress.status_message = (
                            f"Identified: {device.protocol_id or 'unknown'} "
                            f"at {device.ip_address}:{device.port}"
                        )

                        if progress_callback:
                            progress_callback(result.progress)

                        if register_callback and device.is_identified:
                            register_callback(device)

                except Exception as e:
                    logger.debug(f"Identification task error: {e}")

            # Complete
            result.progress.current_status = ScanStatus.COMPLETED
            result.progress.completed_at = datetime.now(timezone.utc)
            result.progress.status_message = (
                f"Completed: Found {result.progress.identified_devices} devices"
            )

            logger.info(
                f"Discovery scan {result.scan_id} completed: "
                f"{result.progress.identified_devices} devices identified, "
                f"{result.progress.failed_identifications} unidentified hosts"
            )

        except asyncio.CancelledError:
            result.progress.current_status = ScanStatus.CANCELLED
            result.progress.completed_at = datetime.now(timezone.utc)
            result.progress.status_message = "Scan cancelled"
            logger.info(f"Discovery scan {result.scan_id} cancelled")
            raise

        except Exception as e:
            result.progress.current_status = ScanStatus.FAILED
            result.progress.completed_at = datetime.now(timezone.utc)
            result.progress.last_error = str(e)
            result.progress.status_message = f"Scan failed: {e}"
            logger.error(f"Discovery scan {result.scan_id} failed: {e}")

        finally:
            if progress_callback:
                progress_callback(result.progress)

        return result

    async def _identify_device(
        self,
        ip: str,
        port: int,
        response_time_ms: float,
        timeout: float,
    ) -> Optional[DiscoveredDevice]:
        """
        Attempt to identify a device at the given address.

        Args:
            ip: IP address of the device.
            port: Port number.
            response_time_ms: Initial response time from scan.
            timeout: Identification timeout.

        Returns:
            DiscoveredDevice with identification results, or None on error.
        """
        device = DiscoveredDevice(
            ip_address=ip,
            port=port,
            response_time_ms=response_time_ms,
        )

        try:
            # Create TCP connection for identification
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout / 2,
            )

            try:
                connection = TCPConnection(reader, writer)

                # Try to identify using prober
                identified = await asyncio.wait_for(
                    self.prober.identify(connection),
                    timeout=timeout,
                )

                if identified:
                    device.is_identified = True
                    device.protocol_id = identified.protocol_id
                    device.serial_number = identified.serial_number
                    device.device_type = identified.device_type
                    device.model = identified.model
                    device.manufacturer = identified.manufacturer
                    device.firmware_version = identified.firmware_version
                    device.extra_data = identified.extra_data

                    logger.info(
                        f"Identified {device.protocol_id} at {ip}:{port} "
                        f"(serial: {device.serial_number})"
                    )
                else:
                    logger.debug(f"Could not identify device at {ip}:{port}")

            finally:
                writer.close()
                await writer.wait_closed()

        except asyncio.TimeoutError:
            logger.debug(f"Identification timeout for {ip}:{port}")
        except Exception as e:
            logger.debug(f"Identification error for {ip}:{port}: {e}")

        return device

    async def scan_network_async(
        self,
        network: str,
        ports: Optional[List[int]] = None,
        site_id: Optional[UUID] = None,
        **kwargs,
    ) -> UUID:
        """
        Start a background network scan.

        Args:
            network: Network in CIDR notation.
            ports: Ports to scan.
            site_id: Optional site ID.
            **kwargs: Additional arguments for scan_network.

        Returns:
            Scan ID for tracking progress.
        """
        scan_id = uuid4()

        # Create initial result for tracking
        result = DiscoveryResult(
            scan_id=scan_id,
            network=network,
            ports=ports or [502, 8502],
            site_id=site_id,
        )
        result.progress.current_status = ScanStatus.PENDING
        self._active_scans[scan_id] = result

        # Start background task
        async def run_scan():
            try:
                final_result = await self.scan_network(
                    network=network,
                    ports=ports,
                    site_id=site_id,
                    **kwargs,
                )
                # Update tracked result
                self._active_scans[scan_id] = final_result
            except Exception as e:
                logger.error(f"Background scan {scan_id} failed: {e}")
                result.progress.current_status = ScanStatus.FAILED
                result.progress.last_error = str(e)

        task = asyncio.create_task(run_scan())
        self._scan_tasks[scan_id] = task

        return scan_id

    def get_scan_status(self, scan_id: UUID) -> Optional[DiscoveryResult]:
        """
        Get status of a scan.

        Args:
            scan_id: Scan ID to check.

        Returns:
            DiscoveryResult if found, None otherwise.
        """
        return self._active_scans.get(scan_id)

    async def cancel_scan(self, scan_id: UUID) -> bool:
        """
        Cancel a running scan.

        Args:
            scan_id: Scan ID to cancel.

        Returns:
            True if cancelled, False if not found.
        """
        task = self._scan_tasks.get(scan_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return True
        return False

    def get_active_scans(self) -> List[DiscoveryResult]:
        """Get all active/recent scans."""
        return list(self._active_scans.values())

    def clear_known_devices(self) -> None:
        """Clear the known devices cache (for allowing re-discovery)."""
        self._known_serials.clear()
