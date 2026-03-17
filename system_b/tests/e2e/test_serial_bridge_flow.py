"""
E2E tests for the Pylontech serial bridge flow.

Tests the complete chain:
  PylontechBridgeSimulator (TCP client, mimics ESP32)
    → asyncio TCP server (mimics System B device server framing layer)
      → HELLO detection
      → COMMAND_REQUEST / COMMAND_RESPONSE framing
      → PING / PONG keepalive

The tests use a lightweight asyncio TCP server that speaks the same
length-prefixed binary protocol as the real ConnectionManager /
TCPCommandAdapter, without requiring the full System B stack.
"""
import asyncio
import struct
import pytest
from typing import List, Optional, Tuple

from system_b.tests.simulators.pylontech_simulator import (
    PylontechBridgeSimulator,
    MSG_HELLO,
    MSG_COMMAND_REQUEST,
    MSG_COMMAND_RESPONSE,
    MSG_PING,
    MSG_PONG,
    FRAME_HEADER_SIZE,
)


# ---------------------------------------------------------------------------
# Framing helpers
# ---------------------------------------------------------------------------

def pack_frame(msg_type: int, payload: bytes) -> bytes:
    return struct.pack(">BI", msg_type, len(payload)) + payload


async def recv_frame(reader: asyncio.StreamReader) -> Tuple[int, bytes]:
    """Read one length-prefixed frame; return (msg_type, payload)."""
    header = await asyncio.wait_for(reader.readexactly(FRAME_HEADER_SIZE), timeout=5.0)
    msg_type = header[0]
    payload_len = struct.unpack(">I", header[1:5])[0]
    payload = b""
    if payload_len:
        payload = await asyncio.wait_for(reader.readexactly(payload_len), timeout=5.0)
    return msg_type, payload


# ---------------------------------------------------------------------------
# Minimal server that exercises the bridge protocol
# ---------------------------------------------------------------------------

class _BridgeTestServer:
    """
    Minimal asyncio TCP server for bridge protocol testing.

    Records frames received from the client and provides helpers to
    send frames back.  Designed for single-client use in tests.
    """

    def __init__(self):
        self._server: Optional[asyncio.AbstractServer] = None
        self._port: Optional[int] = None

        # Set when a client connects
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = asyncio.Event()

        # All frames received (including HELLO)
        self.hello_serial: Optional[str] = None
        self.frames_received: List[Tuple[int, bytes]] = []

        # Queue of (command_str, Future) for tests to send commands
        self._cmd_queue: asyncio.Queue = asyncio.Queue()

        # Internal task running the per-connection dispatch loop
        self._handler_task: Optional[asyncio.Task] = None

    @property
    def port(self) -> int:
        assert self._port is not None, "Server not started"
        return self._port

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, "127.0.0.1", 0
        )
        self._port = self._server.sockets[0].getsockname()[1]
        # Explicitly start serving (needed on some Python versions)
        await self._server.start_serving()

    async def stop(self) -> None:
        """Tear down the server without blocking on active connections."""
        # Cancel the dispatch task first so the connection handler exits
        if self._handler_task and not self._handler_task.done():
            self._handler_task.cancel()
            try:
                await asyncio.wait_for(self._handler_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                pass

        # Close the server — do NOT call wait_closed() while a connection
        # handler is active; that would block until all connections close.
        if self._server:
            self._server.close()

        # Now close the writer so the remote peer gets an EOF
        if self._writer:
            try:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), timeout=1.0)
            except Exception:
                pass

    async def wait_for_connection(self, timeout: float = 5.0) -> None:
        """Block until a client connects."""
        await asyncio.wait_for(self._connected.wait(), timeout=timeout)

    # ------------------------------------------------------------------
    # Per-connection handler (called by asyncio.start_server)
    # ------------------------------------------------------------------

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._connected.set()

        # Capture this task so stop() can cancel it
        self._handler_task = asyncio.current_task()

        try:
            # First frame must be HELLO
            msg_type, payload = await recv_frame(reader)
            self.frames_received.append((msg_type, payload))
            if msg_type == MSG_HELLO:
                self.hello_serial = payload.decode("utf-8", errors="replace").strip()

            # Dispatch loop
            # Queue items: (msg_type, payload_bytes_or_none, cmd_str_or_none, future)
            # - For COMMAND_REQUEST: (MSG_COMMAND_REQUEST, None, cmd_str, future)
            # - For PING:            (MSG_PING, b"", None, future)
            while True:
                try:
                    item = self._cmd_queue.get_nowait()
                except asyncio.QueueEmpty:
                    item = None

                if item is not None:
                    out_type, out_payload, cmd_str, future = item
                    if out_type == MSG_COMMAND_REQUEST:
                        frame = pack_frame(MSG_COMMAND_REQUEST, cmd_str.encode("utf-8"))
                    else:
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
                    # Nothing queued — wait briefly for spontaneous frames
                    try:
                        msg_type, payload = await asyncio.wait_for(
                            recv_frame(reader), timeout=0.1
                        )
                        self.frames_received.append((msg_type, payload))
                    except asyncio.TimeoutError:
                        pass

        except (asyncio.IncompleteReadError, ConnectionResetError):
            # Client disconnected
            pass
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    async def send_command(self, cmd: str, timeout: float = 10.0) -> Tuple[int, bytes]:
        """Enqueue a COMMAND_REQUEST; wait for the (msg_type, payload) response."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        await self._cmd_queue.put((MSG_COMMAND_REQUEST, None, cmd, future))
        return await asyncio.wait_for(future, timeout=timeout)

    async def send_ping(self, timeout: float = 5.0) -> Tuple[int, bytes]:
        """Enqueue a PING via the dispatch loop; return the (MSG_PONG, b'') response."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        await self._cmd_queue.put((MSG_PING, b"", None, future))
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
def pylontech_sim():
    return PylontechBridgeSimulator(
        data_logger_serial="SH01BTTEST0001",
        barcode="PYLT00001234",
        num_units=2,
        initial_soc=78.0,
    )


# ---------------------------------------------------------------------------
# Helper: connect sim and return the background run task
# ---------------------------------------------------------------------------

async def _connect_and_run(
    sim: PylontechBridgeSimulator,
    server: _BridgeTestServer,
) -> asyncio.Task:
    """Connect simulator, wait for server to see the connection, start run loop."""
    await sim.connect("127.0.0.1", server.port)
    await server.wait_for_connection(timeout=3.0)
    # Give the server handler time to read the HELLO frame
    await asyncio.sleep(0.15)
    return asyncio.create_task(sim.run())


async def _teardown(sim: PylontechBridgeSimulator, task: asyncio.Task) -> None:
    """Cancel the sim run task and stop the sim."""
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await sim.stop()


# ---------------------------------------------------------------------------
# HELLO handshake tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_hello_serial_received(bridge_server, pylontech_sim):
    """ESP32 must send a HELLO frame with the data logger serial immediately."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        assert bridge_server.hello_serial == "SH01BTTEST0001"
        assert bridge_server.frames_received[0][0] == MSG_HELLO
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_hello_payload_is_utf8(bridge_server, pylontech_sim):
    """HELLO payload must decode to the data logger serial as UTF-8."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        _, payload = bridge_server.frames_received[0]
        assert payload.decode("utf-8") == "SH01BTTEST0001"
    finally:
        await _teardown(pylontech_sim, task)


# ---------------------------------------------------------------------------
# COMMAND_REQUEST / COMMAND_RESPONSE tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_info_response_contains_pylon(bridge_server, pylontech_sim):
    """info command response must contain PYLON manufacturer string."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        msg_type, payload = await bridge_server.send_command("info")
        assert msg_type == MSG_COMMAND_RESPONSE
        assert "PYLON" in payload.decode("utf-8")
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_info_response_contains_barcode(bridge_server, pylontech_sim):
    """info command response must contain the battery barcode."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command("info")
        assert "PYLT00001234" in payload.decode("utf-8")
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_all_standard_commands_end_with_prompt(bridge_server, pylontech_sim):
    """info, pwr, bat responses must all end with the pylon> prompt."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        for cmd in ("info", "pwr", "bat"):
            _, payload = await bridge_server.send_command(cmd)
            assert "pylon>" in payload.decode("utf-8"), \
                f"'{cmd}' response missing pylon> prompt"
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pwr_response_contains_table_headers(bridge_server, pylontech_sim):
    """pwr response must include Voltage and Current table headers."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command("pwr")
        response = payload.decode("utf-8")
        assert "Voltage" in response
        assert "Current" in response
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_bat_response_contains_bank_soc(bridge_server, pylontech_sim):
    """bat response must include Bank SOC at the initial value."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command("bat")
        response = payload.decode("utf-8")
        assert "Bank SOC" in response
        assert "78" in response   # initial_soc=78.0
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_sequential_commands(bridge_server, pylontech_sim):
    """Multiple sequential commands must all receive valid responses."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        for cmd in ("info", "pwr", "bat", "log"):
            msg_type, payload = await bridge_server.send_command(cmd)
            assert msg_type == MSG_COMMAND_RESPONSE
            assert len(payload) > 0

        assert pylontech_sim.commands_received >= 4
        assert pylontech_sim.responses_sent >= 4
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_unknown_command_returns_prompt(bridge_server, pylontech_sim):
    """Unknown command must return a COMMAND_RESPONSE frame ending with prompt."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        msg_type, payload = await bridge_server.send_command("xyzzy")
        assert msg_type == MSG_COMMAND_RESPONSE
        response = payload.decode("utf-8")
        assert "pylon>" in response
    finally:
        await _teardown(pylontech_sim, task)


# ---------------------------------------------------------------------------
# PING / PONG keepalive tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ping_receives_pong(bridge_server, pylontech_sim):
    """Server PING → simulator must reply with PONG."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        msg_type, payload = await bridge_server.send_ping()
        assert msg_type == MSG_PONG
        assert payload == b""
        assert pylontech_sim.pings_received >= 1
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_pings_all_answered(bridge_server, pylontech_sim):
    """Every PING must receive exactly one PONG."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        for _ in range(3):
            msg_type, _ = await bridge_server.send_ping()
            assert msg_type == MSG_PONG

        assert pylontech_sim.pings_received == 3
    finally:
        await _teardown(pylontech_sim, task)


# ---------------------------------------------------------------------------
# Simulator counter and state tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_counters_are_accurate(bridge_server, pylontech_sim):
    """commands_received and responses_sent must track every round-trip."""
    task = await _connect_and_run(pylontech_sim, bridge_server)
    try:
        for cmd in ("info", "pwr"):
            await bridge_server.send_command(cmd)

        assert pylontech_sim.commands_received == 2
        assert pylontech_sim.responses_sent == 2
    finally:
        await _teardown(pylontech_sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_is_connected_flag(bridge_server, pylontech_sim):
    """is_connected must be True after connect() and False after stop()."""
    assert not pylontech_sim.is_connected

    task = await _connect_and_run(pylontech_sim, bridge_server)
    assert pylontech_sim.is_connected

    await _teardown(pylontech_sim, task)
    assert not pylontech_sim.is_connected


# ---------------------------------------------------------------------------
# Battery state reflected in responses
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_two_units_appear_in_pwr_response(bridge_server):
    """Simulator with num_units=2 must show 2 row entries in pwr response."""
    sim = PylontechBridgeSimulator(
        data_logger_serial="SH01BTTEST0003",
        num_units=2,
    )
    task = await _connect_and_run(sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command("pwr")
        response = payload.decode("utf-8")
        assert "  1 " in response
        assert "  2 " in response
    finally:
        await _teardown(sim, task)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_custom_barcode_in_info(bridge_server):
    """Custom barcode must appear in the info response."""
    sim = PylontechBridgeSimulator(
        data_logger_serial="SH01BTTEST0004",
        barcode="PYLT99999999",
    )
    task = await _connect_and_run(sim, bridge_server)
    try:
        _, payload = await bridge_server.send_command("info")
        assert "PYLT99999999" in payload.decode("utf-8")
    finally:
        await _teardown(sim, task)
