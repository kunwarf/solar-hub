"""
Network scanner for discovering devices on local networks.

Provides async TCP port scanning with configurable concurrency
and timeout settings.
"""
import asyncio
import ipaddress
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ScanConfig:
    """Configuration for network scanning."""

    # Target configuration
    network: str = "192.168.1.0/24"
    ports: List[int] = field(default_factory=lambda: [502, 8502])
    exclude_ips: Set[str] = field(default_factory=set)

    # Performance settings
    max_concurrent: int = 50
    connect_timeout: float = 2.0
    scan_timeout: float = 300.0  # Overall timeout for entire scan

    # Behavior settings
    skip_own_ip: bool = True
    stop_on_first_port: bool = False  # Stop checking ports once one responds


@dataclass
class ScanResult:
    """Result of a single port scan."""
    ip: str
    port: int
    is_open: bool
    response_time_ms: float = 0.0
    error: Optional[str] = None


class NetworkScanner:
    """
    Async network scanner for TCP port scanning.

    Scans IP ranges and ports with configurable concurrency,
    yielding results as they are discovered.
    """

    def __init__(self, config: Optional[ScanConfig] = None):
        """
        Initialize the network scanner.

        Args:
            config: Scan configuration. Uses defaults if not provided.
        """
        self.config = config or ScanConfig()
        self._cancelled = False
        self._semaphore: Optional[asyncio.Semaphore] = None

    def cancel(self) -> None:
        """Cancel an ongoing scan."""
        self._cancelled = True

    def reset(self) -> None:
        """Reset the scanner for a new scan."""
        self._cancelled = False

    def _get_hosts(self) -> List[str]:
        """
        Get list of hosts to scan from network specification.

        Returns:
            List of IP addresses to scan.
        """
        try:
            network = ipaddress.ip_network(self.config.network, strict=False)
            hosts = []

            for ip in network.hosts():
                ip_str = str(ip)

                # Skip excluded IPs
                if ip_str in self.config.exclude_ips:
                    continue

                hosts.append(ip_str)

            logger.info(f"Prepared {len(hosts)} hosts to scan from {self.config.network}")
            return hosts

        except ValueError as e:
            logger.error(f"Invalid network specification: {e}")
            return []

    async def _check_port(self, ip: str, port: int) -> ScanResult:
        """
        Check if a port is open on a host.

        Args:
            ip: IP address to check.
            port: Port number to check.

        Returns:
            ScanResult with connection status.
        """
        start_time = time.perf_counter()

        try:
            # Use semaphore to limit concurrency
            async with self._semaphore:
                if self._cancelled:
                    return ScanResult(ip=ip, port=port, is_open=False, error="cancelled")

                # Attempt TCP connection
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=self.config.connect_timeout,
                )

                # Connection successful, close it
                writer.close()
                await writer.wait_closed()

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                logger.debug(f"Port {port} open on {ip} (response: {elapsed_ms:.1f}ms)")

                return ScanResult(
                    ip=ip,
                    port=port,
                    is_open=True,
                    response_time_ms=elapsed_ms,
                )

        except asyncio.TimeoutError:
            return ScanResult(
                ip=ip,
                port=port,
                is_open=False,
                error="timeout",
            )
        except ConnectionRefusedError:
            return ScanResult(
                ip=ip,
                port=port,
                is_open=False,
                error="refused",
            )
        except OSError as e:
            return ScanResult(
                ip=ip,
                port=port,
                is_open=False,
                error=str(e),
            )
        except Exception as e:
            logger.debug(f"Error scanning {ip}:{port}: {e}")
            return ScanResult(
                ip=ip,
                port=port,
                is_open=False,
                error=str(e),
            )

    async def scan(
        self,
        progress_callback: Optional[Callable[[int, int, str, int], None]] = None,
    ) -> AsyncIterator[ScanResult]:
        """
        Scan the network and yield open ports.

        Args:
            progress_callback: Optional callback for progress updates.
                Signature: callback(scanned_count, total_count, current_ip, current_port)

        Yields:
            ScanResult for each responsive host/port.
        """
        self.reset()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)

        hosts = self._get_hosts()
        if not hosts:
            return

        total_targets = len(hosts) * len(self.config.ports)
        scanned = 0

        logger.info(
            f"Starting network scan: {len(hosts)} hosts x {len(self.config.ports)} ports "
            f"= {total_targets} targets"
        )

        try:
            # Create tasks for all host/port combinations
            pending_tasks: Set[asyncio.Task] = set()
            host_port_map: dict = {}  # Map task to (ip, port)

            # Process hosts in batches to avoid memory issues with large networks
            batch_size = self.config.max_concurrent * 2

            for i in range(0, len(hosts), batch_size):
                if self._cancelled:
                    break

                batch_hosts = hosts[i:i + batch_size]

                for ip in batch_hosts:
                    if self._cancelled:
                        break

                    for port in self.config.ports:
                        task = asyncio.create_task(self._check_port(ip, port))
                        pending_tasks.add(task)
                        host_port_map[id(task)] = (ip, port)

                # Wait for batch to complete
                while pending_tasks:
                    if self._cancelled:
                        # Cancel remaining tasks
                        for task in pending_tasks:
                            task.cancel()
                        break

                    done, pending_tasks = await asyncio.wait(
                        pending_tasks,
                        timeout=1.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in done:
                        scanned += 1

                        try:
                            result = task.result()
                            ip, port = host_port_map.get(id(task), ("unknown", 0))

                            # Update progress
                            if progress_callback:
                                progress_callback(scanned, total_targets, ip, port)

                            # Yield open ports
                            if result.is_open:
                                yield result

                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.debug(f"Task error: {e}")

        except asyncio.TimeoutError:
            logger.warning("Scan timeout exceeded")
        except Exception as e:
            logger.error(f"Scan error: {e}")
        finally:
            logger.info(
                f"Scan completed: {scanned}/{total_targets} targets scanned"
            )

    async def scan_host(
        self,
        ip: str,
        ports: Optional[List[int]] = None,
    ) -> List[ScanResult]:
        """
        Scan a single host for open ports.

        Args:
            ip: IP address to scan.
            ports: Ports to check. Uses config ports if not specified.

        Returns:
            List of ScanResult for responsive ports.
        """
        self._semaphore = asyncio.Semaphore(len(ports or self.config.ports))
        ports_to_scan = ports or self.config.ports

        tasks = [
            self._check_port(ip, port)
            for port in ports_to_scan
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        open_ports = []
        for result in results:
            if isinstance(result, ScanResult) and result.is_open:
                open_ports.append(result)

        return open_ports

    async def quick_check(self, ip: str, port: int) -> bool:
        """
        Quickly check if a single port is open.

        Args:
            ip: IP address to check.
            port: Port to check.

        Returns:
            True if port is open, False otherwise.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=self.config.connect_timeout,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
