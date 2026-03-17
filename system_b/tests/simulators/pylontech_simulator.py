"""
Pylontech battery serial bridge simulator.

Simulates the ESP32 + Pylontech battery as a TCP CLIENT that connects
to System B's device server.  This is the inverse of the other simulators
(inverter, meter) which are TCP servers.

Connection flow:
  1. Simulator connects to System B device server (127.0.0.1:port)
  2. Sends HELLO frame (0x06) with data logger serial number
  3. Waits for COMMAND_REQUEST frames (0x01)
  4. Routes each command to the internal Pylontech response engine
  5. Sends COMMAND_RESPONSE frame (0x02) with battery output
  6. Handles PING (0x04) → PONG (0x05)

Run standalone for manual integration testing:

    python -m system_b.tests.simulators.pylontech_simulator \\
        --host 127.0.0.1 --port 8502 --serial SH01BTTEST0001

Or use PylontechBridgeSimulator in pytest fixtures.
"""
import asyncio
import logging
import random
import struct
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Framing constants (must match serial_bridge.py and adapter_factory.py)
MSG_HELLO = 0x06
MSG_COMMAND_REQUEST = 0x01
MSG_COMMAND_RESPONSE = 0x02
MSG_ERROR = 0x03
MSG_PING = 0x04
MSG_PONG = 0x05

FRAME_HEADER_SIZE = 5
MAX_PAYLOAD = 8192


# ---------------------------------------------------------------------------
# Pylontech battery response engine
# ---------------------------------------------------------------------------

class PylontechBattery:
    """
    Pure-Python Pylontech battery response generator.

    Produces text responses matching the real Pylontech RS232 console
    protocol.  Responses end with ``\r\npylon>\r\n`` (configurable prompt).
    """

    def __init__(
        self,
        barcode: str = "PYLT00001234",
        num_units: int = 2,
        initial_soc: float = 78.0,
        capacity_wh: int = 10240,
        prompt: str = "pylon>",
    ):
        self.barcode = barcode
        self.num_units = num_units
        self.prompt = prompt
        self.capacity_wh = capacity_wh

        # Live state (updated each call to simulate_tick)
        self.soc = initial_soc
        self.voltage_mv = 51200          # mV
        self.current_ma = 2500           # mA (positive = charging)
        self.temp_01c = 250              # 0.1 °C units
        self.cycles = random.randint(80, 300)

        # Per-unit state
        self.units = [
            {
                "voltage_mv": 51200 + i * 100,
                "current_ma": 2500,
                "temp_01c": 250 + i * 2,
                "soc": initial_soc,
                "status": "Chrgng",
            }
            for i in range(num_units)
        ]

        self._power_w = self.voltage_mv / 1000 * self.current_ma / 1000

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def process_command(self, command: str) -> str:
        """
        Return the Pylontech response for a given command.

        Args:
            command: Raw command string (e.g. "info", "pwr", "bat 1").

        Returns:
            Full response text ending with the pylon> prompt.
        """
        cmd = command.strip().lower()

        if cmd == "info":
            body = self._info_response()
        elif cmd.startswith("pwr"):
            body = self._pwr_response()
        elif cmd.startswith("bat"):
            body = self._bat_response()
        elif cmd.startswith("log"):
            body = self._log_response()
        elif cmd.startswith("help") or cmd == "?":
            body = self._help_response()
        else:
            body = f"Error: Command '{command}' not found\r\n"

        return body + f"\r\n{self.prompt}\r\n"

    # ------------------------------------------------------------------
    # Response formatters
    # ------------------------------------------------------------------

    def _info_response(self) -> str:
        return (
            "\r\nSystem Info\r\n"
            "-----------------------------------------------------------\r\n"
            f"System Ver   :    V2.8\r\n"
            f"Manufacturer :    PYLON\r\n"
            f"CPU Version  :    V001.00\r\n"
            f"Main SoftVer :    V002.05\r\n"
            f"Module SerialNum : {self.barcode}\r\n"
            f"Barcode      :   {self.barcode}\r\n"
            f"Cell Type    :    LFP\r\n"
            f"Capacity(Ah) :    {self.capacity_wh // 51:>6}\r\n"
            f"Nominal V(V) :    51.2\r\n"
            f"Num Modules  :    {self.num_units}\r\n"
            "Command completed successfully\r\n"
        )

    def _pwr_response(self) -> str:
        header = (
            "\r\nPower         Voltage     Current     Temperature\r\n"
            "              mV          mA          0.1C\r\n"
        )
        rows = ""
        for i, u in enumerate(self.units, 1):
            rows += (
                f"  {i:<10}  {u['voltage_mv']:<10}  "
                f"{u['current_ma']:<10}  {u['temp_01c']:<10}\r\n"
            )
        return header + rows + "Command completed successfully\r\n"

    def _bat_response(self) -> str:
        header = (
            "\r\nBattery   Voltage    Current    Temperature  Coulomb  "
            "State    Time            B.V.Chk  B.T.Chk\r\n"
            "          mV         mA         0.1C         %\r\n"
        )
        rows = ""
        for i, u in enumerate(self.units, 1):
            time_str = "00:00:10:25"
            rows += (
                f"  {i:<7}  {u['voltage_mv']:<9}  {u['current_ma']:<9}  "
                f"{u['temp_01c']:<11}  {int(u['soc']):<7}  "
                f"{u['status']:<8} {time_str:<15}  Normal   Normal\r\n"
            )
        return (
            header + rows
            + f"\r\nBank SOC     :   {int(self.soc):>3} %\r\n"
            + f"Bank Voltage :   {self.voltage_mv:>6} mV\r\n"
            + f"Bank Current :   {self.current_ma:>6} mA\r\n"
            + "Command completed successfully\r\n"
        )

    def _log_response(self) -> str:
        return (
            "\r\nLog (last 5 events)\r\n"
            "2026-03-17 10:00:01  SOC changed: 77% -> 78%\r\n"
            "2026-03-17 09:00:00  Charging started\r\n"
            "2026-03-16 22:00:00  Discharging started\r\n"
            "Command completed successfully\r\n"
        )

    def _help_response(self) -> str:
        return (
            "\r\nAvailable commands:\r\n"
            "  info  - System information\r\n"
            "  pwr   - Power readings\r\n"
            "  bat   - Battery status\r\n"
            "  log   - Event log\r\n"
            "  help  - This message\r\n"
            "Command completed successfully\r\n"
        )

    # ------------------------------------------------------------------
    # Simulation tick (call periodically to advance state)
    # ------------------------------------------------------------------

    def simulate_tick(self, dt: float) -> None:
        """Advance battery state by dt seconds."""
        power_w = self.voltage_mv / 1000 * self.current_ma / 1000
        energy_wh = power_w * (dt / 3600)
        soc_delta = (energy_wh / self.capacity_wh) * 100

        self.soc = max(0, min(100, self.soc + soc_delta))

        # Drift voltage with SOC
        base_cell_mv = 3000 + int(self.soc / 100 * 400)
        self.voltage_mv = base_cell_mv * 16 + random.randint(-50, 50)

        for u in self.units:
            u["soc"] = self.soc
            u["voltage_mv"] = self.voltage_mv + random.randint(-100, 100)
            u["current_ma"] = self.current_ma + random.randint(-50, 50)

    def get_state(self) -> Dict[str, Any]:
        """Return current battery state as a dict for assertions."""
        return {
            "barcode": self.barcode,
            "soc": self.soc,
            "voltage_mv": self.voltage_mv,
            "current_ma": self.current_ma,
            "temp_01c": self.temp_01c,
            "num_units": self.num_units,
            "cycles": self.cycles,
        }


# ---------------------------------------------------------------------------
# ESP32 serial bridge simulator  (TCP client)
# ---------------------------------------------------------------------------

class PylontechBridgeSimulator:
    """
    Simulates the ESP32 serial bridge with a Pylontech battery attached.

    Operates as a TCP CLIENT — connects outbound to System B's device server,
    sends HELLO, then handles framed command requests.

    Usage in tests::

        sim = PylontechBridgeSimulator(
            data_logger_serial="SH01BTTEST0001",
            barcode="PYLT00001234",
        )
        await sim.connect("127.0.0.1", server_port)
        # ... let the test run ...
        await sim.disconnect()
    """

    def __init__(
        self,
        data_logger_serial: str = "SH01BTTEST0001",
        barcode: str = "PYLT00001234",
        num_units: int = 2,
        initial_soc: float = 78.0,
        prompt: str = "pylon>",
    ):
        """
        Initialize the simulator.

        Args:
            data_logger_serial: Serial sent in HELLO (matches self-registration).
            barcode: Pylontech battery barcode from ``info`` command.
            num_units: Number of battery modules to simulate.
            initial_soc: Starting state of charge (%).
            prompt: Console prompt expected at end of each response.
        """
        self.data_logger_serial = data_logger_serial
        self.battery = PylontechBattery(
            barcode=barcode,
            num_units=num_units,
            initial_soc=initial_soc,
            prompt=prompt,
        )

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._run_task: Optional[asyncio.Task] = None
        self._connected = False
        self._stop_event = asyncio.Event()

        # Counters for assertions
        self.commands_received: int = 0
        self.responses_sent: int = 0
        self.pings_received: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, host: str, port: int, timeout: float = 5.0) -> None:
        """
        Open TCP connection to System B device server and send HELLO.

        Args:
            host: System B device server host.
            port: System B device server port.
            timeout: Connection timeout in seconds.
        """
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        self._connected = True
        self._stop_event.clear()

        # Send HELLO immediately (same as real ESP32 serial_bridge.py)
        await self._send_frame(MSG_HELLO, self.data_logger_serial.encode("utf-8"))
        logger.info(
            f"PylontechBridgeSimulator: HELLO sent "
            f"(serial={self.data_logger_serial}) to {host}:{port}"
        )

    async def run(self) -> None:
        """
        Main loop: handle frames from System B until stop() is called.

        Runs until the connection is closed or stop() is called.
        Creates an internal task — call ``await sim.run()`` directly or use
        ``await asyncio.create_task(sim.run())``.
        """
        try:
            while not self._stop_event.is_set() and self._connected:
                try:
                    header = await asyncio.wait_for(
                        self._recv_exact(FRAME_HEADER_SIZE),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    # No frame received — check stop event and loop
                    continue
                except (ConnectionResetError, asyncio.IncompleteReadError):
                    logger.info("PylontechBridgeSimulator: Connection closed by server")
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
            logger.error(f"PylontechBridgeSimulator error: {e}")
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
        logger.info("PylontechBridgeSimulator: stopped")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Frame dispatch
    # ------------------------------------------------------------------

    async def _dispatch(self, msg_type: int, payload: bytes) -> None:
        if msg_type == MSG_COMMAND_REQUEST:
            cmd = payload.decode("utf-8", errors="replace").strip()
            logger.debug(f"PylontechBridgeSimulator: CMD={cmd!r}")
            self.commands_received += 1

            response = self.battery.process_command(cmd)
            await self._send_frame(MSG_COMMAND_RESPONSE, response.encode("utf-8"))
            self.responses_sent += 1

        elif msg_type == MSG_PING:
            await self._send_frame(MSG_PONG, b"")
            self.pings_received += 1

        else:
            logger.warning(
                f"PylontechBridgeSimulator: unknown msg_type={msg_type:#04x}"
            )

    # ------------------------------------------------------------------
    # Framing helpers
    # ------------------------------------------------------------------

    async def _send_frame(self, msg_type: int, payload: bytes) -> None:
        """Pack and send a length-prefixed frame."""
        frame = struct.pack(">BI", msg_type, len(payload)) + payload
        self._writer.write(frame)
        await self._writer.drain()

    async def _recv_exact(self, n: int) -> Optional[bytes]:
        """Read exactly n bytes; return None on EOF."""
        try:
            return await self._reader.readexactly(n)
        except asyncio.IncompleteReadError:
            return None


# ---------------------------------------------------------------------------
# Standalone runner for manual testing
# ---------------------------------------------------------------------------

async def _run_standalone(host: str, port: int, serial: str,
                           barcode: str, reconnect_delay: int) -> None:
    """Connect the simulator to a running System B instance and loop."""
    sim = PylontechBridgeSimulator(
        data_logger_serial=serial,
        barcode=barcode,
    )

    while True:
        try:
            print(f"[sim] Connecting to {host}:{port} as {serial}...")
            await sim.connect(host, port)
            print(f"[sim] Connected. Waiting for commands...")
            await sim.run()
            print(f"[sim] Disconnected.")
        except Exception as e:
            print(f"[sim] Error: {e}")

        print(f"[sim] Reconnecting in {reconnect_delay}s...")
        await asyncio.sleep(reconnect_delay)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Pylontech battery serial bridge simulator"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8502)
    parser.add_argument("--serial", default="SH01BTTEST0001")
    parser.add_argument("--barcode", default="PYLT00001234")
    parser.add_argument("--reconnect-delay", type=int, default=5)

    args = parser.parse_args()

    asyncio.run(_run_standalone(
        args.host, args.port, args.serial, args.barcode, args.reconnect_delay
    ))
