"""
TCP connection wrapper for data logger connections.

Provides a high-level interface for reading and writing data
over TCP connections with timeout and error handling.
"""
import asyncio
import logging
import struct
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class ConnectionState(str, Enum):
    """Connection state enumeration."""
    CONNECTED = "connected"
    IDENTIFYING = "identifying"
    IDENTIFIED = "identified"
    POLLING = "polling"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class TCPConnection:
    """
    Wrapper for asyncio TCP connection.

    Provides high-level methods for reading and writing data,
    with proper timeout handling and connection state tracking.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        connection_id: Optional[UUID] = None,
    ):
        """
        Initialize the connection wrapper.

        Args:
            reader: Asyncio stream reader.
            writer: Asyncio stream writer.
            connection_id: Optional connection ID. Generated if not provided.
        """
        self.reader = reader
        self.writer = writer
        self.connection_id = connection_id or uuid4()

        # Connection info
        self._remote_addr: Optional[Tuple[str, int]] = None
        self._local_addr: Optional[Tuple[str, int]] = None

        # State tracking
        self._state = ConnectionState.CONNECTED
        self._connected_at = datetime.now(timezone.utc)
        self._last_activity = self._connected_at
        self._bytes_received = 0
        self._bytes_sent = 0
        self._error_count = 0

        # Device info (set after identification)
        self._device_id: Optional[UUID] = None
        self._protocol_id: Optional[str] = None
        self._serial_number: Optional[str] = None

        # Extract addresses
        try:
            peername = writer.get_extra_info("peername")
            if peername:
                self._remote_addr = (peername[0], peername[1])
            sockname = writer.get_extra_info("sockname")
            if sockname:
                self._local_addr = (sockname[0], sockname[1])
        except Exception:
            pass

        logger.info(
            f"Connection {self.connection_id} established from {self.remote_addr}"
        )

    @property
    def remote_addr(self) -> str:
        """Get remote address as string."""
        if self._remote_addr:
            return f"{self._remote_addr[0]}:{self._remote_addr[1]}"
        return "unknown"

    @property
    def remote_ip(self) -> str:
        """Get remote IP address."""
        if self._remote_addr:
            return self._remote_addr[0]
        return "unknown"

    @property
    def remote_port(self) -> int:
        """Get remote port."""
        if self._remote_addr:
            return self._remote_addr[1]
        return 0

    @property
    def local_addr(self) -> str:
        """Get local address as string."""
        if self._local_addr:
            return f"{self._local_addr[0]}:{self._local_addr[1]}"
        return "unknown"

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @state.setter
    def state(self, value: ConnectionState) -> None:
        """Set connection state."""
        if self._state != value:
            logger.debug(
                f"Connection {self.connection_id} state: "
                f"{self._state.value} -> {value.value}"
            )
            self._state = value

    @property
    def is_connected(self) -> bool:
        """Check if connection is still active."""
        return self._state not in (
            ConnectionState.DISCONNECTED,
            ConnectionState.ERROR,
        )

    @property
    def device_id(self) -> Optional[UUID]:
        """Get associated device ID."""
        return self._device_id

    @device_id.setter
    def device_id(self, value: UUID) -> None:
        """Set associated device ID."""
        self._device_id = value

    @property
    def protocol_id(self) -> Optional[str]:
        """Get identified protocol ID."""
        return self._protocol_id

    @protocol_id.setter
    def protocol_id(self, value: str) -> None:
        """Set identified protocol ID."""
        self._protocol_id = value

    @property
    def serial_number(self) -> Optional[str]:
        """Get device serial number."""
        return self._serial_number

    @serial_number.setter
    def serial_number(self, value: str) -> None:
        """Set device serial number."""
        self._serial_number = value

    async def read(
        self,
        num_bytes: int,
        timeout: float = 10.0,
    ) -> bytes:
        """
        Read exact number of bytes from connection.

        Args:
            num_bytes: Number of bytes to read.
            timeout: Read timeout in seconds.

        Returns:
            Bytes read from the connection.

        Raises:
            asyncio.TimeoutError: If read times out.
            ConnectionError: If connection is closed or fails.
        """
        if not self.is_connected:
            raise ConnectionError("Connection is not active")

        try:
            data = await asyncio.wait_for(
                self.reader.readexactly(num_bytes),
                timeout=timeout,
            )
            self._bytes_received += len(data)
            self._last_activity = datetime.now(timezone.utc)
            return data
        except asyncio.IncompleteReadError as e:
            # Connection closed while reading
            self._state = ConnectionState.DISCONNECTED
            raise ConnectionError(
                f"Connection closed while reading: got {len(e.partial)} "
                f"of {num_bytes} bytes"
            ) from e
        except asyncio.TimeoutError:
            self._error_count += 1
            raise

    async def read_until(
        self,
        separator: bytes = b"\n",
        timeout: float = 10.0,
        max_bytes: int = 4096,
    ) -> bytes:
        """
        Read until separator is encountered.

        Args:
            separator: Byte sequence to read until.
            timeout: Read timeout in seconds.
            max_bytes: Maximum bytes to read.

        Returns:
            Bytes read including separator.

        Raises:
            asyncio.TimeoutError: If read times out.
            ConnectionError: If connection fails or max bytes exceeded.
        """
        if not self.is_connected:
            raise ConnectionError("Connection is not active")

        try:
            data = await asyncio.wait_for(
                self.reader.readuntil(separator),
                timeout=timeout,
            )
            if len(data) > max_bytes:
                raise ConnectionError(f"Response exceeds maximum size: {len(data)}")
            self._bytes_received += len(data)
            self._last_activity = datetime.now(timezone.utc)
            return data
        except asyncio.LimitOverrunError as e:
            raise ConnectionError(
                f"Response too large (limit: {e.consumed} bytes)"
            ) from e
        except asyncio.IncompleteReadError as e:
            self._state = ConnectionState.DISCONNECTED
            raise ConnectionError(
                f"Connection closed while reading: {len(e.partial)} bytes"
            ) from e
        except asyncio.TimeoutError:
            self._error_count += 1
            raise

    async def read_available(
        self,
        max_bytes: int = 4096,
        timeout: float = 0.1,
    ) -> bytes:
        """
        Read whatever data is available.

        Args:
            max_bytes: Maximum bytes to read.
            timeout: Time to wait for data.

        Returns:
            Available bytes, may be empty.
        """
        if not self.is_connected:
            return b""

        try:
            data = await asyncio.wait_for(
                self.reader.read(max_bytes),
                timeout=timeout,
            )
            if data:
                self._bytes_received += len(data)
                self._last_activity = datetime.now(timezone.utc)
            return data
        except asyncio.TimeoutError:
            return b""
        except Exception:
            return b""

    async def write(
        self,
        data: bytes,
        timeout: float = 10.0,
    ) -> None:
        """
        Write data to the connection.

        Args:
            data: Bytes to write.
            timeout: Write timeout in seconds.

        Raises:
            asyncio.TimeoutError: If write times out.
            ConnectionError: If connection fails.
        """
        if not self.is_connected:
            raise ConnectionError("Connection is not active")

        try:
            self.writer.write(data)
            await asyncio.wait_for(
                self.writer.drain(),
                timeout=timeout,
            )
            self._bytes_sent += len(data)
            self._last_activity = datetime.now(timezone.utc)
        except ConnectionError:
            self._state = ConnectionState.DISCONNECTED
            raise
        except asyncio.TimeoutError:
            self._error_count += 1
            raise

    async def modbus_request(
        self,
        request: bytes,
        expected_length: int,
        timeout: float = 5.0,
    ) -> bytes:
        """
        Send Modbus request and read response.

        For Modbus TCP, adds MBAP header handling.

        Args:
            request: Modbus request bytes.
            expected_length: Expected response length.
            timeout: Request timeout.

        Returns:
            Response bytes.
        """
        await self.write(request, timeout=timeout)
        response = await self.read(expected_length, timeout=timeout)
        return response

    async def send_command(
        self,
        command: str,
        line_ending: str = "\r\n",
        timeout: float = 5.0,
    ) -> str:
        """
        Send text command and read response.

        Args:
            command: Command string to send.
            line_ending: Line ending to append.
            timeout: Command timeout.

        Returns:
            Response string.
        """
        cmd_bytes = (command + line_ending).encode("utf-8")
        await self.write(cmd_bytes, timeout=timeout)

        # Read response until line ending
        response = await self.read_until(
            line_ending.encode("utf-8"),
            timeout=timeout,
        )
        return response.decode("utf-8", errors="replace").strip()

    async def close(self) -> None:
        """Close the connection gracefully."""
        if self._state == ConnectionState.DISCONNECTED:
            return

        logger.info(
            f"Closing connection {self.connection_id} "
            f"(device={self._device_id}, protocol={self._protocol_id})"
        )

        self._state = ConnectionState.DISCONNECTED

        try:
            self.writer.close()
            await asyncio.wait_for(
                self.writer.wait_closed(),
                timeout=5.0,
            )
        except Exception as e:
            logger.debug(f"Error closing connection: {e}")

    def get_stats(self) -> dict:
        """Get connection statistics."""
        now = datetime.now(timezone.utc)
        return {
            "connection_id": str(self.connection_id),
            "remote_addr": self.remote_addr,
            "state": self._state.value,
            "device_id": str(self._device_id) if self._device_id else None,
            "protocol_id": self._protocol_id,
            "serial_number": self._serial_number,
            "connected_at": self._connected_at.isoformat(),
            "uptime_seconds": (now - self._connected_at).total_seconds(),
            "last_activity": self._last_activity.isoformat(),
            "idle_seconds": (now - self._last_activity).total_seconds(),
            "bytes_received": self._bytes_received,
            "bytes_sent": self._bytes_sent,
            "error_count": self._error_count,
        }

    def __repr__(self) -> str:
        return (
            f"TCPConnection("
            f"id={self.connection_id}, "
            f"remote={self.remote_addr}, "
            f"state={self._state.value})"
        )
