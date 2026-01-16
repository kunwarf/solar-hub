"""
Adapter factory for creating device adapters.

Creates appropriate adapter instances based on protocol definitions,
with TCP connection wrapping for data logger communication.
"""
import importlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

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

    async def poll(self) -> Dict[str, Any]:
        """
        Poll all readable registers and return telemetry data.

        Returns:
            Dictionary of register ID to decoded value.
        """
        values: Dict[str, Any] = {}

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

            except Exception as e:
                logger.debug(f"Failed to read register {reg_id}: {e}")
                continue

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

    async def send_command(self, command: str) -> Optional[str]:
        """
        Send command and get response.

        Args:
            command: Command string.

        Returns:
            Response string or None.
        """
        try:
            cmd_bytes = (command + self.line_ending).encode("utf-8")
            await self.connection.write(cmd_bytes, timeout=self.timeout)

            # Read response lines
            response_lines = []
            import asyncio

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
            logger.debug(f"Command error: {e}")
            return None

    async def poll(self) -> Dict[str, Any]:
        """
        Poll device using command-based protocol.

        Returns:
            Dictionary of parsed telemetry values.
        """
        values: Dict[str, Any] = {}

        # For Pytes, common commands
        if "pytes" in self.protocol.protocol_id.lower():
            # Power command
            response = await self.send_command("pwr")
            if response:
                values["power_response"] = response

            # Battery info
            response = await self.send_command("bat")
            if response:
                values["battery_response"] = response

        return values


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
