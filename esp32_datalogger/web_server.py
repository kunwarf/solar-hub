"""
Web server for ESP32 Data Logger configuration.

Provides a simple HTTP interface for configuring WiFi, Modbus settings,
and viewing device status.
"""
import json
import socket

from config import (
    load_config, save_config, load_wifi, save_wifi,
    get_config, get_device_id, DEFAULT_CONFIG
)


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
<a href="/wifi">WiFi</a>
<a href="/modbus">Modbus</a>
<a href="/server">Server</a>
</div>
"""

HTML_FOOTER = """
</body>
</html>
"""


class WebServer:
    """Simple HTTP server for configuration."""

    def __init__(self, wifi_manager, bridge=None, rtu=None, port=80):
        """
        Initialize web server.

        Args:
            wifi_manager: WiFiManager instance.
            bridge: ModbusBridge instance (optional).
            rtu: ModbusRTU instance (optional).
            port: HTTP port (default 80).
        """
        self.wifi = wifi_manager
        self.bridge = bridge
        self.rtu = rtu
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
                request = client.recv(1024).decode("utf-8")
                if request:
                    response = self._handle_request(request)
                    client.sendall(response.encode("utf-8"))
            except Exception as e:
                print("[Web] Request error:", e)
            finally:
                client.close()

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

            # Parse POST body
            body = {}
            if method == "POST":
                # Find body after empty line
                body_start = request.find("\r\n\r\n")
                if body_start > 0:
                    body_str = request[body_start + 4:]
                    for pair in body_str.split("&"):
                        if "=" in pair:
                            k, v = pair.split("=", 1)
                            body[k] = self._url_decode(v)

            # Route request
            if path == "/" or path == "/status":
                content = self._page_status()
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

            return self._response(200, HTML_HEADER + content + HTML_FOOTER)

        except Exception as e:
            print("[Web] Error:", e)
            return self._response(500, "Error: " + str(e))

    def _response(self, code, body, content_type="text/html"):
        """Build HTTP response."""
        status = {200: "OK", 404: "Not Found", 500: "Error"}.get(code, "OK")
        return "HTTP/1.1 {} {}\r\nContent-Type: {}\r\nConnection: close\r\n\r\n{}".format(
            code, status, content_type, body
        )

    def _json_response(self, data):
        """Build JSON response."""
        return self._response(200, json.dumps(data), "application/json")

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

        # Bridge stats
        bridge_stats = self.bridge.get_stats() if self.bridge else {}

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

        # Bridge Status
        if self.bridge:
            html += '<div class="card"><h2>Bridge Status</h2><table>'
            html += "<tr><td>Connected</td><td>{}</td></tr>".format(
                "Yes" if self.bridge.is_connected() else "No"
            )
            html += "<tr><td>Requests</td><td>{}</td></tr>".format(bridge_stats.get("requests", 0))
            html += "<tr><td>Responses</td><td>{}</td></tr>".format(bridge_stats.get("responses", 0))
            html += "<tr><td>Errors</td><td>{}</td></tr>".format(bridge_stats.get("errors", 0))
            html += "</table></div>"

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

        html += '<label>DE Pin (0=disabled)</label>'
        html += '<input type="number" name="de_pin" value="{}">'.format(rtu.get("de_pin", 4))

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

    def _get_status_json(self):
        """Get status as JSON."""
        wifi_status = self.wifi.get_status()
        bridge_stats = self.bridge.get_stats() if self.bridge else {}

        return {
            "device_id": get_device_id(),
            "wifi": wifi_status,
            "bridge": {
                "connected": self.bridge.is_connected() if self.bridge else False,
                "stats": bridge_stats,
            }
        }

