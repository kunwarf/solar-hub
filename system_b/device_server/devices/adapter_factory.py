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
_MAX_PAYLOAD = 65536   # JK BMS bus dumps can exceed 8 KB (multiple broadcast cycles)

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

    async def write_register(self, address: int, value: int, retries: int = 2) -> None:
        """
        Write single holding register (public API).

        Uses FC16 (Write Multiple Registers) even for single registers because the
        Deye/Powdrive spec mandates FC16 for all R/W registers (addresses 60-499).
        FC06 (Write Single Register) is rejected by the inverter for those addresses.

        Retries on transient failures (e.g. timeout waiting for Modbus ACK over
        RS485/TCP — the inverter may have accepted the write even if the response
        was lost, so retries are safe for idempotent register writes).

        Args:
            address: Register address.
            value: Value to write (0-65535).
            retries: Number of additional attempts after first failure (default 2).

        Raises:
            ValueError: If value is out of range.
            Exception: On communication error after all retries exhausted.
        """
        if not 0 <= value <= 65535:
            raise ValueError(f"Value {value} out of range [0, 65535]")

        last_exc: Exception = RuntimeError("no attempts made")
        for attempt in range(retries + 1):
            try:
                # Use FC16 (write multiple registers) with a single value.
                # The spec restricts registers 60-499 to FC16; FC06 is not accepted.
                await self._write_holding_u16_list(address, [value])
                if attempt > 0:
                    logger.info(
                        f"[MODBUS] Write addr={address} succeeded on attempt {attempt + 1}"
                    )
                return
            except Exception as e:
                last_exc = e
                if attempt < retries:
                    logger.warning(
                        f"[MODBUS] Write addr={address} attempt {attempt + 1} failed "
                        f"({type(e).__name__}: {e}), retrying in 1s..."
                    )
                    await asyncio.sleep(1.0)
                else:
                    logger.error(
                        f"[MODBUS] Write addr={address} failed after {retries + 1} attempts: "
                        f"{type(e).__name__}: {e}"
                    )
        raise last_exc

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
                    "grid_power_w", "load_power_w", "phase_r_watt_of_eps", "inverter_temp_c"]:
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
        offset = r.get("offset")
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
            # Word order is manufacturer-specific, configured per protocol in protocols.yaml.
            # Powdrive/Deye: "little_endian" — regs[0] is LOW word, regs[1] is HIGH word.
            # Senergy and most others: "big_endian" — regs[0] is HIGH word (standard Modbus).
            little_endian = (
                self.protocol is not None
                and self.protocol.telemetry.u32_word_order == "little_endian"
            )
            if little_endian:
                lo, hi = regs[0], regs[1]
            else:
                hi, lo = regs[0], regs[1]
            val = (hi << 16) | lo
            if "s32" in t and val & 0x80000000:
                val = -((~val & 0xFFFFFFFF) + 1)
        else:
            val = 0

        # HHMM decoders: both normalise to decimal-HHMM integer (e.g. 630 = 06:30)
        # so the same user-facing value format works for reads and writes.
        if enc == "hhmm_decimal":
            # Powdrive stores time as decimal HHMM (e.g. 630 means 06:30).
            # Raw register value IS already in this format — return as-is.
            return int(val)
        if enc == "hhmm_binary":
            # Senergy stores time as binary-packed byte (hour<<8 | minute).
            # Normalise to decimal HHMM so the user always works in one format.
            raw_int = int(val)
            hour = (raw_int >> 8) & 0xFF
            minute = raw_int & 0xFF
            return hour * 100 + minute  # e.g. 0x061E (1566) → 630

        # Apply offset before scale: actual = (raw - offset) * scale
        if offset is not None and isinstance(val, (int, float)):
            val = val - offset

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

        # Background task that responds to PING keepalives during idle periods
        self._keepalive_task: Optional[asyncio.Task] = None

        # Stateful stream parser for JK BMS serial bridge (reference approach):
        # accumulates raw RS485 bytes across polls, tracks current_battery_id
        # via Modbus request frames, returns latest per-unit telemetry.
        self._jkbms_stream: Optional[Any] = None

        # Voltronic: detected protocol family (PI30 / PI18), set on first poll.
        self._voltronic_pid: Optional[str] = None
        # Counter used to poll QPIWS/QPIRI at reduced frequency.
        self._voltronic_poll_count: int = 0

    async def _keepalive_loop(self) -> None:
        """
        Respond to PING frames from the ESP32 during idle periods between polls.

        The ESP32 sends PING every ~30s. _send_command_framed() handles PINGs
        that arrive DURING a command (while the lock is held). This task handles
        PINGs during the idle gap between polls when no one is reading the socket.

        Without this, a PING landing in the idle window goes unanswered and the
        ESP32 disconnects after its PING timeout (~5s), reconnecting every ~35s.
        """
        while True:
            try:
                await asyncio.sleep(1.0)

                # Skip if a command is in progress — it handles PINGs itself
                if self._command_lock.locked():
                    continue

                # Non-blocking lock attempt: skip this cycle if lock is busy
                acquired = False
                try:
                    await asyncio.wait_for(
                        self._command_lock.acquire(), timeout=0.05
                    )
                    acquired = True
                except asyncio.TimeoutError:
                    continue

                try:
                    # Short timeout: just peeking for pending PING frames
                    header = await asyncio.wait_for(
                        self.connection.read(5), timeout=1.0
                    )
                    msg_type = header[0]
                    resp_len = struct.unpack(">I", header[1:5])[0]

                    # Read and discard any payload
                    if resp_len > 0:
                        await asyncio.wait_for(
                            self.connection.read(resp_len), timeout=2.0
                        )

                    if msg_type == _MSG_PING:
                        pong = struct.pack(">BI", _MSG_PONG, 0)
                        await self.connection.write(pong, timeout=2.0)
                        logger.debug("Keepalive: PING received during idle, PONG sent")
                    else:
                        logger.warning(
                            f"Keepalive: unexpected frame {msg_type:#04x} during idle"
                        )

                except asyncio.TimeoutError:
                    pass  # No data pending — normal, nothing to do
                finally:
                    if acquired:
                        self._command_lock.release()

            except asyncio.CancelledError:
                raise
            except (ConnectionError, OSError):
                break  # Connection closed, stop loop
            except Exception as e:
                logger.debug(f"Keepalive loop error: {e}")

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
                    logger.warning(f"Binary framed response too large: {resp_len} bytes — closing connection to prevent framing corruption")
                    # Do NOT leave payload bytes in the socket; close so the next
                    # connection starts clean.  Returning None without draining
                    # causes every subsequent read to parse garbage lengths.
                    raise ValueError(f"Response payload too large: {resp_len} bytes")

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

    async def execute_voltronic_command(
        self,
        command_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a Voltronic serial command and return success/failure.

        Builds the command string from the definition template, appends the
        CRC-XMODEM frame, sends it via the serial bridge, and checks whether
        the response contains '(ACK' (success) or '(NAK' (device rejected).

        Args:
            command_type: High-level command name (from VOLTRONIC_COMMANDS).
            params:       Dict of parameter values (e.g., {"priority": 1}).

        Returns:
            Dict with keys:
              success   – bool
              command   – the raw command string sent (e.g. "POP01")
              response  – stripped response data string
              error     – error message on failure (absent on success)
        """
        # Import here to avoid circular import; command_definitions is in commands/
        from ..commands.command_definitions import VOLTRONIC_COMMANDS

        params = params or {}

        cmd_def = VOLTRONIC_COMMANDS.get(command_type)
        if not cmd_def:
            available = list(VOLTRONIC_COMMANDS.keys())
            return {
                "success": False,
                "command": command_type,
                "error": f"Unknown Voltronic command '{command_type}'. "
                         f"Available: {available}",
            }

        # Resolve named string values to their integer codes
        # e.g. priority="solar" → 1 for set_output_priority
        named_values = cmd_def.get("values", {})
        resolved_params: Dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, str) and v in named_values:
                resolved_params[k] = named_values[v]
            else:
                resolved_params[k] = v

        # Map the canonical param name to 'value' for simple single-param templates
        canonical_param = cmd_def.get("param")
        if canonical_param and canonical_param in resolved_params:
            resolved_params["value"] = resolved_params[canonical_param]
        elif canonical_param and canonical_param in params:
            resolved_params["value"] = params[canonical_param]

        # Validate numeric range
        raw_value = resolved_params.get("value")
        if raw_value is not None and cmd_def.get("param_type") in ("int", "float"):
            conv = int if cmd_def["param_type"] == "int" else float
            try:
                raw_value = conv(raw_value)
                resolved_params["value"] = raw_value
            except (ValueError, TypeError) as e:
                return {"success": False, "command": command_type, "error": str(e)}

            min_v = cmd_def.get("min_value")
            max_v = cmd_def.get("max_value")
            if min_v is not None and raw_value < min_v:
                return {
                    "success": False,
                    "command": command_type,
                    "error": f"{canonical_param} {raw_value} is below minimum {min_v}",
                }
            if max_v is not None and raw_value > max_v:
                return {
                    "success": False,
                    "command": command_type,
                    "error": f"{canonical_param} {raw_value} exceeds maximum {max_v}",
                }

        # Build the command string from template
        try:
            cmd_str = cmd_def["cmd_template"].format(**resolved_params)
        except KeyError as e:
            return {
                "success": False,
                "command": command_type,
                "error": f"Missing parameter {e} for command '{command_type}'",
            }

        # Send the framed command and read response
        logger.info(
            "Voltronic command: sending %r to device %s",
            cmd_str, self.protocol.protocol_id
        )
        raw_resp = await self.send_command_bytes(_build_voltronic_cmd(cmd_str))
        response_str = _strip_voltronic_frame(raw_resp) if raw_resp else None

        if response_str is not None and response_str.upper().startswith("ACK"):
            logger.info("Voltronic command %r: ACK received", cmd_str)
            return {
                "success": True,
                "command": cmd_str,
                "response": "(ACK",
            }
        else:
            reason = f"(NAK" if response_str and "NAK" in response_str.upper() else \
                     f"no response" if not raw_resp else \
                     f"unexpected response: {response_str!r}"
            logger.warning(
                "Voltronic command %r failed: %s (device %s)",
                cmd_str, reason, self.protocol.protocol_id
            )
            return {
                "success": False,
                "command": cmd_str,
                "error": reason,
            }

    async def poll(self) -> Dict[str, Any]:
        """
        Poll device using command-based protocol.


        Returns:
            Dictionary of parsed telemetry values.
        """
        # Ensure idle PING responder is running for serial bridge connections
        if self.connection.bridged and (
            self._keepalive_task is None or self._keepalive_task.done()
        ):
            self._keepalive_task = asyncio.create_task(
                self._keepalive_loop(),
                name=f"keepalive-{id(self)}",
            )

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

        # Voltronic inverters (PI30 / PI18) — serial bridge path only.
        # Protocol family is detected via QPI on first poll; subsequent polls
        # use QPIGS (PI30) or GS (PI18), QMOD, and QPIWS.
        elif "voltronic" in pid:
            values = await self._poll_voltronic()

        # For JK BMS serial bridge: reference approach — ESP32 is a dumb byte
        # pipe returning a burst of raw RS485 bytes per poll.  The stateful
        # JKBMSStreamParser accumulates these across polls, tracks
        # current_battery_id via Modbus request frames, and returns the
        # latest per-unit telemetry (battery_units / battery_cells lists).
        elif "jkbms_serial" in pid or ("jkbms" in pid and self.connection.bridged):
            if self._jkbms_stream is None:
                from ..telemetry.jkbms_parser import JKBMSStreamParser
                self._jkbms_stream = JKBMSStreamParser(cells_per_bms=16)

            raw = await self.send_command_bytes(b"")
            if raw:
                self._jkbms_stream.feed(raw)
                logger.debug(
                    f"JK BMS stream: fed {len(raw)} bytes, "
                    f"units={self._jkbms_stream.unit_count}, "
                    f"cycles={self._jkbms_stream.cycle_count}"
                )

            result = self._jkbms_stream.get_result()
            if result:
                values.update(result)

        return values

    async def _voltronic_detect_protocol(self) -> Optional[str]:
        """
        Detect Voltronic protocol family.

        Step 1 — Seed from registered protocol_id (fastest, most reliable).
                 If the device was registered as 'voltronic_pi17', return 'PI17'.
        Step 2 — Send QPI and parse standard '(' frame response.
        Step 3 — If QPI returns a SEC '^D' frame, parse it as SEC format.
        Returns None on complete failure (caller defaults to 'PI30').
        """
        # Step 1: use registered protocol_id if it contains a known family tag
        pid_reg = self.protocol.protocol_id.upper()
        for family in ("PI34", "PI18", "PI17", "PI16", "PI41", "PI30"):
            if family in pid_reg:
                logger.info("Voltronic: protocol family %s from registry", family)
                return family

        # Step 2: query device via QPI (standard frame format)
        raw = await self.send_command_bytes(_build_voltronic_cmd("QPI"))
        if raw:
            # Standard frame response starts with '('
            data = _strip_voltronic_frame(raw)
            if data:
                data_upper = data.upper()
                for family in ("PI34", "PI18", "PI17", "PI16", "PI41", "PI30"):
                    if family in data_upper:
                        logger.info("Voltronic: detected protocol %s via QPI", family)
                        return family

            # SEC frame response starts with '^D' — device is PI17 or PI18-InfiniSolar
            if raw.startswith(b"^D"):
                sec_data = _strip_sec_frame(raw)
                if sec_data:
                    sec_upper = sec_data.upper()
                    for family in ("PI18", "PI17", "PI16"):
                        if family in sec_upper:
                            logger.info(
                                "Voltronic: detected SEC protocol %s via QPI", family
                            )
                            return family
                # SEC device but couldn't parse family — try the SEC PI command
                sec_raw = await self.send_command_bytes(_build_sec_cmd("PI"))
                sec_resp = _strip_sec_frame(sec_raw)
                if sec_resp:
                    for family in ("PI18", "PI17"):
                        if family in sec_resp.upper():
                            logger.info(
                                "Voltronic: identified SEC protocol %s", family
                            )
                            return family
                logger.warning(
                    "Voltronic: SEC device but unrecognised protocol, defaulting to PI17"
                )
                return "PI17"

        logger.warning("Voltronic: QPI failed or unrecognised response, defaulting to PI30")
        return "PI30"

    async def _poll_voltronic(self) -> Dict[str, Any]:
        """
        Poll a Voltronic inverter/charger via the ESP8266/ESP32 serial bridge.

        Step 1  — Detect protocol family on first poll only (registry → QPI → SEC PI).
        Step 2  — Query general status (command depends on family):
                    PI30 / PI16 / PI41 → QPIGS (standard frame, space-separated)
                    PI18               → GS     (standard frame, space-separated, ×10)
                    PI17               → ^P003GS (SEC frame, comma-separated)
                    PI34               → QPIGS (standard frame, 11 fields)
        Step 3  — Query working mode (QMOD) every poll (PI30/PI16/PI34).
        Step 4  — Query warning status (QPIWS) every 5th poll (PI30/PI16/PI34).
        Step 5  — Derive battery_power_w and grid_power_w.
        """
        # Step 1: protocol detection (once per connection)
        if self._voltronic_pid is None:
            self._voltronic_pid = await self._voltronic_detect_protocol() or "PI30"

        pid = self._voltronic_pid
        values: Dict[str, Any] = {"voltronic_protocol_id": pid}

        # Step 2: general status query
        if pid == "PI18":
            # Axpert MAX — standard frame, 28 space-separated fields, int×10 encoding
            raw = await self.send_command_bytes(_build_voltronic_cmd("GS"))
            data = _strip_voltronic_frame(raw)
            if data:
                values.update(_parse_voltronic_fields(data, _PI18_GS_FIELDS))

        elif pid == "PI17":
            # InfiniSolar 5KW — SEC frame, 28 comma-separated fields
            raw = await self.send_command_bytes(_build_sec_cmd("GS"))
            data = _strip_sec_frame(raw)
            if data:
                values.update(_parse_sec_fields(data, _PI17_SEC_GS_FIELDS))
            # PI17 grid_power_w is a direct field from the SEC response; skip computed
            # battery power: signed current field (battery_current_a, +=charging)
            bat_v = values.get("battery_voltage_v")
            bat_a = values.get("battery_current_a")
            if bat_v is not None and bat_a is not None:
                # PI17 convention: positive current = charging → negate to positive_discharging
                values["battery_power_w"] = round(-float(bat_a) * float(bat_v), 1)

        elif pid == "PI16":
            # SUNNY protocol — standard frame, 22 space-separated fields, 3 MPPT
            raw = await self.send_command_bytes(_build_voltronic_cmd("QPIGS"))
            data = _strip_voltronic_frame(raw)
            if data:
                values.update(_parse_voltronic_fields(data, _PI16_QPIGS_FIELDS))
            # PI16 has no battery current field; battery_power_w stays None/absent
            # grid_power_w will be computed in Step 5 if output power is available

        elif pid == "PI34":
            # MPPT-3000 charge controller — standard frame, 11 fields, no AC data
            raw = await self.send_command_bytes(_build_voltronic_cmd("QPIGS"))
            data = _strip_voltronic_frame(raw)
            if data:
                values.update(_parse_voltronic_fields(data, _PI34_QPIGS_FIELDS))

        else:
            # PI30, PI41, PI30MAX, PI30REVO, PI30_HS/MS/MSX — standard frame, QPIGS
            # All use identical first 16 fields; shorter variants (17 vs 21) are handled
            # gracefully — parser silently ignores fields beyond the response length.
            raw = await self.send_command_bytes(_build_voltronic_cmd("QPIGS"))
            data = _strip_voltronic_frame(raw)
            if data:
                values.update(_parse_voltronic_fields(data, _PI30_QPIGS_FIELDS))

        # Step 3: working mode (not applicable to PI17 which has inverter_mode field,
        # and PI34 which is a charge controller without operating modes)
        if pid not in ("PI17", "PI34"):
            raw = await self.send_command_bytes(_build_voltronic_cmd("QMOD"))
            mode_data = _strip_voltronic_frame(raw)
            if mode_data:
                values["working_mode_raw"] = mode_data[:1]

        # Step 4: less-frequent commands (5th-poll and 30th-poll cadences)
        self._voltronic_poll_count += 1

        # Warning/fault status every 5th poll; PI17 exposes fault_code in GS response
        if self._voltronic_poll_count % 5 == 1 and pid != "PI17":
            raw = await self.send_command_bytes(_build_voltronic_cmd("QPIWS"))
            ws_data = _strip_voltronic_frame(raw)
            if ws_data:
                values["warning_status_raw"] = ws_data

        # Rated settings (QPIRI / PIRI) every 30th poll (~5 min at 10 s interval)
        # Settings rarely change — no need to read every poll.
        if self._voltronic_poll_count % 30 == 1:
            settings = await self._poll_voltronic_settings(pid)
            values.update(settings)

        # Step 5: derived quantities (battery_power_w already set for PI17/PI18 direction)
        if pid not in ("PI17", "PI34"):
            _compute_voltronic_battery_power(values)
        if pid not in ("PI17", "PI34"):
            _compute_voltronic_grid_power(values)

        logger.debug(
            "Voltronic %s poll: %d fields, bat_pwr=%.0fW, grid_pwr=%.0fW",
            pid,
            len(values),
            values.get("battery_power_w", 0),
            values.get("grid_power_w", 0),
        )
        return values

    async def _poll_voltronic_settings(self, pid: str) -> Dict[str, Any]:
        """
        Query inverter rated settings via QPIRI (standard families) or PIRI (PI17 SEC).

        Returns a dict of configuration fields to merge into the telemetry record.
        Returns an empty dict on any communication failure (non-critical).

        Settings covered:
          - Rated output voltage/frequency/current/power
          - Battery type, nominal/bulk/float/recharge/under voltages
          - Max AC charging current, total charging current
          - Output source priority (utility / solar / SBU)
          - Charger source priority (utility / solar / solar+utility / solar-only)
          - Machine type (grid-tie / off-grid / hybrid)
          - Topology (transformerless / transformer)
        """
        values: Dict[str, Any] = {}

        try:
            if pid == "PI17":
                # SEC format: ^P004PIRI\r
                raw = await self.send_command_bytes(_build_sec_cmd("PIRI"))
                data = _strip_sec_frame(raw)
                if data:
                    values.update(_parse_sec_fields(data, _PI17_SEC_PIRI_FIELDS))

            elif pid == "PI34":
                # PI34 (charge controller) uses QPIRI with different field meanings
                # but same frame format; field layout matches PI30 subset
                raw = await self.send_command_bytes(_build_voltronic_cmd("QPIRI"))
                data = _strip_voltronic_frame(raw)
                if data:
                    # PI34 QPIRI: battery nominal, bulk, float, type, max charging current
                    pi34_piri = [
                        ("battery_nominal_voltage_v",   float),
                        ("battery_bulk_voltage_v",      float),
                        ("battery_float_voltage_v",     float),
                        ("battery_type_code",           int),
                        ("charging_current_a",          int),
                    ]
                    values.update(_parse_voltronic_fields(data, pi34_piri))

            elif pid == "PI18":
                raw = await self.send_command_bytes(_build_voltronic_cmd("QPIRI"))
                data = _strip_voltronic_frame(raw)
                if data:
                    values.update(_parse_voltronic_fields(data, _PI18_QPIRI_FIELDS))

            else:
                # PI30, PI16, PI41, PI30MAX and all other standard families
                raw = await self.send_command_bytes(_build_voltronic_cmd("QPIRI"))
                data = _strip_voltronic_frame(raw)
                if data:
                    values.update(_parse_voltronic_fields(data, _PI30_QPIRI_FIELDS))

        except Exception as e:
            logger.warning("Voltronic QPIRI failed for %s: %s", pid, e)
            return {}

        # Annotate numeric codes with human-readable strings
        bat_type = values.get("battery_type_code")
        if bat_type is not None:
            values["battery_type"] = _BATTERY_TYPES.get(int(bat_type), f"unknown_{bat_type}")

        out_prio = values.get("output_source_priority")
        if out_prio is not None:
            values["output_source_priority_str"] = _OUTPUT_PRIORITY.get(
                int(out_prio), f"unknown_{out_prio}"
            )

        chg_prio = values.get("charger_source_priority")
        if chg_prio is not None:
            values["charger_source_priority_str"] = _CHARGER_PRIORITY.get(
                int(chg_prio), f"unknown_{chg_prio}"
            )

        if values:
            logger.debug(
                "Voltronic %s QPIRI: bat_type=%s, out_prio=%s, chg_prio=%s",
                pid,
                values.get("battery_type"),
                values.get("output_source_priority_str"),
                values.get("charger_source_priority_str"),
            )

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


# =============================================================================
# Voltronic serial protocol helpers (module-level, used by TCPCommandAdapter)
# =============================================================================

def _voltronic_crc(data: bytes) -> bytes:
    """
    CRC-XMODEM over command bytes (poly 0x1021, init 0, no reflection).

    Returns two bytes with reserved values escaped:
      0x28 → 0x29  (avoids collision with response leader '(')
      0x0D → 0x0E  (avoids collision with frame terminator CR)
      0x0A → 0x0B  (avoids collision with LF)
    """
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
        crc &= 0xFFFF

    def _esc(b: int) -> int:
        return b + 1 if b in (0x28, 0x0D, 0x0A) else b

    return bytes([_esc((crc >> 8) & 0xFF), _esc(crc & 0xFF)])


def _build_voltronic_cmd(cmd: str) -> bytes:
    """Build a Voltronic command frame: ASCII command + CRC(2) + CR."""
    data = cmd.encode("ascii")
    return data + _voltronic_crc(data) + b"\r"


def _strip_voltronic_frame(raw: Optional[bytes]) -> Optional[str]:
    """
    Strip Voltronic response framing and return the bare data string.

    Frame: ( <data> <CRC_H> <CRC_L> CR
    Returns None if the response is absent or malformed.
    """
    if not raw or not raw.startswith(b"("):
        return None
    cr_pos = raw.rfind(b"\r")
    if cr_pos < 3:  # need at least '(' + 1 byte + 2 CRC + CR
        return None
    # Slice: skip leading '(', drop 2 CRC bytes before CR
    return raw[1 : cr_pos - 2].decode("ascii", errors="replace").strip()


# QPIGS PI30 — 21 space-separated fields (indices 0-20)
_PI30_QPIGS_FIELDS = [
    ("grid_voltage_v",              float),
    ("grid_frequency_hz",           float),
    ("ac_output_voltage_v",         float),
    ("ac_output_frequency_hz",      float),
    ("ac_output_apparent_va",       int),
    ("ac_output_active_w",          int),
    ("output_load_pct",             int),
    ("bus_voltage_v",               int),
    ("battery_voltage_v",           float),
    ("battery_charging_current_a",  int),
    ("battery_capacity_pct",        int),
    ("heatsink_temp_c",             int),
    ("pv_input_current_a",          float),
    ("pv_input_voltage_v",          float),
    ("battery_scc_voltage_v",       float),
    ("battery_discharge_current_a", int),
    ("device_status_raw",           str),   # 8-bit flag string
    ("rsv_battery_offset",          int),
    ("eeprom_version",              int),
    ("pv_input_power_w",            int),
    ("device_status2_raw",          str),   # 3-bit flag string
]

# GS PI18 — 28 space-separated fields (indices 0-27)
# Fields 0-3, 7-9, 18-19 are integer×10 (divide by 10 for actual value).
_PI18_GS_FIELDS = [
    ("grid_voltage_v",              lambda x: int(x) / 10),
    ("grid_frequency_hz",           lambda x: int(x) / 10),
    ("ac_output_voltage_v",         lambda x: int(x) / 10),
    ("ac_output_frequency_hz",      lambda x: int(x) / 10),
    ("ac_output_apparent_va",       int),
    ("ac_output_active_w",          int),
    ("output_load_pct",             int),
    ("battery_voltage_v",           lambda x: int(x) / 10),
    ("battery_scc1_voltage_v",      lambda x: int(x) / 10),
    ("battery_scc2_voltage_v",      lambda x: int(x) / 10),
    ("battery_discharge_current_a", int),
    ("battery_charging_current_a",  int),
    ("battery_capacity_pct",        int),
    ("heatsink_temp_c",             int),
    ("mppt1_temp_c",                int),
    ("mppt2_temp_c",                int),
    ("pv1_input_power_w",           int),
    ("pv2_input_power_w",           int),
    ("pv1_input_voltage_v",         lambda x: int(x) / 10),
    ("pv2_input_voltage_v",         lambda x: int(x) / 10),
    ("config_status",               int),   # option code
    ("mppt1_charger_status",        int),   # option code
    ("mppt2_charger_status",        int),   # option code
    ("load_connection",             int),   # option code
    ("battery_power_direction",     int),   # 0=idle, 1=charging, 2=discharging
    ("dc_ac_power_direction",       int),   # option code
    ("line_power_direction",        int),   # 0=idle, 1=input, 2=output
    ("parallel_id",                 int),
]


def _safe_voltronic_float(x: str) -> Optional[float]:
    """
    Convert a Voltronic field to float, returning None for placeholder values.

    PI16 QPIGS uses '---.-' and '-----' for unavailable PV strings.
    """
    s = x.strip()
    if not s or all(c in "-. " for c in s):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# QPIGS PI16 — 22 space-separated fields (SUNNY / PI15 / PI16 protocol)
# Fields with placeholder '---.-' or '-----' (unused PV strings) are parsed
# via _safe_voltronic_float which returns None; the adapter drops None values.
_PI16_QPIGS_FIELDS = [
    ("grid_voltage_v",          float),                # AAA.A
    ("ac_output_active_w",      int),                  # BBBBBB (output power W)
    ("grid_frequency_hz",       float),                # CC.C
    ("ac_output_current_a",     float),                # DDDD.D
    ("ac_output_voltage_v",     float),                # EEE.E (output voltage R)
    ("ac_output_power_r_w",     _safe_voltronic_float),# FFFFF (output power R)
    ("ac_output_frequency_hz",  float),                # GG.G
    ("ac_output_current_r_a",   _safe_voltronic_float),# HHH.H
    ("output_load_pct",         int),                  # III
    ("pbus_voltage_v",          float),                # JJJ.J
    ("sbus_voltage_v",          float),                # KKK.K
    ("battery_voltage_v",       float),                # LLL.L (positive battery V)
    ("battery_neg_voltage_v",   _safe_voltronic_float),# MMM.M (negative; --- for single)
    ("battery_capacity_pct",    int),                  # NNN
    ("pv1_input_power_w",       _safe_voltronic_float),# OOOOO
    ("pv2_input_power_w",       _safe_voltronic_float),# PPPPP
    ("pv3_input_power_w",       _safe_voltronic_float),# QQQQQ (--- if not present)
    ("pv1_input_voltage_v",     float),                # RRR.R
    ("pv2_input_voltage_v",     _safe_voltronic_float),# SSS.S
    ("pv3_input_voltage_v",     _safe_voltronic_float),# TTT.T
    ("max_temp_c",              float),                # UUU.U
    ("device_status_raw",       str),                  # VWWWWWWWWW (9-bit: V + WWWWWWWWW)
]

# QPIGS PI34 — 11 space-separated fields (MPPT-3000 charge controller)
# Temperatures and some current fields are signed integers.
_PI34_QPIGS_FIELDS = [
    ("pv_input_voltage_v",          float),     # BBB.B
    ("battery_voltage_v",           float),     # CC.CC
    ("charging_current_a",          float),     # DD.DD (total charging current)
    ("charging_current1_a",         float),     # EE.EE (charger 1)
    ("charging_current2_a",         float),     # FF.FF (charger 2)
    ("charging_power_w",            int),       # GGGG
    ("unit_temp_c",                 int),       # ±HHH (signed)
    ("remote_battery_voltage_v",    float),     # II.II
    ("remote_battery_temp_c",       int),       # ±JJJ (signed)
    ("reserved",                    str),       # KKKK
    ("device_status_raw",           str),       # b7-b0
]

# GS PI17 — 28 comma-separated fields (InfiniSolar 5KW, SEC frame format)
# Solar voltages/currents use 0.1-unit steps (divide by 10).
# Battery current signed: positive = charging, negative = discharging.
# Battery voltage uses 0.01V steps (divide by 100).
_PI17_SEC_GS_FIELDS = [
    ("pv1_input_voltage_v",         lambda x: int(x) / 10),    # 0001-9999 (0.1V)
    ("pv1_input_current_a",         lambda x: int(x) / 10),    # 0001-9999 (0.1A)
    ("pv1_input_power_w",           int),                       # 00001-99999 (W)
    ("pv2_input_voltage_v",         lambda x: int(x) / 10),    # (0.1V)
    ("pv2_input_current_a",         lambda x: int(x) / 10),    # (0.1A)
    ("pv2_input_power_w",           int),                       # (W)
    ("battery_voltage_v",           lambda x: int(x) / 100),   # 0001-9999 (0.01V)
    ("battery_current_a",           lambda x: int(x) / 10),    # signed (0.1A, +chg)
    ("battery_capacity_pct",        int),                       # 000-100 (%)
    ("ac_output_voltage_v",         lambda x: int(x) / 10),    # (0.1V)
    ("ac_output_frequency_hz",      lambda x: int(x) / 10),    # (0.1Hz)
    ("ac_output_current_a",         lambda x: int(x) / 10),    # (0.1A)
    ("ac_output_apparent_va",       int),                       # (VA)
    ("ac_output_active_w",          int),                       # (W)
    ("output_load_pct",             int),                       # (%)
    ("heatsink_temp_c",             int),                       # (°C)
    ("battery_temp_c",              int),                       # (°C)
    ("remote_battery_voltage_v",    lambda x: int(x) / 100),   # (0.01V)
    ("remote_battery_temp_c",       int),                       # (°C)
    ("grid_voltage_v",              lambda x: int(x) / 10),    # (0.1V)
    ("grid_frequency_hz",           lambda x: int(x) / 10),    # (0.1Hz)
    ("grid_power_w",                int),                       # (W, signed)
    ("inverter_mode",               int),                       # operating mode code
    ("fault_code",                  int),                       # fault code
    ("warning_code",                int),                       # warning code
    ("fan1_speed_pct",              int),                       # fan 1 (%)
    ("fan2_speed_pct",              int),                       # fan 2 (%)
    ("reserved",                    str),                       # reserved
]


# QPIRI — Rated / settings information (PI30 family, 20 space-separated fields)
# Polled at low frequency (every 30th poll ~= every 5 min at 10s interval).
# Tells us: configured output voltage/frequency, battery type, charging limits,
# source priority, machine type, topology, etc.
_PI30_QPIRI_FIELDS = [
    ("rated_output_voltage_v",      float),     # BBB.B
    ("rated_output_frequency_hz",   float),     # CC.C
    ("rated_ac_output_current_a",   float),     # DD.D
    ("rated_ac_apparent_va",        int),       # EEEE
    ("rated_ac_active_w",           int),       # FFFF
    ("battery_nominal_voltage_v",   float),     # GGG.G
    ("battery_recharge_voltage_v",  float),     # HHH.H
    ("battery_under_voltage_v",     float),     # III.I
    ("battery_bulk_voltage_v",      float),     # JJJ.J
    ("battery_float_voltage_v",     float),     # KKK.K
    ("battery_type_code",           int),       # LLL (0=AGM,1=Flooded,2=User,3=Pylon,5=Weco)
    ("ac_charging_current_a",       int),       # MMM
    ("charging_current_a",          int),       # NNN (total max charging current)
    ("input_voltage_range",         int),       # O   (0=Appliance,1=UPS)
    ("output_source_priority",      int),       # P   (0=Utility,1=Solar,2=SBU)
    ("charger_source_priority",     int),       # Q   (0=Utility,1=Solar,2=Solar+Utility,3=Solar only)
    ("parallel_max_num",            int),       # RR
    ("machine_type_code",           str),       # SS  (00=Grid-tie,01=Off-grid,10=Hybrid)
    ("topology_code",               int),       # T   (0=Transformerless,1=Transformer)
    ("output_mode_code",            int),       # UU  (00=single,01=parallel,02-04=phase)
]

# QPIRI — PI18 Axpert MAX (20 space-separated fields, same semantics as PI30)
# PI18 adds battery_recharge_when_soc and battery_recharge_to_soc as last two fields.
_PI18_QPIRI_FIELDS = [
    ("rated_output_voltage_v",      float),     # field 0
    ("rated_output_frequency_hz",   float),
    ("rated_ac_output_current_a",   float),
    ("rated_ac_apparent_va",        int),
    ("rated_ac_active_w",           int),
    ("battery_nominal_voltage_v",   float),
    ("battery_recharge_voltage_v",  float),
    ("battery_under_voltage_v",     float),
    ("battery_bulk_voltage_v",      float),
    ("battery_float_voltage_v",     float),
    ("battery_type_code",           int),
    ("ac_charging_current_a",       int),
    ("charging_current_a",          int),
    ("input_voltage_range",         int),
    ("output_source_priority",      int),
    ("charger_source_priority",     int),
    ("parallel_max_num",            int),
    ("machine_type_code",           str),
    ("topology_code",               int),
    ("output_mode_code",            int),
    ("battery_recharge_when_soc",   int),       # PI18 extra: recharge threshold (%)
    ("battery_recharge_to_soc",     int),       # PI18 extra: recharge target (%)
]

# PIRI — PI17 SEC rated information (comma-separated, SEC frame)
_PI17_SEC_PIRI_FIELDS = [
    ("rated_output_voltage_v",      lambda x: int(x) / 10),
    ("rated_output_frequency_hz",   lambda x: int(x) / 10),
    ("rated_ac_output_current_a",   lambda x: int(x) / 10),
    ("rated_ac_apparent_va",        int),
    ("battery_nominal_voltage_v",   lambda x: int(x) / 10),
    ("battery_recharge_voltage_v",  lambda x: int(x) / 10),
    ("battery_under_voltage_v",     lambda x: int(x) / 10),
    ("battery_bulk_voltage_v",      lambda x: int(x) / 10),
    ("battery_float_voltage_v",     lambda x: int(x) / 10),
    ("battery_type_code",           int),
    ("ac_charging_current_a",       int),
    ("charging_current_a",          int),
    ("input_voltage_range",         int),
    ("output_source_priority",      int),
    ("charger_source_priority",     int),
    ("machine_type_code",           int),
    ("topology_code",               int),
    ("output_mode_code",            int),
]

# Human-readable labels for settings codes
_BATTERY_TYPES = {0: "AGM", 1: "Flooded", 2: "User", 3: "Pylontech",
                  5: "Weco", 6: "Soltaro", 8: "Lib", 9: "Lic"}
_OUTPUT_PRIORITY = {0: "utility_first", 1: "solar_first", 2: "sbu"}
_CHARGER_PRIORITY = {0: "utility_first", 1: "solar_first",
                     2: "solar_and_utility", 3: "solar_only"}


def _parse_voltronic_fields(
    data: str,
    field_defs: list,
) -> Dict[str, Any]:
    """Parse space-separated Voltronic response data into a dict."""
    parts = data.split()
    result: Dict[str, Any] = {}
    for i, (name, conv) in enumerate(field_defs):
        if i >= len(parts):
            break
        try:
            val = conv(parts[i])
            if val is not None:
                result[name] = val
        except (ValueError, TypeError):
            logger.debug("Voltronic: could not parse field %s=%r", name, parts[i])
    return result


def _compute_voltronic_battery_power(values: Dict[str, Any]) -> None:
    """
    Derive battery_power_w from separate charge/discharge current fields.

    Convention (positive_discharging):
      positive → battery supplying load (discharging)
      negative → battery absorbing power (charging)
    """
    bat_v = values.get("battery_voltage_v")
    chg_a = values.get("battery_charging_current_a")
    dis_a = values.get("battery_discharge_current_a")
    if bat_v is None:
        return
    chg = float(chg_a or 0)
    dis = float(dis_a or 0)
    # net: positive = discharging
    values["battery_power_w"] = round((dis - chg) * float(bat_v), 1)


def _compute_voltronic_grid_power(values: Dict[str, Any]) -> None:
    """
    Derive grid_power_w via energy balance:
      grid = load - pv - battery_net
    Negative result = exporting to grid.

    Falls back to voltage × current when pv_input_power_w is absent
    (handles PI30REVO / PI30_HS_MS_MSX which lack the power field).
    """
    load = values.get("ac_output_active_w") or values.get("load_power_w")
    # Primary: explicit power field(s)
    pv: Optional[float] = values.get("pv_input_power_w")
    if pv is None:
        pv1w = values.get("pv1_input_power_w")
        pv2w = values.get("pv2_input_power_w")
        pv3w = values.get("pv3_input_power_w")
        if any(x is not None for x in (pv1w, pv2w, pv3w)):
            pv = (pv1w or 0.0) + (pv2w or 0.0) + (pv3w or 0.0)
    # Fallback: derive from V×I when the power register is absent (REVO/HS/MSX)
    if pv is None:
        pv_v = values.get("pv_input_voltage_v")
        pv_a = values.get("pv_input_current_a")
        if pv_v is not None and pv_a is not None:
            pv = float(pv_v) * float(pv_a)
    bat = values.get("battery_power_w", 0)
    if load is None:
        return
    values["grid_power_w"] = round(float(load) - float(pv or 0) - float(bat), 1)


# =============================================================================
# SEC frame format helpers (PI17 InfiniSolar 5KW and PI18 InfiniSolar V)
# =============================================================================
# Frame: ^ T nnn PAYLOAD \r
#   T   = P (command) or D (data response)
#   nnn = 3-digit decimal length of PAYLOAD (not including \r)
#   PAYLOAD for data responses includes 2 CRC bytes at the end
# CRC: CRC-CCITT poly 0x1021, init 0xFFFF (differs from standard Voltronic 0x0000 init)

def _sec_crc(data: bytes) -> bytes:
    """CRC-CCITT for SEC frame format (poly 0x1021, init 0xFFFF, no reflection)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
        crc &= 0xFFFF
    return bytes([(crc >> 8) & 0xFF, crc & 0xFF])


def _build_sec_cmd(cmd: str) -> bytes:
    """
    Build a SEC-format command frame: ^Pnnn<cmd><CR>
    nnn = len(cmd) + 1  (counts the trailing <CR> as part of payload length)
    No CRC in commands for PI17; some firmware variants accept it — omitting is safe.
    """
    payload = cmd.encode("ascii")
    nnn = len(payload) + 1  # +1 for the \r terminator
    return b"^P" + f"{nnn:03d}".encode("ascii") + payload + b"\r"


def _strip_sec_frame(raw: Optional[bytes]) -> Optional[str]:
    """
    Strip SEC response framing and return the bare comma-separated data string.

    Frame: ^ D nnn DATA <CRC_H> <CRC_L> \r
    Returns None if absent, wrong prefix, or too short.
    """
    if not raw or not raw.startswith(b"^D"):
        return None
    cr_pos = raw.rfind(b"\r")
    # Minimum valid frame: ^D + 3-digit nnn + 1 data byte + 2 CRC = 9 bytes
    if cr_pos < 8:
        return None
    # Skip "^D" (2) + nnn (3) = 5 bytes header; drop 2 CRC bytes before \r
    return raw[5:cr_pos - 2].decode("ascii", errors="replace").strip()


def _parse_sec_fields(data: str, field_defs: list) -> Dict[str, Any]:
    """Parse comma-separated SEC response data into a dict."""
    parts = [p.strip() for p in data.split(",")]
    result: Dict[str, Any] = {}
    for i, (name, conv) in enumerate(field_defs):
        if i >= len(parts):
            break
        try:
            val = conv(parts[i])
            if val is not None:
                result[name] = val
        except (ValueError, TypeError):
            logger.debug("Voltronic SEC: could not parse field %s=%r", name, parts[i])
    return result


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
