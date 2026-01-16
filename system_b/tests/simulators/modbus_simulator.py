"""
Modbus TCP simulator.

Provides a simulated Modbus TCP server that responds to
function codes 0x03 (Read Holding Registers) and 0x06 (Write Single Register).
"""
import asyncio
import logging
import struct
from typing import Dict, Optional

from .base_simulator import BaseSimulator

logger = logging.getLogger(__name__)


class ModbusTCPSimulator(BaseSimulator):
    """
    Modbus TCP server simulator.

    Responds to Modbus TCP requests for reading and writing registers.
    Maintains an internal register map that can be read and modified.
    """

    # Modbus function codes
    READ_HOLDING_REGISTERS = 0x03
    READ_INPUT_REGISTERS = 0x04
    WRITE_SINGLE_REGISTER = 0x06
    WRITE_MULTIPLE_REGISTERS = 0x10

    def __init__(
        self,
        register_map: Optional[Dict[int, int]] = None,
        unit_id: int = 1,
        serial_number: str = "MODSIM001",
        name: str = "ModbusSimulator",
    ):
        """
        Initialize Modbus TCP simulator.

        Args:
            register_map: Initial register values (address -> value).
            unit_id: Modbus unit ID to respond to.
            serial_number: Device serial number.
            name: Human-readable name.
        """
        super().__init__(serial_number=serial_number, name=name)

        self.unit_id = unit_id
        self.registers: Dict[int, int] = register_map.copy() if register_map else {}

        # Response delay simulation (milliseconds)
        self.response_delay_ms: float = 0

        # Error simulation
        self._error_rate: float = 0.0  # Probability of error response
        self._timeout_rate: float = 0.0  # Probability of no response

    def get_register(self, address: int) -> int:
        """
        Get register value.

        Args:
            address: Register address.

        Returns:
            Register value (0 if not set).
        """
        return self.registers.get(address, 0)

    def set_register(self, address: int, value: int) -> None:
        """
        Set register value.

        Args:
            address: Register address.
            value: Register value (16-bit unsigned).
        """
        self.registers[address] = value & 0xFFFF

    def set_registers(self, start_address: int, values: list) -> None:
        """
        Set multiple consecutive registers.

        Args:
            start_address: Starting register address.
            values: List of register values.
        """
        for i, value in enumerate(values):
            self.set_register(start_address + i, value)

    async def handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle Modbus TCP connection."""
        while self._running:
            try:
                # Read MBAP header (7 bytes)
                header = await asyncio.wait_for(reader.read(7), timeout=30.0)
                if not header or len(header) < 7:
                    break

                # Parse MBAP header
                transaction_id, protocol_id, length, unit_id = struct.unpack(
                    ">HHHB", header
                )

                # Read PDU (length - 1 bytes, since unit_id is part of length)
                pdu_length = length - 1
                if pdu_length <= 0:
                    continue

                pdu = await asyncio.wait_for(reader.read(pdu_length), timeout=5.0)
                if not pdu:
                    break

                self._total_requests += 1

                # Check unit ID
                if unit_id != self.unit_id:
                    logger.debug(f"{self.name}: Ignoring request for unit {unit_id}")
                    continue

                # Process request
                response_pdu = self._process_request(pdu)

                if response_pdu is None:
                    # Simulate timeout
                    continue

                # Simulate response delay
                if self.response_delay_ms > 0:
                    await asyncio.sleep(self.response_delay_ms / 1000.0)

                # Build response
                response_length = len(response_pdu) + 1  # +1 for unit_id
                response_header = struct.pack(
                    ">HHHB",
                    transaction_id,
                    protocol_id,
                    response_length,
                    unit_id,
                )

                writer.write(response_header + response_pdu)
                await writer.drain()

            except asyncio.TimeoutError:
                # Client idle timeout
                break
            except (ConnectionResetError, BrokenPipeError):
                break
            except Exception as e:
                logger.error(f"{self.name}: Error processing request: {e}")
                break

    def _process_request(self, pdu: bytes) -> Optional[bytes]:
        """
        Process Modbus PDU and return response PDU.

        Args:
            pdu: Protocol Data Unit.

        Returns:
            Response PDU or None for timeout simulation.
        """
        if len(pdu) < 1:
            return self._error_response(0x00, 0x01)  # Illegal function

        function_code = pdu[0]

        if function_code == self.READ_HOLDING_REGISTERS:
            return self._handle_read_registers(pdu)
        elif function_code == self.READ_INPUT_REGISTERS:
            return self._handle_read_registers(pdu)
        elif function_code == self.WRITE_SINGLE_REGISTER:
            return self._handle_write_single_register(pdu)
        elif function_code == self.WRITE_MULTIPLE_REGISTERS:
            return self._handle_write_multiple_registers(pdu)
        else:
            return self._error_response(function_code, 0x01)  # Illegal function

    def _handle_read_registers(self, pdu: bytes) -> bytes:
        """
        Handle Read Holding/Input Registers (FC 0x03/0x04).

        Request format: FC (1) + Start Address (2) + Quantity (2) = 5 bytes
        Response format: FC (1) + Byte Count (1) + Values (2 * quantity)
        """
        if len(pdu) < 5:
            return self._error_response(pdu[0], 0x03)  # Illegal data value

        function_code = pdu[0]
        start_address, quantity = struct.unpack(">HH", pdu[1:5])

        # Validate quantity (max 125 registers)
        if quantity < 1 or quantity > 125:
            return self._error_response(function_code, 0x03)

        # Read register values
        values = []
        for i in range(quantity):
            addr = start_address + i
            values.append(self.get_register(addr))

        # Build response
        byte_count = quantity * 2
        response = struct.pack(">BB", function_code, byte_count)
        for value in values:
            response += struct.pack(">H", value)

        return response

    def _handle_write_single_register(self, pdu: bytes) -> bytes:
        """
        Handle Write Single Register (FC 0x06).

        Request format: FC (1) + Address (2) + Value (2) = 5 bytes
        Response format: Echo of request
        """
        if len(pdu) < 5:
            return self._error_response(pdu[0], 0x03)

        function_code = pdu[0]
        address, value = struct.unpack(">HH", pdu[1:5])

        # Write register
        self.set_register(address, value)

        # Echo back the request
        return pdu[:5]

    def _handle_write_multiple_registers(self, pdu: bytes) -> bytes:
        """
        Handle Write Multiple Registers (FC 0x10).

        Request format: FC (1) + Start Address (2) + Quantity (2) + Byte Count (1) + Values
        Response format: FC (1) + Start Address (2) + Quantity (2) = 5 bytes
        """
        if len(pdu) < 6:
            return self._error_response(pdu[0], 0x03)

        function_code = pdu[0]
        start_address, quantity, byte_count = struct.unpack(">HHB", pdu[1:6])

        expected_bytes = quantity * 2
        if byte_count != expected_bytes or len(pdu) < 6 + byte_count:
            return self._error_response(function_code, 0x03)

        # Write registers
        for i in range(quantity):
            offset = 6 + i * 2
            value = struct.unpack(">H", pdu[offset:offset + 2])[0]
            self.set_register(start_address + i, value)

        # Build response
        return struct.pack(">BHH", function_code, start_address, quantity)

    def _error_response(self, function_code: int, exception_code: int) -> bytes:
        """
        Build error response.

        Args:
            function_code: Original function code.
            exception_code: Modbus exception code.

        Returns:
            Error response PDU.
        """
        return struct.pack(">BB", function_code | 0x80, exception_code)

    def encode_ascii_to_registers(self, text: str, num_registers: int) -> list:
        """
        Encode ASCII text to register values.

        Each register holds 2 ASCII characters.

        Args:
            text: Text to encode.
            num_registers: Number of registers to fill.

        Returns:
            List of register values.
        """
        # Pad or truncate text
        text = text.ljust(num_registers * 2)[:num_registers * 2]

        values = []
        for i in range(0, len(text), 2):
            high = ord(text[i])
            low = ord(text[i + 1]) if i + 1 < len(text) else 0
            values.append((high << 8) | low)

        return values

    def set_serial_number_registers(self, start_address: int, serial: str, num_registers: int = 5) -> None:
        """
        Set serial number in register map.

        Args:
            start_address: Starting register address for serial.
            serial: Serial number string.
            num_registers: Number of registers for serial (default 5 = 10 chars).
        """
        values = self.encode_ascii_to_registers(serial, num_registers)
        self.set_registers(start_address, values)
