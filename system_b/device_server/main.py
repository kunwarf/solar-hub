"""
Device Server - Main Entry Point.

Starts the device communication server that:
1. Accepts TCP connections from data loggers
2. Auto-identifies connected devices
3. Sets up telemetry polling
4. Stores data in TimescaleDB and System A
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

from .config import DeviceServerSettings, get_device_server_settings
from .protocols.registry import ProtocolRegistry
from .protocols.loader import ProtocolLoader
from .connection.tcp_server import TCPServer
from .connection.connection_manager import ConnectionManager, IdentifiedDevice
from .identification.prober import DeviceProber
from .devices.device_manager import DeviceManager
from .devices.device_state import DeviceStatus
from .polling.scheduler import PollingScheduler
from .storage.timescale_writer import TimescaleWriter
from .storage.system_a_client import SystemAClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


class DeviceServer:
    """
    Main device server orchestrator.

    Coordinates all components to provide a complete device
    communication and telemetry collection system.
    """

    def __init__(
        self,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the device server.

        Args:
            settings: Server settings.
        """
        self.settings = settings or get_device_server_settings()

        # Core components
        self.registry: Optional[ProtocolRegistry] = None
        self.tcp_server: Optional[TCPServer] = None
        self.connection_manager: Optional[ConnectionManager] = None
        self.device_prober: Optional[DeviceProber] = None
        self.device_manager: Optional[DeviceManager] = None
        self.polling_scheduler: Optional[PollingScheduler] = None
        self.timescale_writer: Optional[TimescaleWriter] = None
        self.system_a_client: Optional[SystemAClient] = None

        # State
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the device server."""
        logger.info("Starting Device Server...")

        # Load protocols
        self.registry = self._load_protocols()

        # Initialize components
        self.device_manager = DeviceManager(self.registry, self.settings)
        self.device_prober = DeviceProber(self.registry, self.settings)
        self.polling_scheduler = PollingScheduler(
            self.device_manager, self.settings
        )

        # Setup connection manager
        self.connection_manager = ConnectionManager(
            prober=self.device_prober,
            settings=self.settings,
        )

        # Set up callbacks
        self.connection_manager.set_on_device_identified(
            self._on_device_identified
        )
        self.connection_manager.set_on_connection_lost(
            self._on_connection_lost
        )

        # Setup device manager callbacks
        self.device_manager.set_on_device_added(self._on_device_added)
        self.device_manager.set_on_device_removed(self._on_device_removed)
        self.device_manager.set_on_device_status_changed(
            self._on_device_status_changed
        )

        # Setup polling callbacks
        self.polling_scheduler.set_on_telemetry(self._on_telemetry)
        self.polling_scheduler.set_on_device_offline(self._on_poll_device_offline)

        # Initialize storage
        self.timescale_writer = TimescaleWriter(self.settings)
        self.system_a_client = SystemAClient(self.settings)

        await self.timescale_writer.connect()
        await self.system_a_client.connect()

        # Start polling scheduler
        await self.polling_scheduler.start()

        # Start TCP server
        self.tcp_server = TCPServer(
            connection_handler=self.connection_manager.handle_connection,
            settings=self.settings,
        )
        await self.tcp_server.start()

        self._running = True
        logger.info(
            f"Device Server started on "
            f"{self.settings.tcp_server.host}:{self.settings.tcp_server.port}"
        )

    async def stop(self) -> None:
        """Stop the device server."""
        if not self._running:
            return

        logger.info("Stopping Device Server...")
        self._running = False
        self._shutdown_event.set()

        # Stop TCP server
        if self.tcp_server:
            await self.tcp_server.stop()

        # Stop polling
        if self.polling_scheduler:
            await self.polling_scheduler.stop()

        # Shutdown device manager
        if self.device_manager:
            await self.device_manager.shutdown()

        # Disconnect storage
        if self.timescale_writer:
            await self.timescale_writer.disconnect()

        if self.system_a_client:
            await self.system_a_client.disconnect()

        logger.info("Device Server stopped")

    async def serve_forever(self) -> None:
        """Run the server until shutdown."""
        await self._shutdown_event.wait()

    def _load_protocols(self) -> ProtocolRegistry:
        """Load protocol definitions."""
        registry = ProtocolRegistry()
        loader = ProtocolLoader()

        # Load from config directory
        config_path = self.settings.protocols_config_path
        if config_path.exists():
            protocols = loader.load_from_file(config_path)
            for protocol in protocols:
                registry.register(protocol)
            logger.info(f"Loaded {len(protocols)} protocols from {config_path}")
        else:
            logger.warning(f"Protocol config not found: {config_path}")

        return registry

    async def _on_device_identified(
        self,
        connection,
        identified: IdentifiedDevice,
    ) -> None:
        """Handle device identification."""
        protocol = self.registry.get(identified.protocol_id)
        if not protocol:
            logger.error(f"Protocol not found: {identified.protocol_id}")
            return

        # Add device to manager
        device_id = await self.device_manager.add_device(
            connection=connection,
            identified=identified,
            protocol=protocol,
        )

        logger.info(
            f"Device identified and added: {device_id} "
            f"(serial={identified.serial_number})"
        )

    async def _on_connection_lost(
        self,
        connection_id: UUID,
        reason: str,
    ) -> None:
        """Handle connection loss."""
        # Find device by connection
        device_state = self.device_manager.get_device_by_connection(connection_id)
        if device_state:
            await self.polling_scheduler.cancel_polling(device_state.device_id)
            await self.device_manager.mark_device_offline(
                device_state.device_id, reason
            )
            logger.info(f"Device {device_state.device_id} disconnected: {reason}")

    async def _on_device_added(
        self,
        device_id: UUID,
        device_state,
    ) -> None:
        """Handle device added."""
        # Register with System A (if configured)
        if self.system_a_client:
            # Get site ID (could be based on IP or other logic)
            site_id = await self.system_a_client.get_site_for_device(
                device_state.remote_addr
            )

            if site_id:
                await self.system_a_client.register_device(
                    site_id=site_id,
                    serial_number=device_state.serial_number,
                    device_type=device_state.device_type,
                    protocol_id=device_state.protocol_id,
                    model=device_state.model,
                    manufacturer=device_state.manufacturer,
                )

        # Start polling
        await self.polling_scheduler.schedule_polling(device_id)

    async def _on_device_removed(
        self,
        device_id: UUID,
        device_state,
    ) -> None:
        """Handle device removed."""
        await self.polling_scheduler.cancel_polling(device_id)

    async def _on_device_status_changed(
        self,
        device_id: UUID,
        old_status: DeviceStatus,
        new_status: DeviceStatus,
    ) -> None:
        """Handle device status change."""
        if self.system_a_client:
            await self.system_a_client.update_device_status(
                device_id, new_status
            )

    async def _on_telemetry(
        self,
        device_id: UUID,
        telemetry: dict,
    ) -> None:
        """Handle collected telemetry."""
        # Write to TimescaleDB
        if self.timescale_writer:
            await self.timescale_writer.write(device_id, telemetry.copy())

        # Update System A snapshot
        if self.system_a_client:
            await self.system_a_client.update_device_snapshot(
                device_id, telemetry.copy()
            )

    async def _on_poll_device_offline(
        self,
        device_id: UUID,
        device_state,
    ) -> None:
        """Handle device going offline due to poll failures."""
        if self.system_a_client:
            await self.system_a_client.update_device_status(
                device_id,
                DeviceStatus.OFFLINE,
                "Too many poll failures",
            )

    def get_stats(self) -> dict:
        """Get server statistics."""
        stats = {
            "running": self._running,
        }

        if self.device_manager:
            stats["devices"] = self.device_manager.get_stats()

        if self.polling_scheduler:
            stats["polling"] = self.polling_scheduler.get_polling_stats()

        if self.tcp_server:
            stats["tcp_server"] = self.tcp_server.get_stats()

        return stats


def setup_signal_handlers(server: DeviceServer, loop: asyncio.AbstractEventLoop):
    """Setup signal handlers for graceful shutdown."""
    def signal_handler():
        logger.info("Received shutdown signal")
        loop.create_task(server.stop())

    # Handle both SIGINT and SIGTERM
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: signal_handler())


async def main():
    """Main entry point."""
    server = DeviceServer()

    try:
        await server.start()
        await server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
