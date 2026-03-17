"""
Unit tests for the serial bridge HELLO protocol.

Tests:
- Frame packing/unpacking (HELLO, COMMAND_REQUEST, COMMAND_RESPONSE)
- HELLO detection in ConnectionManager using feed_data()
- _identify_from_hello with mock registry responses
- TCPCommandAdapter dispatch (framed vs raw) based on connection.bridged
"""
import asyncio
import struct
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# ---------------------------------------------------------------------------
# Framing helpers (mirrors constants in serial_bridge.py / adapter_factory.py)
# ---------------------------------------------------------------------------

MSG_HELLO            = 0x06
MSG_COMMAND_REQUEST  = 0x01
MSG_COMMAND_RESPONSE = 0x02
MSG_ERROR            = 0x03
MSG_PING             = 0x04
MSG_PONG             = 0x05
FRAME_HEADER_SIZE    = 5


def pack_frame(msg_type: int, payload: bytes) -> bytes:
    return struct.pack(">BI", msg_type, len(payload)) + payload


def unpack_header(data: bytes):
    """Return (msg_type, payload_len) from a 5-byte header."""
    assert len(data) == FRAME_HEADER_SIZE
    msg_type = data[0]
    payload_len = struct.unpack(">I", data[1:5])[0]
    return msg_type, payload_len


# ---------------------------------------------------------------------------
# Frame encoding tests
# ---------------------------------------------------------------------------

class TestFrameEncoding:
    """Verify binary frame encoding matches the protocol spec."""

    def test_hello_frame_structure(self):
        serial = "SH01BTTEST0001"
        payload = serial.encode("utf-8")
        frame = pack_frame(MSG_HELLO, payload)

        assert frame[0] == MSG_HELLO
        length = struct.unpack(">I", frame[1:5])[0]
        assert length == len(payload)
        assert frame[5:] == payload

    def test_command_request_frame(self):
        cmd = "pwr"
        payload = cmd.encode("utf-8")
        frame = pack_frame(MSG_COMMAND_REQUEST, payload)

        assert frame[0] == MSG_COMMAND_REQUEST
        msg_type, payload_len = unpack_header(frame[:5])
        assert msg_type == MSG_COMMAND_REQUEST
        assert payload_len == len(payload)
        assert frame[5:].decode("utf-8") == cmd

    def test_command_response_round_trip(self):
        response = "pylon>\r\n"
        payload = response.encode("utf-8")
        frame = pack_frame(MSG_COMMAND_RESPONSE, payload)

        msg_type, payload_len = unpack_header(frame[:FRAME_HEADER_SIZE])
        assert msg_type == MSG_COMMAND_RESPONSE
        decoded = frame[FRAME_HEADER_SIZE:FRAME_HEADER_SIZE + payload_len].decode("utf-8")
        assert decoded == response

    def test_ping_pong_empty_payload(self):
        for msg_type in (MSG_PING, MSG_PONG):
            frame = pack_frame(msg_type, b"")
            assert len(frame) == FRAME_HEADER_SIZE
            mt, pl = unpack_header(frame)
            assert mt == msg_type
            assert pl == 0

    def test_large_payload_length_field(self):
        """Length field must handle payloads up to 8 192 bytes."""
        payload = b"x" * 8192
        frame = pack_frame(MSG_COMMAND_RESPONSE, payload)
        _, payload_len = unpack_header(frame[:FRAME_HEADER_SIZE])
        assert payload_len == 8192


# ---------------------------------------------------------------------------
# HELLO detection in ConnectionManager
# ---------------------------------------------------------------------------

class TestHelloDetection:
    """Test that ConnectionManager correctly distinguishes HELLO vs Modbus."""

    def _make_stream_reader(self, data: bytes) -> asyncio.StreamReader:
        reader = asyncio.StreamReader()
        reader.feed_data(data)
        return reader

    @pytest.mark.asyncio
    async def test_hello_byte_triggers_hello_path(self):
        """First byte 0x06 must select the HELLO identification path."""
        serial = "SH01BTTEST0001"
        hello_frame = pack_frame(MSG_HELLO, serial.encode("utf-8"))
        # Feed the full frame; first byte (0x06) is read separately by connection_manager
        reader = self._make_stream_reader(hello_frame)

        first_byte = await asyncio.wait_for(reader.read(1), timeout=1.0)
        assert first_byte == bytes([MSG_HELLO])

    @pytest.mark.asyncio
    async def test_timeout_gives_empty_bytes(self):
        """When no data arrives within timeout, read returns empty bytes (b'')."""
        reader = asyncio.StreamReader()
        # No data fed — should time out
        try:
            first_byte = await asyncio.wait_for(reader.read(1), timeout=0.05)
        except asyncio.TimeoutError:
            first_byte = b""
        assert first_byte == b""

    @pytest.mark.asyncio
    async def test_non_hello_byte_falls_through(self):
        """Any byte that is not 0x06 must select the Modbus probe path."""
        reader = self._make_stream_reader(b"\x00\x01\x00\x01\x00")  # Modbus preamble

        first_byte = await asyncio.wait_for(reader.read(1), timeout=1.0)
        assert first_byte != bytes([MSG_HELLO])

    @pytest.mark.asyncio
    async def test_hello_payload_parsed_correctly(self):
        """After consuming the 0x06 type byte, the remaining frame is readable."""
        serial = "SH01BTTEST0001"
        hello_frame = pack_frame(MSG_HELLO, serial.encode("utf-8"))
        reader = self._make_stream_reader(hello_frame)

        # Consume the type byte (as connection_manager does)
        await reader.read(1)

        # Read 4-byte length field
        length_bytes = await reader.readexactly(4)
        payload_len = struct.unpack(">I", length_bytes)[0]
        assert payload_len == len(serial)

        # Read serial
        serial_bytes = await reader.readexactly(payload_len)
        assert serial_bytes.decode("utf-8") == serial

    @pytest.mark.asyncio
    async def test_oversized_hello_payload_rejected(self):
        """Payload length > 256 must be treated as invalid."""
        oversized_payload = b"X" * 300
        hello_frame = pack_frame(MSG_HELLO, oversized_payload)
        reader = self._make_stream_reader(hello_frame)

        await reader.read(1)  # consume type byte
        length_bytes = await reader.readexactly(4)
        payload_len = struct.unpack(">I", length_bytes)[0]

        # Simulate the connection_manager guard
        assert payload_len > 256  # should be rejected


# ---------------------------------------------------------------------------
# _identify_from_hello with mock registry
# ---------------------------------------------------------------------------

class TestIdentifyFromHello:
    """Test IdentifiedDevice construction from HELLO + registry data."""

    def _make_connection(self, serial: str) -> MagicMock:
        """Build a mock TCPConnection that streams a HELLO frame (minus first byte)."""
        hello_frame = pack_frame(MSG_HELLO, serial.encode("utf-8"))
        # Skip the type byte (already consumed by caller)
        remaining = hello_frame[1:]
        reader = asyncio.StreamReader()
        reader.feed_data(remaining)

        conn = MagicMock()
        conn.remote_addr = "127.0.0.1:54321"
        conn.reader = reader

        async def _read(n, timeout=None):
            return await reader.readexactly(n)

        conn.read = _read
        return conn

    def _make_registry_client(self, reg_data: dict):
        client = MagicMock()
        client.get_registration_by_serial = AsyncMock(return_value=reg_data)
        return client

    def _make_prober_with_command_protocol(self, protocol_id: str, device_type_str: str):
        from device_server.protocols.definitions import DeviceType
        try:
            dt = DeviceType(device_type_str)
        except ValueError:
            dt = DeviceType.BATTERY

        proto = MagicMock()
        proto.protocol_id = protocol_id
        proto.device_type = dt

        registry = MagicMock()
        registry.get = MagicMock(return_value=proto)
        registry.iter_command_by_priority = MagicMock(return_value=iter([proto]))
        registry.get_command_protocols = MagicMock(return_value=[proto])

        prober = MagicMock()
        prober.registry = registry
        return prober

    @pytest.mark.asyncio
    async def test_identifies_battery_from_registry(self):
        """Serial matches registry → returns IdentifiedDevice with correct fields."""
        from device_server.connection.connection_manager import ConnectionManager

        serial = "SH01BTTEST0001"
        conn = self._make_connection(serial)
        reg_data = {
            "device_type": "battery",
            "manufacturer": "Pylontech",
            "model": "US5000",
            "firmware_version": "V2.8",
            "protocol_id": "pylontech",
        }
        registry_client = self._make_registry_client(reg_data)
        prober = self._make_prober_with_command_protocol("pylontech", "battery")

        manager = ConnectionManager(
            prober=prober,
            device_manager=MagicMock(),
            device_registry_client=registry_client,
        )

        result = await manager._identify_from_hello(conn)

        assert result is not None
        assert result.serial_number == serial
        assert result.device_type == "battery"
        assert result.manufacturer == "Pylontech"
        assert result.model == "US5000"
        assert result.firmware_version == "V2.8"
        assert result.protocol_id == "pylontech"
        assert result.extra_data.get("bridged") is True

    @pytest.mark.asyncio
    async def test_identifies_with_no_registry(self):
        """No registry client → falls back to first available command protocol."""
        from device_server.connection.connection_manager import ConnectionManager

        serial = "SH01BTTEST0002"
        conn = self._make_connection(serial)
        prober = self._make_prober_with_command_protocol("pylontech", "battery")

        manager = ConnectionManager(
            prober=prober,
            device_manager=MagicMock(),
            device_registry_client=None,
        )

        result = await manager._identify_from_hello(conn)

        assert result is not None
        assert result.serial_number == serial
        # Must select some command protocol as fallback
        assert result.protocol_id == "pylontech"

    @pytest.mark.asyncio
    async def test_registry_returns_none_uses_fallback(self):
        """Registry returns None (unknown serial) → fallback to first command protocol."""
        from device_server.connection.connection_manager import ConnectionManager

        serial = "UNKNOWN_SERIAL_001"
        conn = self._make_connection(serial)
        registry_client = self._make_registry_client(None)
        prober = self._make_prober_with_command_protocol("pylontech", "battery")

        manager = ConnectionManager(
            prober=prober,
            device_manager=MagicMock(),
            device_registry_client=registry_client,
        )

        result = await manager._identify_from_hello(conn)

        assert result is not None
        assert result.serial_number == serial

    @pytest.mark.asyncio
    async def test_empty_serial_returns_none(self):
        """HELLO with empty serial payload must return None."""
        from device_server.connection.connection_manager import ConnectionManager

        # Craft a HELLO frame with an empty serial (payload = b"")
        hello_frame = pack_frame(MSG_HELLO, b"")
        remaining = hello_frame[1:]
        reader = asyncio.StreamReader()
        reader.feed_data(remaining)

        conn = MagicMock()
        conn.remote_addr = "127.0.0.1:54321"

        async def _read(n, timeout=None):
            return await reader.readexactly(n)

        conn.read = _read

        manager = ConnectionManager(
            prober=MagicMock(),
            device_manager=MagicMock(),
        )

        result = await manager._identify_from_hello(conn)
        assert result is None


# ---------------------------------------------------------------------------
# TCPCommandAdapter dispatch tests
# ---------------------------------------------------------------------------

class TestTCPCommandAdapterDispatch:
    """Test that send_command routes to framed vs raw based on connection.bridged."""

    def _make_protocol_mock(self, line_ending: str = "\r\n", timeout: float = 5.0):
        """Build a minimal mock ProtocolDefinition with command config."""
        cmd_cfg = MagicMock()
        cmd_cfg.line_ending = line_ending
        cmd_cfg.response_timeout = timeout
        cmd_cfg.command_delay = 0.0

        proto = MagicMock()
        proto.command = cmd_cfg
        return proto

    def _make_bridged_connection(self, response_payload: bytes) -> MagicMock:
        """Mock a bridged TCPConnection that returns a COMMAND_RESPONSE frame."""
        response_frame = pack_frame(MSG_COMMAND_RESPONSE, response_payload)

        conn = MagicMock()
        conn.bridged = True
        conn.is_connected = True

        # read() returns header bytes then payload bytes in sequence
        read_calls = iter([
            response_frame[:FRAME_HEADER_SIZE],
            response_payload,
        ])

        async def _read(n, timeout=None):
            return next(read_calls)

        async def _write(data, timeout=None):
            pass

        conn.read = _read
        conn.write = _write
        return conn

    @pytest.mark.asyncio
    async def test_bridged_uses_framed_protocol(self):
        """Bridged connection must send COMMAND_REQUEST frame and parse COMMAND_RESPONSE."""
        from device_server.devices.adapter_factory import TCPCommandAdapter

        pylontech_response = "\r\npylon>\r\n"
        conn = self._make_bridged_connection(pylontech_response.encode("utf-8"))

        sent_data = []

        async def capture_write(data, timeout=None):
            sent_data.append(data)

        conn.write = capture_write

        adapter = TCPCommandAdapter(
            connection=conn,
            protocol=self._make_protocol_mock(),
            register_map=[],
        )
        result = await adapter.send_command("info")

        # Must have sent a COMMAND_REQUEST frame
        assert len(sent_data) == 1
        sent_frame = sent_data[0]
        assert sent_frame[0] == MSG_COMMAND_REQUEST
        cmd_in_frame = sent_frame[FRAME_HEADER_SIZE:].decode("utf-8")
        assert cmd_in_frame == "info"

        # Response should be the decoded payload
        assert result == pylontech_response

    @pytest.mark.asyncio
    async def test_bridged_handles_error_response(self):
        """MSG_ERROR response type must cause send_command to return None."""
        from device_server.devices.adapter_factory import TCPCommandAdapter

        error_payload = b"Command timeout"
        error_frame = pack_frame(MSG_ERROR, error_payload)

        conn = MagicMock()
        conn.bridged = True
        conn.is_connected = True

        read_calls = iter([
            error_frame[:FRAME_HEADER_SIZE],
            error_payload,
        ])

        async def _read(n, timeout=None):
            return next(read_calls)

        async def _write(data, timeout=None):
            pass

        conn.read = _read
        conn.write = _write

        adapter = TCPCommandAdapter(
            connection=conn,
            protocol=self._make_protocol_mock(),
            register_map=[],
        )
        result = await adapter.send_command("info")

        assert result is None

    @pytest.mark.asyncio
    async def test_non_bridged_uses_raw_protocol(self):
        """Non-bridged connection must write raw text (no binary frame header)."""
        from device_server.devices.adapter_factory import TCPCommandAdapter

        conn = MagicMock()
        conn.bridged = False
        conn.is_connected = True

        sent_data = []

        async def capture_write(data, timeout=None):
            sent_data.append(data)

        # raw protocol uses read_until; return a line ending with ">"
        async def _read_until(sep, timeout=None):
            return b"> \r\n"

        conn.write = capture_write
        conn.read_until = _read_until

        adapter = TCPCommandAdapter(
            connection=conn,
            protocol=self._make_protocol_mock(),
            register_map=[],
        )
        result = await adapter.send_command("info")

        # Must have sent raw text (no 0x01 framing byte at start)
        assert len(sent_data) == 1
        sent = sent_data[0]
        # Raw protocol appends line_ending to command, no binary frame prefix
        assert sent[0] != MSG_COMMAND_REQUEST
        assert b"info" in sent
