"""
Serial Command Bridge for ESP32 Data Logger 11.

Connects TO System B and bridges text commands to/from a serial port
(e.g., Pylontech battery via RS232/MAX3232).

Protocol: Length-prefixed binary framing
  [MSG_TYPE: 1 byte][LENGTH: 4 bytes big-endian][PAYLOAD: LENGTH bytes]

Message types:
  0x01 COMMAND_REQUEST  B -> ESP32: command string (UTF-8)
  0x02 COMMAND_RESPONSE ESP32 -> B: response string (UTF-8)
  0x03 ERROR            ESP32 -> B: error message (UTF-8)
  0x04 PING             B -> ESP32: empty payload
  0x05 PONG             ESP32 -> B: empty payload
  0x06 HELLO            ESP32 -> B: serial number (UTF-8), sent on connect

The ESP32 sends HELLO immediately after TCP connect so System B can
identify the device without probing, then relays command/response pairs.
"""
import gc
import socket
import struct
import time

from config import get_config
from log_buffer import log_print as print
from http_utils import http_post_json

# Frame message types
MSG_HELLO = 0x06
MSG_COMMAND_REQUEST = 0x01
MSG_COMMAND_RESPONSE = 0x02
MSG_ERROR = 0x03
MSG_PING = 0x04
MSG_PONG = 0x05

# Limits
MAX_PAYLOAD = 8192
FRAME_HEADER_SIZE = 5  # 1 byte type + 4 bytes big-endian length


class SerialBridge:
    """
    Serial command bridge TCP client.

    Connects to System B, sends HELLO with the data logger serial,
    then relays COMMAND_REQUEST frames to UART and sends COMMAND_RESPONSE
    frames back to System B.
    """

    def __init__(self, serial_port, config=None):
        """
        Initialize the serial bridge.

        Args:
            serial_port: SerialPort instance for UART communication.
            config: Configuration dict (uses get_config() if None).
        """
        self.serial = serial_port
        self.config = config or get_config()
        self.socket = None
        self._connected = False
        self._running = False
        self._registered = False
        self._device_id = None

        self.stats = {
            "commands": 0,
            "responses": 0,
            "errors": 0,
            "reconnects": 0,
        }

    def connect(self):
        """
        Connect to System B and send HELLO frame with serial number.

        Returns:
            True if connected and HELLO sent, False otherwise.
        """
        cfg = self.config["serial_bridge"]
        host = cfg["server_host"]
        port = cfg["server_port"]

        try:
            print("[SerialBridge] Connecting to {}:{}...".format(host, port))

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((host, port))
            self.socket.settimeout(None)

            self._connected = True

            # Send HELLO frame immediately with serial number
            serial = self.config.get("device", {}).get("serial", "")
            if not serial:
                print("[SerialBridge] No serial number configured")
                self._cleanup_socket()
                return False

            self._send_frame(MSG_HELLO, serial.encode("utf-8"))
            print("[SerialBridge] Connected, sent HELLO (serial={})".format(serial))
            return True

        except Exception as e:
            print("[SerialBridge] Connection failed:", e)
            self._cleanup_socket()
            return False

    def disconnect(self):
        """Disconnect from server."""
        self._running = False
        self._cleanup_socket()
        print("[SerialBridge] Disconnected")

    def _cleanup_socket(self):
        """Clean up socket resources."""
        self._connected = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def is_connected(self):
        """Check if connected to server."""
        return self._connected

    def is_registered(self):
        """Check if device is registered with System B API."""
        return self._registered

    def register_device(self):
        """
        Self-register device with System B API.

        Returns:
            True if registration successful, False otherwise.
        """
        api_config = self.config.get("api", {})
        device_config = self.config.get("device", {})

        base_url = api_config.get("base_url", "http://localhost:8001")
        endpoint = api_config.get("register_endpoint", "/api/v1/devices/self-register")

        serial = device_config.get("serial", "")
        if not serial:
            print("[SerialBridge] No serial number configured, skipping registration")
            return False

        protocol = device_config.get("protocol", "command")
        print("[SerialBridge] device config: type={} protocol={}".format(
            device_config.get("type"), protocol))

        payload = {
            "serial_number": serial,
            "device_type": device_config.get("type", "battery"),
            "firmware_version": device_config.get("firmware_version", "1.0.0"),
            "manufacturer": device_config.get("manufacturer", "SolarHub"),
            "protocol": protocol,
            "model": device_config.get("model"),
        }

        url = base_url + endpoint
        print("[SerialBridge] Registering: {} -> {}".format(serial, url))

        status_code, response = http_post_json(url, payload)

        if status_code == 200:
            self._registered = True
            self._device_id = response.get("device_id") if response else None
            is_claimed = response.get("is_claimed", False) if response else False
            print("[SerialBridge] Registration successful!")
            print("[SerialBridge]   Device ID: {}".format(self._device_id))
            print("[SerialBridge]   Claimed: {}".format(is_claimed))
            return True
        else:
            error = response.get("detail") if response else "Unknown error"
            print("[SerialBridge] Registration failed: {} - {}".format(status_code, error))
            return False

    def run(self):
        """
        Main bridge loop.

        Receives framed command requests from System B, forwards to serial
        port, and sends framed responses back.
        """
        self._running = True
        cfg = self.config["serial_bridge"]
        reconnect_delay = cfg.get("reconnect_delay", 5)
        keepalive_interval = cfg.get("keepalive_interval", 30)
        passive = self.config.get("serial", {}).get("passive", False)
        print("[SerialBridge] mode: {} (passive={})".format(
            self.config.get("device", {}).get("protocol", "command"), passive))

        while self._running:
            # Connect if needed
            if not self._connected:
                if not self.connect():
                    print("[SerialBridge] Retrying in {}s...".format(reconnect_delay))
                    time.sleep(reconnect_delay)
                    self.stats["reconnects"] += 1
                    continue

                if not self._registered:
                    if self.register_device():
                        print("[SerialBridge] Device registered with System B")
                    else:
                        print("[SerialBridge] Registration failed, continuing...")

            try:
                self.socket.settimeout(keepalive_interval)

                # Read frame header (5 bytes)
                header = self._recv_exact(FRAME_HEADER_SIZE)
                if not header:
                    print("[SerialBridge] Connection closed by server")
                    self._cleanup_socket()
                    continue

                msg_type = header[0]
                payload_len = struct.unpack(">I", header[1:5])[0]

                if payload_len > MAX_PAYLOAD:
                    print("[SerialBridge] Payload too large: {}".format(payload_len))
                    self._cleanup_socket()
                    continue

                # Read payload
                payload = b""
                if payload_len > 0:
                    payload = self._recv_exact(payload_len)
                    if not payload:
                        print("[SerialBridge] Failed to receive payload")
                        self._cleanup_socket()
                        continue

                # Dispatch
                if msg_type == MSG_COMMAND_REQUEST:
                    self.stats["commands"] += 1

                    if self.config.get("serial", {}).get("passive", False):
                        # Passive binary mode (e.g. JK BMS RS485 broadcast).
                        # Ignore command content; wait for the next broadcast
                        # frame and return raw bytes.
                        raw = self._handle_command_passive()
                        if raw is not None:
                            self._send_frame(MSG_COMMAND_RESPONSE, raw)
                            # Release the buffer immediately — if raw is a
                            # memoryview of the static _RX_BUF it costs nothing,
                            # but if it's a bytearray this frees it before the
                            # next gc.collect() call in _handle_command_passive.
                            del raw
                            gc.collect()
                            self.stats["responses"] += 1
                        else:
                            self._send_frame(MSG_ERROR,
                                             b"No frame received from device")
                            self.stats["errors"] += 1
                    else:
                        # Active text-command mode (Pylontech / Pytes).
                        cmd_str = payload.decode("utf-8", "replace").strip()
                        response_str = self._handle_command(cmd_str)
                        if response_str is not None:
                            self._send_frame(MSG_COMMAND_RESPONSE,
                                             response_str.encode("utf-8"))
                            self.stats["responses"] += 1
                        else:
                            self._send_frame(MSG_ERROR,
                                             b"No response from device")
                            self.stats["errors"] += 1

                elif msg_type == MSG_PING:
                    self._send_frame(MSG_PONG, b"")

                else:
                    pass  # Unknown frame type — ignore

            except OSError as e:
                if e.args[0] == 110:  # ETIMEDOUT — keepalive window, normal
                    continue
                self.stats["errors"] += 1
                self._cleanup_socket()
                time.sleep(1)

            except Exception:
                self.stats["errors"] += 1
                self._cleanup_socket()
                time.sleep(1)

    def _handle_command(self, cmd_str):
        """
        Send command to serial device and return response.

        Args:
            cmd_str: Command string (without line ending).

        Returns:
            Response string or None on failure.
        """
        try:
            cfg = self.config.get("serial", {})
            prompt = cfg.get("prompt", "pylon>")
            timeout_ms = cfg.get("response_timeout_ms", 5000)

            self.serial.flush_rx()
            self.serial.write(cmd_str)
            response = self.serial.read_until_prompt(
                prompt=prompt, timeout_ms=timeout_ms
            )
            return response

        except Exception:
            return None

    def _handle_command_passive(self):
        """
        Drain the RS485 bus and return raw bytes (passive mode).

        The ESP32 is a dumb byte pipe: it reads whatever arrives on the
        RS485 bus until the bus goes idle (end of broadcast burst), then
        returns the raw bytes to System B.

        System B accumulates these chunks across polls and parses frames
        from the stream, using Modbus request frames to track which JK BMS
        unit each ``55 AA EB 90`` data frame belongs to.  No frame-boundary
        or timing logic is needed here.

        Returns:
            Raw bytes from the current broadcast burst, or None on timeout.
        """
        try:
            # Collect garbage before the large bytearray allocation so the
            # web server thread's dead objects are freed first.
            gc.collect()
            raw = self.serial.read_available()
            if raw is not None:
                print("[SerialBridge] Passive: {} bytes".format(len(raw)))
            return raw
        except Exception as e:
            gc.collect()  # Recover heap after any allocation failure
            print("[SerialBridge] Passive exception:", e)
            return None

    def _send_frame(self, msg_type, payload):
        """
        Send length-prefixed frame.

        Args:
            msg_type: Message type byte (0x01–0x06).
            payload: Payload bytes or bytearray.
        """
        header = struct.pack(">BI", msg_type, len(payload))
        # Send header and payload separately — avoids allocating a combined
        # copy (header + payload) which would duplicate the entire payload in
        # memory.  TCP buffers the two sends transparently.
        self.socket.sendall(header)
        if payload:
            self.socket.sendall(payload)

    def _recv_exact(self, length):
        """
        Receive exact number of bytes.

        Args:
            length: Number of bytes to receive.

        Returns:
            Bytes received, or None on error/peer close.

        Raises:
            OSError(ETIMEDOUT) when the socket idle-timeout fires BEFORE any
            byte of this read has arrived.  The caller treats that as the
            expected keepalive window and loops — the socket stays alive.
            See esp32_datalogger/modbus_bridge.py._recv_exact for the full
            rationale.
        """
        # bytearray avoids the O(n²) copy cost of bytes += on MicroPython.
        data = bytearray()
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except OSError as e:
                # ETIMEDOUT at the start of a read is normal idle; propagate.
                if e.args and e.args[0] == 110 and not data:
                    raise
                return None
            except Exception:
                return None
        return bytes(data)

    def get_stats(self):
        """Get bridge statistics."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "commands": 0,
            "responses": 0,
            "errors": 0,
            "reconnects": 0,
        }
