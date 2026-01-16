"""
TCP server for accepting data logger connections.

Provides an asyncio-based TCP server that accepts connections
from solar device data loggers and routes them for identification.
"""
import asyncio
import logging
import signal
from typing import Callable, Optional, Set

from ..config import DeviceServerSettings, get_device_server_settings
from .tcp_connection import TCPConnection

logger = logging.getLogger(__name__)


# Type for connection handler callback
ConnectionHandler = Callable[[TCPConnection], asyncio.Task]


class TCPServer:
    """
    TCP server for data logger connections.

    Accepts incoming TCP connections from solar device data loggers,
    wraps them in TCPConnection objects, and routes them to the
    connection manager for identification and handling.
    """

    def __init__(
        self,
        connection_handler: ConnectionHandler,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the TCP server.

        Args:
            connection_handler: Callback to handle new connections.
                               Should return an asyncio.Task for the connection.
            settings: Server settings. Uses defaults if not provided.
        """
        self.settings = settings or get_device_server_settings()
        self._connection_handler = connection_handler

        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._connections: Set[TCPConnection] = set()
        self._connection_tasks: Set[asyncio.Task] = set()

        # Statistics
        self._total_connections = 0
        self._rejected_connections = 0

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running and self._server is not None

    @property
    def active_connections(self) -> int:
        """Get count of active connections."""
        return len(self._connections)

    @property
    def total_connections(self) -> int:
        """Get total connections since start."""
        return self._total_connections

    async def start(self) -> None:
        """
        Start the TCP server.

        Binds to the configured host and port and begins accepting
        connections from data loggers.

        Raises:
            OSError: If the port is already in use.
        """
        if self._running:
            logger.warning("Server is already running")
            return

        host = self.settings.server.host
        port = self.settings.server.port

        logger.info(f"Starting TCP server on {host}:{port}")

        self._server = await asyncio.start_server(
            self._handle_connection,
            host=host,
            port=port,
            backlog=self.settings.server.backlog,
        )

        self._running = True

        # Get actual bound addresses
        addrs = []
        for sock in self._server.sockets:
            addr = sock.getsockname()
            addrs.append(f"{addr[0]}:{addr[1]}")

        logger.info(f"TCP server listening on: {', '.join(addrs)}")

    async def stop(self, timeout: float = 10.0) -> None:
        """
        Stop the TCP server gracefully.

        Stops accepting new connections and waits for existing
        connections to close.

        Args:
            timeout: Maximum time to wait for connections to close.
        """
        if not self._running:
            return

        logger.info("Stopping TCP server...")
        self._running = False

        if self._server:
            # Stop accepting new connections
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # Close all active connections
        if self._connections:
            logger.info(f"Closing {len(self._connections)} active connections")

            close_tasks = [
                asyncio.create_task(conn.close())
                for conn in self._connections
            ]

            try:
                await asyncio.wait_for(
                    asyncio.gather(*close_tasks, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for connections to close")

        # Cancel any remaining tasks
        for task in self._connection_tasks:
            if not task.done():
                task.cancel()

        self._connections.clear()
        self._connection_tasks.clear()

        logger.info("TCP server stopped")

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle new incoming connection.

        Args:
            reader: Asyncio stream reader.
            writer: Asyncio stream writer.
        """
        # Check connection limit
        if len(self._connections) >= self.settings.server.max_connections:
            logger.warning(
                f"Connection limit reached ({self.settings.server.max_connections}), "
                f"rejecting new connection"
            )
            self._rejected_connections += 1
            writer.close()
            await writer.wait_closed()
            return

        # Create connection wrapper
        connection = TCPConnection(reader, writer)
        self._connections.add(connection)
        self._total_connections += 1

        logger.info(
            f"New connection from {connection.remote_addr} "
            f"(active: {len(self._connections)})"
        )

        try:
            # Delegate to connection handler
            task = self._connection_handler(connection)
            self._connection_tasks.add(task)

            # Add cleanup callback
            task.add_done_callback(
                lambda t: self._connection_done(connection, t)
            )

        except Exception as e:
            logger.error(f"Error handling connection: {e}")
            await connection.close()
            self._connections.discard(connection)

    def _connection_done(
        self,
        connection: TCPConnection,
        task: asyncio.Task,
    ) -> None:
        """
        Callback when connection handling completes.

        Args:
            connection: The connection that completed.
            task: The completed task.
        """
        self._connections.discard(connection)
        self._connection_tasks.discard(task)

        # Log any exceptions
        if task.done() and not task.cancelled():
            exc = task.exception()
            if exc:
                logger.error(
                    f"Connection {connection.connection_id} ended with error: {exc}"
                )
            else:
                logger.debug(f"Connection {connection.connection_id} completed")

    async def serve_forever(self) -> None:
        """
        Run the server until stopped.

        This is the main entry point for running the server.
        It will block until the server is stopped via stop() or
        a shutdown signal is received.
        """
        if not self._running:
            await self.start()

        # Setup signal handlers
        loop = asyncio.get_running_loop()

        try:
            # On Windows, signal handling is limited
            import platform
            if platform.system() != "Windows":
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(
                        sig,
                        lambda: asyncio.create_task(self.stop()),
                    )
        except NotImplementedError:
            pass  # Signal handlers not supported

        logger.info("Server is running. Press Ctrl+C to stop.")

        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1.0)

    def get_stats(self) -> dict:
        """Get server statistics."""
        return {
            "running": self._running,
            "host": self.settings.server.host,
            "port": self.settings.server.port,
            "active_connections": len(self._connections),
            "total_connections": self._total_connections,
            "rejected_connections": self._rejected_connections,
            "max_connections": self.settings.server.max_connections,
            "connections": [conn.get_stats() for conn in self._connections],
        }

    def list_connections(self) -> list:
        """Get list of active connections."""
        return [conn.get_stats() for conn in self._connections]
