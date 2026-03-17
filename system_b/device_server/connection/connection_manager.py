"""
Connection manager for data logger connections.

Orchestrates the connection lifecycle from acceptance through
identification to polling, managing device state transitions.
"""
import asyncio
import logging
import struct
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from uuid import UUID

from ..config import DeviceServerSettings, get_device_server_settings
from .tcp_connection import ConnectionState, TCPConnection

if TYPE_CHECKING:
    from ..identification.prober import DeviceProber
    from ..devices.device_manager import DeviceManager
    from ..storage.device_registry_client import DeviceRegistryClient

# Serial bridge framing constants
_MSG_HELLO = 0x06

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
        device_registry_client: Optional["DeviceRegistryClient"] = None,
    ):
        """
        Initialize the connection manager.

        Args:
            prober: Device prober for identification.
            device_manager: Device manager for handling identified devices.
            settings: Server settings.
            device_registry_client: Optional registry client for HELLO-based
                identification (serial bridge connections).
        """
        self.prober = prober
        self.device_manager = device_manager
        self.settings = settings or get_device_server_settings()
        self._device_registry_client = device_registry_client

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
            logger.info(f"Starting connection lifecycle for {connection.remote_addr}")

            # Brief stabilization delay
            await asyncio.sleep(0.5)

            # Phase 1: Identification
            # First, peek for HELLO frame (0x06) sent immediately by serial bridge ESP32.
            # Non-bridged connections (Modbus bridge) never send data until polled, so
            # read(1) with a 0.5s timeout is safe — it will time out for Modbus bridges.
            logger.info(f"Phase 1: Identifying device on {connection.remote_addr}")
            connection.state = ConnectionState.IDENTIFYING

            try:
                first_byte = await asyncio.wait_for(
                    connection.reader.read(1),
                    timeout=0.5,
                )
            except asyncio.TimeoutError:
                first_byte = b""

            if first_byte == bytes([_MSG_HELLO]):
                logger.info(
                    f"HELLO detected from {connection.remote_addr} — "
                    f"using serial bridge identification path"
                )
                identified = await self._identify_from_hello(connection)
                if identified:
                    connection.bridged = True
            else:
                if first_byte and first_byte[0] != _MSG_HELLO:
                    logger.warning(
                        f"Unexpected initial byte from {connection.remote_addr}: "
                        f"{first_byte.hex()} — falling back to probe identification"
                    )
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

            # Get protocol definition for the device
            protocol = self.prober.registry.get(identified.protocol_id)
            if not protocol:
                logger.error(f"Protocol not found: {identified.protocol_id}")
                await connection.close()
                return

            await self.device_manager.add_device(
                connection=connection,
                identified=identified,
                protocol=protocol,
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

    async def _identify_from_hello(
        self,
        connection: TCPConnection,
    ) -> Optional[IdentifiedDevice]:
        """
        Identify a serial bridge device from its HELLO frame.

        The first byte (0x06) has already been consumed; read the remaining
        4-byte length header + serial number payload.

        Args:
            connection: The connection that sent HELLO.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        try:
            # Read 4-byte length field (already consumed the 0x06 type byte)
            length_bytes = await connection.read(4, timeout=5.0)
            payload_len = struct.unpack(">I", length_bytes)[0]

            if payload_len == 0 or payload_len > 256:
                logger.warning(
                    f"Invalid HELLO payload length {payload_len} from "
                    f"{connection.remote_addr}"
                )
                return None

            # Read serial number
            serial_bytes = await connection.read(payload_len, timeout=5.0)
            serial_number = serial_bytes.decode("utf-8", errors="replace").strip()

            if not serial_number:
                logger.warning(
                    f"Empty serial number in HELLO from {connection.remote_addr}"
                )
                return None

            logger.info(
                f"HELLO serial={serial_number} from {connection.remote_addr}"
            )

            # Query device registry for registration metadata
            device_type = "battery"
            manufacturer = None
            model = None
            firmware_version = None
            protocol_id_hint = None

            if self._device_registry_client:
                reg = await self._device_registry_client.get_registration_by_serial(
                    serial_number
                )
                if reg:
                    device_type = reg.get("device_type", "battery")
                    manufacturer = reg.get("manufacturer")
                    model = reg.get("model")
                    firmware_version = reg.get("firmware_version")
                    protocol_id_hint = reg.get("protocol_id")

            # Find the protocol to use
            from ..protocols.definitions import DeviceType
            protocol = None

            # 1. Try explicit protocol hint from registry metadata
            if protocol_id_hint:
                protocol = self.prober.registry.get(protocol_id_hint)

            # 2. Find highest-priority command protocol matching device_type
            if not protocol:
                try:
                    dt = DeviceType(device_type)
                except ValueError:
                    dt = None

                for p in self.prober.registry.iter_command_by_priority():
                    if dt is None or p.device_type == dt:
                        protocol = p
                        break

            # 3. Last resort: any command protocol
            if not protocol:
                cmd_protocols = list(self.prober.registry.get_command_protocols())
                if cmd_protocols:
                    protocol = cmd_protocols[0]

            if not protocol:
                logger.error(
                    f"No command protocol found for serial bridge device "
                    f"{serial_number} (device_type={device_type})"
                )
                return None

            logger.info(
                f"HELLO identification: serial={serial_number}, "
                f"protocol={protocol.protocol_id}, device_type={device_type}"
            )

            return IdentifiedDevice(
                protocol_id=protocol.protocol_id,
                serial_number=serial_number,
                device_type=device_type,
                model=model,
                manufacturer=manufacturer,
                firmware_version=firmware_version,
                extra_data={"bridged": True},
            )

        except Exception as e:
            logger.warning(
                f"HELLO identification error for {connection.remote_addr}: {e}"
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
