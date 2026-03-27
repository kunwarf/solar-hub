"""Web server for ESP8266 Data Logger configuration.

Slim core: Status, WiFi, Device identity, Reboot.
Mode-specific config (/config) is delegated to the active bridge module via
bridge.get_config_page() and bridge.save_config(body).

CSS and HTML header are built on demand inside _hdr() so they are NOT
permanently resident on the heap — they are allocated per-request and freed
after sendall().
"""
import gc
import json
import socket

from config import load_config, save_config, load_wifi, save_wifi, get_config, get_device_id


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
                    print("[Web] error:", e)
            except Exception as e:
                print("[Web] error:", e)
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

            ab = self.bridge or self.serial_bridge
            if path == "/" or path == "/status":
                content = self._page_status()
            elif path == "/wifi":
                content = self._handle_wifi_save(body) if method == "POST" else self._page_wifi()
            elif path == "/device":
                content = self._handle_device_save(body) if method == "POST" else self._page_device()
            elif path == "/config":
                if ab is None:
                    content = '<div class="c">No bridge loaded — set mode and reboot.</div>'
                else:
                    content = ab.save_config(body) if method == "POST" else ab.get_config_page()
            elif path == "/reboot":
                content = self._handle_reboot()
            elif path == "/api/status":
                return self._json_response(self._get_status_json())
            else:
                return self._response(404, "Not Found")
            return self._response(200, content)
        except Exception as e:
            print("[Web] handler error:", e)
            return self._response(500, "Error: " + str(e))

    def _hdr(self):
        ab = self.bridge or self.serial_bridge
        nav = ('<a href="/">Status</a> '
               '<a href="/wifi">WiFi</a> '
               '<a href="/device">Device</a>')
        if ab:
            nav += ' <a href="/config">Config</a>'
        return (
            '<!DOCTYPE html><html><head>'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Solar Logger</title><style>'
            'body{font-family:sans-serif;margin:10px}'
            '.c{border:1px solid #ddd;padding:10px;margin:8px 0;border-radius:4px}'
            'h1,h2{margin:0 0 8px;color:#333}'
            'label{display:block;margin:5px 0 2px;font-weight:bold}'
            'input,select{width:100%;padding:5px;border:1px solid #ccc;box-sizing:border-box}'
            'button{background:#4CAF50;color:#fff;padding:7px 14px;border:none;cursor:pointer;margin:2px}'
            '.bd{background:#d9534f}'
            'td{padding:5px;border-bottom:1px solid #eee}'
            'td:first-child{font-weight:bold;width:40%}'
            'a{color:#4CAF50}.ok{color:green}.er{color:red}'
            '</style></head><body>'
            '<h1>Solar Logger</h1><p>' + nav + '</p>'
        )

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
            hdr = self._hdr()
            client.sendall(hdr.encode())
            del hdr
            gc.collect()
        if isinstance(body, (bytes, bytearray, memoryview)):
            client.sendall(body)
        else:
            client.sendall(body.encode())
        del body
        gc.collect()
        if ct == "text/html":
            client.sendall(b"</body></html>")

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
            p.append("<tr><td>Status</td><td>Not connected</td></tr>")
        if ws["ap_active"]:
            p.append("<tr><td>AP</td><td>{} / {}</td></tr>".format(ws["ap_ssid"], ws["ap_ip"]))
        p.append("</table></div>")
        if ab:
            lbl = "Serial Bridge" if self.serial_bridge and not self.bridge else "Modbus Bridge"
            p.append('<div class="c"><h2>{}</h2><table>'.format(lbl))
            p.append("<tr><td>Connected</td><td>{}</td></tr>".format(
                "Yes" if ab.is_connected() else "No"))
            for k in ("requests", "commands", "responses", "errors"):
                if k in bs:
                    p.append("<tr><td>{}</td><td>{}</td></tr>".format(k.capitalize(), bs[k]))
            p.append("</table></div>")
        p.append('<div class="c">')
        p.append('<button onclick="location.reload()">Refresh</button> ')
        p.append('<button class="bd" onclick="if(confirm(\'Reboot?\'))location.href=\'/reboot\'">Reboot</button>')
        p.append('</div>')
        return ''.join(p)

    def _page_wifi(self):
        ssid = load_wifi().get("ssid", "")
        return (''.join([
            '<div class="c"><h2>WiFi</h2><form method="POST" action="/wifi">',
            '<label>SSID</label><input name="ssid" value="{}" placeholder="Network name">'.format(ssid),
            '<label>Password</label><input type="password" name="password" placeholder="Password">',
            '<button type="submit">Save &amp; Connect</button></form></div>',
        ]))

    def _handle_wifi_save(self, body):
        ssid = body.get("ssid", "").strip()
        if not ssid:
            return '<p class="er">SSID required</p>' + self._page_wifi()
        save_wifi(ssid, body.get("password", ""))
        if self.wifi.connect_sta(timeout_s=10):
            return '<p class="ok">Connected to {}</p>'.format(ssid) + self._page_wifi()
        return '<p class="er">Failed to connect to {}</p>'.format(ssid) + self._page_wifi()

    def _page_device(self):
        config = get_config()
        dc = config.get("device", {})
        mode = config.get("mode", "modbus_bridge")

        def s(cur, val):
            return " selected" if cur == val else ""

        p = []
        p.append('<div class="c"><h2>Mode</h2><form method="POST" action="/device">')
        p.append('<input type="hidden" name="section" value="mode">')
        p.append('<label>Mode</label><select name="mode">')
        for val, lbl in [("modbus_bridge", "Modbus Bridge (RS485)"),
                         ("serial_bridge", "Serial Bridge (RS232)")]:
            p.append('<option value="{}"{}>{}</option>'.format(val, s(mode, val), lbl))
        p.append('</select><button type="submit">Save Mode</button></form></div>')

        p.append('<div class="c"><h2>Identity</h2><form method="POST" action="/device">')
        p.append('<input type="hidden" name="section" value="identity">')
        p.append('<label>Serial Number</label><input name="serial" value="{}" placeholder="SH01XXXXXXXX">'.format(
            dc.get("serial", "")))
        p.append('<label>Name</label><input name="name" value="{}" placeholder="Solar Logger 1">'.format(
            dc.get("name", "")))
        p.append('<label>Type</label><select name="type">')
        for val in ["inverter", "battery", "meter", "gateway"]:
            p.append('<option value="{}"{}>{}</option>'.format(val, s(dc.get("type", "inverter"), val), val.capitalize()))
        p.append('</select>')
        p.append('<label>Manufacturer</label><input name="manufacturer" value="{}" placeholder="SolarHub">'.format(
            dc.get("manufacturer", "SolarHub")))
        p.append('<label>Model</label><input name="model" value="{}" placeholder="e.g. US5000">'.format(
            dc.get("model", "")))
        p.append('<label>Protocol</label><select name="protocol">')
        for val, lbl in [("modbus_tcp", "Modbus TCP"), ("command", "Command (Pylontech/Pytes)"),
                         ("jkbms_serial", "JK BMS Serial"), ("jkbms_modbus", "JK BMS Modbus")]:
            p.append('<option value="{}"{}>{}</option>'.format(val, s(dc.get("protocol", "modbus_tcp"), val), lbl))
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
        return '<p class="ok">Saved. Reboot to apply.</p>' + self._page_device()

    def _handle_reboot(self):
        self._pending_reboot = True
        return ('<div class="c"><p class="ok">Rebooting...</p>'
                '<script>setTimeout(function(){location.href="/";},5000);</script></div>')

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
