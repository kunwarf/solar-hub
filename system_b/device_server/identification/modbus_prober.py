"""
Modbus-based device identification.

Probes devices using Modbus TCP protocol to identify device type
by reading identification registers.
"""
import asyncio
import logging
import struct
from typing import List, Optional, Tuple

from ..connection.tcp_connection import TCPConnection
from ..connection.connection_manager import IdentifiedDevice
from ..protocols.definitions import ProtocolDefinition, ProtocolType

logger = logging.getLogger(__name__)


class ModbusProber:
    """
    Modbus-based device prober.

    Uses Modbus TCP to read identification registers and determine
    device type and protocol.
    """

    # Modbus function codes
    READ_HOLDING_REGISTERS = 0x03
    READ_INPUT_REGISTERS = 0x04

    def __init__(self, timeout: float = 5.0):
        """
        Initialize the Modbus prober.

        Args:
            timeout: Timeout for Modbus operations.
        """
        self.timeout = timeout
        self._transaction_id = 0

    def _next_transaction_id(self) -> int:
        """Get next Modbus transaction ID."""
        self._transaction_id = (self._transaction_id + 1) & 0xFFFF
        return self._transaction_id

    def _build_mbap_header(
        self,
        transaction_id: int,
        length: int,
        unit_id: int = 1,
    ) -> bytes:
        """
        Build Modbus Application Protocol (MBAP) header.

        Args:
            transaction_id: Transaction identifier.
            length: Length of following data (unit ID + PDU).
            unit_id: Modbus unit/slave ID.

        Returns:
            7-byte MBAP header.
        """
        # MBAP Header: Transaction ID (2) | Protocol ID (2) | Length (2) | Unit ID (1)
        return struct.pack(
            ">HHHB",
            transaction_id,
            0,  # Protocol ID (0 = Modbus)
            length,
            unit_id,
        )

    def _build_read_request(
        self,
        register: int,
        count: int,
        unit_id: int = 1,
        function_code: int = READ_HOLDING_REGISTERS,
    ) -> Tuple[bytes, int]:
        """
        Build Modbus read registers request.

        Args:
            register: Starting register address.
            count: Number of registers to read.
            unit_id: Modbus unit ID.
            function_code: Read function code.

        Returns:
            Tuple of (request bytes, transaction ID).
        """
        transaction_id = self._next_transaction_id()

        # PDU: Function Code (1) | Start Address (2) | Quantity (2)
        pdu = struct.pack(">BHH", function_code, register, count)

        # MBAP + PDU
        mbap = self._build_mbap_header(transaction_id, len(pdu) + 1, unit_id)

        return mbap + pdu, transaction_id

    def _parse_read_response(
        self,
        data: bytes,
        expected_transaction_id: int,
    ) -> Optional[List[int]]:
        """
        Parse Modbus read registers response.

        Args:
            data: Response bytes.
            expected_transaction_id: Expected transaction ID.

        Returns:
            List of register values, or None on error.
        """
        if len(data) < 9:
            logger.debug(f"Response too short: {len(data)} bytes")
            return None

        # Parse MBAP header
        transaction_id, protocol_id, length, unit_id = struct.unpack(
            ">HHHB", data[:7]
        )

        if transaction_id != expected_transaction_id:
            logger.debug(
                f"Transaction ID mismatch: {transaction_id} != "
                f"{expected_transaction_id}"
            )
            return None

        if protocol_id != 0:
            logger.debug(f"Invalid protocol ID: {protocol_id}")
            return None

        # Parse PDU
        function_code = data[7]

        # Check for exception response
        if function_code & 0x80:
            exception_code = data[8] if len(data) > 8 else 0
            logger.debug(
                f"Modbus exception: function={function_code & 0x7F}, "
                f"exception={exception_code}"
            )
            return None

        if function_code not in (
            self.READ_HOLDING_REGISTERS,
            self.READ_INPUT_REGISTERS,
        ):
            logger.debug(f"Unexpected function code: {function_code}")
            return None

        # Parse data
        byte_count = data[8]
        if len(data) < 9 + byte_count:
            logger.debug(
                f"Response data too short: expected {byte_count} bytes, "
                f"got {len(data) - 9}"
            )
            return None

        # Extract register values
        register_data = data[9:9 + byte_count]
        registers = []
        for i in range(0, len(register_data), 2):
            if i + 1 < len(register_data):
                value = struct.unpack(">H", register_data[i:i + 2])[0]
                registers.append(value)

        return registers

    async def read_registers(
        self,
        connection: TCPConnection,
        register: int,
        count: int,
        unit_id: int = 1,
    ) -> Optional[List[int]]:
        """
        Read holding registers from device.

        Args:
            connection: TCP connection to device.
            register: Starting register address.
            count: Number of registers to read.
            unit_id: Modbus unit ID.

        Returns:
            List of register values, or None on error.
        """
        request, transaction_id = self._build_read_request(
            register, count, unit_id
        )

        try:
            # Send request
            await connection.write(request, timeout=self.timeout)

            # Read response header (MBAP = 7 bytes + function + byte count = 9 min)
            header = await connection.read(9, timeout=self.timeout)

            # Get byte count and read remaining data
            byte_count = header[8]
            if byte_count > 0:
                data = await connection.read(byte_count, timeout=self.timeout)
                response = header + data
            else:
                response = header

            return self._parse_read_response(response, transaction_id)

        except asyncio.TimeoutError:
            logger.debug(f"Timeout reading registers {register}-{register+count-1}")
            return None
        except Exception as e:
            logger.debug(f"Error reading registers: {e}")
            return None

    async def read_serial_number(
        self,
        connection: TCPConnection,
        register: int,
        size: int,
        unit_id: int = 1,
        encoding: str = "ascii",
    ) -> Optional[str]:
        """
        Read device serial number.

        Args:
            connection: TCP connection to device.
            register: Serial number register address.
            size: Number of registers containing serial.
            unit_id: Modbus unit ID.
            encoding: String encoding (ascii, utf-8).

        Returns:
            Serial number string, or None on error.
        """
        registers = await self.read_registers(connection, register, size, unit_id)

        if not registers:
            return None

        try:
            # Convert registers to bytes
            raw_bytes = b""
            for reg in registers:
                raw_bytes += struct.pack(">H", reg)

            # Decode string
            serial = raw_bytes.decode(encoding, errors="ignore")

            # Clean up (remove nulls and whitespace)
            serial = serial.replace("\x00", "").strip()

            return serial if serial else None

        except Exception as e:
            logger.debug(f"Error decoding serial number: {e}")
            return None

    async def probe(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
    ) -> Optional[IdentifiedDevice]:
        """
        Probe a connection using a specific protocol definition.

        Args:
            connection: TCP connection to probe.
            protocol: Protocol definition to try.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        if protocol.protocol_type not in (
            ProtocolType.MODBUS_TCP,
            ProtocolType.MODBUS_RTU,
        ):
            return None

        ident_config = protocol.identification
        if not ident_config.is_modbus_based():
            return None

        unit_id = protocol.modbus.unit_id if protocol.modbus else 1

        logger.debug(
            f"Probing for {protocol.protocol_id}: "
            f"register={ident_config.register}, "
            f"expected={ident_config.expected_values}"
        )

        # Read identification register
        registers = await self.read_registers(
            connection,
            ident_config.register,
            ident_config.size,
            unit_id,
        )

        if not registers:
            logger.debug(f"No response for {protocol.protocol_id}")
            return None

        # Check if value matches expected
        value = registers[0]
        if value not in ident_config.expected_values:
            logger.debug(
                f"{protocol.protocol_id}: value {value} not in "
                f"expected {ident_config.expected_values}"
            )
            return None

        logger.info(
            f"Identified {protocol.protocol_id}: "
            f"register {ident_config.register} = {value}"
        )

        # Read serial number
        serial_config = protocol.serial_number
        serial_number = None

        if serial_config.register is not None:
            serial_number = await self.read_serial_number(
                connection,
                serial_config.register,
                serial_config.size,
                unit_id,
                serial_config.encoding,
            )

        if not serial_number:
            # Generate fallback serial from connection info
            serial_number = f"{protocol.protocol_id}_{connection.remote_ip}_{connection.remote_port}"

        return IdentifiedDevice(
            protocol_id=protocol.protocol_id,
            serial_number=serial_number,
            device_type=protocol.device_type.value,
            model=protocol.name,
            manufacturer=protocol.manufacturer,
            extra_data={
                "identification_register": ident_config.register,
                "identification_value": value,
            },
        )
