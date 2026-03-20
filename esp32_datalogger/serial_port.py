"""
Serial port wrapper for ESP32 Data Logger.

Provides UART communication for devices using text command protocol
(e.g., Pylontech battery console interface via RS232/MAX3232) or
binary protocol (e.g., JK BMS over RS485 with MAX485).

Hardware notes:
- Pylontech/Pytes batteries use true RS232 (±12V) — a MAX3232 level
  converter is required between the ESP32 UART pins and the battery.
- JK BMS uses RS485 differential signalling — a MAX485 or similar chip
  is required. The DE/RE pin (de_pin) controls TX vs RX direction.
- Default: UART1 on GPIO17(TX)/GPIO16(RX) to avoid conflict with the
  CH340 chip on UART0.
"""
import machine
import time

try:
    from log_buffer import log_print as print
except ImportError:
    pass  # log_buffer not available in test/host environments


class SerialPort:
    """
    UART wrapper for text command-based and binary serial protocols.

    Designed for RS232 console devices (e.g., Pylontech battery) and
    RS485 binary devices (e.g., JK BMS).  RS232 requires MAX3232 level
    converter; RS485 requires MAX485 with DE/RE direction control pin.
    """

    def __init__(self, config):
        """
        Initialize serial port.

        Args:
            config: Serial configuration dict with uart_id, tx_pin, rx_pin,
                    baudrate, parity, stop_bits, data_bits, response_timeout_ms,
                    prompt, line_ending.  Optional: de_pin (RS485 direction
                    control), frame_header (binary protocol header bytes).
        """
        self.config = config
        self.uart = None
        self._de_pin = None  # RS485 DE pin (Driver Enable, active-HIGH)
        self._re_pin = None  # RS485 RE pin (Receiver Enable, active-LOW)
        self._init_uart()

    def _init_uart(self):
        """Initialize UART and optional DE pin for RS485."""
        cfg = self.config

        # Parse parity: "N" -> None, "E" -> 0, "O" -> 1
        parity = None
        if cfg.get("parity") == "E":
            parity = 0
        elif cfg.get("parity") == "O":
            parity = 1

        self.uart = machine.UART(
            cfg["uart_id"],
            baudrate=cfg.get("baudrate", 115200),
            bits=cfg.get("data_bits", 8),
            parity=parity,
            stop=cfg.get("stop_bits", 1),
            tx=cfg["tx_pin"],
            rx=cfg["rx_pin"],
            rxbuf=2048,
        )
        self.uart.init(timeout=0)

        # Optional DE/RE pins for RS485 (MAX485) direction control.
        # DE (Driver Enable, active-HIGH): assert before TX, deassert after TX.
        # RE (Receiver Enable, active-LOW): assert (LOW) for RX, deassert (HIGH) during TX.
        de_pin_num = cfg.get("de_pin", -1)
        re_pin_num = cfg.get("re_pin", -1)
        if de_pin_num is not None and de_pin_num >= 0:
            self._de_pin = machine.Pin(de_pin_num, machine.Pin.OUT)
            self._de_pin.value(0)  # Start in RX mode
        if re_pin_num is not None and re_pin_num >= 0:
            self._re_pin = machine.Pin(re_pin_num, machine.Pin.OUT)
            self._re_pin.value(0)  # Start in RX mode (RE=LOW = receiver enabled)

        rs485_info = ""
        if de_pin_num >= 0 or re_pin_num >= 0:
            rs485_info = " RS485-DE={} RE={}".format(
                de_pin_num if de_pin_num >= 0 else "off",
                re_pin_num if re_pin_num >= 0 else "off"
            )
        print("[Serial] UART{} initialized: TX={}, RX={}, {}baud{}".format(
            cfg["uart_id"], cfg["tx_pin"], cfg["rx_pin"],
            cfg.get("baudrate", 115200), rs485_info
        ))

    def write_bytes(self, data):
        """
        Send raw bytes to device (binary protocol, e.g., JK BMS RS485).

        Asserts DE pin before transmission and deasserts after for RS485.

        Args:
            data: Bytes to send.
        """
        if self._de_pin:
            self._de_pin.value(1)  # Assert DE: enable transmit
        if self._re_pin:
            self._re_pin.value(1)  # Deassert RE: disable receiver during TX
        self.uart.write(data)
        if self._de_pin or self._re_pin:
            # Wait for TX FIFO to drain at current baudrate before releasing bus.
            # ~2 ms is sufficient for up to ~23 bytes at 115200 baud.
            time.sleep_ms(2)
        if self._de_pin:
            self._de_pin.value(0)  # Deassert DE: disable transmit
        if self._re_pin:
            self._re_pin.value(0)  # Assert RE: enable receiver (RE active-LOW)

    def read_frame(self, header=None, max_len=512, timeout_ms=None):
        """
        Read a binary frame starting with a specific header sequence.

        Accumulates bytes until the header is found, then continues until
        no new data arrives for 20 ms or max_len bytes have been received.

        Suitable for JK BMS ``55 AA EB 90`` broadcast frames.

        Args:
            header: Header bytes to search for (defaults to b'\\x55\\xAA\\xEB\\x90').
            max_len: Maximum number of bytes to read after the header.
            timeout_ms: Total read timeout in milliseconds.

        Returns:
            Bytes from the header onwards (inclusive), or None on timeout/miss.
        """
        if header is None:
            cfg_header = self.config.get("frame_header")
            if cfg_header:
                header = bytes(cfg_header) if isinstance(cfg_header, list) else cfg_header
            else:
                header = b'\x55\xAA\xEB\x90'
        if timeout_ms is None:
            timeout_ms = self.config.get("response_timeout_ms", 5000)

        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        buf = b""
        header_found = False
        idle_count = 0

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            available = self.uart.any()
            if available:
                chunk = self.uart.read(available)
                if chunk:
                    buf += chunk
                    idle_count = 0

                    if not header_found:
                        idx = buf.find(header)
                        if idx >= 0:
                            buf = buf[idx:]  # Trim pre-header garbage
                            header_found = True

                    if header_found and len(buf) >= max_len:
                        break
            else:
                if header_found and len(buf) > len(header):
                    idle_count += 1
                    if idle_count >= 2:  # ~20 ms silence after header
                        break
                time.sleep_ms(10)

        if not header_found or len(buf) <= len(header):
            print("[Serial] read_frame: timeout after {}ms, {} bytes rx, header_found={}{}".format(
                timeout_ms, len(buf),
                header_found,
                (" first={}".format(buf[:8].hex()) if buf else ""),
            ))
            return None
        return buf

    def write(self, data_str, line_ending=None):
        """
        Send command string to device.

        Args:
            data_str: Command to send (string, no line ending needed).
            line_ending: Line ending to append (defaults to config value).
        """
        if line_ending is None:
            line_ending = self.config.get("line_ending", "\r\n")
        data = (data_str + line_ending).encode("utf-8")
        self.uart.write(data)

    def read_until_prompt(self, prompt=None, timeout_ms=None):
        """
        Accumulate bytes until the prompt string is detected or timeout.

        Args:
            prompt: Prompt string to detect (defaults to config "prompt").
            timeout_ms: Timeout in milliseconds (defaults to config value).

        Returns:
            Response string (all bytes up to and including the prompt line),
            or None on timeout with no data.
        """
        if prompt is None:
            prompt = self.config.get("prompt", "pylon>")
        if timeout_ms is None:
            timeout_ms = self.config.get("response_timeout_ms", 5000)

        prompt_bytes = prompt.encode("utf-8")
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        response = b""

        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            available = self.uart.any()
            if available:
                chunk = self.uart.read(available)
                if chunk:
                    response += chunk
                    if prompt_bytes in response:
                        break
            time.sleep_ms(10)

        if not response:
            return None

        try:
            return response.decode("utf-8", "replace")
        except Exception:
            return response.decode("latin-1")

    def flush_rx(self):
        """Clear the RX buffer."""
        try:
            while self.uart.any():
                self.uart.read()
        except Exception:
            pass
