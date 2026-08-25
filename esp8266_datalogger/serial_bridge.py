"""Serial command bridge for ESP8266. Outbound TCP to System B, relays UART."""
import gc
import socket
import struct
import time

from config import get_config
from log_buffer import log_print as print
from http_utils import http_post_json

MSG_HELLO = 0x06
MSG_COMMAND_REQUEST = 0x01
MSG_COMMAND_RESPONSE = 0x02
MSG_ERROR = 0x03
MSG_PING = 0x04
MSG_PONG = 0x05

MAX_PAYLOAD = 4096
FRAME_HEADER_SIZE = 5  # 1 byte type + 4 bytes big-endian length


class SerialBridge:

    def __init__(self, serial_port, config=None):
        self.serial = serial_port
        self.config = config or get_config()
        self.socket = None
        self._connected = False
        self._running = False
        self._registered = False
        self._device_id = None
        self.stats = {"commands": 0, "responses": 0, "errors": 0, "reconnects": 0}

    def connect(self):
        cfg = self.config["serial_bridge"]
        host = cfg["server_host"]
        port = cfg["server_port"]
        try:
            print("[SB] Connecting to {}:{}...".format(host, port))
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((host, port))
            self.socket.settimeout(None)
            self._connected = True
            serial = self.config.get("device", {}).get("serial", "")
            if not serial:
                print("[SB] No serial number configured")
                self._cleanup_socket()
                return False
            self._send_frame(MSG_HELLO, serial.encode("utf-8"))
            print("[SB] Connected, HELLO sent (serial={})".format(serial))
            return True
        except Exception as e:
            print("[SB] Connection failed:", e)
            self._cleanup_socket()
            return False

    def disconnect(self):
        self._running = False
        self._cleanup_socket()
        print("[SB] Disconnected")

    def _cleanup_socket(self):
        self._connected = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def is_connected(self):
        return self._connected

    def is_registered(self):
        return self._registered

    def register_device(self):
        api_config = self.config.get("api", {})
        device_config = self.config.get("device", {})
        base_url = api_config.get("base_url", "http://localhost:8001")
        endpoint = api_config.get("register_endpoint", "/api/v1/devices/self-register")
        serial = device_config.get("serial", "")
        if not serial:
            print("[SB] No serial, skipping registration")
            return False
        protocol = device_config.get("protocol", "command")
        payload = {
            "serial_number": serial,
            "device_type": device_config.get("type", "battery"),
            "firmware_version": device_config.get("firmware_version", "1.0.0"),
            "manufacturer": device_config.get("manufacturer", "SolarHub"),
            "protocol": protocol,
            "model": device_config.get("model"),
        }
        url = base_url + endpoint
        print("[SB] Registering: {} -> {}".format(serial, url))
        status_code, response = http_post_json(url, payload)
        if status_code == 200:
            self._registered = True
            self._device_id = response.get("device_id") if response else None
            is_claimed = response.get("is_claimed", False) if response else False
            print("[SB] Registered! ID={} claimed={}".format(self._device_id, is_claimed))
            return True
        else:
            error = response.get("detail") if response else "Unknown error"
            print("[SB] Registration failed: {} - {}".format(status_code, error))
            return False

    def run(self, idle_cb=None):
        self._running = True
        cfg = self.config["serial_bridge"]
        reconnect_delay = cfg.get("reconnect_delay", 5)
        keepalive_interval = cfg.get("keepalive_interval", 1)
        passive = self.config.get("serial", {}).get("passive", False)

        while self._running:
            if not self._connected:
                if not self.connect():
                    print("[SB] Retrying in {}s...".format(reconnect_delay))
                    for _ in range(reconnect_delay):
                        if idle_cb:
                            idle_cb()
                        time.sleep(1)
                    self.stats["reconnects"] += 1
                    continue
                if not self._registered:
                    if self.register_device():
                        print("[SB] Device registered with System B")
                    else:
                        print("[SB] Registration failed, continuing...")

            try:
                self.socket.settimeout(keepalive_interval)
                header = self._recv_exact(FRAME_HEADER_SIZE)
                if not header:
                    print("[SB] Connection closed by server")
                    self._cleanup_socket()
                    continue
                msg_type = header[0]
                payload_len = struct.unpack(">I", header[1:5])[0]
                if payload_len > MAX_PAYLOAD:
                    print("[SB] Payload too large: {}".format(payload_len))
                    self._cleanup_socket()
                    continue
                payload = b""
                if payload_len > 0:
                    payload = self._recv_exact(payload_len)
                    if not payload:
                        print("[SB] Failed to receive payload")
                        self._cleanup_socket()
                        continue
                if msg_type == MSG_COMMAND_REQUEST:
                    self.stats["commands"] += 1
                    if passive:
                        gc.collect()
                        raw = self._handle_command_passive()
                        if raw is not None:
                            self._send_frame(MSG_COMMAND_RESPONSE, raw)
                            del raw
                            gc.collect()
                            self.stats["responses"] += 1
                        else:
                            self._send_frame(MSG_ERROR, b"No frame received from device")
                            self.stats["errors"] += 1
                    else:
                        cmd_str = payload.decode("utf-8", "replace").strip()
                        response_str = self._handle_command(cmd_str)
                        if response_str is not None:
                            self._send_frame(MSG_COMMAND_RESPONSE, response_str.encode("utf-8"))
                            self.stats["responses"] += 1
                        else:
                            self._send_frame(MSG_ERROR, b"No response from device")
                            self.stats["errors"] += 1
                elif msg_type == MSG_PING:
                    self._send_frame(MSG_PONG, b"")

            except OSError as e:
                if e.args[0] in (110, 116):
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
        try:
            cfg = self.config.get("serial", {})
            prompt = cfg.get("prompt", "pylon>")
            timeout_ms = cfg.get("response_timeout_ms", 5000)
            self.serial.flush_rx()
            self.serial.write(cmd_str)
            return self.serial.read_until_prompt(prompt=prompt, timeout_ms=timeout_ms)
        except Exception:
            return None

    def _handle_command_passive(self):
        try:
            gc.collect()
            raw = self.serial.read_available()
            if raw is not None:
                print("[SB] Passive: {} bytes".format(len(raw)))
            return raw
        except Exception as e:
            gc.collect()
            print("[SB] Passive exception:", e)
            return None

    def _send_frame(self, msg_type, payload):
        header = struct.pack(">BI", msg_type, len(payload))
        self.socket.sendall(header)
        if payload:
            self.socket.sendall(payload)

    def _recv_exact(self, length):
        # See esp32_datalogger/modbus_bridge.py._recv_exact for the rationale.
        # Propagate ETIMEDOUT (errno 110) when we've received nothing yet
        # so the outer keepalive handler in run() can `continue` instead of
        # tearing down the connection.
        data = bytearray()
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except OSError as e:
                if e.args and e.args[0] == 110 and not data:
                    raise
                return None
            except Exception:
                return None
        return bytes(data)

    def get_stats(self):
        return self.stats.copy()

    def reset_stats(self):
        self.stats = {"commands": 0, "responses": 0, "errors": 0, "reconnects": 0}

    def get_config_page(self):
        from config import get_config as _gc
        cfg = _gc()
        sc = cfg.get("serial", {})
        bc = cfg.get("serial_bridge", {})

        def s(cur, val):
            return " selected" if cur == val else ""

        p = []
        p.append('<div class="c"><h2>Serial Port</h2><form method="POST" action="/config">')
        p.append('<input type="hidden" name="section" value="port">')
        p.append('<label>DE Pin (-1=none)</label><input type="number" name="de_pin" value="{}" min="-1" max="16">'.format(sc.get("de_pin", -1)))
        p.append('<label>RE Pin (-1=none)</label><input type="number" name="re_pin" value="{}" min="-1" max="16">'.format(sc.get("re_pin", -1)))
        p.append('<label>Baud</label><select name="baudrate">')
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
        p.append('<label>Max Frame bytes</label><input type="number" name="max_frame_len" value="{}" min="64" max="2048">'.format(sc.get("max_frame_len", 512)))
        fh = sc.get("frame_header", [0x55, 0xAA, 0xEB, 0x90])
        p.append('<label>Frame Header (decimal)</label><input name="frame_header" value="{}">'.format(",".join(str(b) for b in fh)))
        p.append('<label>Prompt</label><select name="prompt">')
        for pv in ["pylon>", "pytes>", ">"]:
            p.append('<option value="{}"{}>{}</option>'.format(pv, s(sc.get("prompt", "pylon>"), pv), pv))
        p.append('</select><label>Response Timeout ms</label><input type="number" name="response_timeout_ms" value="{}" min="1000" max="30000">'.format(sc.get("response_timeout_ms", 5000)))
        p.append('<label>Line Ending</label><select name="line_ending">')
        stored = sc.get("line_ending", "\r\n").replace("\r\n", "\\r\\n").replace("\n", "\\n").replace("\r", "\\r")
        for val, lbl in [("\\r\\n", "CR+LF"), ("\\n", "LF"), ("\\r", "CR")]:
            p.append('<option value="{}"{}>{}</option>'.format(val, s(stored, val), lbl))
        p.append('</select><button type="submit">Save Port</button></form></div>')
        p.append('<div class="c"><h2>Bridge Server</h2><form method="POST" action="/config">')
        p.append('<input type="hidden" name="section" value="bridge">')
        p.append('<label>Host</label><input name="host" value="{}">'.format(bc.get("server_host", "")))
        p.append('<label>Port</label><input type="number" name="port" value="{}">'.format(bc.get("server_port", 8502)))
        p.append('<label>Reconnect Delay s</label><input type="number" name="reconnect_delay" value="{}">'.format(bc.get("reconnect_delay", 5)))
        p.append('<label>Keepalive s</label><input type="number" name="keepalive_interval" value="{}">'.format(bc.get("keepalive_interval", 1)))
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
