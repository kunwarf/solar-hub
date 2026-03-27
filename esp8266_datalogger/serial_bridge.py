"""
Serial Command Bridge for ESP8266 Data Logger.

Connects TO System B and bridges text commands to/from a serial port
(e.g., Pylontech battery via RS232/MAX3232).

Protocol: Length-prefixed binary framing
  [MSG_TYPE: 1 byte][LENGTH: 4 bytes big-endian][PAYLOAD: LENGTH bytes]

Message types:
  0x01 COMMAND_REQUEST  B -> ESP8266: command string (UTF-8)
  0x02 COMMAND_RESPONSE ESP8266 -> B: response string (UTF-8)
  0x03 ERROR            ESP8266 -> B: error message (UTF-8)
  0x04 PING             B -> ESP8266: empty payload
  0x05 PONG             ESP8266 -> B: empty payload
  0x06 HELLO            ESP8266 -> B: serial number (UTF-8), sent on connect

ESP8266 Cooperative Scheduling Note
------------------------------------
The ESP8266 does not support threading (_thread module is absent).
run() accepts an optional idle_cb callable that is invoked every time
the bridge socket recv times out (keepalive_interval, default 1 s).

Usage in main.py:
    bridge.run(idle_cb=web.handle_requests)
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

# Limits — reduced from 8192 on ESP32 to conserve heap on ESP8266
MAX_PAYLOAD = 4096
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
            print("[SerialBridge] Registration failed: {} - {}".format(
                status_code, error))
            return False

    def run(self, idle_cb=None):
        """
        Main bridge loop.

        Receives framed command requests from System B, forwards to serial
        port, and sends framed responses back.

        Args:
            idle_cb: Optional callable invoked on each recv timeout.
                     Use this on ESP8266 to service the web server
                     cooperatively, e.g. idle_cb=web.handle_requests.
        """
        self._running = True
        cfg = self.config["serial_bridge"]
        reconnect_delay = cfg.get("reconnect_delay", 5)
        keepalive_interval = cfg.get("keepalive_interval", 1)
        passive = self.config.get("serial", {}).get("passive", False)
        print("[SerialBridge] mode: {} (passive={})".format(
            self.config.get("device", {}).get("protocol", "command"), passive))

        while self._running:
            # Connect if needed
            if not self._connected:
                if not self.connect():
                    print("[SerialBridge] Retrying in {}s...".format(reconnect_delay))
                    for _ in range(reconnect_delay):
                        if idle_cb:
                            idle_cb()
                        time.sleep(1)
                    self.stats["reconnects"] += 1
                    continue

                if not self._registered:
                    if self.register_device():
                        print("[SerialBridge] Device registered with System B")
                    else:
                        print("[SerialBridge] Registration failed, continuing...")

            try:
                # Short timeout so idle_cb is called regularly
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
                        gc.collect()
                        raw = self._handle_command_passive()
                        if raw is not None:
                            self._send_frame(MSG_COMMAND_RESPONSE, raw)
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
                if e.args[0] in (110, 116):  # ETIMEDOUT — keepalive window, normal
                    # Service web server on each timeout (cooperative scheduling)
                    if idle_cb:
                        idle_cb()
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

        The ESP8266 is a dumb byte pipe: it reads whatever arrives on the
        RS485 bus until the bus goes idle, then returns the raw bytes to
        System B.

        Returns:
            Raw bytes from the current broadcast burst, or None on timeout.
        """
        try:
            gc.collect()
            raw = self.serial.read_available()
            if raw is not None:
                print("[SerialBridge] Passive: {} bytes".format(len(raw)))
            return raw
        except Exception as e:
            gc.collect()
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
        self.socket.sendall(header)
        if payload:
            self.socket.sendall(payload)

    def _recv_exact(self, length):
        """
        Receive exact number of bytes.

        Args:
            length: Number of bytes to receive.

        Returns:
            Bytes received or None on error/close.
        """
        data = bytearray()
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
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

    # ── Web config page (called by WebServer /config route) ──────────────────

    def get_config_page(self):
        from config import get_config as _gc
        cfg = _gc()
        sc = cfg.get("serial", {})
        bc = cfg.get("serial_bridge", {})

        def s(cur, val):
            return " selected" if cur == val else ""

        p = []
        p.append('<div class="c"><h2>Serial Port (RS232 / RS485)</h2>')
        p.append('<form method="POST" action="/config">')
        p.append('<input type="hidden" name="section" value="port">')
        p.append('<label>DE Pin (-1=none)</label><input type="number" name="de_pin" value="{}" min="-1" max="16">'.format(sc.get("de_pin", -1)))
        p.append('<label>RE Pin (-1=none)</label><input type="number" name="re_pin" value="{}" min="-1" max="16">'.format(sc.get("re_pin", -1)))
        p.append('<label>Baud Rate</label><select name="baudrate">')
        for b in [9600, 19200, 38400, 57600, 115200]:
            p.append('<option value="{}"{}>{}</option>'.format(b, s(sc.get("baudrate", 115200), b), b))
        p.append('</select><label>Parity</label><select name="parity">')
        for pv, pn in [("N", "None"), ("E", "Even"), ("O", "Odd")]:
            p.append('<option value="{}"{}>{}</option>'.format(pv, s(sc.get("parity", "N"), pv), pn))
        p.append('</select><label>Stop Bits</label><select name="stop_bits">')
        for sv in [1, 2]:
            p.append('<option value="{}"{}>{}</option>'.format(sv, s(sc.get("stop_bits", 1), sv), sv))
        passive = "checked" if sc.get("passive", False) else ""
        p.append('</select><label>RS485 Passive (JK BMS) <input type="checkbox" name="passive" value="1" {}></label>'.format(passive))
        p.append('<label>Max Frame (bytes)</label><input type="number" name="max_frame_len" value="{}" min="64" max="2048">'.format(sc.get("max_frame_len", 512)))
        fh = sc.get("frame_header", [0x55, 0xAA, 0xEB, 0x90])
        p.append('<label>Frame Header (decimal, JK BMS=85,170,235,144)</label><input name="frame_header" value="{}">'.format(
            ",".join(str(b) for b in fh)))
        p.append('<label>Prompt</label><select name="prompt">')
        for pv in ["pylon>", "pytes>", ">"]:
            p.append('<option value="{}"{}>{}</option>'.format(pv, s(sc.get("prompt", "pylon>"), pv), pv))
        p.append('</select><label>Response Timeout (ms)</label><input type="number" name="response_timeout_ms" value="{}" min="1000" max="30000">'.format(sc.get("response_timeout_ms", 5000)))
        p.append('<label>Line Ending</label><select name="line_ending">')
        stored = sc.get("line_ending", "\r\n").replace("\r\n", "\\r\\n").replace("\n", "\\n").replace("\r", "\\r")
        for val, lbl in [("\\r\\n", "CR+LF"), ("\\n", "LF"), ("\\r", "CR")]:
            p.append('<option value="{}"{}>{}</option>'.format(val, s(stored, val), lbl))
        p.append('</select><button type="submit">Save Port</button></form></div>')

        p.append('<div class="c"><h2>Serial Bridge Server</h2>')
        p.append('<form method="POST" action="/config">')
        p.append('<input type="hidden" name="section" value="bridge">')
        p.append('<label>Host</label><input name="host" value="{}">'.format(bc.get("server_host", "")))
        p.append('<label>Port</label><input type="number" name="port" value="{}">'.format(bc.get("server_port", 8502)))
        p.append('<label>Reconnect Delay (s)</label><input type="number" name="reconnect_delay" value="{}">'.format(bc.get("reconnect_delay", 5)))
        p.append('<label>Keepalive (s)</label><input type="number" name="keepalive_interval" value="{}">'.format(bc.get("keepalive_interval", 1)))
        p.append('<button type="submit">Save Bridge</button></form></div>')
        return ''.join(p)

    def save_config(self, body):
        from config import load_config as _lc, save_config as _sc
        config = _lc()
        section = body.get("section", "bridge")
        if section == "port":
            sc = config.setdefault("serial", {})
            sc["uart_id"] = 0
            sc["de_pin"] = int(body.get("de_pin", -1))
            sc["re_pin"] = int(body.get("re_pin", -1))
            sc["baudrate"] = int(body.get("baudrate", 115200))
            sc["parity"] = body.get("parity", "N")
            sc["stop_bits"] = int(body.get("stop_bits", 1))
            sc["passive"] = body.get("passive") == "1"
            sc["max_frame_len"] = int(body.get("max_frame_len", 512))
            try:
                fh = [int(x.strip()) for x in
                      body.get("frame_header", "85,170,235,144").split(",") if x.strip()]
                sc["frame_header"] = fh if fh else [0x55, 0xAA, 0xEB, 0x90]
            except Exception:
                sc["frame_header"] = [0x55, 0xAA, 0xEB, 0x90]
            sc["prompt"] = body.get("prompt", "pylon>")
            sc["response_timeout_ms"] = int(body.get("response_timeout_ms", 5000))
            le = body.get("line_ending", "\\r\\n")
            sc["line_ending"] = le.replace("\\r\\n", "\r\n").replace("\\n", "\n").replace("\\r", "\r")
        else:
            sb = config.setdefault("serial_bridge", {})
            sb["server_host"] = body.get("host", "").strip()
            sb["server_port"] = int(body.get("port", 8502))
            sb["reconnect_delay"] = int(body.get("reconnect_delay", 5))
            sb["keepalive_interval"] = int(body.get("keepalive_interval", 1))
        _sc(config)
        return '<p class="ok">Saved. Reboot to apply.</p>' + self.get_config_page()
