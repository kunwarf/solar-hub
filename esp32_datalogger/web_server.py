"""
Web server for ESP32 Data Logger configuration.

Provides a simple HTTP interface for configuring WiFi, Modbus settings,
and viewing device status.
"""
import gc
import json
import socket

from config import (
    load_config, save_config, load_wifi, save_wifi,
    get_config, get_device_id, DEFAULT_CONFIG
)
from file_manager import FileManager

# Optional log buffer for web interface logging
try:
    from log_buffer import get_log_buffer
    _LOG_BUFFER_AVAILABLE = True
except ImportError:
    _LOG_BUFFER_AVAILABLE = False
    def get_log_buffer():
        """Dummy function when log_buffer not available."""
        return None


# HTML Templates
HTML_HEADER = """<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Logger Config</title>
<style>
body{font-family:sans-serif;margin:20px;background:#f5f5f5}
.card{background:white;padding:20px;margin:10px 0;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}
h1{color:#333;margin-bottom:20px}
h2{color:#555;margin-top:0}
label{display:block;margin:10px 0 5px;font-weight:bold}
input,select{width:100%;padding:8px;margin-bottom:10px;border:1px solid #ddd;border-radius:4px;box-sizing:border-box}
button{background:#4CAF50;color:white;padding:10px 20px;border:none;border-radius:4px;cursor:pointer;margin:5px}
button:hover{background:#45a049}
.btn-danger{background:#f44336}
.btn-danger:hover{background:#d32f2f}
.status{padding:10px;border-radius:4px;margin:10px 0}
.status-ok{background:#dff0d8;color:#3c763d}
.status-err{background:#f2dede;color:#a94442}
table{width:100%;border-collapse:collapse}
td{padding:8px;border-bottom:1px solid #ddd}
td:first-child{font-weight:bold;width:40%}
.nav{margin-bottom:20px}
.nav a{margin-right:15px;text-decoration:none;color:#4CAF50}
</style>
</head>
<body>
<h1>Solar Logger</h1>
<div class="nav">
<a href="/">Status</a>
<a href="/logs">Logs</a>
<a href="/files">Files</a>
<a href="/wifi">WiFi</a>
<a href="/device">Device</a>
<a href="/modbus">Modbus</a>
<a href="/serial">Serial</a>
<a href="/server">Server</a>
</div>
"""

HTML_FOOTER = """
</body>
</html>
"""


class WebServer:
    """Simple HTTP server for configuration."""

    def __init__(self, wifi_manager, bridge=None, rtu=None, port=80,
                 serial_bridge=None):
        """
        Initialize web server.

        Args:
            wifi_manager: WiFiManager instance.
            bridge: ModbusBridge instance (optional).
            rtu: ModbusRTU instance (optional).
            port: HTTP port (default 80).
            serial_bridge: SerialBridge instance (optional, for serial_bridge mode).
        """
        self.wifi = wifi_manager
        self.bridge = bridge
        self.rtu = rtu
        self.serial_bridge = serial_bridge
        self.port = port
        self.socket = None
        self._running = False

    def start(self):
        """Start the web server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("0.0.0.0", self.port))
        self.socket.listen(5)
        self.socket.settimeout(0.5)

        self._running = True
        print("[Web] Server started on port", self.port)

    def stop(self):
        """Stop the web server."""
        self._running = False
        if self.socket:
            self.socket.close()
            self.socket = None
        print("[Web] Server stopped")

    def handle_requests(self):
        """
        Handle pending HTTP requests (non-blocking).

        Call this periodically from main loop.
        """
        if not self._running:
            return

        try:
            client, addr = self.socket.accept()
            client.settimeout(5)

            try:
                # Free dead objects before any allocations in the request path.
                # The serial bridge thread may have released large bytearrays
                # that the GC hasn't reclaimed yet.
                gc.collect()

                # Read headers first (up to 2 KB)
                raw = b""
                while b"\r\n\r\n" not in raw:
                    chunk = client.recv(512)
                    if not chunk:
                        break
                    raw += chunk
                    if len(raw) > 2048:
                        break

                # Read body based on Content-Length
                header_end = raw.find(b"\r\n\r\n")
                if header_end >= 0:
                    headers_raw = raw[:header_end].decode("utf-8", "replace")
                    body_so_far = raw[header_end + 4:]
                    content_length = 0
                    content_type = ""
                    for line in headers_raw.split("\r\n"):
                        ll = line.lower()
                        if ll.startswith("content-length:"):
                            try:
                                content_length = int(line.split(":", 1)[1].strip())
                            except ValueError:
                                pass
                        elif ll.startswith("content-type:"):
                            content_type = line.split(":", 1)[1].strip()

                    # Extract method + path from first header line
                    first_line = headers_raw.split("\r\n")[0]
                    parts = first_line.split(" ")
                    req_method = parts[0] if parts else "GET"
                    req_path = parts[1] if len(parts) > 1 else "/"

                    # Stream file uploads directly to flash — no full-body buffering
                    if req_method == "POST" and req_path.startswith("/api/files/upload"):
                        result = self._stream_file_upload(
                            client, body_so_far, content_length, req_path
                        )
                        self._send_result(client, result)
                    else:
                        while len(body_so_far) < content_length:
                            chunk = client.recv(512)
                            if not chunk:
                                break
                            body_so_far += chunk
                        request = headers_raw + "\r\n\r\n" + body_so_far.decode("utf-8", "replace")
                        if request:
                            self._send_result(client, self._handle_request(request))
                else:
                    request = raw.decode("utf-8", "replace")
                    if request:
                        self._send_result(client, self._handle_request(request))
            except OSError as e:
                # ETIMEDOUT (116) — client connected but did not send headers
                # in time (e.g. browser prefetch, network scanner).  Benign.
                if e.args[0] != 116:
                    print("[Web] Request error:", e)
            except Exception as e:
                print("[Web] Request error:", e)
            finally:
                client.close()
                # Immediately free the response string and request buffers so
                # the serial bridge thread doesn't compete for that heap space.
                gc.collect()

        except OSError:
            # Timeout, no connection
            pass

    def _handle_request(self, request):
        """Handle HTTP request and return response."""
        try:
            # Parse request line
            lines = request.split("\r\n")
            method, path, _ = lines[0].split(" ", 2)

            # Parse query string
            query = {}
            if "?" in path:
                path, query_str = path.split("?", 1)
                for pair in query_str.split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        query[k] = self._url_decode(v)

            # Get Content-Type header
            content_type = ""
            for line in lines[1:]:
                if line.lower().startswith("content-type:"):
                    content_type = line.split(":", 1)[1].strip()
                    break

            # Parse POST body
            body = {}
            body_raw = ""
            if method == "POST":
                # Find body after empty line
                body_start = request.find("\r\n\r\n")
                if body_start > 0:
                    body_str = request[body_start + 4:]
                    body_raw = body_str

                    # Parse based on content type
                    if "application/json" in content_type:
                        try:
                            body = json.loads(body_str)
                        except:
                            pass
                    else:
                        # URL-encoded form data
                        for pair in body_str.split("&"):
                            if "=" in pair:
                                k, v = pair.split("=", 1)
                                body[k] = self._url_decode(v)

            # Route request
            if path == "/" or path == "/status":
                content = self._page_status()
            elif path == "/logs":
                content = self._page_logs()
            elif path == "/api/logs":
                # API endpoint for fetching logs
                since_id = query.get("since_id")
                since_id = int(since_id) if since_id else None
                return self._json_response(self._get_logs_json(since_id))
            elif path == "/api/logs/clear":
                log_buffer = get_log_buffer()
                if log_buffer:
                    log_buffer.clear()
                return self._json_response({"success": True})
            elif path == "/files":
                content = self._page_files()
            elif path == "/api/files/list":
                return self._json_response(self._get_files_json())
            elif path == "/api/files/upload":
                if method == "POST":
                    return self._handle_file_upload(body_raw, content_type)
                return self._json_response({"error": "Method not allowed"}, status=405)
            elif path == "/api/files/delete":
                if method == "POST":
                    return self._handle_file_delete(body)
                return self._json_response({"error": "Method not allowed"}, status=405)
            elif path == "/api/files/reboot":
                import machine
                machine.reset()
            elif path == "/device":
                if method == "POST":
                    content = self._handle_device_save(body)
                else:
                    content = self._page_device()
            elif path == "/wifi":
                if method == "POST":
                    content = self._handle_wifi_save(body)
                else:
                    content = self._page_wifi()
            elif path == "/modbus":
                if method == "POST":
                    content = self._handle_modbus_save(body)
                else:
                    content = self._page_modbus()
            elif path == "/serial":
                if method == "POST":
                    content = self._handle_serial_save(body)
                else:
                    content = self._page_serial()
            elif path == "/server":
                if method == "POST":
                    content = self._handle_server_save(body)
                else:
                    content = self._page_server()
            elif path == "/reboot":
                content = self._handle_reboot()
            elif path == "/api/status":
                return self._json_response(self._get_status_json())
            else:
                return self._response(404, "Not Found")

            # Return just the page body — HTML_HEADER/FOOTER added by _send_result
            return self._response(200, content)

        except Exception as e:
            print("[Web] Error:", e)
            return self._response(500, "Error: " + str(e))

    def _response(self, code, body="", content_type="text/html"):
        """Return (code, content_type, body) tuple — streamed by _send_result."""
        return (code, content_type, body)

    def _json_response(self, data, status=200):
        """Return JSON response tuple."""
        return (status, "application/json", json.dumps(data))

    def _send_result(self, client, result):
        """
        Stream a (code, content_type, body) tuple to the client.

        For text/html responses, HTML_HEADER and HTML_FOOTER are sent as
        separate sendall() calls so the full page is never concatenated in
        RAM.  This reduces peak allocation from 3× page size to 1× page size.
        """
        code, ct, body = result
        status = {200: "OK", 404: "Not Found", 405: "Method Not Allowed",
                  500: "Internal Server Error"}.get(code, "OK")
        client.sendall(
            "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nConnection: close\r\n\r\n"
            .format(code, status, ct).encode()
        )
        if ct == "text/html":
            client.sendall(HTML_HEADER.encode())
            gc.collect()
        if isinstance(body, (bytes, bytearray, memoryview)):
            client.sendall(body)
        else:
            client.sendall(body.encode())
        del body
        gc.collect()
        if ct == "text/html":
            client.sendall(HTML_FOOTER.encode())

    def _url_decode(self, s):
        """Decode URL-encoded string."""
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
        """Status page."""
        wifi_status = self.wifi.get_status()
        config = get_config()
        device_id = get_device_id()

        # Bridge stats (Modbus or Serial bridge)
        active_bridge = self.bridge or self.serial_bridge
        bridge_stats = active_bridge.get_stats() if active_bridge else {}

        html = '<div class="card"><h2>Device Info</h2><table>'
        html += "<tr><td>Device ID</td><td>{}</td></tr>".format(device_id)
        html += "<tr><td>Mode</td><td>{}</td></tr>".format(config.get("mode", "unknown"))
        html += "</table></div>"

        # WiFi Status
        html += '<div class="card"><h2>WiFi Status</h2><table>'
        if wifi_status["sta_connected"]:
            html += '<tr><td>Status</td><td class="status-ok">Connected</td></tr>'
            html += "<tr><td>SSID</td><td>{}</td></tr>".format(wifi_status["sta_ssid"])
            html += "<tr><td>IP Address</td><td>{}</td></tr>".format(wifi_status["sta_ip"])
        else:
            html += '<tr><td>Status</td><td class="status-err">Not Connected</td></tr>'

        if wifi_status["ap_active"]:
            html += "<tr><td>AP SSID</td><td>{}</td></tr>".format(wifi_status["ap_ssid"])
            html += "<tr><td>AP IP</td><td>{}</td></tr>".format(wifi_status["ap_ip"])
        html += "</table></div>"

        # Bridge Status (Modbus or Serial)
        active_bridge = self.bridge or self.serial_bridge
        if active_bridge:
            bridge_label = "Serial Bridge Status" if self.serial_bridge and not self.bridge \
                else "Bridge Status"
            html += '<div class="card"><h2>{}</h2><table>'.format(bridge_label)
            html += "<tr><td>Connected</td><td>{}</td></tr>".format(
                "Yes" if active_bridge.is_connected() else "No"
            )
            if self.serial_bridge and not self.bridge:
                html += "<tr><td>Commands</td><td>{}</td></tr>".format(
                    bridge_stats.get("commands", 0))
                html += "<tr><td>Responses</td><td>{}</td></tr>".format(
                    bridge_stats.get("responses", 0))
            else:
                html += "<tr><td>Requests</td><td>{}</td></tr>".format(
                    bridge_stats.get("requests", 0))
                html += "<tr><td>Responses</td><td>{}</td></tr>".format(
                    bridge_stats.get("responses", 0))
            html += "<tr><td>Errors</td><td>{}</td></tr>".format(bridge_stats.get("errors", 0))
            html += "</table></div>"

        # Recent Logs
        log_buffer = get_log_buffer()
        recent_logs = log_buffer.get_recent(count=10) if log_buffer else []

        html += '<div class="card"><h2>Recent Logs</h2>'
        if recent_logs:
            html += '<div style="background:#1e1e1e;color:#d4d4d4;padding:10px;border-radius:4px;font-family:monospace;font-size:11px;max-height:200px;overflow-y:auto;">'
            for log in recent_logs:
                html += '<div style="margin-bottom:3px;">'
                html += '<span style="color:#858585;">[{}]</span> {}'.format(log["time"], log["msg"])
                html += '</div>'
            html += '</div>'
            html += '<div style="margin-top:10px;">'
            html += '<button onclick="location.href=\'/logs\'">View All Logs</button>'
            html += '</div>'
        else:
            html += '<p style="color:#888;">No logs available</p>'
        html += '</div>'

        # Actions
        html += '<div class="card">'
        html += '<button onclick="location.reload()">Refresh</button>'
        html += '<button class="btn-danger" onclick="if(confirm(\'Reboot?\'))location.href=\'/reboot\'">Reboot</button>'
        html += "</div>"

        return html

    def _page_wifi(self):
        """WiFi configuration page."""
        wifi_cfg = load_wifi()
        current_ssid = wifi_cfg.get("ssid", "")

        html = '<div class="card"><h2>WiFi Configuration</h2>'
        html += '<form method="POST" action="/wifi">'
        html += '<label>SSID</label>'
        html += '<input name="ssid" value="{}" placeholder="WiFi network name">'.format(current_ssid)
        html += '<label>Password</label>'
        html += '<input type="password" name="password" placeholder="WiFi password">'
        html += '<button type="submit">Save & Connect</button>'
        html += '</form></div>'

        return html

    def _handle_wifi_save(self, body):
        """Handle WiFi save."""
        ssid = body.get("ssid", "").strip()
        password = body.get("password", "")

        if ssid:
            save_wifi(ssid, password)
            # Try to connect
            if self.wifi.connect_sta(timeout_s=10):
                return '<div class="status status-ok">Connected to ' + ssid + '</div>' + self._page_wifi()
            else:
                return '<div class="status status-err">Failed to connect to ' + ssid + '</div>' + self._page_wifi()
        else:
            return '<div class="status status-err">SSID required</div>' + self._page_wifi()

    def _page_modbus(self):
        """Modbus RTU configuration page."""
        config = get_config()
        rtu = config.get("rtu", {})

        html = '<div class="card"><h2>Modbus RTU Configuration</h2>'
        html += '<form method="POST" action="/modbus">'

        html += '<label>UART ID</label>'
        html += '<select name="uart_id">'
        for i in [1, 2]:
            sel = "selected" if rtu.get("uart_id") == i else ""
            html += '<option value="{}" {}>{}</option>'.format(i, sel, i)
        html += '</select>'

        html += '<label>TX Pin</label>'
        html += '<input type="number" name="tx_pin" value="{}">'.format(rtu.get("tx_pin", 17))

        html += '<label>RX Pin</label>'
        html += '<input type="number" name="rx_pin" value="{}">'.format(rtu.get("rx_pin", 16))

        html += '<label>DE Pin (Driver Enable, active-HIGH; 0=disabled)</label>'
        html += '<input type="number" name="de_pin" value="{}">'.format(rtu.get("de_pin", 4))

        html += '<label>RE Pin (Receiver Enable, active-LOW; 0=disabled)</label>'
        html += '<input type="number" name="re_pin" value="{}">'.format(rtu.get("re_pin", 5))

        html += '<label>Unit ID</label>'
        html += '<input type="number" name="unit_id" value="{}">'.format(rtu.get("unit_id", 1))

        html += '<label>Baud Rate</label>'
        html += '<select name="baudrate">'
        for baud in [9600, 19200, 38400, 57600, 115200]:
            sel = "selected" if rtu.get("baudrate") == baud else ""
            html += '<option value="{}" {}>{}</option>'.format(baud, sel, baud)
        html += '</select>'

        html += '<label>Parity</label>'
        html += '<select name="parity">'
        for p, name in [("N", "None"), ("E", "Even"), ("O", "Odd")]:
            sel = "selected" if rtu.get("parity") == p else ""
            html += '<option value="{}" {}>{}</option>'.format(p, sel, name)
        html += '</select>'

        html += '<label>Stop Bits</label>'
        html += '<select name="stop_bits">'
        for s in [1, 2]:
            sel = "selected" if rtu.get("stop_bits") == s else ""
            html += '<option value="{}" {}>{}</option>'.format(s, sel, s)
        html += '</select>'

        html += '<button type="submit">Save</button>'
        html += '</form></div>'

        return html

    def _handle_modbus_save(self, body):
        """Handle Modbus save."""
        config = load_config()
        if "rtu" not in config:
            config["rtu"] = {}

        config["rtu"]["uart_id"] = int(body.get("uart_id", 1))
        config["rtu"]["tx_pin"] = int(body.get("tx_pin", 17))
        config["rtu"]["rx_pin"] = int(body.get("rx_pin", 16))
        config["rtu"]["de_pin"] = int(body.get("de_pin", 4))
        config["rtu"]["re_pin"] = int(body.get("re_pin", 5))
        config["rtu"]["unit_id"] = int(body.get("unit_id", 1))
        config["rtu"]["baudrate"] = int(body.get("baudrate", 9600))
        config["rtu"]["parity"] = body.get("parity", "N")
        config["rtu"]["stop_bits"] = int(body.get("stop_bits", 1))

        save_config(config)

        return '<div class="status status-ok">Modbus settings saved. Reboot to apply.</div>' + self._page_modbus()

    def _page_server(self):
        """Server configuration page."""
        config = get_config()
        bridge_cfg = config.get("modbus_bridge", {})

        html = '<div class="card"><h2>Server Configuration</h2>'
        html += '<form method="POST" action="/server">'

        html += '<label>Server Host</label>'
        html += '<input name="server_host" value="{}">'.format(bridge_cfg.get("server_host", ""))

        html += '<label>Server Port</label>'
        html += '<input type="number" name="server_port" value="{}">'.format(bridge_cfg.get("server_port", 8502))

        html += '<label>Reconnect Delay (seconds)</label>'
        html += '<input type="number" name="reconnect_delay" value="{}">'.format(bridge_cfg.get("reconnect_delay", 5))

        html += '<label>Keepalive Interval (seconds)</label>'
        html += '<input type="number" name="keepalive_interval" value="{}">'.format(bridge_cfg.get("keepalive_interval", 30))

        html += '<button type="submit">Save</button>'
        html += '</form></div>'

        return html

    def _handle_server_save(self, body):
        """Handle server save."""
        config = load_config()
        if "modbus_bridge" not in config:
            config["modbus_bridge"] = {}

        config["modbus_bridge"]["server_host"] = body.get("server_host", "").strip()
        config["modbus_bridge"]["server_port"] = int(body.get("server_port", 8502))
        config["modbus_bridge"]["reconnect_delay"] = int(body.get("reconnect_delay", 5))
        config["modbus_bridge"]["keepalive_interval"] = int(body.get("keepalive_interval", 30))

        save_config(config)

        return '<div class="status status-ok">Server settings saved. Reboot to apply.</div>' + self._page_server()

    def _page_device(self):
        """Device identity and operating mode configuration page."""
        config = get_config()
        device_cfg = config.get("device", {})
        current_mode = config.get("mode", "modbus_bridge")

        html = '<div class="card"><h2>Operating Mode</h2>'
        html += '<form method="POST" action="/device">'
        html += '<input type="hidden" name="section" value="mode">'
        html += '<label>Mode</label>'
        html += '<select name="mode">'
        for val, label in [
            ("modbus_bridge", "Modbus Bridge (inverter/meter via RS485)"),
            ("serial_bridge", "Serial Bridge (Pylontech/Pytes battery via RS232)"),
        ]:
            sel = "selected" if current_mode == val else ""
            html += '<option value="{}" {}>{}</option>'.format(val, sel, label)
        html += '</select>'
        html += '<p style="color:#888;font-size:0.85em;margin-top:-5px;">'
        html += 'Reboot required after changing mode.</p>'
        html += '<button type="submit">Save Mode</button>'
        html += '</form></div>'

        html += '<div class="card"><h2>Device Identity</h2>'
        html += '<form method="POST" action="/device">'
        html += '<input type="hidden" name="section" value="identity">'

        html += '<label>Serial Number</label>'
        html += '<input name="serial" value="{}" placeholder="SH01XXXXXXXX">'.format(
            device_cfg.get("serial", ""))

        html += '<label>Friendly Name (optional)</label>'
        html += '<input name="name" value="{}" placeholder="e.g. Solar Logger 1">'.format(
            device_cfg.get("name", ""))

        html += '<label>Device Type</label>'
        html += '<select name="type">'
        for val in ["inverter", "battery", "meter", "gateway"]:
            sel = "selected" if device_cfg.get("type") == val else ""
            html += '<option value="{}" {}>{}</option>'.format(val, sel, val[0].upper() + val[1:])
        html += '</select>'

        html += '<label>Manufacturer</label>'
        html += '<input name="manufacturer" value="{}" placeholder="e.g. Pylontech">'.format(
            device_cfg.get("manufacturer", "SolarHub"))

        html += '<label>Model</label>'
        html += '<input name="model" value="{}" placeholder="e.g. US5000">'.format(
            device_cfg.get("model", ""))

        html += '<label>Protocol</label>'
        html += '<select name="protocol">'
        for val, label in [
            ("modbus_tcp", "Modbus TCP (inverter / meter)"),
            ("command", "Command (Pylontech / Pytes battery via RS232)"),
            ("jkbms_serial", "JK BMS Passive RS485 (broadcast mode, switches 0000)"),
            ("jkbms_modbus", "JK BMS Modbus RTU"),
        ]:
            sel = "selected" if device_cfg.get("protocol", "modbus_tcp") == val else ""
            html += '<option value="{}" {}>{}</option>'.format(val, sel, label)
        html += '</select>'

        html += '<label>Firmware Version</label>'
        html += '<input name="firmware_version" value="{}">'.format(
            device_cfg.get("firmware_version", "1.0.0"))

        html += '<button type="submit">Save Identity</button>'
        html += '</form></div>'

        return html

    def _handle_device_save(self, body):
        """Handle device/mode config save."""
        config = load_config()
        section = body.get("section", "identity")

        if section == "mode":
            mode = body.get("mode", "modbus_bridge")
            if mode in ("modbus_bridge", "serial_bridge", "tcp_server", "mqtt"):
                config["mode"] = mode
        else:
            if "device" not in config:
                config["device"] = {}
            serial = body.get("serial", "").strip()
            if serial:
                config["device"]["serial"] = serial
            config["device"]["name"] = body.get("name", "").strip()
            config["device"]["type"] = body.get("type", "inverter")
            config["device"]["manufacturer"] = body.get("manufacturer", "SolarHub").strip()
            config["device"]["model"] = body.get("model", "").strip()
            config["device"]["firmware_version"] = body.get("firmware_version", "1.0.0").strip()
            protocol = body.get("protocol", "modbus_tcp")
            if protocol in ("modbus_tcp", "command", "jkbms_serial", "jkbms_modbus"):
                config["device"]["protocol"] = protocol

        save_config(config)

        return '<div class="status status-ok">Saved. Reboot to apply.</div>' + self._page_device()

    def _page_serial(self):
        """Serial port + serial bridge server configuration page."""
        config = get_config()
        serial_cfg = config.get("serial", {})
        bridge_cfg = config.get("serial_bridge", {})

        html = '<div class="card"><h2>Serial Port — RS232 / RS485</h2>'
        html += '<p style="color:#888;font-size:0.85em;">UART settings for serial device communication. '
        html += 'Use MAX3232 for RS232 (Pylontech/Pytes), or MAX485 for RS485 (JK BMS broadcast).</p>'
        html += '<form method="POST" action="/serial">'
        html += '<input type="hidden" name="section" value="port">'

        html += '<label>UART ID</label>'
        html += '<select name="uart_id">'
        for i in [0, 1, 2]:
            sel = "selected" if serial_cfg.get("uart_id") == i else ""
            html += '<option value="{}" {}>{}</option>'.format(i, sel, i)
        html += '</select>'

        html += '<label>TX Pin</label>'
        html += '<input type="number" name="tx_pin" value="{}" min="0" max="48">'.format(
            serial_cfg.get("tx_pin", 17))

        html += '<label>RX Pin</label>'
        html += '<input type="number" name="rx_pin" value="{}" min="0" max="48">'.format(
            serial_cfg.get("rx_pin", 16))

        html += '<label>DE Pin (Driver Enable, active-HIGH; -1 = not used)</label>'
        html += '<input type="number" name="de_pin" value="{}" min="-1" max="48">'.format(
            serial_cfg.get("de_pin", -1))

        html += '<label>RE Pin (Receiver Enable, active-LOW; -1 = not used)</label>'
        html += '<input type="number" name="re_pin" value="{}" min="-1" max="48">'.format(
            serial_cfg.get("re_pin", -1))

        html += '<label>Baud Rate</label>'
        html += '<select name="baudrate">'
        for baud in [9600, 19200, 38400, 57600, 115200]:
            sel = "selected" if serial_cfg.get("baudrate") == baud else ""
            html += '<option value="{}" {}>{}</option>'.format(baud, sel, baud)
        html += '</select>'

        html += '<label>Parity</label>'
        html += '<select name="parity">'
        for p, pname in [("N", "None"), ("E", "Even"), ("O", "Odd")]:
            sel = "selected" if serial_cfg.get("parity", "N") == p else ""
            html += '<option value="{}" {}>{}</option>'.format(p, sel, pname)
        html += '</select>'

        html += '<label>Stop Bits</label>'
        html += '<select name="stop_bits">'
        for s in [1, 2]:
            sel = "selected" if serial_cfg.get("stop_bits", 1) == s else ""
            html += '<option value="{}" {}>{}</option>'.format(s, sel, s)
        html += '</select>'

        passive_checked = "checked" if serial_cfg.get("passive", False) else ""
        html += '<label>RS485 Passive Mode (JK BMS broadcast / listen-only)</label>'
        html += '<input type="checkbox" name="passive" value="1" {}>'.format(passive_checked)

        html += '<label>Max Frame Length (bytes, passive mode)</label>'
        html += '<input type="number" name="max_frame_len" value="{}" min="64" max="4096">'.format(
            serial_cfg.get("max_frame_len", 512))

        fh = serial_cfg.get("frame_header", [0x55, 0xAA, 0xEB, 0x90])
        fh_str = ",".join(str(b) for b in fh)
        html += '<label>Frame Header (decimal bytes, passive mode)</label>'
        html += '<input name="frame_header" value="{}" placeholder="85,170,235,144">'.format(fh_str)
        html += '<p style="color:#888;font-size:0.85em;margin-top:-5px;">'
        html += 'JK BMS default: 85,170,235,144 (0x55 0xAA 0xEB 0x90)</p>'

        html += '<label>Console Prompt</label>'
        html += '<select name="prompt">'
        for p in ["pylon>", "pytes>", ">"]:
            sel = "selected" if serial_cfg.get("prompt", "pylon>") == p else ""
            html += '<option value="{}" {}>{}</option>'.format(p, sel, p)
        html += '</select>'
        html += '<p style="color:#888;font-size:0.85em;margin-top:-5px;">'
        html += 'pylon&gt; for Pylontech, pytes&gt; for Pytes</p>'

        html += '<label>Response Timeout (ms)</label>'
        html += '<input type="number" name="response_timeout_ms" value="{}" min="1000" max="30000">'.format(
            serial_cfg.get("response_timeout_ms", 5000))

        html += '<label>Line Ending</label>'
        html += '<select name="line_ending">'
        for val, label in [("\\r\\n", "CR+LF (\\r\\n)"), ("\\n", "LF (\\n)"), ("\\r", "CR (\\r)")]:
            # compare the stored value against the Python escape sequence
            stored = serial_cfg.get("line_ending", "\r\n")
            stored_repr = stored.replace("\r\n", "\\r\\n").replace("\n", "\\n").replace("\r", "\\r")
            sel = "selected" if stored_repr == val else ""
            html += '<option value="{}" {}>{}</option>'.format(val, sel, label)
        html += '</select>'

        html += '<button type="submit">Save Port Settings</button>'
        html += '</form></div>'

        html += '<div class="card"><h2>Serial Bridge Server</h2>'
        html += '<p style="color:#888;font-size:0.85em;">System B server that this device connects to when in serial_bridge mode.</p>'
        html += '<form method="POST" action="/serial">'
        html += '<input type="hidden" name="section" value="bridge">'

        html += '<label>Server Host</label>'
        html += '<input name="server_host" value="{}" placeholder="192.168.x.x or hostname">'.format(
            bridge_cfg.get("server_host", ""))

        html += '<label>Server Port</label>'
        html += '<input type="number" name="server_port" value="{}" min="1" max="65535">'.format(
            bridge_cfg.get("server_port", 8502))

        html += '<label>Reconnect Delay (seconds)</label>'
        html += '<input type="number" name="reconnect_delay" value="{}" min="1" max="300">'.format(
            bridge_cfg.get("reconnect_delay", 5))

        html += '<label>Keepalive Interval (seconds)</label>'
        html += '<input type="number" name="keepalive_interval" value="{}" min="10" max="300">'.format(
            bridge_cfg.get("keepalive_interval", 30))

        html += '<button type="submit">Save Bridge Settings</button>'
        html += '</form></div>'

        return html

    def _handle_serial_save(self, body):
        """Handle serial config save."""
        config = load_config()
        section = body.get("section", "port")

        if section == "bridge":
            if "serial_bridge" not in config:
                config["serial_bridge"] = {}
            config["serial_bridge"]["server_host"] = body.get("server_host", "").strip()
            config["serial_bridge"]["server_port"] = int(body.get("server_port", 8502))
            config["serial_bridge"]["reconnect_delay"] = int(body.get("reconnect_delay", 5))
            config["serial_bridge"]["keepalive_interval"] = int(body.get("keepalive_interval", 30))
        else:
            if "serial" not in config:
                config["serial"] = {}
            config["serial"]["uart_id"] = int(body.get("uart_id", 1))
            config["serial"]["tx_pin"] = int(body.get("tx_pin", 17))
            config["serial"]["rx_pin"] = int(body.get("rx_pin", 16))
            config["serial"]["de_pin"] = int(body.get("de_pin", -1))
            config["serial"]["re_pin"] = int(body.get("re_pin", -1))
            config["serial"]["baudrate"] = int(body.get("baudrate", 115200))
            config["serial"]["parity"] = body.get("parity", "N")
            config["serial"]["stop_bits"] = int(body.get("stop_bits", 1))
            config["serial"]["passive"] = body.get("passive") == "1"
            config["serial"]["max_frame_len"] = int(body.get("max_frame_len", 512))
            try:
                fh = [int(x.strip()) for x in body.get("frame_header", "85,170,235,144").split(",") if x.strip()]
                config["serial"]["frame_header"] = fh if fh else [0x55, 0xAA, 0xEB, 0x90]
            except Exception:
                config["serial"]["frame_header"] = [0x55, 0xAA, 0xEB, 0x90]
            config["serial"]["prompt"] = body.get("prompt", "pylon>")
            config["serial"]["response_timeout_ms"] = int(
                body.get("response_timeout_ms", 5000))
            # Convert escaped line ending representation back to real characters
            le = body.get("line_ending", "\\r\\n")
            config["serial"]["line_ending"] = le.replace("\\r\\n", "\r\n").replace("\\n", "\n").replace("\\r", "\r")

        save_config(config)

        return '<div class="status status-ok">Serial settings saved. Reboot to apply.</div>' + self._page_serial()

    def _handle_reboot(self):
        """Handle reboot request."""
        import machine
        html = '<div class="status status-ok">Rebooting...</div>'
        html += '<script>setTimeout(function(){location.href="/";}, 5000);</script>'

        # Schedule reboot after response
        import _thread
        def reboot_later():
            import time
            time.sleep(1)
            machine.reset()
        _thread.start_new_thread(reboot_later, ())

        return html

    def _page_logs(self):
        """Console logs page with real-time updates."""
        # Check if log buffer is available
        if not _LOG_BUFFER_AVAILABLE:
            return '''
<div class="card">
    <h2>Console Logs</h2>
    <div class="status status-err">
        Log buffer not available. Please upload <code>log_buffer.py</code> to enable web logging.
    </div>
    <p>The log buffer module is required for viewing logs through the web interface.</p>
</div>
'''

        html = '''
<div class="card">
    <h2>Console Logs</h2>
    <div style="margin-bottom: 15px;">
        <button id="startBtn" onclick="startLogs()">▶ Start Live Logs</button>
        <button id="stopBtn" onclick="stopLogs()" disabled>⏸ Stop</button>
        <button onclick="clearLogs()">🗑 Clear</button>
        <button onclick="refreshLogs()">🔄 Refresh</button>
        <span id="status" style="margin-left: 15px; color: #888;"></span>
    </div>
    <div id="logContainer" style="
        background: #1e1e1e;
        color: #d4d4d4;
        padding: 15px;
        border-radius: 4px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        height: 500px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
    ">
        Loading logs...
    </div>
</div>

<script>
let isStreaming = false;
let streamInterval = null;
let lastLogId = 0;
let autoScroll = true;

function startLogs() {
    isStreaming = true;
    document.getElementById('startBtn').disabled = true;
    document.getElementById('stopBtn').disabled = false;
    document.getElementById('status').textContent = '🟢 Live';
    document.getElementById('status').style.color = '#4CAF50';

    // Initial load
    refreshLogs();

    // Poll every 1 second
    streamInterval = setInterval(fetchNewLogs, 1000);
}

function stopLogs() {
    isStreaming = false;
    document.getElementById('startBtn').disabled = false;
    document.getElementById('stopBtn').disabled = true;
    document.getElementById('status').textContent = '⏸ Paused';
    document.getElementById('status').style.color = '#888';

    if (streamInterval) {
        clearInterval(streamInterval);
        streamInterval = null;
    }
}

function refreshLogs() {
    fetch('/api/logs?count=50')
        .then(r => r.json())
        .then(data => {
            displayLogs(data.logs, true);
            lastLogId = data.last_id;
        })
        .catch(err => {
            document.getElementById('logContainer').textContent = 'Error loading logs: ' + err;
        });
}

function fetchNewLogs() {
    if (!isStreaming) return;

    fetch('/api/logs?since_id=' + lastLogId)
        .then(r => r.json())
        .then(data => {
            if (data.logs.length > 0) {
                displayLogs(data.logs, false);
                lastLogId = data.last_id;
            }
        })
        .catch(err => console.error('Failed to fetch logs:', err));
}

function displayLogs(logs, clearFirst) {
    const container = document.getElementById('logContainer');

    if (clearFirst) {
        container.innerHTML = '';
    }

    logs.forEach(log => {
        const line = document.createElement('div');
        line.style.marginBottom = '2px';

        // Format: [TIME] MESSAGE
        const timeSpan = document.createElement('span');
        timeSpan.style.color = '#858585';
        timeSpan.textContent = '[' + log.time + '] ';

        const msgSpan = document.createElement('span');
        msgSpan.textContent = log.msg;

        // Color code based on message content
        if (log.msg.includes('ERROR') || log.msg.includes('Error') || log.msg.includes('error')) {
            msgSpan.style.color = '#f48771';
        } else if (log.msg.includes('WARNING') || log.msg.includes('Warning') || log.msg.includes('Failed')) {
            msgSpan.style.color = '#dcdcaa';
        } else if (log.msg.includes('SUCCESS') || log.msg.includes('Connected') || log.msg.includes('successful')) {
            msgSpan.style.color = '#4ec9b0';
        } else if (log.msg.includes('[RTU]')) {
            msgSpan.style.color = '#ce9178';
        } else if (log.msg.includes('[Bridge]')) {
            msgSpan.style.color = '#9cdcfe';
        } else if (log.msg.includes('[WiFi]')) {
            msgSpan.style.color = '#c586c0';
        } else if (log.msg.includes('[Web]')) {
            msgSpan.style.color = '#b5cea8';
        }

        line.appendChild(timeSpan);
        line.appendChild(msgSpan);
        container.appendChild(line);
    });

    // Auto-scroll to bottom if enabled
    if (autoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}

function clearLogs() {
    if (confirm('Clear all logs?')) {
        fetch('/api/logs/clear')
            .then(() => {
                document.getElementById('logContainer').innerHTML = '<span style="color: #888;">Logs cleared</span>';
                lastLogId = 0;
            })
            .catch(err => alert('Failed to clear logs'));
    }
}

// Detect manual scroll to disable auto-scroll
document.getElementById('logContainer').addEventListener('scroll', function() {
    const el = this;
    autoScroll = (el.scrollHeight - el.scrollTop - el.clientHeight) < 50;
});

// Initial load
refreshLogs();
</script>
'''
        return html

    def _get_logs_json(self, since_id=None):
        """Get logs as JSON."""
        log_buffer = get_log_buffer()

        if not log_buffer:
            return {"logs": [], "count": 0, "last_id": 0}

        if since_id is not None:
            logs = log_buffer.get_recent(count=100, since_id=since_id)
        else:
            logs = log_buffer.get_recent(count=50)

        return {
            "logs": logs,
            "count": len(logs),
            "last_id": log_buffer.get_last_id()
        }

    def _get_status_json(self):
        """Get status as JSON."""
        wifi_status = self.wifi.get_status()
        active_bridge = self.bridge or self.serial_bridge
        bridge_stats = active_bridge.get_stats() if active_bridge else {}

        return {
            "device_id": get_device_id(),
            "wifi": wifi_status,
            "bridge": {
                "connected": active_bridge.is_connected() if active_bridge else False,
                "type": "serial" if self.serial_bridge and not self.bridge else "modbus",
                "stats": bridge_stats,
            }
        }

    def _page_files(self):
        """File manager page."""
        files = FileManager.list_files()
        disk = FileManager.get_disk_usage()

        html = '<div class="card"><h2>File Manager</h2>'

        # Disk usage
        if disk:
            html += '<div style="margin-bottom:20px;">'
            html += '<strong>Disk Usage:</strong> {} / {} ({}\% used)'.format(
                FileManager.format_size(disk['used']),
                FileManager.format_size(disk['total']),
                disk['percent']
            )
            html += '</div>'

        # Upload form
        html += '''
<div style="margin-bottom:20px;padding:15px;background:#f9f9f9;border-radius:4px;">
    <h3 style="margin-top:0;">Upload File</h3>
    <input type="text" id="filename" placeholder="Filename (e.g., main.py)" style="margin-bottom:10px;">
    <textarea id="filecontent" rows="10" placeholder="Paste file content here..." style="width:100%;margin-bottom:10px;font-family:monospace;"></textarea>
    <button onclick="uploadFile()">📤 Upload File</button>
    <span id="uploadStatus" style="margin-left:15px;"></span>
</div>
'''

        # File list
        html += '<h3>Files</h3>'
        if files:
            html += '<table><tr><th>Name</th><th>Size</th><th>Action</th></tr>'
            for f in files:
                if f['type'] == 'file':
                    html += '<tr><td>{}</td><td>{}</td><td>'.format(
                        f['name'],
                        FileManager.format_size(f['size'])
                    )
                    if f['name'] not in FileManager.PROTECTED_FILES:
                        html += '<button class="btn-danger" onclick="deleteFile(\'{}\')">Delete</button>'.format(f['name'])
                    else:
                        html += '<span style="color:#999;">Protected</span>'
                    html += '</td></tr>'
            html += '</table>'
        else:
            html += '<p>No files found</p>'

        html += '''
</div>
<script>
async function uploadFile() {
    const filename = document.getElementById('filename').value;
    const content = document.getElementById('filecontent').value;
    const status = document.getElementById('uploadStatus');

    if (!filename) {
        status.innerHTML = '<span style="color:red;">Please enter a filename</span>';
        return;
    }

    if (!content) {
        status.innerHTML = '<span style="color:red;">Please enter file content</span>';
        return;
    }

    status.innerHTML = 'Uploading...';

    try {
        const response = await fetch('/api/files/upload?filename=' + encodeURIComponent(filename), {
            method: 'POST',
            headers: {'Content-Type': 'text/plain'},
            body: content
        });

        const result = await response.json();

        if (result.success) {
            status.innerHTML = '<span style="color:green;">✓ Upload successful!</span>';
            setTimeout(() => location.reload(), 1500);
        } else {
            status.innerHTML = '<span style="color:red;">Error: ' + (result.error || 'Unknown error') + '</span>';
        }
    } catch (e) {
        status.innerHTML = '<span style="color:red;">Upload failed: ' + e + '</span>';
    }
}

async function deleteFile(filename) {
    if (!confirm('Delete ' + filename + '?')) return;

    try {
        const response = await fetch('/api/files/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: filename})
        });

        const result = await response.json();

        if (result.success) {
            location.reload();
        } else {
            alert('Delete failed: ' + (result.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Delete failed: ' + e);
    }
}
</script>
'''
        return html

    def _get_files_json(self):
        """Get file list as JSON."""
        files = FileManager.list_files()
        disk = FileManager.get_disk_usage()
        return {"files": files, "disk": disk}

    def _stream_file_upload(self, client, body_so_far, content_length, path_full):
        """
        Stream file upload directly to flash without buffering the full body in RAM.

        Expects: POST /api/files/upload?filename=<name>
        Body: raw file bytes (text/plain or application/octet-stream)
        """
        import gc

        # Extract filename from query string
        filename = ""
        if "?" in path_full:
            qs = path_full.split("?", 1)[1]
            for param in qs.split("&"):
                if param.startswith("filename="):
                    filename = param[9:].replace("%2F", "/").replace("%20", " ")
                    break

        if not filename:
            # Drain remaining body then return error
            received = len(body_so_far)
            while received < content_length:
                chunk = client.recv(512)
                if not chunk:
                    break
                received += len(chunk)
            return self._json_response({"success": False, "error": "Missing filename"})

        try:
            received = len(body_so_far)
            with open(filename, "wb") as f:
                if body_so_far:
                    f.write(body_so_far)
                while received < content_length:
                    chunk = client.recv(512)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    gc.collect()
            return self._json_response({"success": True, "filename": filename, "size": received})
        except Exception as e:
            return self._json_response({"success": False, "error": str(e)})

    def _handle_file_upload(self, body_raw, content_type):
        """Handle file upload (legacy JSON path — kept for compatibility)."""
        try:
            # Parse JSON body
            data = json.loads(body_raw) if body_raw else {}
            filename = data.get('filename', '')
            content = data.get('content', '')

            if not filename or not content:
                return self._json_response({"success": False, "error": "Missing filename or content"})

            # Save file
            if FileManager.save_file(filename, content):
                return self._json_response({"success": True})
            else:
                return self._json_response({"success": False, "error": "Failed to save file"})

        except Exception as e:
            return self._json_response({"success": False, "error": str(e)})

    def _handle_file_delete(self, body):
        """Handle file deletion."""
        try:
            filename = body.get('filename', '')

            if not filename:
                return self._json_response({"success": False, "error": "Missing filename"})

            if FileManager.delete_file(filename):
                return self._json_response({"success": True})
            else:
                return self._json_response({"success": False, "error": "Failed to delete file"})

        except Exception as e:
            return self._json_response({"success": False, "error": str(e)})

