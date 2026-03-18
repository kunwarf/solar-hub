"""
Adapter factory for creating device adapters.

Creates appropriate adapter instances based on protocol definitions,
with TCP connection wrapping for data logger communication.
"""
import asyncio
import importlib
import json
import logging
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# Serial bridge framing constants (must match ESP32 serial_bridge.py)
_MSG_COMMAND_REQUEST = 0x01
_MSG_COMMAND_RESPONSE = 0x02
_MSG_ERROR = 0x03
_MSG_PING = 0x04
_MSG_PONG = 0x05
_MAX_PAYLOAD = 8192

from ..config import DeviceServerSettings, get_device_server_settings
from ..connection.tcp_connection import TCPConnection
from ..protocols.definitions import ProtocolDefinition, ProtocolType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TCPModbusAdapter:
    """
    Modbus adapter that communicates over TCP connection.

    Wraps a TCPConnection to provide Modbus read/write operations
    for use with JsonRegisterMixin-based adapters.
    """

    def __init__(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
        register_map: List[Dict[str, Any]],
    ):
        """
        Initialize the TCP Modbus adapter.

        Args:
            connection: TCP connection to device.
            protocol: Protocol definition.
            register_map: Loaded register map.
        """
        self.connection = connection
        self.protocol = protocol
        self.regs = register_map
        self.addr_offset = 0

        # Modbus settings
        self.unit_id = protocol.modbus.unit_id if protocol.modbus else 1
        self.timeout = protocol.modbus.timeout if protocol.modbus else 5.0

        # Transaction tracking
        self._transaction_id = 0

        # Lock for serializing Modbus operations (prevents concurrent access)
        self._modbus_lock = asyncio.Lock()

    def _next_transaction_id(self) -> int:
        """Get next Modbus transaction ID."""
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        return self._transaction_id

    async def _read_holding_regs(
        self,
        addr: int,
        count: int,
    ) -> List[int]:
        """
        Read holding registers.

        Args:
            addr: Starting register address.
            count: Number of registers to read.

        Returns:
            List of register values.

        Raises:
            Exception: On communication error.
        """
        import struct

        async with self._modbus_lock:
            transaction_id = self._next_transaction_id()

            # Build Modbus TCP request
            # MBAP header: Transaction ID (2) | Protocol ID (2) | Length (2) | Unit ID (1)
            # PDU: Function (1) | Start Address (2) | Quantity (2)
            pdu = struct.pack(">BHH", 0x03, addr, count)
            mbap = struct.pack(
                ">HHHB",
                transaction_id,
                0,  # Protocol ID
                len(pdu) + 1,
                self.unit_id,
            )

            request = mbap + pdu

            # Send and receive
            await self.connection.write(request, timeout=self.timeout)

            # Read response header
            header = await self.connection.read(9, timeout=self.timeout)

            # Parse MBAP
            resp_trans_id, _, length, resp_unit_id = struct.unpack(">HHHB", header[:7])

            if resp_trans_id != transaction_id:
                raise ValueError(f"Transaction ID mismatch: {resp_trans_id} != {transaction_id}")

            # Check function code
            function_code = header[7]
            if function_code & 0x80:
                # Exception response
                raise ValueError(f"Modbus exception: {header[8]}")

            # Read data
            byte_count = header[8]
            data = await self.connection.read(byte_count, timeout=self.timeout)

            # Parse registers
            registers = []
            for i in range(0, len(data), 2):
                if i + 1 < len(data):
                    value = struct.unpack(">H", data[i:i + 2])[0]
                    registers.append(value)

            return registers

    async def _write_holding_u16(self, addr: int, value: int) -> None:
        """
        Write single holding register.

        Args:
            addr: Register address.
            value: Value to write.
        """
        import struct

        async with self._modbus_lock:
            logger.info(f"[SERVER->DEVICE] WRITE SINGLE addr={addr}, value={value}")
            transaction_id = self._next_transaction_id()

            # Function code 0x06: Write Single Register
            pdu = struct.pack(">BHH", 0x06, addr, value)
            mbap = struct.pack(
                ">HHHB",
                transaction_id,
                0,
                len(pdu) + 1,
                self.unit_id,
            )

            request = mbap + pdu

            await self.connection.write(request, timeout=self.timeout)

            # Read response (should echo back)
            response = await self.connection.read(12, timeout=self.timeout)

            # Verify response
            resp_trans_id = struct.unpack(">H", response[:2])[0]
            if resp_trans_id != transaction_id:
                raise ValueError(f"Transaction ID mismatch")

            function_code = response[7]
            if function_code & 0x80:
                raise ValueError(f"Modbus exception: {response[8]}")

            logger.info(f"[SERVER<-DEVICE] WRITE SINGLE response: OK")

    async def _write_holding_u16_list(
        self,
        addr: int,
        values: List[int],
    ) -> None:
        """
        Write multiple holding registers.

        Args:
            addr: Starting register address.
            values: List of values to write.
        """
        import struct

        async with self._modbus_lock:
            logger.info(f"[SERVER->DEVICE] WRITE MULTIPLE addr={addr}, values={values}")
            transaction_id = self._next_transaction_id()

            # Function code 0x10: Write Multiple Registers
            byte_count = len(values) * 2
            pdu = struct.pack(">BHHB", 0x10, addr, len(values), byte_count)

            for value in values:
                pdu += struct.pack(">H", value)

            mbap = struct.pack(
                ">HHHB",
                transaction_id,
                0,
                len(pdu) + 1,
                self.unit_id,
            )

            request = mbap + pdu

            await self.connection.write(request, timeout=self.timeout)

            # Read response
            response = await self.connection.read(12, timeout=self.timeout)

            resp_trans_id = struct.unpack(">H", response[:2])[0]
            if resp_trans_id != transaction_id:
                raise ValueError(f"Transaction ID mismatch")

            function_code = response[7]
            if function_code & 0x80:
                raise ValueError(f"Modbus exception: {response[8]}")

            logger.info(f"[SERVER<-DEVICE] WRITE MULTIPLE response: OK")

    async def write_register(self, address: int, value: int) -> None:
        """
        Write single holding register (public API).

        Args:
            address: Register address.
            value: Value to write (0-65535).

        Raises:
            ValueError: If value is out of range.
            Exception: On communication error.
        """
        if not 0 <= value <= 65535:
            raise ValueError(f"Value {value} out of range [0, 65535]")
        await self._write_holding_u16(address, value)

    async def write_registers(self, address: int, values: List[int]) -> None:
        """
        Write multiple holding registers (public API).

        Args:
            address: Starting register address.
            values: List of values to write (each 0-65535).

        Raises:
            ValueError: If any value is out of range.
            Exception: On communication error.
        """
        for i, val in enumerate(values):
            if not 0 <= val <= 65535:
                raise ValueError(f"Value at index {i} ({val}) out of range [0, 65535]")
        await self._write_holding_u16_list(address, values)

    async def poll(self) -> Dict[str, Any]:
        """
        Poll all readable registers and return telemetry data.

        Returns:
            Dictionary of register ID to decoded value.
        """
        values: Dict[str, Any] = {}

        # Note: _read_holding_regs already uses the lock, so multiple reads
        # during polling are serialized automatically

        for reg in self.regs:
            reg_id = reg.get("id")
            if not reg_id:
                continue

            # Skip write-only registers
            if str(reg.get("rw", "RO")).upper() in ("WO", "Write-Only"):
                continue

            # Only read holding/input registers
            kind = (reg.get("kind") or "").lower()
            if kind not in ("holding", "input"):
                continue

            try:
                addr = int(reg["addr"]) + self.addr_offset
                size = max(1, int(reg.get("size", 1)))

                regs = await self._read_holding_regs(addr, size)

                # Decode value
                value = self._decode_words(reg, regs)
                values[reg_id] = value

            except Exception:
                continue

        # Log summary with key metrics
        key_metrics = []
        for key in ["pv1_power_w", "pv2_power_w", "battery_power_w", "battery_soc_pct",
                    "grid_power_w", "load_power_w", "inverter_temp_c"]:
            if key in values:
                val = values[key]
                if isinstance(val, float):
                    key_metrics.append(f"{key}={val:.1f}")
                else:
                    key_metrics.append(f"{key}={val}")

        if key_metrics:
            logger.info(f"Poll: {len(values)} regs | {' | '.join(key_metrics)}")

        return values

    def _decode_words(self, r: Dict[str, Any], regs: List[int]) -> Any:
        """Decode register words to value."""
        t = (r.get("type") or "").lower()
        size = max(1, int(r.get("size", 1)))
        scale = r.get("scale")
        enc = (r.get("encoder") or "").lower()

        # ASCII decoder
        if enc == "ascii":
            buf = bytearray()
            for w in regs[:size]:
                w = int(w) & 0xFFFF
                buf.append((w >> 8) & 0xFF)
                buf.append(w & 0xFF)
            try:
                return bytes(buf).split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
            except Exception:
                return ""

        # Numeric decode
        if size == 1 and regs:
            val = int(regs[0])
            if "s16" in t and val >= 0x8000:
                val = val - 0x10000
        elif size == 2 and regs and len(regs) >= 2:
            hi, lo = regs[0], regs[1]
            val = (hi << 16) | lo
            if "s32" in t and val & 0x80000000:
                val = -((~val & 0xFFFFFFFF) + 1)
        else:
            val = 0

        if scale and isinstance(val, (int, float)):
            val = val * scale

        return val


class TCPCommandAdapter:
    """
    Command-based adapter that communicates over TCP connection.

    For batteries like Pytes that use text commands.
    """

    def __init__(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
        register_map: List[Dict[str, Any]],
    ):
        """
        Initialize the TCP command adapter.

        Args:
            connection: TCP connection to device.
            protocol: Protocol definition.
            register_map: Loaded register map (command definitions).
        """
        self.connection = connection
        self.protocol = protocol
        self.regs = register_map

        # Command settings
        self.line_ending = (
            protocol.command.line_ending if protocol.command else "\r\n"
        )
        self.timeout = (
            protocol.command.response_timeout if protocol.command else 5.0
        )
        self.command_delay = (
            protocol.command.command_delay if protocol.command else 0.1
        )

        # Lock ensures sequential command execution (ESP32 bridge is single-threaded)
        self._command_lock = asyncio.Lock()

    async def send_command_bytes(self, payload: bytes) -> Optional[bytes]:
        """
        Send a raw-bytes command via the serial bridge and return raw bytes.

        Used for binary protocols like JK BMS where the COMMAND_RESPONSE
        payload must NOT be decoded as UTF-8.

        Args:
            payload: Raw bytes to send as COMMAND_REQUEST payload.

        Returns:
            Raw response bytes or None on error.
        """
        async with self._command_lock:
            try:
                frame = struct.pack(">BI", _MSG_COMMAND_REQUEST, len(payload)) + payload
                await self.connection.write(frame, timeout=self.timeout)

                resp_header = await self.connection.read(5, timeout=self.timeout)
                msg_type = resp_header[0]
                resp_len = struct.unpack(">I", resp_header[1:5])[0]

                if resp_len > _MAX_PAYLOAD:
                    logger.warning(f"Binary framed response too large: {resp_len} bytes")
                    return None

                resp_payload = b""
                if resp_len > 0:
                    resp_payload = await self.connection.read(resp_len, timeout=self.timeout)

                if msg_type == _MSG_COMMAND_RESPONSE:
                    return resp_payload
                elif msg_type == _MSG_ERROR:
                    logger.warning(
                        f"Serial bridge returned error: {resp_payload.decode('utf-8', errors='replace')}"
                    )
                    return None
                else:
                    logger.warning(f"Unexpected binary response frame type: {msg_type:#04x}")
                    return None

            except Exception as e:
                logger.debug(f"Binary framed command error: {e}")
                return None

    async def send_command(self, command: str) -> Optional[str]:
        """
        Send command and get response.

        Dispatches to framed protocol (bridged ESP32 serial connection) or
        raw text protocol (direct serial-to-TCP converters) based on
        whether the underlying connection is a serial bridge.

        Args:
            command: Command string.

        Returns:
            Response string or None.
        """
        if self.connection.bridged:
            return await self._send_command_framed(command)
        return await self._send_command_raw(command)

    async def _send_command_framed(self, command: str) -> Optional[str]:
        """
        Send command using ESP32 serial bridge length-prefixed framing.

        Frame format: [MSG_TYPE: 1B][LENGTH: 4B big-endian][PAYLOAD: LENGTH B]

        Args:
            command: Command string to forward to the battery.

        Returns:
            Response string or None on error.
        """
        async with self._command_lock:
            try:
                payload = command.encode("utf-8")
                frame = struct.pack(">BI", _MSG_COMMAND_REQUEST, len(payload)) + payload
                await self.connection.write(frame, timeout=self.timeout)

                # Read 5-byte response frame header, handling PING transparently
                while True:
                    resp_header = await self.connection.read(5, timeout=self.timeout)
                    msg_type = resp_header[0]
                    resp_len = struct.unpack(">I", resp_header[1:5])[0]

                    if msg_type == _MSG_PING:
                        # ESP32 keepalive — send PONG and wait for the real response
                        pong = struct.pack(">BI", _MSG_PONG, 0)
                        await self.connection.write(pong, timeout=self.timeout)
                        logger.debug("Serial bridge PING received, PONG sent")
                        continue

                    break

                if resp_len > _MAX_PAYLOAD:
                    logger.warning(f"Framed response too large: {resp_len} bytes")
                    return None

                resp_payload = b""
                if resp_len > 0:
                    resp_payload = await self.connection.read(
                        resp_len, timeout=self.timeout
                    )

                if msg_type == _MSG_COMMAND_RESPONSE:
                    return resp_payload.decode("utf-8", errors="replace")
                elif msg_type == _MSG_ERROR:
                    error_msg = resp_payload.decode("utf-8", errors="replace")
                    logger.warning(f"Serial bridge returned error: {error_msg}")
                    return None
                else:
                    logger.warning(
                        f"Unexpected response frame type: {msg_type:#04x}"
                    )
                    return None

            except Exception as e:
                logger.debug(f"Framed command error: {e}")
                return None

    async def _send_command_raw(self, command: str) -> Optional[str]:
        """
        Send command using raw text protocol (direct serial-to-TCP converter).

        Reads response lines until a prompt character ('>') is detected.

        Args:
            command: Command string.

        Returns:
            Response string or None.
        """
        try:
            cmd_bytes = (command + self.line_ending).encode("utf-8")
            await self.connection.write(cmd_bytes, timeout=self.timeout)

            # Read response lines until prompt
            response_lines = []
            try:
                while True:
                    line = await asyncio.wait_for(
                        self.connection.read_until(
                            self.line_ending.encode("utf-8"),
                            timeout=self.timeout,
                        ),
                        timeout=self.timeout,
                    )
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        response_lines.append(decoded)
                    if decoded.startswith(">"):
                        break
            except asyncio.TimeoutError:
                pass

            return "\n".join(response_lines) if response_lines else None

        except Exception as e:
            logger.debug(f"Raw command error: {e}")
            return None

    async def poll(self) -> Dict[str, Any]:
        """
        Poll device using command-based protocol.

        Returns:
            Dictionary of parsed telemetry values.
        """
        values: Dict[str, Any] = {}
        pid = self.protocol.protocol_id.lower()

        # For Pytes/Pylontech text-command batteries
        if "pytes" in pid or "pylontech" in pid:
            # Wake-up: ensure the console is at a clean prompt before commands
            await self.send_command("")

            # Step 1 — get all module summaries in one shot
            pwr_resp = await self.send_command("pwr")
            if pwr_resp:
                parsed = _parse_pylontech_pwr(pwr_resp)
                values.update(parsed)

            # Step 2 — per-cell voltages for each module in the stack
            # bat N uses space-separated format: "bat 1", "bat 2", ...
            modules = values.get("battery_units", [])
            all_cells: List[Dict[str, Any]] = []
            for unit_data in modules:
                module_num = unit_data["unit"]
                bat_resp = await self.send_command(f"bat {module_num}")
                if bat_resp:
                    cells = _parse_pylontech_bat_cells(bat_resp, module_num)
                    all_cells.extend(cells)
                    # Derive per-module power from voltage × current
                    unit_data["power_w"] = (
                        unit_data.get("voltage_v", 0)
                        * unit_data.get("current_a", 0)
                    )

            if all_cells:
                values["battery_cells"] = all_cells

            logger.debug(
                f"Pylontech stack: {len(modules)} module(s), "
                f"{len(all_cells)} cells total"
            )

        # For JK BMS serial bridge (binary RS485 broadcast protocol)
        elif "jkbms_serial" in pid or ("jkbms" in pid and self.connection.bridged):
            raw = await self.send_command_bytes(b"")
            if raw:
                from ..telemetry.jkbms_parser import parse_jkbms_status_frame
                parsed = parse_jkbms_status_frame(raw)
                if parsed:
                    values.update(parsed)

        return values


def _parse_pylontech_pwr(pwr_text: str) -> Dict[str, Any]:
    """
    Parse Pylontech/Pytes 'pwr' command response.

    Handles two firmware variants:
      Old:  ... vhigh  MosTempr  State(text)  SOC(int)  BI  Ah  ...
      New:  ... vhigh  Base.St   Volt.St  Curr.St  Temp.St  Coulomb(XX%)  Time  ...

    Returns structured dict with bank-level scalars and battery_units list.
    """
    units = []
    for line in pwr_text.splitlines():
        parts = line.split()
        if not parts or not parts[0].isdigit():
            continue
        # Only the four numeric fields are mandatory
        try:
            unit_num  = int(parts[0])
            volt_mv   = int(parts[1])
            curr_ma   = int(parts[2])
            temp_mdeg = int(parts[3])
        except (ValueError, IndexError):
            continue

        # SOC: new firmware encodes as "81%" somewhere in cols 8+
        # Old firmware has a plain integer at col 10.
        soc_pct = None
        for i in range(8, min(len(parts), 20)):
            if parts[i].endswith('%'):
                try:
                    soc_pct = int(parts[i].rstrip('%'))
                    break
                except ValueError:
                    pass
        if soc_pct is None and len(parts) > 10:
            try:
                soc_pct = int(parts[10])  # old format: plain SOC integer
            except (ValueError, IndexError):
                pass

        voltage_v = volt_mv   / 1000.0
        current_a = curr_ma   / 1000.0
        unit_data: Dict[str, Any] = {
            "unit":      unit_num,
            "voltage_v": voltage_v,
            "current_a": current_a,
            "temp_c":    temp_mdeg / 1000.0,
            "power_w":   voltage_v * current_a,
        }
        if soc_pct is not None:
            unit_data["soc_pct"] = soc_pct
        units.append(unit_data)

    if not units:
        return {}

    result: Dict[str, Any] = {
        "battery_units":       units,
        "battery_units_count": len(units),
    }

    # Bank voltage: modules are in parallel — voltages should be equal, take average
    result["battery_voltage_v"] = sum(u["voltage_v"] for u in units) / len(units)
    # Bank current: sum across parallel modules
    result["battery_current_a"] = sum(u["current_a"] for u in units)
    # Bank power
    result["battery_power_w"] = (
        result["battery_voltage_v"] * result["battery_current_a"]
    )
    # Bank temp: maximum across modules
    result["battery_temp_c"] = max(u["temp_c"] for u in units)
    # Bank SOC: minimum (weakest module limits usable capacity)
    socs = [u["soc_pct"] for u in units if "soc_pct" in u]
    if socs:
        result["battery_soc_pct"] = min(socs)

    return result


def _parse_pylontech_bat_cells(
    bat_text: str,
    module_num: int,
) -> List[Dict[str, Any]]:
    """
    Parse 'bat N' response into per-cell voltage list.

    The response rows have the form:
      cell_idx  volt_mv  curr_ma  tempr_mdeg  state  ...

    Each row is 0-indexed (cell 0 … 14 for 15-cell, cell 0 … 15 for 16-cell).
    Only volt_mv is stored; current and temperature come from 'pwr' at module level.

    Args:
        bat_text:   Raw response string from 'bat N' command.
        module_num: 1-indexed module number (matches 'pwr' row number).

    Returns:
        List of {"module": N, "cell": idx, "voltage_v": float}.
    """
    cells: List[Dict[str, Any]] = []
    for line in bat_text.splitlines():
        parts = line.split()
        if not parts or not parts[0].isdigit():
            continue
        try:
            cell_idx = int(parts[0])
            volt_mv  = int(parts[1])
        except (ValueError, IndexError):
            continue
        cells.append({
            "module":    module_num,
            "cell":      cell_idx,
            "voltage_v": volt_mv / 1000.0,
        })
    return cells


class AdapterFactory:
    """
    Factory for creating device adapters.

    Creates appropriate adapter instances based on protocol definitions.
    """

    def __init__(
        self,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the adapter factory.

        Args:
            settings: Server settings.
        """
        self.settings = settings or get_device_server_settings()

        # Cache for loaded register maps
        self._register_map_cache: Dict[str, List[Dict[str, Any]]] = {}

    def load_register_map(
        self,
        protocol: ProtocolDefinition,
    ) -> List[Dict[str, Any]]:
        """
        Load register map for a protocol.

        Args:
            protocol: Protocol definition.

        Returns:
            List of register definitions.
        """
        if not protocol.register_map_file:
            return []

        # Check cache
        if protocol.register_map_file in self._register_map_cache:
            return self._register_map_cache[protocol.register_map_file]

        # Load from file
        map_path = self.settings.register_maps_dir / protocol.register_map_file

        if not map_path.exists():
            logger.warning(f"Register map not found: {map_path}")
            return []

        try:
            with open(map_path, "r", encoding="utf-8") as f:
                register_map = json.load(f)

            self._register_map_cache[protocol.register_map_file] = register_map
            logger.debug(
                f"Loaded register map: {protocol.register_map_file} "
                f"({len(register_map)} registers)"
            )
            return register_map

        except Exception as e:
            logger.error(f"Error loading register map {map_path}: {e}")
            return []

    def create_adapter(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
    ) -> Any:
        """
        Create an adapter for a device.

        Args:
            connection: TCP connection to device.
            protocol: Protocol definition.

        Returns:
            Adapter instance for the device.
        """
        register_map = self.load_register_map(protocol)

        if protocol.protocol_type in (
            ProtocolType.MODBUS_TCP,
            ProtocolType.MODBUS_RTU,
        ):
            return TCPModbusAdapter(connection, protocol, register_map)
        elif protocol.protocol_type == ProtocolType.COMMAND:
            return TCPCommandAdapter(connection, protocol, register_map)
        else:
            logger.warning(
                f"Unsupported protocol type: {protocol.protocol_type}"
            )
            return TCPModbusAdapter(connection, protocol, register_map)

    def clear_cache(self) -> None:
        """Clear the register map cache."""
        self._register_map_cache.clear()
