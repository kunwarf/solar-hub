"""
Connection manager for data logger connections.

Orchestrates the connection lifecycle from acceptance through
identification to polling, managing device state transitions.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from uuid import UUID

from ..config import DeviceServerSettings, get_device_server_settings
from .tcp_connection import ConnectionState, TCPConnection

if TYPE_CHECKING:
    from ..identification.prober import DeviceProber
    from ..devices.device_manager import DeviceManager

logger = logging.getLogger(__name__)


class IdentifiedDevice:
    """Information about an identified device."""

    def __init__(
        self,
        protocol_id: str,
        serial_number: str,
        device_type: str,
        model: Optional[str] = None,
        manufacturer: Optional[str] = None,
        firmware_version: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ):
        self.protocol_id = protocol_id
        self.serial_number = serial_number
        self.device_type = device_type
        self.model = model
        self.manufacturer = manufacturer
        self.firmware_version = firmware_version
        self.extra_data = extra_data or {}
        self.identified_at = datetime.now(timezone.utc)


class ConnectionManager:
    """
    Manages the lifecycle of data logger connections.

    Responsibilities:
    - Accept incoming connections from TCP server
    - Coordinate device identification
    - Register identified devices with System A
    - Hand off to device manager for polling
    - Handle connection failures and reconnection
    """

    def __init__(
        self,
        prober: "DeviceProber",
        device_manager: "DeviceManager",
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the connection manager.

        Args:
            prober: Device prober for identification.
            device_manager: Device manager for handling identified devices.
            settings: Server settings.
        """
        self.prober = prober
        self.device_manager = device_manager
        self.settings = settings or get_device_server_settings()

        # Track connections by various keys
        self._connections: Dict[UUID, TCPConnection] = {}
        self._by_serial: Dict[str, UUID] = {}
        self._by_device_id: Dict[UUID, UUID] = {}

        # Pending identifications
        self._identifying: Dict[UUID, asyncio.Task] = {}

        # Statistics
        self._total_identified = 0
        self._total_failed = 0

    async def handle_connection(self, connection: TCPConnection) -> asyncio.Task:
        """
        Handle a new connection from the TCP server.

        This is the main entry point called by the TCP server for
        each new connection.

        Args:
            connection: The new TCP connection.

        Returns:
            Task handling the connection lifecycle.
        """
        # Track the connection
        self._connections[connection.connection_id] = connection

        # Create and return the handling task
        task = asyncio.create_task(
            self._connection_lifecycle(connection),
            name=f"conn-{connection.connection_id}",
        )

        return task

    async def _connection_lifecycle(self, connection: TCPConnection) -> None:
        """
        Manage the full lifecycle of a connection.

        1. Wait briefly for connection to stabilize
        2. Attempt device identification
        3. Register device with System A
        4. Hand off to device manager for polling
        5. Clean up on disconnect

        Args:
            connection: The connection to manage.
        """
        try:
            # Brief stabilization delay
            await asyncio.sleep(0.5)

            # Phase 1: Identification
            connection.state = ConnectionState.IDENTIFYING
            identified = await self._identify_device(connection)

            if not identified:
                logger.warning(
                    f"Failed to identify device on {connection.remote_addr}, "
                    f"closing connection"
                )
                self._total_failed += 1
                await connection.close()
                return

            # Store identification info on connection
            connection.protocol_id = identified.protocol_id
            connection.serial_number = identified.serial_number
            connection.state = ConnectionState.IDENTIFIED

            logger.info(
                f"Identified device: {identified.protocol_id} "
                f"(serial: {identified.serial_number}) "
                f"on {connection.remote_addr}"
            )

            # Check for existing connection with same serial
            if identified.serial_number in self._by_serial:
                old_conn_id = self._by_serial[identified.serial_number]
                old_conn = self._connections.get(old_conn_id)
                if old_conn and old_conn.is_connected:
                    logger.info(
                        f"Replacing existing connection for "
                        f"{identified.serial_number}"
                    )
                    await old_conn.close()

            # Track by serial number
            self._by_serial[identified.serial_number] = connection.connection_id

            # Phase 2: Register with System A
            device_id = await self._register_device(connection, identified)
            if device_id:
                connection.device_id = device_id
                self._by_device_id[device_id] = connection.connection_id

            # Phase 3: Hand off to device manager for polling
            connection.state = ConnectionState.POLLING
            self._total_identified += 1

            await self.device_manager.add_device(
                device_id=device_id,
                connection=connection,
                identified=identified,
            )

            # Wait for device manager to complete (e.g., polling loop)
            # This will block until the connection is closed or device removed
            while connection.is_connected:
                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info(f"Connection {connection.connection_id} cancelled")
            raise
        except Exception as e:
            logger.exception(
                f"Error in connection lifecycle for {connection.connection_id}: {e}"
            )
            connection.state = ConnectionState.ERROR
        finally:
            await self._cleanup_connection(connection)

    async def _identify_device(
        self,
        connection: TCPConnection,
    ) -> Optional[IdentifiedDevice]:
        """
        Attempt to identify the device on a connection.

        Tries each registered protocol in priority order until
        one successfully identifies the device.

        Args:
            connection: The connection to probe.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        max_retries = self.settings.identification.max_retries
        retry_delay = self.settings.identification.retry_delay

        for attempt in range(max_retries):
            if attempt > 0:
                logger.debug(
                    f"Identification attempt {attempt + 1}/{max_retries} "
                    f"for {connection.remote_addr}"
                )
                await asyncio.sleep(retry_delay)

            try:
                result = await asyncio.wait_for(
                    self.prober.identify(connection),
                    timeout=self.settings.identification.timeout,
                )

                if result:
                    return result

            except asyncio.TimeoutError:
                logger.warning(
                    f"Identification timeout for {connection.remote_addr} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
            except Exception as e:
                logger.warning(
                    f"Identification error for {connection.remote_addr}: {e}"
                )

        return None

    async def _register_device(
        self,
        connection: TCPConnection,
        identified: IdentifiedDevice,
    ) -> Optional[UUID]:
        """
        Register the identified device with System A.

        Args:
            connection: The device connection.
            identified: Identification information.

        Returns:
            Device UUID from System A, or None if registration failed.
        """
        # This will be implemented in the storage module
        # For now, just generate a local UUID
        from uuid import uuid4

        # TODO: Call System A API to register device
        # device_id = await self.system_a_client.register_device(
        #     serial_number=identified.serial_number,
        #     device_type=identified.device_type,
        #     protocol=identified.protocol_id,
        #     model=identified.model,
        #     manufacturer=identified.manufacturer,
        # )

        device_id = uuid4()
        logger.info(
            f"Registered device {identified.serial_number} "
            f"with ID {device_id}"
        )

        return device_id

    async def _cleanup_connection(self, connection: TCPConnection) -> None:
        """
        Clean up after a connection closes.

        Args:
            connection: The connection to clean up.
        """
        logger.debug(f"Cleaning up connection {connection.connection_id}")

        # Remove from tracking
        self._connections.pop(connection.connection_id, None)

        if connection.serial_number:
            self._by_serial.pop(connection.serial_number, None)

        if connection.device_id:
            self._by_device_id.pop(connection.device_id, None)
            # Notify device manager
            await self.device_manager.remove_device(connection.device_id)

        # Ensure connection is closed
        if connection.is_connected:
            await connection.close()

    def get_connection_by_device(
        self,
        device_id: UUID,
    ) -> Optional[TCPConnection]:
        """
        Get connection for a device.

        Args:
            device_id: The device UUID.

        Returns:
            The connection, or None if not found.
        """
        conn_id = self._by_device_id.get(device_id)
        if conn_id:
            return self._connections.get(conn_id)
        return None

    def get_connection_by_serial(
        self,
        serial_number: str,
    ) -> Optional[TCPConnection]:
        """
        Get connection for a device by serial number.

        Args:
            serial_number: The device serial number.

        Returns:
            The connection, or None if not found.
        """
        conn_id = self._by_serial.get(serial_number)
        if conn_id:
            return self._connections.get(conn_id)
        return None

    async def close_all(self) -> None:
        """Close all active connections."""
        logger.info(f"Closing {len(self._connections)} connections")

        for connection in list(self._connections.values()):
            await connection.close()

        self._connections.clear()
        self._by_serial.clear()
        self._by_device_id.clear()

    def get_stats(self) -> dict:
        """Get connection manager statistics."""
        return {
            "active_connections": len(self._connections),
            "devices_by_serial": len(self._by_serial),
            "devices_by_id": len(self._by_device_id),
            "pending_identifications": len(self._identifying),
            "total_identified": self._total_identified,
            "total_failed": self._total_failed,
        }
