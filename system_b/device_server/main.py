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
from .storage.redis_cache import TelemetryCacheWriter
from .storage.device_registry_client import DeviceRegistryClient
from .storage.command_db_client import CommandDatabaseClient
from .commands.command_executor import ModbusCommandExecutor
from .workers.command_worker import CommandWorker

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
        self.redis_cache: Optional[TelemetryCacheWriter] = None
        self.device_registry_client: Optional[DeviceRegistryClient] = None
        self.command_db_client: Optional[CommandDatabaseClient] = None
        self.command_executor: Optional[ModbusCommandExecutor] = None
        self.command_worker: Optional[CommandWorker] = None

        # State
        self._running = False
        self._shutdown_event = asyncio.Event()
        # In-memory set of data logger serials already paired this session.
        # Prevents two inverters from racing to claim the same orphan data logger.
        self._claimed_data_loggers: set = set()

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
            device_manager=self.device_manager,
            settings=self.settings,
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
        self.redis_cache = TelemetryCacheWriter(self.settings)
        self.device_registry_client = DeviceRegistryClient(self.settings)

        await self.timescale_writer.connect()
        await self.system_a_client.connect()
        await self.redis_cache.connect()
        try:
            await self.device_registry_client.connect()
        except Exception as e:
            logger.warning(f"Device registry client connection failed: {e} - serial linking disabled")

        # Start polling scheduler
        await self.polling_scheduler.start()

        # Initialize command database client
        self.command_db_client = CommandDatabaseClient(self.settings.device_registry_db)
        await self.command_db_client.connect()

        # Initialize command executor with device registry for UUID to serial mapping
        self.command_executor = ModbusCommandExecutor(
            self.device_manager,
            device_registry_client=self.device_registry_client
        )
        self.command_worker = CommandWorker(
            poll_interval=5.0,
            batch_size=10,
        )
        self.command_worker.set_executor(self.command_executor)

        # Wire database callbacks for command queue
        logger.info("[DEVICE_SERVER] Wiring command worker database callbacks...")
        self.command_worker.set_fetch_pending(self.command_db_client.fetch_pending_commands)
        self.command_worker.set_mark_sent(self.command_db_client.mark_sent)
        self.command_worker.set_mark_completed(self.command_db_client.mark_completed)
        self.command_worker.set_mark_failed(self.command_db_client.mark_failed)
        self.command_worker.set_expire_stale(self.command_db_client.expire_stale_commands)
        logger.info("[DEVICE_SERVER] Command worker database callbacks wired successfully")

        await self.command_worker.start()

        # Start TCP server
        self.tcp_server = TCPServer(
            connection_handler=self.connection_manager.handle_connection,
            settings=self.settings,
        )
        await self.tcp_server.start()

        self._running = True
        logger.info(
            f"Device Server started on "
            f"{self.settings.server.host}:{self.settings.server.port}"
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

        # Stop command worker
        if self.command_worker:
            await self.command_worker.stop()

        # Shutdown device manager
        if self.device_manager:
            await self.device_manager.shutdown()

        # Disconnect storage
        if self.timescale_writer:
            await self.timescale_writer.disconnect()

        if self.system_a_client:
            await self.system_a_client.disconnect()

        if self.redis_cache:
            await self.redis_cache.disconnect()

        if self.device_registry_client:
            await self.device_registry_client.disconnect()

        if self.command_db_client:
            await self.command_db_client.disconnect()

        logger.info("Device Server stopped")

    async def serve_forever(self) -> None:
        """Run the server until shutdown."""
        await self._shutdown_event.wait()

    def _load_protocols(self) -> ProtocolRegistry:
        """Load protocol definitions."""
        registry = ProtocolRegistry()
        loader = ProtocolLoader()

        # Load from config directory
        config_path = self.settings.protocols_file
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
        # For serial bridge devices (identified via HELLO frame), the serial number
        # sent in the HELLO IS the data logger serial — no inverter lookup needed.
        is_bridged = bool(
            device_state.extra_data and device_state.extra_data.get("bridged")
        )

        if is_bridged:
            # HELLO serial = data logger serial; set directly and skip Modbus linking
            device_state.data_logger_serial = device_state.serial_number
            logger.info(
                f"Serial bridge device {device_state.serial_number}: "
                f"data_logger_serial set from HELLO"
            )
        elif self.device_registry_client:
            # Link Modbus-identified inverter serial with data logger serial from
            # self-registration. This is critical for telemetry caching — we cache
            # under the data logger serial which is what the user sees on the device.
            data_logger_serial = await self.device_registry_client.get_device_by_inverter_serial(
                device_state.serial_number
            )

            if not data_logger_serial:
                # Look for a recently self-registered orphan device of the same type.
                # Check _claimed_data_loggers BEFORE awaiting to avoid the race where
                # two inverters connect simultaneously and both see the same unclaimed
                # data logger before either commits the DB update.
                candidate = await self.device_registry_client.get_recently_connected_serial(
                    device_type=device_state.device_type,
                    within_minutes=10,
                )

                if candidate and candidate not in self._claimed_data_loggers:
                    # Claim it immediately (no await between check and add)
                    self._claimed_data_loggers.add(candidate)
                    data_logger_serial = candidate
                    # Link the inverter serial to this data logger for future lookups
                    await self.device_registry_client.update_inverter_serial(
                        data_logger_serial=data_logger_serial,
                        inverter_serial=device_state.serial_number,
                    )
                elif candidate:
                    logger.warning(
                        f"Data logger {candidate} already claimed this session, "
                        f"inverter {device_state.serial_number} has no paired data logger. "
                        f"Telemetry will be cached under inverter serial."
                    )

            if data_logger_serial:
                self._claimed_data_loggers.add(data_logger_serial)
                logger.info(
                    f"Linked device: data_logger={data_logger_serial}, "
                    f"inverter={device_state.serial_number}"
                )
                device_state.data_logger_serial = data_logger_serial
            else:
                logger.warning(
                    f"No data logger serial found for inverter {device_state.serial_number}. "
                    f"Telemetry will be cached under inverter serial."
                )

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
        # Update Redis cache with new status
        device_state = self.device_manager.get_device(device_id)
        if self.redis_cache and device_state:
            # Use data_logger_serial for Redis caching (matches System A lookups)
            cache_serial = device_state.data_logger_serial or device_state.serial_number
            if cache_serial:
                status_str = "online" if new_status == DeviceStatus.ONLINE else "offline"
                await self.redis_cache.write_status(cache_serial, status_str)

    async def _on_telemetry(
        self,
        device_id: UUID,
        telemetry: dict,
    ) -> None:
        """Handle collected telemetry."""
        device_state = self.device_manager.get_device(device_id) if self.device_manager else None

        # Determine which device_id to use for telemetry storage
        # If this is an inverter linked to a data logger, use the data logger's device_id
        # (because the data logger has a stable device_id and site_id in device_registry)
        storage_device_id = device_id  # Default to current device

        if device_state and device_state.data_logger_serial:
            # Look up the data logger's device_id from device_registry
            data_logger_info = await self.device_registry_client.get_device_by_serial(
                device_state.data_logger_serial
            )
            if data_logger_info:
                storage_device_id = data_logger_info["device_id"]
                logger.debug(
                    f"Using data logger device_id {storage_device_id} for telemetry storage "
                    f"(inverter device_id: {device_id}, inverter serial: {device_state.serial_number})"
                )
            else:
                logger.warning(
                    f"Data logger {device_state.data_logger_serial} not found in registry, "
                    f"using inverter device_id {device_id} for storage"
                )

        # Write to TimescaleDB for historical storage
        if self.timescale_writer:
            await self.timescale_writer.write(storage_device_id, telemetry.copy())

        # Write to Redis cache for real-time access by System A
        # Use data_logger_serial (the serial printed on the device that users see)
        # for Redis caching, as this is what System A uses to look up telemetry
        # Prefer data_logger_serial (from self-registration), fall back to Modbus serial
        if device_state and device_state.data_logger_serial:
            cache_serial = device_state.data_logger_serial
            logger.debug(
                f"Caching telemetry under data logger serial: {cache_serial} "
                f"(inverter serial: {device_state.serial_number})"
            )
        else:
            cache_serial = telemetry.get("_serial_number")

        if self.redis_cache and cache_serial:
            await self.redis_cache.write_telemetry(cache_serial, telemetry.copy())

    async def _on_poll_device_offline(
        self,
        device_id: UUID,
        device_state,
    ) -> None:
        """Handle device going offline due to poll failures."""
        # Update Redis cache with offline status
        if self.redis_cache and device_state:
            # Use data_logger_serial for Redis caching (matches System A lookups)
            cache_serial = device_state.data_logger_serial or device_state.serial_number
            if cache_serial:
                await self.redis_cache.write_status(cache_serial, "offline")

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

        if self.command_worker:
            stats["command_worker"] = self.command_worker.get_stats()

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
