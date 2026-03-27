"""Web server for ESP8266 Data Logger configuration.

ESP8266: _handle_reboot() uses _pending_reboot flag (no _thread available).
"""
import gc
import json
import socket

from config import load_config, save_config, load_wifi, save_wifi, get_config, get_device_id

_CSS = (
    "body{font-family:sans-serif;margin:16px;background:#f0f0f0}"
    ".c{background:#fff;padding:16px;margin:8px 0;border-radius:6px}"
    "h1,h2{color:#333;margin:0 0 10px}"
    "label{display:block;margin:8px 0 2px;font-weight:bold}"
    "input,select{width:100%;padding:6px;border:1px solid #ccc;"
    "border-radius:3px;box-sizing:border-box}"
    "button{background:#4CAF50;color:#fff;padding:8px 16px;border:none;"
    "border-radius:3px;cursor:pointer;margin:3px}"
    ".bd{background:#d9534f}"
    "td{padding:6px;border-bottom:1px solid #eee}"
    "td:first-child{font-weight:bold;width:40%}"
    ".nav a{margin-right:12px;color:#4CAF50;text-decoration:none}"
    ".ok{color:#3c763d;background:#dff0d8;padding:8px;border-radius:3px}"
    ".er{color:#a94442;background:#f2dede;padding:8px;border-radius:3px}"
)

_HDR = (
    '<!DOCTYPE html><html><head>'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>Solar Logger</title><style>' + _CSS + '</style></head><body>'
    '<h1>Solar Logger</h1>'
    '<div class="nav">'
    '<a href="/">Status</a>'
    '<a href="/wifi">WiFi</a>'
    '<a href="/device">Device</a>'
    '<a href="/serial">Serial</a>'
    '<a href="/server">Server</a>'
    '</div>'
)

_FTR = '</body></html>'


class WebServer:

    def __init__(self, wifi_manager, bridge=None, rtu=None, port=80, serial_bridge=None):
        self.wifi = wifi_manager
        self.bridge = bridge
        self.rtu = rtu
        self.serial_bridge = serial_bridge
        self.port = port
        self.socket = None
        self._running = False
        self._pending_reboot = False

    def start(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", self.port))
        self.socket.listen(5)
        self.socket.settimeout(0.5)
        self._running = True
        print("[Web] Server started on port", self.port)

    def stop(self):
        self._running = False
        if self.socket:
            self.socket.close()
            self.socket = None
        print("[Web] Server stopped")

    def handle_requests(self):
        if not self._running:
            return
        if self._pending_reboot:
            import time
            import machine
            time.sleep(1)
            machine.reset()
        try:
            client, addr = self.socket.accept()
            client.settimeout(5)
            try:
                gc.collect()
                raw = b""
                while b"\r\n\r\n" not in raw:
                    chunk = client.recv(512)
                    if not chunk:
                        break
                    raw += chunk
                    if len(raw) > 2048:
                        break
                header_end = raw.find(b"\r\n\r\n")
                if header_end >= 0:
                    headers_raw = raw[:header_end].decode("utf-8", "replace")
                    body_so_far = raw[header_end + 4:]
                    content_length = 0
                    for line in headers_raw.split("\r\n"):
                        if line.lower().startswith("content-length:"):
                            try:
                                content_length = int(line.split(":", 1)[1].strip())
                            except ValueError:
                                pass
                    while len(body_so_far) < content_length:
                        chunk = client.recv(512)
                        if not chunk:
                            break
                        body_so_far += chunk
                    request = headers_raw + "\r\n\r\n" + body_so_far.decode("utf-8", "replace")
                else:
                    request = raw.decode("utf-8", "replace")
                if request:
                    self._send_result(client, self._handle_request(request))
            except OSError as e:
                if e.args[0] not in (110, 116):
                    print("[Web] Request error:", e)
            except Exception as e:
                print("[Web] Request error:", e)
            finally:
                client.close()
                gc.collect()
        except OSError:
            pass

    def _handle_request(self, request):
        try:
            lines = request.split("\r\n")
            method, path, _ = lines[0].split(" ", 2)
            if "?" in path:
                path, _ = path.split("?", 1)
            content_type = ""
            for line in lines[1:]:
                if line.lower().startswith("content-type:"):
                    content_type = line.split(":", 1)[1].strip()
                    break
            body = {}
            if method == "POST":
                bs = request.find("\r\n\r\n")
                if bs > 0:
                    body_str = request[bs + 4:]
                    if "application/json" in content_type:
                        try:
                            body = json.loads(body_str)
                        except:
                            pass
                    else:
                        for pair in body_str.split("&"):
                            if "=" in pair:
                                k, v = pair.split("=", 1)
                                body[k] = self._url_decode(v)

            if path == "/" or path == "/status":
                content = self._page_status()
            elif path == "/wifi":
                content = self._handle_wifi_save(body) if method == "POST" else self._page_wifi()
            elif path == "/device":
                content = self._handle_device_save(body) if method == "POST" else self._page_device()
            elif path == "/serial":
                content = self._handle_serial_save(body) if method == "POST" else self._page_serial()
            elif path == "/server":
                content = self._handle_server_save(body) if method == "POST" else self._page_server()
            elif path == "/reboot":
                content = self._handle_reboot()
            elif path == "/api/status":
                return self._json_response(self._get_status_json())
            else:
                return self._response(404, "Not Found")
            return self._response(200, content)
        except Exception as e:
            print("[Web] Error:", e)
            return self._response(500, "Error: " + str(e))

    def _response(self, code, body="", content_type="text/html"):
        return (code, content_type, body)

    def _json_response(self, data, status=200):
        return (status, "application/json", json.dumps(data))

    def _send_result(self, client, result):
        code, ct, body = result
        status = {200: "OK", 404: "Not Found", 500: "Internal Server Error"}.get(code, "OK")
        client.sendall(
            "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nConnection: close\r\n\r\n"
            .format(code, status, ct).encode()
        )
        if ct == "text/html":
            client.sendall(_HDR.encode())
            gc.collect()
        if isinstance(body, (bytes, bytearray, memoryview)):
            client.sendall(body)
        else:
            client.sendall(body.encode())
        del body
        gc.collect()
        if ct == "text/html":
            client.sendall(_FTR.encode())

    def _url_decode(self, s):
        result = s.replace("+", " ")
        i = 0
        decoded = ""
        while i < len(result):
            if result[i] == "%" and i + 2 < len(result):
                try:
                    decoded += chr(int(result[i+1:i+3], 16))
                    i += 3
                    continue
                except:
                    pass
            decoded += result[i]
            i += 1
        return decoded

    def _sel(self, current, value):
        return " selected" if current == value else ""

    def _page_status(self):
        ws = self.wifi.get_status()
        config = get_config()
        ab = self.bridge or self.serial_bridge
        bs = ab.get_stats() if ab else {}
        p = []
        p.append('<div class="c"><h2>Device</h2><table>')
        p.append("<tr><td>ID</td><td>{}</td></tr>".format(get_device_id()))
        p.append("<tr><td>Mode</td><td>{}</td></tr>".format(config.get("mode", "?")))
        p.append("<tr><td>Platform</td><td>ESP8266</td></tr></table></div>")
        p.append('<div class="c"><h2>WiFi</h2><table>')
        if ws["sta_connected"]:
            p.append("<tr><td>Status</td><td>Connected</td></tr>")
            p.append("<tr><td>SSID</td><td>{}</td></tr>".format(ws["sta_ssid"]))
            p.append("<tr><td>IP</td><td>{}</td></tr>".format(ws["sta_ip"]))
        else:
            p.append("<tr><td>Status</td><td>Not Connected</td></tr>")
        if ws["ap_active"]:
            p.append("<tr><td>AP</td><td>{} / {}</td></tr>".format(ws["ap_ssid"], ws["ap_ip"]))
        p.append("</table></div>")
        if ab:
            lbl = "Serial Bridge" if self.serial_bridge and not self.bridge else "Modbus Bridge"
            p.append('<div class="c"><h2>{}</h2><table>'.format(lbl))
            p.append("<tr><td>Connected</td><td>{}</td></tr>".format(
                "Yes" if ab.is_connected() else "No"))
            if self.serial_bridge and not self.bridge:
                p.append("<tr><td>Commands</td><td>{}</td></tr>".format(bs.get("commands", 0)))
            else:
                p.append("<tr><td>Requests</td><td>{}</td></tr>".format(bs.get("requests", 0)))
            p.append("<tr><td>Responses</td><td>{}</td></tr>".format(bs.get("responses", 0)))
            p.append("<tr><td>Errors</td><td>{}</td></tr>".format(bs.get("errors", 0)))
            p.append("</table></div>")
        p.append('<div class="c">')
        p.append('<button onclick="location.reload()">Refresh</button>')
        p.append('<button class="bd" onclick="if(confirm(\'Reboot?\'))location.href=\'/reboot\'">Reboot</button>')
        p.append('</div>')
        return ''.join(p)

    def _page_wifi(self):
        ssid = load_wifi().get("ssid", "")
        p = []
        p.append('<div class="c"><h2>WiFi</h2><form method="POST" action="/wifi">')
        p.append('<label>SSID</label><input name="ssid" value="{}" placeholder="Network name">'.format(ssid))
        p.append('<label>Password</label><input type="password" name="password" placeholder="Password">')
        p.append('<button type="submit">Save &amp; Connect</button></form></div>')
        return ''.join(p)

    def _handle_wifi_save(self, body):
        ssid = body.get("ssid", "").strip()
        if not ssid:
            return '<div class="er">SSID required</div>' + self._page_wifi()
        save_wifi(ssid, body.get("password", ""))
        if self.wifi.connect_sta(timeout_s=10):
            return '<div class="ok">Connected to {}</div>'.format(ssid) + self._page_wifi()
        return '<div class="er">Failed to connect to {}</div>'.format(ssid) + self._page_wifi()

    def _page_server(self):
        cfg = get_config().get("modbus_bridge", {})
        p = []
        p.append('<div class="c"><h2>Modbus Bridge Server</h2><form method="POST" action="/server">')
        p.append('<label>Host</label><input name="server_host" value="{}">'.format(
            cfg.get("server_host", "")))
        p.append('<label>Port</label><input type="number" name="server_port" value="{}">'.format(
            cfg.get("server_port", 8502)))
        p.append('<label>Reconnect Delay (s)</label><input type="number" name="reconnect_delay" value="{}">'.format(
            cfg.get("reconnect_delay", 5)))
        p.append('<label>Keepalive Interval (s)</label><input type="number" name="keepalive_interval" value="{}">'.format(
            cfg.get("keepalive_interval", 1)))
        p.append('<button type="submit">Save</button></form></div>')
        return ''.join(p)

    def _handle_server_save(self, body):
        config = load_config()
        mb = config.setdefault("modbus_bridge", {})
        mb["server_host"] = body.get("server_host", "").strip()
        mb["server_port"] = int(body.get("server_port", 8502))
        mb["reconnect_delay"] = int(body.get("reconnect_delay", 5))
        mb["keepalive_interval"] = int(body.get("keepalive_interval", 1))
        save_config(config)
        return '<div class="ok">Saved. Reboot to apply.</div>' + self._page_server()

    def _page_device(self):
        config = get_config()
        dc = config.get("device", {})
        mode = config.get("mode", "modbus_bridge")
        p = []
        p.append('<div class="c"><h2>Mode</h2><form method="POST" action="/device">')
        p.append('<input type="hidden" name="section" value="mode">')
        p.append('<label>Mode</label><select name="mode">')
        for val, lbl in [("modbus_bridge", "Modbus Bridge (RS485)"),
                         ("serial_bridge", "Serial Bridge (RS232)")]:
            p.append('<option value="{}"{}>{}</option>'.format(val, self._sel(mode, val), lbl))
        p.append('</select><button type="submit">Save Mode</button></form></div>')

        p.append('<div class="c"><h2>Identity</h2><form method="POST" action="/device">')
        p.append('<input type="hidden" name="section" value="identity">')
        p.append('<label>Serial Number</label><input name="serial" value="{}" placeholder="SH01XXXXXXXX">'.format(
            dc.get("serial", "")))
        p.append('<label>Name (optional)</label><input name="name" value="{}" placeholder="Solar Logger 1">'.format(
            dc.get("name", "")))
        p.append('<label>Type</label><select name="type">')
        for val in ["inverter", "battery", "meter", "gateway"]:
            p.append('<option value="{}"{}>{}</option>'.format(
                val, self._sel(dc.get("type", "inverter"), val), val.capitalize()))
        p.append('</select>')
        p.append('<label>Manufacturer</label><input name="manufacturer" value="{}" placeholder="SolarHub">'.format(
            dc.get("manufacturer", "SolarHub")))
        p.append('<label>Model</label><input name="model" value="{}" placeholder="e.g. US5000">'.format(
            dc.get("model", "")))
        p.append('<label>Protocol</label><select name="protocol">')
        for val, lbl in [("modbus_tcp", "Modbus TCP"),
                         ("command", "Command (Pylontech/Pytes)"),
                         ("jkbms_serial", "JK BMS Serial"),
                         ("jkbms_modbus", "JK BMS Modbus")]:
            p.append('<option value="{}"{}>{}</option>'.format(
                val, self._sel(dc.get("protocol", "modbus_tcp"), val), lbl))
        p.append('</select>')
        p.append('<label>Firmware</label><input name="firmware_version" value="{}">'.format(
            dc.get("firmware_version", "1.0.0")))
        p.append('<button type="submit">Save Identity</button></form></div>')
        return ''.join(p)

    def _handle_device_save(self, body):
        config = load_config()
        section = body.get("section", "identity")
        if section == "mode":
            mode = body.get("mode", "modbus_bridge")
            if mode in ("modbus_bridge", "serial_bridge"):
                config["mode"] = mode
        else:
            dc = config.setdefault("device", {})
            serial = body.get("serial", "").strip()
            if serial:
                dc["serial"] = serial
            dc["name"] = body.get("name", "").strip()
            dc["type"] = body.get("type", "inverter")
            dc["manufacturer"] = body.get("manufacturer", "SolarHub").strip()
            dc["model"] = body.get("model", "").strip()
            dc["firmware_version"] = body.get("firmware_version", "1.0.0").strip()
            proto = body.get("protocol", "modbus_tcp")
            if proto in ("modbus_tcp", "command", "jkbms_serial", "jkbms_modbus"):
                dc["protocol"] = proto
        save_config(config)
        return '<div class="ok">Saved. Reboot to apply.</div>' + self._page_device()

    def _page_serial(self):
        config = get_config()
        rc = config.get("rtu", {})
        sc = config.get("serial", {})
        bc = config.get("serial_bridge", {})
        p = []

        # Modbus RTU card
        p.append('<div class="c"><h2>Modbus RTU (RS485)</h2>')
        p.append('<form method="POST" action="/serial">')
        p.append('<input type="hidden" name="section" value="rtu">')
        p.append('<label>DE Pin</label><input type="number" name="rtu_de_pin" value="{}" min="0" max="16">'.format(
            rc.get("de_pin", 4)))
        p.append('<label>RE Pin</label><input type="number" name="rtu_re_pin" value="{}" min="0" max="16">'.format(
            rc.get("re_pin", 5)))
        p.append('<label>Unit ID (0=pass-through)</label><input type="number" name="rtu_unit_id" value="{}" min="0" max="247">'.format(
            rc.get("unit_id", 1)))
        p.append('<label>Baud Rate</label><select name="rtu_baudrate">')
        for b in [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]:
            p.append('<option value="{}"{}>{}</option>'.format(
                b, self._sel(rc.get("baudrate", 9600), b), b))
        p.append('</select>')
        p.append('<label>Parity</label><select name="rtu_parity">')
        for pv, pn in [("N", "None"), ("E", "Even"), ("O", "Odd")]:
            p.append('<option value="{}"{}>{}</option>'.format(
                pv, self._sel(rc.get("parity", "N"), pv), pn))
        p.append('</select>')
        p.append('<label>Stop Bits</label><select name="rtu_stop_bits">')
        for s in [1, 2]:
            p.append('<option value="{}"{}>{}</option>'.format(
                s, self._sel(rc.get("stop_bits", 1), s), s))
        p.append('</select>')
        p.append('<label>Timeout (ms)</label><input type="number" name="rtu_timeout_ms" value="{}" min="100" max="10000">'.format(
            rc.get("timeout_ms", 1000)))
        p.append('<button type="submit">Save RTU</button></form></div>')

        # Serial Port card
        p.append('<div class="c"><h2>Serial Port (RS232 / RS485)</h2>')
        p.append('<form method="POST" action="/serial">')
        p.append('<input type="hidden" name="section" value="port">')
        p.append('<label>DE Pin (-1=none)</label><input type="number" name="de_pin" value="{}" min="-1" max="16">'.format(
            sc.get("de_pin", -1)))
        p.append('<label>RE Pin (-1=none)</label><input type="number" name="re_pin" value="{}" min="-1" max="16">'.format(
            sc.get("re_pin", -1)))
        p.append('<label>Baud Rate</label><select name="baudrate">')
        for b in [9600, 19200, 38400, 57600, 115200]:
            p.append('<option value="{}"{}>{}</option>'.format(
                b, self._sel(sc.get("baudrate", 115200), b), b))
        p.append('</select>')
        p.append('<label>Parity</label><select name="parity">')
        for pv, pn in [("N", "None"), ("E", "Even"), ("O", "Odd")]:
            p.append('<option value="{}"{}>{}</option>'.format(
                pv, self._sel(sc.get("parity", "N"), pv), pn))
        p.append('</select>')
        p.append('<label>Stop Bits</label><select name="stop_bits">')
        for s in [1, 2]:
            p.append('<option value="{}"{}>{}</option>'.format(
                s, self._sel(sc.get("stop_bits", 1), s), s))
        p.append('</select>')
        passive = "checked" if sc.get("passive", False) else ""
        p.append('<label>RS485 Passive (JK BMS) <input type="checkbox" name="passive" value="1" {}></label>'.format(passive))
        p.append('<label>Max Frame (bytes)</label><input type="number" name="max_frame_len" value="{}" min="64" max="2048">'.format(
            sc.get("max_frame_len", 512)))
        fh = sc.get("frame_header", [0x55, 0xAA, 0xEB, 0x90])
        p.append('<label>Frame Header (decimal, JK BMS: 85,170,235,144)</label><input name="frame_header" value="{}">'.format(
            ",".join(str(b) for b in fh)))
        p.append('<label>Prompt</label><select name="prompt">')
        for pv in ["pylon>", "pytes>", ">"]:
            p.append('<option value="{}"{}>{}</option>'.format(
                pv, self._sel(sc.get("prompt", "pylon>"), pv), pv))
        p.append('</select>')
        p.append('<label>Response Timeout (ms)</label><input type="number" name="response_timeout_ms" value="{}" min="1000" max="30000">'.format(
            sc.get("response_timeout_ms", 5000)))
        p.append('<label>Line Ending</label><select name="line_ending">')
        stored = sc.get("line_ending", "\r\n").replace("\r\n", "\\r\\n").replace("\n", "\\n").replace("\r", "\\r")
        for val, lbl in [("\\r\\n", "CR+LF"), ("\\n", "LF"), ("\\r", "CR")]:
            p.append('<option value="{}"{}>{}</option>'.format(val, self._sel(stored, val), lbl))
        p.append('</select>')
        p.append('<button type="submit">Save Port</button></form></div>')

        # Serial Bridge Server card
        p.append('<div class="c"><h2>Serial Bridge Server</h2>')
        p.append('<form method="POST" action="/serial">')
        p.append('<input type="hidden" name="section" value="bridge">')
        p.append('<label>Host</label><input name="server_host" value="{}">'.format(
            bc.get("server_host", "")))
        p.append('<label>Port</label><input type="number" name="server_port" value="{}">'.format(
            bc.get("server_port", 8502)))
        p.append('<label>Reconnect Delay (s)</label><input type="number" name="reconnect_delay" value="{}">'.format(
            bc.get("reconnect_delay", 5)))
        p.append('<label>Keepalive (s)</label><input type="number" name="keepalive_interval" value="{}">'.format(
            bc.get("keepalive_interval", 1)))
        p.append('<button type="submit">Save Bridge</button></form></div>')
        return ''.join(p)

    def _handle_serial_save(self, body):
        config = load_config()
        section = body.get("section", "port")
        if section == "bridge":
            sb = config.setdefault("serial_bridge", {})
            sb["server_host"] = body.get("server_host", "").strip()
            sb["server_port"] = int(body.get("server_port", 8502))
            sb["reconnect_delay"] = int(body.get("reconnect_delay", 5))
            sb["keepalive_interval"] = int(body.get("keepalive_interval", 1))
        elif section == "rtu":
            rc = config.setdefault("rtu", {})
            rc["uart_id"] = 0
            rc["de_pin"] = int(body.get("rtu_de_pin", 4))
            rc["re_pin"] = int(body.get("rtu_re_pin", 5))
            rc["unit_id"] = int(body.get("rtu_unit_id", 1))
            rc["baudrate"] = int(body.get("rtu_baudrate", 9600))
            rc["parity"] = body.get("rtu_parity", "N")
            rc["stop_bits"] = int(body.get("rtu_stop_bits", 1))
            rc["data_bits"] = 8
            rc["timeout_ms"] = int(body.get("rtu_timeout_ms", 1000))
        else:
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
        save_config(config)
        return '<div class="ok">Saved. Reboot to apply.</div>' + self._page_serial()

    def _handle_reboot(self):
        self._pending_reboot = True
        return ('<div class="ok">Rebooting...</div>'
                '<script>setTimeout(function(){location.href="/";},5000);</script>')

    def _get_status_json(self):
        ws = self.wifi.get_status()
        ab = self.bridge or self.serial_bridge
        bs = ab.get_stats() if ab else {}
        return {
            "device_id": get_device_id(),
            "platform": "ESP8266",
            "wifi": ws,
            "bridge": {
                "connected": ab.is_connected() if ab else False,
                "type": "serial" if self.serial_bridge and not self.bridge else "modbus",
                "stats": bs,
            }
        }
