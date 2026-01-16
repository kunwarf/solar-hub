"""
Device manager for tracking connected devices.

Manages the lifecycle of connected devices including registration,
state tracking, and coordination with polling.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4

from ..config import DeviceServerSettings, get_device_server_settings
from ..connection.tcp_connection import TCPConnection
from ..connection.connection_manager import IdentifiedDevice
from ..protocols.definitions import ProtocolDefinition
from ..protocols.registry import ProtocolRegistry
from .device_state import DeviceState, DeviceStatus
from .adapter_factory import AdapterFactory

logger = logging.getLogger(__name__)


class DeviceManager:
    """
    Manages connected devices and their lifecycle.

    Responsibilities:
    - Track all connected devices
    - Manage device state transitions
    - Coordinate with polling scheduler
    - Provide device lookup and iteration
    """

    def __init__(
        self,
        registry: ProtocolRegistry,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the device manager.

        Args:
            registry: Protocol registry.
            settings: Server settings.
        """
        self.registry = registry
        self.settings = settings or get_device_server_settings()

        # Device tracking
        self._devices: Dict[UUID, DeviceState] = {}
        self._devices_by_serial: Dict[str, UUID] = {}
        self._devices_by_connection: Dict[UUID, UUID] = {}

        # Adapters and connections
        self._adapters: Dict[UUID, Any] = {}
        self._connections: Dict[UUID, TCPConnection] = {}

        # Factory for creating adapters
        self._adapter_factory = AdapterFactory(settings)

        # Callbacks
        self._on_device_added: Optional[Callable] = None
        self._on_device_removed: Optional[Callable] = None
        self._on_device_status_changed: Optional[Callable] = None

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def add_device(
        self,
        connection: TCPConnection,
        identified: IdentifiedDevice,
        protocol: ProtocolDefinition,
    ) -> UUID:
        """
        Add a newly identified device.

        Args:
            connection: TCP connection to device.
            identified: Identification result.
            protocol: Protocol definition.

        Returns:
            UUID of the added device.
        """
        async with self._lock:
            # Check if device already exists by serial
            if identified.serial_number in self._devices_by_serial:
                existing_id = self._devices_by_serial[identified.serial_number]
                logger.warning(
                    f"Device {identified.serial_number} already registered "
                    f"as {existing_id}, updating connection"
                )
                # Update connection for existing device
                await self._update_device_connection(
                    existing_id, connection, protocol
                )
                return existing_id

            # Generate new device ID
            device_id = uuid4()

            # Create device state
            device_state = DeviceState(
                device_id=device_id,
                serial_number=identified.serial_number,
                protocol_id=protocol.protocol_id,
                device_type=protocol.device_type.value,
                connection_id=connection.connection_id,
                remote_addr=connection.remote_addr,
                status=DeviceStatus.INITIALIZING,
                poll_interval=protocol.polling.default_interval,
                model=identified.model,
                manufacturer=identified.manufacturer,
                extra_data=identified.extra_data or {},
            )

            # Create adapter
            adapter = self._adapter_factory.create_adapter(connection, protocol)

            # Store everything
            self._devices[device_id] = device_state
            self._devices_by_serial[identified.serial_number] = device_id
            self._devices_by_connection[connection.connection_id] = device_id
            self._adapters[device_id] = adapter
            self._connections[device_id] = connection

            logger.info(
                f"Added device {device_id} "
                f"(serial={identified.serial_number}, "
                f"protocol={protocol.protocol_id})"
            )

            # Mark as online
            device_state.mark_online()
            device_state.identified_at = datetime.now(timezone.utc)

            # Trigger callback
            if self._on_device_added:
                try:
                    await self._on_device_added(device_id, device_state)
                except Exception as e:
                    logger.error(f"Error in on_device_added callback: {e}")

            return device_id

    async def _update_device_connection(
        self,
        device_id: UUID,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
    ) -> None:
        """
        Update connection for existing device (reconnection).

        Args:
            device_id: Device ID.
            connection: New TCP connection.
            protocol: Protocol definition.
        """
        device_state = self._devices.get(device_id)
        if not device_state:
            return

        # Close old connection if exists
        old_connection = self._connections.get(device_id)
        if old_connection:
            try:
                await old_connection.close()
            except Exception:
                pass

        # Remove old connection mapping
        if device_state.connection_id in self._devices_by_connection:
            del self._devices_by_connection[device_state.connection_id]

        # Update state
        device_state.connection_id = connection.connection_id
        device_state.remote_addr = connection.remote_addr
        device_state.consecutive_failures = 0
        device_state.mark_online()

        # Create new adapter
        adapter = self._adapter_factory.create_adapter(connection, protocol)

        # Store new connection and adapter
        self._connections[device_id] = connection
        self._adapters[device_id] = adapter
        self._devices_by_connection[connection.connection_id] = device_id

        logger.info(f"Updated connection for device {device_id}")

    async def remove_device(self, device_id: UUID) -> None:
        """
        Remove a device.

        Args:
            device_id: Device ID to remove.
        """
        async with self._lock:
            device_state = self._devices.get(device_id)
            if not device_state:
                return

            # Clean up mappings
            if device_state.serial_number in self._devices_by_serial:
                del self._devices_by_serial[device_state.serial_number]

            if device_state.connection_id in self._devices_by_connection:
                del self._devices_by_connection[device_state.connection_id]

            # Close connection
            connection = self._connections.get(device_id)
            if connection:
                try:
                    await connection.close()
                except Exception:
                    pass
                del self._connections[device_id]

            # Clean up adapter
            if device_id in self._adapters:
                del self._adapters[device_id]

            # Remove device state
            del self._devices[device_id]

            logger.info(f"Removed device {device_id}")

            # Trigger callback
            if self._on_device_removed:
                try:
                    await self._on_device_removed(device_id, device_state)
                except Exception as e:
                    logger.error(f"Error in on_device_removed callback: {e}")

    async def mark_device_offline(
        self,
        device_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        """
        Mark a device as offline.

        Args:
            device_id: Device ID.
            reason: Reason for going offline.
        """
        async with self._lock:
            device_state = self._devices.get(device_id)
            if not device_state:
                return

            old_status = device_state.status
            device_state.mark_offline(reason)

            if old_status != device_state.status:
                logger.warning(
                    f"Device {device_id} marked offline: {reason}"
                )

                if self._on_device_status_changed:
                    try:
                        await self._on_device_status_changed(
                            device_id, old_status, device_state.status
                        )
                    except Exception as e:
                        logger.error(f"Error in status change callback: {e}")

    async def mark_device_error(
        self,
        device_id: UUID,
        error: str,
    ) -> None:
        """
        Mark a device as having an error.

        Args:
            device_id: Device ID.
            error: Error description.
        """
        async with self._lock:
            device_state = self._devices.get(device_id)
            if not device_state:
                return

            old_status = device_state.status
            device_state.mark_error(error)

            if old_status != device_state.status:
                logger.error(f"Device {device_id} error: {error}")

                if self._on_device_status_changed:
                    try:
                        await self._on_device_status_changed(
                            device_id, old_status, device_state.status
                        )
                    except Exception as e:
                        logger.error(f"Error in status change callback: {e}")

    def get_device(self, device_id: UUID) -> Optional[DeviceState]:
        """
        Get device state by ID.

        Args:
            device_id: Device ID.

        Returns:
            DeviceState or None if not found.
        """
        return self._devices.get(device_id)

    def get_device_by_serial(self, serial_number: str) -> Optional[DeviceState]:
        """
        Get device state by serial number.

        Args:
            serial_number: Device serial number.

        Returns:
            DeviceState or None if not found.
        """
        device_id = self._devices_by_serial.get(serial_number)
        if device_id:
            return self._devices.get(device_id)
        return None

    def get_device_by_connection(
        self,
        connection_id: UUID,
    ) -> Optional[DeviceState]:
        """
        Get device state by connection ID.

        Args:
            connection_id: Connection ID.

        Returns:
            DeviceState or None if not found.
        """
        device_id = self._devices_by_connection.get(connection_id)
        if device_id:
            return self._devices.get(device_id)
        return None

    def get_adapter(self, device_id: UUID) -> Optional[Any]:
        """
        Get adapter for a device.

        Args:
            device_id: Device ID.

        Returns:
            Adapter instance or None.
        """
        return self._adapters.get(device_id)

    def get_connection(self, device_id: UUID) -> Optional[TCPConnection]:
        """
        Get connection for a device.

        Args:
            device_id: Device ID.

        Returns:
            TCPConnection or None.
        """
        return self._connections.get(device_id)

    def iter_devices(self) -> List[DeviceState]:
        """
        Iterate all devices.

        Returns:
            List of DeviceState objects.
        """
        return list(self._devices.values())

    def iter_online_devices(self) -> List[DeviceState]:
        """
        Iterate online devices.

        Returns:
            List of online DeviceState objects.
        """
        return [d for d in self._devices.values() if d.is_online]

    def iter_devices_by_type(self, device_type: str) -> List[DeviceState]:
        """
        Iterate devices of a specific type.

        Args:
            device_type: Device type to filter.

        Returns:
            List of DeviceState objects of that type.
        """
        return [
            d for d in self._devices.values()
            if d.device_type == device_type
        ]

    @property
    def device_count(self) -> int:
        """Get total device count."""
        return len(self._devices)

    @property
    def online_count(self) -> int:
        """Get online device count."""
        return sum(1 for d in self._devices.values() if d.is_online)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get device manager statistics.

        Returns:
            Dictionary of statistics.
        """
        by_type: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        by_protocol: Dict[str, int] = {}

        for device in self._devices.values():
            # Count by type
            by_type[device.device_type] = by_type.get(device.device_type, 0) + 1

            # Count by status
            status = device.status.value
            by_status[status] = by_status.get(status, 0) + 1

            # Count by protocol
            by_protocol[device.protocol_id] = (
                by_protocol.get(device.protocol_id, 0) + 1
            )

        return {
            "total_devices": len(self._devices),
            "online_devices": self.online_count,
            "by_type": by_type,
            "by_status": by_status,
            "by_protocol": by_protocol,
        }

    def set_on_device_added(self, callback: Callable) -> None:
        """Set callback for device added events."""
        self._on_device_added = callback

    def set_on_device_removed(self, callback: Callable) -> None:
        """Set callback for device removed events."""
        self._on_device_removed = callback

    def set_on_device_status_changed(self, callback: Callable) -> None:
        """Set callback for device status change events."""
        self._on_device_status_changed = callback

    async def shutdown(self) -> None:
        """
        Shutdown the device manager.

        Closes all connections and cleans up resources.
        """
        logger.info("Shutting down device manager...")

        async with self._lock:
            # Close all connections
            for device_id, connection in list(self._connections.items()):
                try:
                    await connection.close()
                except Exception as e:
                    logger.debug(f"Error closing connection {device_id}: {e}")

            # Clear all state
            self._devices.clear()
            self._devices_by_serial.clear()
            self._devices_by_connection.clear()
            self._adapters.clear()
            self._connections.clear()

        logger.info("Device manager shutdown complete")
