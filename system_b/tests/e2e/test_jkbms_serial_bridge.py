"""
E2E tests for the JK BMS serial bridge flow.

Tests the complete chain:
  JKBMSBridgeSimulator (TCP client, mimics ESP32)
    → asyncio TCP server (mimics System B device server framing layer)
      → HELLO detection
      → COMMAND_REQUEST / COMMAND_RESPONSE (binary JK BMS frames)
      → PING / PONG keepalive

The tests reuse the same lightweight _BridgeTestServer pattern as
test_serial_bridge_flow.py but verify binary (not text) response payloads.
"""
import asyncio
import struct
import pytest
from typing import List, Optional, Tuple

from system_b.tests.simulators.jkbms_simulator import (
    JKBMSBridgeSimulator,
    MSG_HELLO,
    MSG_COMMAND_REQUEST,
    MSG_COMMAND_RESPONSE,
    MSG_PING,
    MSG_PONG,
    FRAME_HEADER_SIZE,
)
from device_server.telemetry.jkbms_parser import (
    parse_jkbms_status_frame,
    JKBMS_FRAME_HEADER,
    JKBMS_FRAME_TYPE_STATUS,
)


# ---------------------------------------------------------------------------
# Framing helpers
# ---------------------------------------------------------------------------

def pack_frame(msg_type: int, payload: bytes) -> bytes:
    return struct.pack(">BI", msg_type, len(payload)) + payload


async def recv_frame(reader: asyncio.StreamReader) -> Tuple[int, bytes]:
    header = await asyncio.wait_for(reader.readexactly(FRAME_HEADER_SIZE), timeout=5.0)
    msg_type = header[0]
    payload_len = struct.unpack(">I", header[1:5])[0]
    payload = b""
    if payload_len:
        payload = await asyncio.wait_for(reader.readexactly(payload_len), timeout=5.0)
    return msg_type, payload


# ---------------------------------------------------------------------------
# Reusable minimal bridge test server
# ---------------------------------------------------------------------------

class _BridgeTestServer:
    def __init__(self):
        self._server: Optional[asyncio.AbstractServer] = None
        self._port: Optional[int] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = asyncio.Event()
        self.hello_serial: Optional[str] = None
        self.frames_received: List[Tuple[int, bytes]] = []
        self._cmd_queue: asyncio.Queue = asyncio.Queue()
        self._handler_task: Optional[asyncio.Task] = None

    @property
    def port(self) -> int:
        assert self._port is not None
        return self._port

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_client, "127.0.0.1", 0)
        self._port = self._server.sockets[0].getsockname()[1]
        await self._server.start_serving()

    async def stop(self) -> None:
        if self._handler_task and not self._handler_task.done():
            self._handler_task.cancel()
            try:
                await asyncio.wait_for(self._handler_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass
        if self._server:
            self._server.close()
        if self._writer:
            try:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), timeout=1.0)
            except Exception:
                pass

    async def wait_for_connection(self, timeout: float = 5.0) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout=timeout)

    async def _handle_client(self, reader, writer) -> None:
        self._reader = reader
        self._writer = writer
        self._connected.set()
        self._handler_task = asyncio.current_task()

        try:
            msg_type, payload = await recv_frame(reader)
            self.frames_received.append((msg_type, payload))
            if msg_type == MSG_HELLO:
                self.hello_serial = payload.decode("utf-8", errors="replace").strip()

            while True:
                try:
                    item = self._cmd_queue.get_nowait()
                except asyncio.QueueEmpty:
                    item = None

                if item is not None:
                    out_type, out_payload, future = item
                    frame = pack_frame(out_type, out_payload)
                    writer.write(frame)
                    await writer.drain()
                    resp_type, resp_payload = await asyncio.wait_for(
                        recv_frame(reader), timeout=5.0
                    )
                    self.frames_received.append((resp_type, resp_payload))
                    if not future.done():
                        future.set_result((resp_type, resp_payload))
                else:
                    try:
                        msg_type, payload = await asyncio.wait_for(
                            recv_frame(reader), timeout=0.1
                        )
                        self.frames_received.append((msg_type, payload))
                    except asyncio.TimeoutError:
                        pass

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def send_command(self, timeout: float = 10.0) -> Tuple[int, bytes]:
        """Send an empty COMMAND_REQUEST; return (msg_type, payload)."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        await self._cmd_queue.put((MSG_COMMAND_REQUEST, b"", future))
        return await asyncio.wait_for(future, timeout=timeout)

    async def send_ping(self, timeout: float = 5.0) -> Tuple[int, bytes]:
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        await self._cmd_queue.put((MSG_PING, b"", future))
        return await asyncio.wait_for(future, timeout=timeout)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def bridge_server():
    server = _BridgeTestServer()
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
def jkbms_sim():
    return JKBMSBridgeSimulator(
        data_logger_serial="SH01JKTEST0001",
        num_cells=16,
        initial_soc=78.0,
        total_ah=50.0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _connect_and_run(
    sim: JKBMSBridgeSimulator,
    server: _BridgeTestServer,
) -> asyncio.Task:
    await sim.connect("127.0.0.1", server.port)
    await server.wait_for_connection(timeout=3.0)
    await asyncio.sleep(0.15)
    return asyncio.create_task(sim.run())


async def _teardown(sim: JKBMSBridgeSimulator, task: asyncio.Task) -> None:
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await sim.stop()


# ---------------------------------------------------------------------------
# HELLO handshake tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_hello_serial_received(bridge_server, jkbms_sim):
    """ESP32 must send a HELLO frame with the data logger serial immediately."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        assert bridge_server.hello_serial == "SH01JKTEST0001"
        assert bridge_server.frames_received[0][0] == MSG_HELLO
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_hello_payload_is_utf8(bridge_server, jkbms_sim):
    """HELLO payload must decode to the data logger serial as UTF-8."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        _, payload = bridge_server.frames_received[0]
        assert payload.decode("utf-8") == "SH01JKTEST0001"
    finally:
        await _teardown(jkbms_sim, task)


# ---------------------------------------------------------------------------
# COMMAND_REQUEST / COMMAND_RESPONSE (binary) tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_command_response_type(bridge_server, jkbms_sim):
    """COMMAND_REQUEST must get a COMMAND_RESPONSE (not an error)."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        msg_type, _ = await bridge_server.send_command()
        assert msg_type == MSG_COMMAND_RESPONSE
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_response_starts_with_jkbms_header(bridge_server, jkbms_sim):
    """Binary response payload must start with JK BMS 55 AA EB 90 header."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command()
        assert payload[:4] == JKBMS_FRAME_HEADER
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_response_frame_type_is_status(bridge_server, jkbms_sim):
    """Binary response byte 4 must be 0x02 (status frame type)."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command()
        assert payload[4] == JKBMS_FRAME_TYPE_STATUS
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_response_is_parseable(bridge_server, jkbms_sim):
    """Binary response must be parseable by parse_jkbms_status_frame()."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command()
        result = parse_jkbms_status_frame(payload)
        assert result is not None
        assert "soc" in result
        assert "cell_voltages" in result
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_soc_in_valid_range(bridge_server, jkbms_sim):
    """Parsed SOC must be in 0-100 range."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command()
        result = parse_jkbms_status_frame(payload)
        assert 0 <= result["soc"] <= 100
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_initial_soc_reflected(bridge_server, jkbms_sim):
    """Parsed SOC must match initial_soc=78 from fixture."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command()
        result = parse_jkbms_status_frame(payload)
        assert result["soc"] == 78
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cell_voltages_count(bridge_server, jkbms_sim):
    """Parsed cell voltages list must have 16 entries."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command()
        result = parse_jkbms_status_frame(payload)
        assert len(result["cell_voltages"]) == 16
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cell_voltages_reasonable(bridge_server, jkbms_sim):
    """Each cell voltage must be in LFP operating range (2.5-4.5V)."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command()
        result = parse_jkbms_status_frame(payload)
        for v in result["cell_voltages"]:
            assert 2.5 <= v <= 4.5, f"Cell voltage {v}V out of LFP range"
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_sequential_commands(bridge_server, jkbms_sim):
    """Multiple sequential COMMAND_REQUESTs must all receive valid responses."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        for _ in range(3):
            msg_type, payload = await bridge_server.send_command()
            assert msg_type == MSG_COMMAND_RESPONSE
            result = parse_jkbms_status_frame(payload)
            assert result is not None

        assert jkbms_sim.commands_received == 3
        assert jkbms_sim.responses_sent == 3
    finally:
        await _teardown(jkbms_sim, task)


# ---------------------------------------------------------------------------
# PING / PONG keepalive tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ping_receives_pong(bridge_server, jkbms_sim):
    """Server PING → simulator must reply with PONG."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        msg_type, payload = await bridge_server.send_ping()
        assert msg_type == MSG_PONG
        assert payload == b""
        assert jkbms_sim.pings_received >= 1
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_pings_answered(bridge_server, jkbms_sim):
    """Every PING must receive exactly one PONG."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        for _ in range(3):
            msg_type, _ = await bridge_server.send_ping()
            assert msg_type == MSG_PONG
        assert jkbms_sim.pings_received == 3
    finally:
        await _teardown(jkbms_sim, task)


# ---------------------------------------------------------------------------
# Simulator state tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_counters_track_commands(bridge_server, jkbms_sim):
    """commands_received and responses_sent must track every round-trip."""
    task = await _connect_and_run(jkbms_sim, bridge_server)
    try:
        for _ in range(2):
            await bridge_server.send_command()
        assert jkbms_sim.commands_received == 2
        assert jkbms_sim.responses_sent == 2
    finally:
        await _teardown(jkbms_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_is_connected_flag(bridge_server, jkbms_sim):
    """is_connected must be True after connect() and False after stop()."""
    assert not jkbms_sim.is_connected
    task = await _connect_and_run(jkbms_sim, bridge_server)
    assert jkbms_sim.is_connected
    await _teardown(jkbms_sim, task)
    assert not jkbms_sim.is_connected


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_custom_cell_count(bridge_server):
    """Simulator with num_cells=8 must produce 8 cell voltage entries."""
    sim = JKBMSBridgeSimulator(
        data_logger_serial="SH01JKTEST0002",
        num_cells=8,
        initial_soc=60.0,
    )
    task = await _connect_and_run(sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command()
        result = parse_jkbms_status_frame(payload, cells_per_bms=8)
        assert result is not None
        assert len(result["cell_voltages"]) == 8
    finally:
        await _teardown(sim, task)
