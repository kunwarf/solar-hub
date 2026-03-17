"""
Modbus TCP Bridge for ESP32 Data Logger.

Connects TO the server and forwards Modbus TCP requests to RTU devices.
The server sends READ/WRITE requests, this bridge forwards them to the
inverter via Modbus RTU and returns the responses.

On startup, the device self-registers with System B using its serial number.
"""
import socket
import struct
import time
import json

from config import get_config


def http_post_json(url, data, timeout=10):
    """
    Simple HTTP POST with JSON body (MicroPython compatible).

    Args:
        url: Full URL (e.g., http://host:port/path)
        data: Dict to send as JSON body
        timeout: Request timeout in seconds

    Returns:
        Tuple of (status_code, response_dict or None)
    """
    try:
        # Parse URL
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            raise ValueError("HTTPS not supported in simple client")

        # Split host:port and path
        if "/" in url:
            host_port, path = url.split("/", 1)
            path = "/" + path
        else:
            host_port = url
            path = "/"

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 80

        # Create JSON body
        body = json.dumps(data)

        # Build HTTP request
        request = (
            "POST {} HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
            "{}"
        ).format(path, host, port, len(body), body)

        # Connect and send
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(request.encode())

        # Receive response
        response = b""
        while True:
            try:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response += chunk
            except:
                break

        sock.close()

        # Parse response (MicroPython doesn't support errors parameter)
        try:
            response = response.decode("utf-8")
        except:
            # If decode fails, try latin-1 which accepts all byte values
            response = response.decode("latin-1")

        # Split headers and body
        if "\r\n\r\n" in response:
            headers, body = response.split("\r\n\r\n", 1)
        else:
            headers = response
            body = ""

        # Get status code
        first_line = headers.split("\r\n")[0]
        parts = first_line.split(" ")
        if len(parts) >= 2:
            status_code = int(parts[1])
        else:
            status_code = 0

        # Parse JSON body
        try:
            result = json.loads(body)
        except:
            result = None

        return status_code, result

    except Exception as e:
        print("[HTTP] Error:", e)
        return 0, None


class ModbusBridge:
    """
    Modbus TCP to RTU Bridge.

    Connects TO server (outbound connection) and acts as a Modbus slave,
    forwarding requests to RTU devices.
    """

    # MBAP Header: Transaction ID (2) + Protocol ID (2) + Length (2) + Unit ID (1)
    MBAP_HEADER_SIZE = 7

    def __init__(self, rtu_master, config=None):
        """
        Initialize bridge.

        Args:
            rtu_master: ModbusRTU instance for communication with inverter.
            config: Configuration dict (uses get_config() if None).
        """
        self.rtu = rtu_master
        self.config = config or get_config()
        self.socket = None
        self._connected = False
        self._running = False
        self._registered = False
        self._device_id = None

        # Stats
        self.stats = {
            "requests": 0,
            "responses": 0,
            "errors": 0,
            "reconnects": 0,
        }

    def connect(self):
        """
        Connect to the server.

        Returns:
            True if connected, False otherwise.
        """
        cfg = self.config["modbus_bridge"]
        host = cfg["server_host"]
        port = cfg["server_port"]

        try:
            print("[Bridge] Connecting to {}:{}...".format(host, port))

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((host, port))

            # Set socket options for keepalive
            self.socket.settimeout(None)  # Blocking mode

            self._connected = True
            print("[Bridge] Connected to server")
            return True

        except Exception as e:
            print("[Bridge] Connection failed:", e)
            self._cleanup_socket()
            return False

    def disconnect(self):
        """Disconnect from server."""
        self._running = False
        self._cleanup_socket()
        print("[Bridge] Disconnected")

    def _cleanup_socket(self):
        """Clean up socket resources."""
        self._connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

    def is_connected(self):
        """Check if connected to server."""
        return self._connected

    def is_registered(self):
        """Check if device is registered with System B."""
        return self._registered

    def get_device_id(self):
        """Get the device ID assigned by System B."""
        return self._device_id

    def register_device(self):
        """
        Self-register the device with System B.

        Returns:
            True if registration successful, False otherwise.
        """
        api_config = self.config.get("api", {})
        device_config = self.config.get("device", {})

        base_url = api_config.get("base_url", "http://localhost:8001")
        endpoint = api_config.get("register_endpoint", "/api/v1/devices/self-register")

        # Build registration payload
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
            print("[Bridge] Registration successful!")
            print("[Bridge]   Device ID: {}".format(self._device_id))
            print("[Bridge]   Claimed: {}".format(is_claimed))
            print("[Bridge]   Polling: {}ms".format(polling_ms))
            return True
        else:
            error = response.get("detail") if response else "Unknown error"
            print("[Bridge] Registration failed: {} - {}".format(status_code, error))
            return False

    def run(self):
        """
        Main bridge loop.

        Receives Modbus TCP requests from server, forwards to RTU,
        and returns responses.
        """
        self._running = True
        cfg = self.config["modbus_bridge"]
        reconnect_delay = cfg.get("reconnect_delay", 5)
        keepalive_interval = cfg.get("keepalive_interval", 30)

        while self._running:
            # Connect if not connected
            if not self._connected:
                if not self.connect():
                    print("[Bridge] Retrying in {}s...".format(reconnect_delay))
                    time.sleep(reconnect_delay)
                    self.stats["reconnects"] += 1
                    continue

                # Register device with System B after successful connection
                if not self._registered:
                    if self.register_device():
                        print("[Bridge] Device registered with System B")
                    else:
                        print("[Bridge] Registration failed, continuing anyway...")

            try:
                # Set read timeout for keepalive
                self.socket.settimeout(keepalive_interval)

                # Read MBAP header
                header = self._recv_exact(self.MBAP_HEADER_SIZE)
                if not header:
                    print("[Bridge] Connection closed by server")
                    self._cleanup_socket()
                    continue

                # Parse MBAP header
                transaction_id, protocol_id, length, unit_id = struct.unpack(
                    ">HHHB", header
                )

                # Validate protocol ID (should be 0 for Modbus)
                if protocol_id != 0:
                    print("[Bridge] Invalid protocol ID:", protocol_id)
                    continue

                # Read PDU (length - 1 because unit_id is included in length)
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

                # Forward to RTU and get response
                response_pdu = self.rtu.forward_pdu(pdu, unit_id)

                if response_pdu:
                    resp_length = len(response_pdu) + 1  # +1 for unit_id
                    resp_header = struct.pack(
                        ">HHHB",
                        transaction_id,
                        0,  # Protocol ID
                        resp_length,
                        unit_id
                    )
                    self.socket.sendall(resp_header + response_pdu)
                    self.stats["responses"] += 1
                else:
                    # Send exception response (gateway target device failed)
                    exc_pdu = bytes([func_code | 0x80, 0x0B])
                    resp_header = struct.pack(
                        ">HHHB",
                        transaction_id,
                        0,
                        3,  # 1 (unit) + 2 (exception PDU)
                        unit_id
                    )
                    self.socket.sendall(resp_header + exc_pdu)
                    self.stats["errors"] += 1

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

    def _recv_exact(self, length):
        """
        Receive exact number of bytes.

        Args:
            length: Number of bytes to receive.

        Returns:
            Bytes received or None on error.
        """
        data = b""
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            except:
                return None
        return data

    def get_stats(self):
        """Get bridge statistics."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "requests": 0,
            "responses": 0,
            "errors": 0,
            "reconnects": 0,
        }

