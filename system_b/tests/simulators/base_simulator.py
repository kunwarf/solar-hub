"""
Base simulator class for device simulators.

Provides abstract interface for all device simulators.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class BaseSimulator(ABC):
    """
    Abstract base class for device simulators.

    Provides common functionality for TCP-based device simulation:
    - TCP server management
    - Connection handling
    - Simulation tick loop
    - Statistics tracking
    """

    def __init__(
        self,
        serial_number: str = "SIM001",
        name: str = "Simulator",
    ):
        """
        Initialize base simulator.

        Args:
            serial_number: Device serial number.
            name: Human-readable name for logging.
        """
        self.serial_number = serial_number
        self.name = name

        # Server state
        self._server: Optional[asyncio.AbstractServer] = None
        self._host: str = "127.0.0.1"
        self._port: int = 0
        self._running: bool = False

        # Connection tracking
        self._connections: Dict[str, Tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}
        self._connection_count: int = 0
        self._total_requests: int = 0

        # Simulation state
        self._last_tick: Optional[datetime] = None
        self._tick_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        """Check if simulator is running."""
        return self._running

    @property
    def address(self) -> str:
        """Get server address string."""
        return f"{self._host}:{self._port}"

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> int:
        """
        Start the simulator TCP server.

        Args:
            host: Host to bind to.
            port: Port to bind to (0 for random available port).

        Returns:
            The actual port the server is listening on.
        """
        if self._running:
            logger.warning(f"{self.name}: Already running")
            return self._port

        self._host = host
        self._server = await asyncio.start_server(
            self._handle_client,
            host=host,
            port=port,
        )

        # Get actual port (useful when port=0)
        addr = self._server.sockets[0].getsockname()
        self._port = addr[1]
        self._running = True

        # Start tick loop
        self._tick_task = asyncio.create_task(
            self._tick_loop(),
            name=f"{self.name}_tick_loop"
        )

        logger.info(f"{self.name} started on {self._host}:{self._port}")
        return self._port

    async def stop(self) -> None:
        """Stop the simulator."""
        if not self._running:
            return

        self._running = False

        # Cancel tick task
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for conn_id, (reader, writer) in list(self._connections.items()):
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

        self._connections.clear()

        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        logger.info(f"{self.name} stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle a client connection.

        Args:
            reader: Stream reader for incoming data.
            writer: Stream writer for outgoing data.
        """
        peer = writer.get_extra_info("peername")
        conn_id = f"{peer[0]}:{peer[1]}"
        self._connections[conn_id] = (reader, writer)
        self._connection_count += 1

        logger.debug(f"{self.name}: Client connected from {conn_id}")

        try:
            await self.handle_connection(reader, writer)
        except asyncio.CancelledError:
            pass
        except ConnectionResetError:
            logger.debug(f"{self.name}: Connection reset by {conn_id}")
        except Exception as e:
            logger.error(f"{self.name}: Error handling {conn_id}: {e}")
        finally:
            self._connections.pop(conn_id, None)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.debug(f"{self.name}: Client {conn_id} disconnected")

    @abstractmethod
    async def handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle client connection.

        Subclasses must implement protocol-specific handling.

        Args:
            reader: Stream reader for incoming data.
            writer: Stream writer for outgoing data.
        """
        pass

    def simulate_tick(self, dt: float) -> None:
        """
        Update simulation state.

        Called periodically to update simulated values.
        Override in subclasses to implement realistic behavior.

        Args:
            dt: Time delta since last tick in seconds.
        """
        pass

    async def _tick_loop(self, interval: float = 1.0) -> None:
        """
        Background tick loop for simulation updates.

        Args:
            interval: Time between ticks in seconds.
        """
        self._last_tick = datetime.now(timezone.utc)

        while self._running:
            try:
                await asyncio.sleep(interval)

                now = datetime.now(timezone.utc)
                dt = (now - self._last_tick).total_seconds()
                self._last_tick = now

                self.simulate_tick(dt)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"{self.name}: Error in tick loop: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get simulator statistics.

        Returns:
            Dictionary of statistics.
        """
        return {
            "name": self.name,
            "serial_number": self.serial_number,
            "running": self._running,
            "address": self.address if self._running else None,
            "active_connections": len(self._connections),
            "total_connections": self._connection_count,
            "total_requests": self._total_requests,
        }

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return f"<{self.__class__.__name__}({self.serial_number}) {status}>"
