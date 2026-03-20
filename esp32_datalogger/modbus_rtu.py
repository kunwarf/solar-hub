"""
Modbus RTU communication for ESP32 Data Logger 1.

Handles serial communication with inverters using Modbus RTU protocol.
"""
import machine
import time

try:
    from log_buffer import log_print as print
except ImportError:
    pass  # not available in test/host environments


def crc16_modbus(data):
    """Calculate Modbus CRC16."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def hex_str(data):
    """Convert bytes to hex string for logging."""
    return " ".join("{:02X}".format(b) for b in data)


class ModbusRTU:
    """
    Modbus RTU master for communication with inverters.

    Supports:
    - Function 03: Read Holding Registers
    - Function 04: Read Input Registers
    - Function 06: Write Single Register
    - Function 16: Write Multiple Registers
    """

    def __init__(self, config):
        """
        Initialize Modbus RTU.

        Args:
            config: RTU configuration dict with uart_id, tx_pin, rx_pin, etc.
        """
        self.config = config
        self.uart = None
        self.de_pin = None  # RS485 DE pin (Driver Enable, active-HIGH)
        self.re_pin = None  # RS485 RE pin (Receiver Enable, active-LOW)

        self._init_uart()

    def _init_uart(self):
        """Initialize UART for Modbus RTU."""
        cfg = self.config

        # Parse parity
        parity = None
        if cfg["parity"] == "E":
            parity = 0
        elif cfg["parity"] == "O":
            parity = 1

        # Initialize UART
        self.uart = machine.UART(
            cfg["uart_id"],
            baudrate=cfg["baudrate"],
            bits=cfg["data_bits"],
            parity=parity,
            stop=cfg["stop_bits"],
            tx=cfg["tx_pin"],
            rx=cfg["rx_pin"]
        )
        self.uart.init(timeout=0)

        # Initialize RS485 direction pins if configured.
        # DE (Driver Enable, active-HIGH): GPIO4 by default.
        # RE (Receiver Enable, active-LOW): GPIO5 by default.
        # TX mode: DE=1, RE=1 (enable driver, disable receiver to avoid echo).
        # RX mode: DE=0, RE=0 (disable driver, enable receiver).
        de = cfg.get("de_pin", 0)
        re = cfg.get("re_pin", 0)
        if de > 0:
            self.de_pin = machine.Pin(de, machine.Pin.OUT)
            self.de_pin.value(0)  # Start in RX mode
        if re > 0:
            self.re_pin = machine.Pin(re, machine.Pin.OUT)
            self.re_pin.value(0)  # Start in RX mode (RE=LOW = receiver enabled)

        print("[RTU] UART{} initialized: TX={}, RX={}, {}baud {}{}{} DE={} RE={}".format(
            cfg["uart_id"], cfg["tx_pin"], cfg["rx_pin"],
            cfg["baudrate"], cfg["data_bits"], cfg["parity"], cfg["stop_bits"],
            de if de > 0 else "off", re if re > 0 else "off"
        ))

    def _flush_rx(self):
        """Flush any pending data in RX buffer."""
        try:
            while self.uart.any():
                self.uart.read()
        except:
            pass

    def _expected_response_len(self, response_head):
        """Calculate expected response length based on function code."""
        if len(response_head) < 2:
            return None

        func = response_head[1]

        # Exception response
        if func & 0x80:
            return 5

        # Read functions (03, 04) - variable length based on byte count
        if func in (0x03, 0x04):
            if len(response_head) < 3:
                return None
            byte_count = response_head[2]
            return 3 + byte_count + 2  # unit + func + bc + data + crc

        # Write single (05, 06) - fixed 8 bytes
        if func in (0x05, 0x06):
            return 8

        # Write multiple (15, 16) - fixed 8 bytes
        if func in (0x0F, 0x10):
            return 8

        return None

    def transceive(self, pdu, unit_id=None, quiet=True):
        """
        Send Modbus RTU request and receive response.

        Args:
            pdu: Protocol Data Unit (without unit ID and CRC).
            unit_id: Modbus unit/slave ID (uses config default if None).
            quiet: Suppress logging if True.

        Returns:
            Complete response frame or None on error.
        """
        if unit_id is None:
            unit_id = self.config["unit_id"]

        # Build frame: unit_id + pdu + crc
        frame = bytes([unit_id]) + pdu
        crc = crc16_modbus(frame)
        frame += bytes([crc & 0xFF, (crc >> 8) & 0xFF])

        # Flush RX buffer
        self._flush_rx()

        if not quiet:
            print("[RTU] TX {} bytes: {}".format(len(frame), hex_str(frame)))

        # Set RS485 to TX mode: DE=1 (enable driver), RE=1 (disable receiver)
        if self.de_pin:
            self.de_pin.value(1)
        if self.re_pin:
            self.re_pin.value(1)

        # Send frame
        self.uart.write(frame)

        # Wait for TX to complete (calculate based on baud rate)
        tx_time_ms = (len(frame) * 11 * 1000) // self.config["baudrate"] + 5
        time.sleep_ms(tx_time_ms)

        # Set RS485 to RX mode: DE=0 (disable driver), RE=0 (enable receiver)
        if self.de_pin:
            self.de_pin.value(0)
        if self.re_pin:
            self.re_pin.value(0)

        # Receive response
        timeout_ms = self.config["timeout_ms"]
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        response = b""

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            try:
                available = self.uart.any()
            except:
                available = 0

            if available:
                chunk = self.uart.read(available)
                if chunk:
                    response += chunk

                    # Check if we have complete response
                    expected_len = self._expected_response_len(response[:3])
                    if expected_len and len(response) >= expected_len:
                        break

            time.sleep_ms(5)

        # Validate response
        if len(response) < 5:
            # Always log RTU failures — silent timeouts make debugging impossible
            print("[RTU] RX: timeout/incomplete ({} bytes)".format(len(response)))
            return None

        # Verify CRC
        received_crc = response[-2] | (response[-1] << 8)
        calculated_crc = crc16_modbus(response[:-2])

        if received_crc != calculated_crc:
            # Always log CRC errors
            print("[RTU] RX: CRC error ({} bytes)".format(len(response)))
            return None

        if not quiet:
            print("[RTU] RX:", hex_str(response))

        return response

    def read_holding_registers(self, address, count, unit_id=None, quiet=True):
        """
        Read holding registers (function 03).

        Args:
            address: Starting register address.
            count: Number of registers to read.
            unit_id: Modbus unit ID.
            quiet: Suppress logging.

        Returns:
            List of register values or None on error.
        """
        pdu = bytes([
            0x03,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF
        ])

        response = self.transceive(pdu, unit_id, quiet)

        if not response or len(response) < 5:
            return None

        if response[1] != 0x03:
            return None

        byte_count = response[2]
        data = response[3:3 + byte_count]

        # Parse register values (big-endian)
        registers = []
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                value = (data[i] << 8) | data[i + 1]
                registers.append(value)

        return registers

    def read_input_registers(self, address, count, unit_id=None, quiet=True):
        """
        Read input registers (function 04).

        Args:
            address: Starting register address.
            count: Number of registers to read.
            unit_id: Modbus unit ID.
            quiet: Suppress logging.

        Returns:
            List of register values or None on error.
        """
        pdu = bytes([
            0x04,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF
        ])

        response = self.transceive(pdu, unit_id, quiet)

        if not response or len(response) < 5:
            return None

        if response[1] != 0x04:
            return None

        byte_count = response[2]
        data = response[3:3 + byte_count]

        registers = []
        for i in range(0, len(data), 2):
            if i + 1 < len(data):
                value = (data[i] << 8) | data[i + 1]
                registers.append(value)

        return registers

    def write_single_register(self, address, value, unit_id=None, quiet=True):
        """
        Write single holding register (function 06).

        Args:
            address: Register address.
            value: Value to write (0-65535).
            unit_id: Modbus unit ID.
            quiet: Suppress logging.

        Returns:
            True on success, False on error.
        """
        value = int(value) & 0xFFFF

        pdu = bytes([
            0x06,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF
        ])

        response = self.transceive(pdu, unit_id, quiet)

        if not response or len(response) < 8:
            return False

        # Response should echo the request
        return response[1] == 0x06

    def write_multiple_registers(self, address, values, unit_id=None, quiet=True):
        """
        Write multiple holding registers (function 16).

        Args:
            address: Starting register address.
            values: List of values to write.
            unit_id: Modbus unit ID.
            quiet: Suppress logging.

        Returns:
            True on success, False on error.
        """
        count = len(values)
        byte_count = count * 2

        pdu = bytes([
            0x10,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF,
            byte_count
        ])

        for value in values:
            v = int(value) & 0xFFFF
            pdu += bytes([(v >> 8) & 0xFF, v & 0xFF])

        response = self.transceive(pdu, unit_id, quiet)

        if not response or len(response) < 8:
            return False

        return response[1] == 0x10

    def forward_pdu(self, pdu, unit_id=None, quiet=True):
        """
        Forward a PDU to the RTU device and return the response PDU.

        This is used by the bridge mode to forward Modbus TCP requests.

        Args:
            pdu: PDU to forward.
            unit_id: Modbus unit ID.
            quiet: Suppress logging.

        Returns:
            Response PDU (without unit ID and CRC) or None on error.
        """
        response = self.transceive(pdu, unit_id, quiet)

        if not response:
            return None

        # Return PDU only (remove unit ID and CRC)
        return response[1:-2]
