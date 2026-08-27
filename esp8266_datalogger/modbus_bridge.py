"""Modbus TCP-to-RTU bridge for ESP8266. Outbound TCP connection to server."""
import socket
import struct
import time

from config import get_config
from log_buffer import log_print as print
from http_utils import http_post_json


class ModbusBridge:

    MBAP_HEADER_SIZE = 7

    def __init__(self, rtu_master, config=None):
        self.rtu = rtu_master
        self.config = config or get_config()
        self.socket = None
        self._rtu_unit_id = self.config.get("rtu", {}).get("unit_id", 0) or 0
        if self._rtu_unit_id > 0:
            print("[Bridge] RTU unit_id override: {}".format(self._rtu_unit_id))
        self._connected = False
        self._running = False
        self._registered = False
        self._device_id = None
        self.stats = {"requests": 0, "responses": 0, "errors": 0, "reconnects": 0}

    def connect(self):
        cfg = self.config["modbus_bridge"]
        host = cfg["server_host"]
        port = cfg["server_port"]
        try:
            print("[Bridge] Connecting to {}:{}...".format(host, port))
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((host, port))
            self.socket.settimeout(None)
            self._connected = True
            print("[Bridge] Connected to server")
            return True
        except Exception as e:
            print("[Bridge] Connection failed:", e)
            self._cleanup_socket()
            return False

    def disconnect(self):
        self._running = False
        self._cleanup_socket()
        print("[Bridge] Disconnected")

    def _cleanup_socket(self):
        self._connected = False
        self._registered = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

    def is_connected(self):
        return self._connected

    def is_registered(self):
        return self._registered

    def get_device_id(self):
        return self._device_id

    def register_device(self):
        api_config = self.config.get("api", {})
        device_config = self.config.get("device", {})
        base_url = api_config.get("base_url", "http://localhost:8001")
        endpoint = api_config.get("register_endpoint", "/api/v1/devices/self-register")
        serial = device_config.get("serial", "")
        if not serial:
            print("[Bridge] No serial number configured, skipping registration")
            return False
        payload = {
            "serial_number": serial,
            "device_type": device_config.get("type", "inverter"),
            "firmware_version": device_config.get("firmware_version", "1.0.0"),
            "manufacturer": device_config.get("manufacturer", "SolarHub"),
            "protocol": device_config.get("protocol", "modbus_tcp"),
            "model": device_config.get("model"),
        }
        url = base_url + endpoint
        print("[Bridge] Registering device: {} -> {}".format(serial, url))
        status_code, response = http_post_json(url, payload)
        if status_code == 200:
            self._registered = True
            self._device_id = response.get("device_id") if response else None
            is_claimed = response.get("is_claimed", False) if response else False
            polling_ms = response.get("polling_interval_ms", 5000) if response else 5000
            print("[Bridge] Registered! ID={} claimed={} poll={}ms".format(
                self._device_id, is_claimed, polling_ms))
            return True
        else:
            error = response.get("detail") if response else "Unknown error"
            print("[Bridge] Registration failed: {} - {}".format(status_code, error))
            return False

    def run(self, idle_cb=None):
        self._running = True
        cfg = self.config["modbus_bridge"]
        reconnect_delay = cfg.get("reconnect_delay", 5)
        keepalive_interval = cfg.get("keepalive_interval", 1)

        while self._running:
            if not self._connected:
                if not self.connect():
                    print("[Bridge] Retrying in {}s...".format(reconnect_delay))
                    for _ in range(reconnect_delay):
                        if idle_cb:
                            idle_cb()
                        time.sleep(1)
                    self.stats["reconnects"] += 1
                    continue
                if not self._registered:
                    if self.register_device():
                        print("[Bridge] Device registered with System B")
                    else:
                        print("[Bridge] Registration failed, continuing anyway...")

            try:
                self.socket.settimeout(keepalive_interval)
                header = self._recv_exact(self.MBAP_HEADER_SIZE)
                if not header:
                    print("[Bridge] Connection closed by server")
                    self._cleanup_socket()
                    continue
                transaction_id, protocol_id, length, unit_id = struct.unpack(">HHHB", header)
                if protocol_id != 0:
                    print("[Bridge] Invalid protocol ID:", protocol_id)
                    continue
                pdu_length = length - 1
                if pdu_length <= 0 or pdu_length > 253:
                    print("[Bridge] Invalid PDU length:", pdu_length)
                    continue
                pdu = self._recv_exact(pdu_length)
                if not pdu:
                    print("[Bridge] Failed to receive PDU")
                    self._cleanup_socket()
                    continue
                self.stats["requests"] += 1
                func_code = pdu[0]
                is_write = func_code in (0x06, 0x10)
                addr = ((pdu[1] << 8) | pdu[2]) if len(pdu) >= 3 else 0
                rtu_unit = self._rtu_unit_id if self._rtu_unit_id > 0 else unit_id
                if is_write and func_code == 0x06:
                    val = ((pdu[3] << 8) | pdu[4]) if len(pdu) >= 5 else 0
                    print("[Bridge] FC06 write addr={} val={} unit={}".format(addr, val, rtu_unit))
                elif is_write and func_code == 0x10:
                    cnt = ((pdu[3] << 8) | pdu[4]) if len(pdu) >= 5 else 0
                    print("[Bridge] FC10 write addr={} cnt={} unit={}".format(addr, cnt, rtu_unit))
                response_pdu = self.rtu.forward_pdu(pdu, rtu_unit)
                if response_pdu:
                    if is_write:
                        print("[Bridge] → OK")
                    resp_length = len(response_pdu) + 1
                    resp_header = struct.pack(">HHHB", transaction_id, 0, resp_length, unit_id)
                    self.socket.sendall(resp_header + response_pdu)
                    self.stats["responses"] += 1
                else:
                    print("[Bridge] FC{:02X} addr={} unit={} → RTU no response".format(
                        func_code, addr, rtu_unit))
                    exc_pdu = bytes([func_code | 0x80, 0x0B])
                    resp_header = struct.pack(">HHHB", transaction_id, 0, 3, unit_id)
                    self.socket.sendall(resp_header + exc_pdu)
                    self.stats["errors"] += 1
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

    def _recv_exact(self, length):
        # See esp32_datalogger/modbus_bridge.py._recv_exact for the rationale.
        # Bare `except: return None` swallowed socket recv-timeouts and made
        # the ESP32 reconnect every keepalive_interval seconds.  Propagate
        # ETIMEDOUT (errno 110) when we've received nothing yet so the
        # outer keepalive handler in run() runs `continue`.
        data = bytearray()
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except OSError as e:
                if e.args and e.args[0] in (110, 116) and not data:  # ETIMEDOUT (110 stdlib, 116 MicroPython/ESP)
                    raise
                return None
            except Exception:
                return None
        return bytes(data)

    def get_stats(self):
        return self.stats.copy()

    def reset_stats(self):
        self.stats = {"requests": 0, "responses": 0, "errors": 0, "reconnects": 0}

    def get_config_page(self):
        from config import get_config as _gc
        cfg = _gc()
        rc = cfg.get("rtu", {})
        bc = cfg.get("modbus_bridge", {})

        def s(cur, val):
            return " selected" if cur == val else ""

        p = []
        p.append('<div class="c"><h2>Modbus RTU</h2><form method="POST" action="/config">')
        p.append('<input type="hidden" name="section" value="rtu">')
        p.append('<label>DE Pin</label><input type="number" name="de_pin" value="{}" min="0" max="16">'.format(rc.get("de_pin", 4)))
        p.append('<label>RE Pin</label><input type="number" name="re_pin" value="{}" min="0" max="16">'.format(rc.get("re_pin", 5)))
        p.append('<label>Unit ID (0=pass-through)</label><input type="number" name="unit_id" value="{}" min="0" max="247">'.format(rc.get("unit_id", 1)))
        p.append('<label>Baud</label><select name="baudrate">')
        for b in [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]:
            p.append('<option value="{}"{}>{}</option>'.format(b, s(rc.get("baudrate", 9600), b), b))
        p.append('</select><label>Parity</label><select name="parity">')
        for pv, pn in [("N", "None"), ("E", "Even"), ("O", "Odd")]:
            p.append('<option value="{}"{}>{}</option>'.format(pv, s(rc.get("parity", "N"), pv), pn))
        p.append('</select><label>Stop Bits</label><select name="stop_bits">')
        for sv in [1, 2]:
            p.append('<option value="{}"{}>{}</option>'.format(sv, s(rc.get("stop_bits", 1), sv), sv))
        p.append('</select><label>Timeout ms</label><input type="number" name="timeout_ms" value="{}" min="100" max="10000">'.format(rc.get("timeout_ms", 1000)))
        p.append('<button type="submit">Save RTU</button></form></div>')
        p.append('<div class="c"><h2>Bridge Server</h2><form method="POST" action="/config">')
        p.append('<input type="hidden" name="section" value="server">')
        p.append('<label>Host</label><input name="host" value="{}">'.format(bc.get("server_host", "")))
        p.append('<label>Port</label><input type="number" name="port" value="{}">'.format(bc.get("server_port", 8502)))
        p.append('<label>Reconnect Delay s</label><input type="number" name="reconnect_delay" value="{}">'.format(bc.get("reconnect_delay", 5)))
        p.append('<label>Keepalive s</label><input type="number" name="keepalive_interval" value="{}">'.format(bc.get("keepalive_interval", 1)))
        p.append('<button type="submit">Save Server</button></form></div>')
        return ''.join(p)

    def save_config(self, body):
        from config import load_config as _lc, save_config as _sc
        config = _lc()
        section = body.get("section", "server")
        if section == "rtu":
            rc = config.setdefault("rtu", {})
            rc["uart_id"] = 0
            rc["de_pin"] = int(body.get("de_pin", 4))
            rc["re_pin"] = int(body.get("re_pin", 5))
            rc["unit_id"] = int(body.get("unit_id", 1))
            rc["baudrate"] = int(body.get("baudrate", 9600))
            rc["parity"] = body.get("parity", "N")
            rc["stop_bits"] = int(body.get("stop_bits", 1))
            rc["data_bits"] = 8
            rc["timeout_ms"] = int(body.get("timeout_ms", 1000))
        else:
            mb = config.setdefault("modbus_bridge", {})
            mb["server_host"] = body.get("host", "").strip()
            mb["server_port"] = int(body.get("port", 8502))
            mb["reconnect_delay"] = int(body.get("reconnect_delay", 5))
            mb["keepalive_interval"] = int(body.get("keepalive_interval", 1))
        _sc(config)
        return '<p class="ok">Saved. Reboot to apply.</p>' + self.get_config_page()
