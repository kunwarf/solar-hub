"""
Device prober - main orchestration for device identification.

Coordinates Modbus and command-based probing to identify
connected devices.
"""
import asyncio
import logging
from typing import Optional

from ..config import DeviceServerSettings, get_device_server_settings
from ..connection.tcp_connection import TCPConnection
from ..connection.connection_manager import IdentifiedDevice
from ..protocols.definitions import ProtocolDefinition, ProtocolType
from ..protocols.registry import ProtocolRegistry
from .modbus_prober import ModbusProber
from .command_prober import CommandProber

logger = logging.getLogger(__name__)


class DeviceProber:
    """
    Main device prober that orchestrates identification.

    Tries each registered protocol in priority order until
    a device is successfully identified.
    """

    def __init__(
        self,
        registry: ProtocolRegistry,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the device prober.

        Args:
            registry: Protocol registry with device definitions.
            settings: Server settings.
        """
        self.registry = registry
        self.settings = settings or get_device_server_settings()

        # Create specialized probers
        self.modbus_prober = ModbusProber(
            timeout=self.settings.identification.timeout
        )
        self.command_prober = CommandProber(
            timeout=self.settings.identification.timeout
        )

    async def identify(
        self,
        connection: TCPConnection,
    ) -> Optional[IdentifiedDevice]:
        """
        Identify the device on a connection.

        Tries protocols in priority order:
        1. First, all Modbus protocols (most common for inverters/meters)
        2. Then, command-based protocols (batteries)

        Args:
            connection: TCP connection to identify.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        logger.info(f"Starting device identification for {connection.remote_addr}")

        # Try Modbus protocols first (most common)
        for protocol in self.registry.iter_modbus_by_priority():
            result = await self._try_protocol(connection, protocol)
            if result:
                return result

        # Then try command-based protocols
        for protocol in self.registry.iter_command_by_priority():
            result = await self._try_protocol(connection, protocol)
            if result:
                return result

        logger.warning(
            f"Failed to identify device on {connection.remote_addr} "
            f"after trying {len(self.registry)} protocols"
        )
        return None

    async def identify_with_protocol(
        self,
        connection: TCPConnection,
        protocol_id: str,
    ) -> Optional[IdentifiedDevice]:
        """
        Identify device using a specific protocol.

        Useful when the protocol is already known or suspected.

        Args:
            connection: TCP connection to identify.
            protocol_id: Specific protocol ID to try.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        protocol = self.registry.get(protocol_id)
        if not protocol:
            logger.error(f"Unknown protocol: {protocol_id}")
            return None

        return await self._try_protocol(connection, protocol)

    async def _try_protocol(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
    ) -> Optional[IdentifiedDevice]:
        """
        Try to identify device with a specific protocol.

        Args:
            connection: TCP connection.
            protocol: Protocol to try.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        logger.debug(f"Trying protocol: {protocol.protocol_id}")

        try:
            # Select appropriate prober based on protocol type
            if protocol.protocol_type in (
                ProtocolType.MODBUS_TCP,
                ProtocolType.MODBUS_RTU,
            ):
                result = await asyncio.wait_for(
                    self.modbus_prober.probe(connection, protocol),
                    timeout=protocol.identification.timeout + 1.0,
                )
            elif protocol.protocol_type == ProtocolType.COMMAND:
                result = await asyncio.wait_for(
                    self.command_prober.probe(connection, protocol),
                    timeout=protocol.identification.timeout + 1.0,
                )
            elif protocol.protocol_type == ProtocolType.BLE:
                # BLE is handled differently (not over TCP)
                logger.debug(f"Skipping BLE protocol: {protocol.protocol_id}")
                return None
            else:
                logger.warning(
                    f"Unsupported protocol type: {protocol.protocol_type}"
                )
                return None

            if result:
                logger.info(
                    f"Successfully identified {protocol.protocol_id} "
                    f"(serial: {result.serial_number})"
                )
                return result

        except asyncio.TimeoutError:
            logger.debug(f"Timeout probing {protocol.protocol_id}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"Error probing {protocol.protocol_id}: {e}")

        return None

    async def probe_all(
        self,
        connection: TCPConnection,
    ) -> list:
        """
        Probe all protocols and return all matches.

        Useful for debugging to see which protocols respond.

        Args:
            connection: TCP connection to probe.

        Returns:
            List of IdentifiedDevice objects for all matching protocols.
        """
        matches = []

        for protocol in self.registry.iter_by_priority():
            try:
                result = await self._try_protocol(connection, protocol)
                if result:
                    matches.append(result)
            except Exception as e:
                logger.debug(f"Error in probe_all for {protocol.protocol_id}: {e}")

        return matches
