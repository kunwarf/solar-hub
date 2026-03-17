"""
Serial port wrapper for ESP32 Data Logger.

Provides UART communication for devices using text command protocol
(e.g., Pylontech battery console interface via RS232/MAX3232).

Hardware notes:
- Pylontech/Pytes batteries use true RS232 (±12V) — a MAX3232 level
  converter is required between the ESP32 UART pins and the battery.
- Default: UART1 on GPIO17(TX)/GPIO16(RX) to avoid conflict with the
  CH340 chip on UART0.
"""
import machine
import time


class SerialPort:
    """
    UART wrapper for text command-based serial protocol.

    Designed for RS232 console devices (e.g., Pylontech battery).
    Requires MAX3232 level converter between ESP32 UART and RS232.
    """

    def __init__(self, config):
        """
        Initialize serial port.

        Args:
            config: Serial configuration dict with uart_id, tx_pin, rx_pin,
                    baudrate, parity, stop_bits, data_bits, response_timeout_ms,
                    prompt, line_ending.
        """
        self.config = config
        self.uart = None
        self._init_uart()

    def _init_uart(self):
        """Initialize UART."""
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

        print("[Serial] UART{} initialized: TX={}, RX={}, {}baud".format(
            cfg["uart_id"], cfg["tx_pin"], cfg["rx_pin"],
            cfg.get("baudrate", 115200)
        ))

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
