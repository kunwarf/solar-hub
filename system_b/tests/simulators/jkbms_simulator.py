"""
JK BMS serial bridge simulator.

Simulates the ESP32 + JK BMS battery as a TCP CLIENT that connects
to System B's device server.  Uses the same length-prefixed binary
framing as PylontechBridgeSimulator, but the COMMAND_RESPONSE payload
is a raw JK BMS binary status frame (``55 AA EB 90 02 ...``).

Connection flow:
  1. Simulator connects to System B device server (127.0.0.1:port)
  2. Sends HELLO frame (0x06) with data logger serial number
  3. Waits for COMMAND_REQUEST frames (0x01) — payload ignored
  4. Builds a binary JK BMS status frame and sends COMMAND_RESPONSE (0x02)
  5. Handles PING (0x04) → PONG (0x05)

Run standalone for manual integration testing:

    python -m system_b.tests.simulators.jkbms_simulator \\
        --host 127.0.0.1 --port 8502 --serial SH01JKTEST0001
"""
import asyncio
import logging
import random
import struct
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Framing constants (must match serial_bridge.py and adapter_factory.py)
MSG_HELLO            = 0x06
MSG_COMMAND_REQUEST  = 0x01
MSG_COMMAND_RESPONSE = 0x02
MSG_ERROR            = 0x03
MSG_PING             = 0x04
MSG_PONG             = 0x05

FRAME_HEADER_SIZE = 5
MAX_PAYLOAD       = 8192

# JK BMS binary constants
JKBMS_HEADER      = b'\x55\xAA\xEB\x90'
JKBMS_TYPE_STATUS = 0x02

# Minimum frame size: up to byte 259 for temp4
_FRAME_SIZE = 260


# ---------------------------------------------------------------------------
# JK BMS binary frame builder
# ---------------------------------------------------------------------------

def _write_int_le(buf: bytearray, offset: int, value: int, length: int) -> None:
    """Write little-endian integer into buffer at offset."""
    b = value.to_bytes(length, "little", signed=(value < 0))
    buf[offset:offset + length] = b


def build_jkbms_status_frame(
    soc: int = 78,
    soh: int = 98,
    pack_voltage_v: float = 51.2,
    current_a: float = -5.0,
    power_w: float = 256.0,
    temp1_c: float = 25.0,
    temp2_c: float = 25.5,
    mos_temp_c: float = 28.0,
    remaining_ah: float = 45.0,
    total_ah: float = 50.0,
    cycle_count: int = 150,
    num_cells: int = 16,
    charge_enabled: bool = True,
    discharge_enabled: bool = True,
    balance_enabled: bool = False,
) -> bytes:
    """
    Build a minimal JK BMS binary status frame for testing.

    All fields are encoded in little-endian format matching the real
    JK BMS 55 AA EB 90 02 frame layout used by parse_jkbms_status_frame().

    Args:
        soc: State of charge (0-100 %).
        soh: State of health (0-100 %).
        pack_voltage_v: Pack voltage (V).
        current_a: Current (A, negative = discharging).
        power_w: Power (W, unsigned).
        temp1_c: Temperature sensor 1 (°C).
        temp2_c: Temperature sensor 2 (°C).
        mos_temp_c: MOSFET temperature (°C).
        remaining_ah: Remaining capacity (Ah).
        total_ah: Total capacity (Ah).
        cycle_count: Charge/discharge cycle count.
        num_cells: Number of cells (1-16).
        charge_enabled: Charge MOSFET state.
        discharge_enabled: Discharge MOSFET state.
        balance_enabled: Balance switch state.

    Returns:
        Raw frame bytes.
    """
    buf = bytearray(_FRAME_SIZE)

    # Header: 55 AA EB 90 02
    buf[0:4] = JKBMS_HEADER
    buf[4] = JKBMS_TYPE_STATUS

    # Cell voltages at offset 6 + cell*2 (2B LE, ÷1000 → V)
    # Distribute pack_voltage evenly with slight random variation
    base_cell_mv = int(pack_voltage_v / max(num_cells, 1) * 1000)
    for cell in range(min(num_cells, 16)):
        cell_mv = base_cell_mv + random.randint(-10, 10)
        _write_int_le(buf, 6 + cell * 2, cell_mv, 2)

    # MOS temp at 144 (2B signed LE, ÷10 → °C)
    _write_int_le(buf, 144, int(mos_temp_c * 10), 2)

    # Power at 154 (4B unsigned LE, ÷1000 → W)
    _write_int_le(buf, 154, int(abs(power_w) * 1000), 4)

    # Current at 158 (4B signed LE, ÷1000 → A)
    _write_int_le(buf, 158, int(current_a * 1000), 4)

    # Temp1 at 162, Temp2 at 164 (2B signed LE, ÷10 → °C)
    _write_int_le(buf, 162, int(temp1_c * 10), 2)
    _write_int_le(buf, 164, int(temp2_c * 10), 2)

    # Balance current at 170 (2B signed LE, ÷1000 → A)
    _write_int_le(buf, 170, 0, 2)

    # Balance action at 172
    buf[172] = 0

    # SOC at 173 (1B, 0-100)
    buf[173] = max(0, min(100, int(soc)))

    # Remaining capacity at 174 (4B signed LE, ÷1000 → Ah)
    _write_int_le(buf, 174, int(remaining_ah * 1000), 4)

    # Total capacity at 178 (4B signed LE, ÷1000 → Ah)
    _write_int_le(buf, 178, int(total_ah * 1000), 4)

    # Cycle count at 182 (4B signed LE)
    _write_int_le(buf, 182, cycle_count, 4)

    # SOH at 190 (1B, 0-100)
    buf[190] = max(0, min(100, int(soh)))

    # Switch states at 198, 199, 200
    buf[198] = 1 if charge_enabled else 0
    buf[199] = 1 if discharge_enabled else 0
    buf[200] = 1 if balance_enabled else 0

    # Pack voltage at 234 (2B unsigned LE, ÷100 → V)
    _write_int_le(buf, 234, int(pack_voltage_v * 100), 2)

    return bytes(buf)


# ---------------------------------------------------------------------------
# JK BMS battery state engine
# ---------------------------------------------------------------------------

class JKBMSBattery:
    """
    Pure-Python JK BMS battery state generator.

    Produces binary status frames matching the real JK BMS RS485 protocol.
    """

    def __init__(
        self,
        num_cells: int = 16,
        initial_soc: float = 78.0,
        total_ah: float = 50.0,
    ):
        self.num_cells    = num_cells
        self.soc          = initial_soc
        self.total_ah     = total_ah
        self.remaining_ah = total_ah * (initial_soc / 100)
        self.pack_voltage = 51.2
        self.current_a    = -5.0   # discharging
        self.temp1_c      = 25.0
        self.temp2_c      = 25.5
        self.mos_temp_c   = 28.0
        self.soh          = 98
        self.cycle_count  = random.randint(80, 300)

    def get_status_frame(self) -> bytes:
        """Build and return a binary status frame for current state."""
        return build_jkbms_status_frame(
            soc=int(self.soc),
            soh=self.soh,
            pack_voltage_v=self.pack_voltage,
            current_a=self.current_a,
            power_w=abs(self.pack_voltage * self.current_a),
            temp1_c=self.temp1_c,
            temp2_c=self.temp2_c,
            mos_temp_c=self.mos_temp_c,
            remaining_ah=self.remaining_ah,
            total_ah=self.total_ah,
            cycle_count=self.cycle_count,
            num_cells=self.num_cells,
        )

    def simulate_tick(self, dt: float) -> None:
        """Advance battery state by dt seconds."""
        energy_wh = abs(self.pack_voltage * self.current_a) * (dt / 3600)
        ah_change = self.current_a * (dt / 3600)
        self.remaining_ah = max(0.0, min(self.total_ah, self.remaining_ah + ah_change))
        self.soc = (self.remaining_ah / self.total_ah) * 100

        # Drift voltage with SOC
        self.pack_voltage = 48.0 + (self.soc / 100) * 4.8 + random.uniform(-0.1, 0.1)
        self.temp1_c = 25.0 + random.uniform(-0.5, 0.5)

    def get_state(self) -> Dict[str, Any]:
        return {
            "soc": self.soc,
            "remaining_ah": self.remaining_ah,
            "pack_voltage": self.pack_voltage,
            "current_a": self.current_a,
            "temp1_c": self.temp1_c,
            "num_cells": self.num_cells,
        }


# ---------------------------------------------------------------------------
# ESP32 serial bridge simulator (TCP client)
# ---------------------------------------------------------------------------

class JKBMSBridgeSimulator:
    """
    Simulates the ESP32 serial bridge with a JK BMS attached.

    Operates as a TCP CLIENT — connects outbound to System B's device server,
    sends HELLO, then responds to COMMAND_REQUEST frames with binary JK BMS
    status frames.

    Usage in tests::

        sim = JKBMSBridgeSimulator(
            data_logger_serial="SH01JKTEST0001",
            num_cells=16,
            initial_soc=78.0,
        )
        await sim.connect("127.0.0.1", server_port)
        task = asyncio.create_task(sim.run())
        # ... run test ...
        await sim.stop()
    """

    def __init__(
        self,
        data_logger_serial: str = "SH01JKTEST0001",
        num_cells: int = 16,
        initial_soc: float = 78.0,
        total_ah: float = 50.0,
    ):
        """
        Initialize the JK BMS bridge simulator.

        Args:
            data_logger_serial: Serial number sent in HELLO frame.
            num_cells: Number of battery cells.
            initial_soc: Initial state of charge (%).
            total_ah: Total battery capacity (Ah).
        """
        self.data_logger_serial = data_logger_serial
        self.battery = JKBMSBattery(
            num_cells=num_cells,
            initial_soc=initial_soc,
            total_ah=total_ah,
        )

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._stop_event = asyncio.Event()

        # Counters for assertions
        self.commands_received: int = 0
        self.responses_sent:    int = 0
        self.pings_received:    int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, host: str, port: int, timeout: float = 5.0) -> None:
        """Open TCP connection and send HELLO."""
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        self._connected = True
        self._stop_event.clear()

        await self._send_frame(MSG_HELLO, self.data_logger_serial.encode("utf-8"))
        logger.info(
            f"JKBMSBridgeSimulator: HELLO sent "
            f"(serial={self.data_logger_serial}) to {host}:{port}"
        )

    async def run(self) -> None:
        """Main loop: handle frames from System B until stop() is called."""
        try:
            while not self._stop_event.is_set() and self._connected:
                try:
                    header = await asyncio.wait_for(
                        self._recv_exact(FRAME_HEADER_SIZE),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    continue
                except (ConnectionResetError, asyncio.IncompleteReadError):
                    logger.info("JKBMSBridgeSimulator: Connection closed by server")
                    break

                if header is None:
                    break

                msg_type = header[0]
                payload_len = struct.unpack(">I", header[1:5])[0]

                payload = b""
                if payload_len > 0:
                    payload = await self._recv_exact(payload_len)
                    if payload is None:
                        break

                await self._dispatch(msg_type, payload)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"JKBMSBridgeSimulator error: {e}")
        finally:
            self._connected = False

    async def stop(self) -> None:
        """Stop the simulator and close the connection."""
        self._stop_event.set()
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        logger.info("JKBMSBridgeSimulator: stopped")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Frame dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, msg_type: int, payload: bytes) -> None:
        if msg_type == MSG_COMMAND_REQUEST:
            # Payload is ignored — just return the current status frame
            logger.debug("JKBMSBridgeSimulator: CMD received, returning binary status frame")
            self.commands_received += 1

            frame = self.battery.get_status_frame()
            await self._send_frame(MSG_COMMAND_RESPONSE, frame)
            self.responses_sent += 1

        elif msg_type == MSG_PING:
            await self._send_frame(MSG_PONG, b"")
            self.pings_received += 1

        else:
            logger.warning(
                f"JKBMSBridgeSimulator: unknown msg_type={msg_type:#04x}"
            )

    # ------------------------------------------------------------------
    # Framing helpers
    # ------------------------------------------------------------------

    async def _send_frame(self, msg_type: int, payload: bytes) -> None:
        frame = struct.pack(">BI", msg_type, len(payload)) + payload
        self._writer.write(frame)
        await self._writer.drain()

    async def _recv_exact(self, n: int) -> Optional[bytes]:
        try:
            return await self._reader.readexactly(n)
        except asyncio.IncompleteReadError:
            return None


# ---------------------------------------------------------------------------
# Standalone runner for manual testing
# ---------------------------------------------------------------------------

async def _run_standalone(host: str, port: int, serial: str, reconnect_delay: int) -> None:
    sim = JKBMSBridgeSimulator(data_logger_serial=serial)
    while True:
        try:
            print(f"[jkbms-sim] Connecting to {host}:{port} as {serial}...")
            await sim.connect(host, port)
            print(f"[jkbms-sim] Connected. Waiting for commands...")
            await sim.run()
            print(f"[jkbms-sim] Disconnected.")
        except Exception as e:
            print(f"[jkbms-sim] Error: {e}")
        print(f"[jkbms-sim] Reconnecting in {reconnect_delay}s...")
        await asyncio.sleep(reconnect_delay)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="JK BMS serial bridge simulator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8502)
    parser.add_argument("--serial", default="SH01JKTEST0001")
    parser.add_argument("--reconnect-delay", type=int, default=5)

    args = parser.parse_args()
    asyncio.run(_run_standalone(args.host, args.port, args.serial, args.reconnect_delay))
