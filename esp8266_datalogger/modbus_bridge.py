"""
Modbus TCP Bridge for ESP8266 Data Logger.

Connects TO the server and forwards Modbus TCP requests to RTU devices.
The server sends READ/WRITE requests, this bridge forwards them to the
inverter via Modbus RTU and returns the responses.

On startup, the device self-registers with System B using its serial number.

ESP8266 Cooperative Scheduling Note
------------------------------------
The ESP8266 does not support threading (_thread module is absent).
To keep the web server responsive, run() accepts an optional idle_cb
callable that is invoked every time the bridge socket recv times out
(controlled by keepalive_interval, default 1 s).

Usage in main.py:
    bridge.run(idle_cb=web.handle_requests)
"""
import socket
import struct
import time

from config import get_config
from log_buffer import log_print as print
from http_utils import http_post_json


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
        # Unit ID override: if rtu.unit_id is set (>0), use it for all RTU
        # requests regardless of what unit_id System B sends in the MBAP header.
        self._rtu_unit_id = self.config.get("rtu", {}).get("unit_id", 0) or 0
        if self._rtu_unit_id > 0:
            print("[Bridge] RTU unit_id override: {}".format(self._rtu_unit_id))
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
        self._registered = False  # Re-register on next connect to refresh last_connected_at
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

    def run(self, idle_cb=None):
        """
        Main bridge loop.

        Receives Modbus TCP requests from server, forwards to RTU,
        and returns responses.

        Args:
            idle_cb: Optional callable invoked on each recv timeout.
                     Use this on ESP8266 to service the web server
                     cooperatively, e.g. idle_cb=web.handle_requests.
                     Keepalive_interval (default 1 s) controls how
                     frequently idle_cb is called.
        """
        self._running = True
        cfg = self.config["modbus_bridge"]
        reconnect_delay = cfg.get("reconnect_delay", 5)
        keepalive_interval = cfg.get("keepalive_interval", 1)

        while self._running:
            # Connect if not connected
            if not self._connected:
                if not self.connect():
                    print("[Bridge] Retrying in {}s...".format(reconnect_delay))
                    # Service web server while waiting to reconnect
                    for _ in range(reconnect_delay):
                        if idle_cb:
                            idle_cb()
                        time.sleep(1)
                    self.stats["reconnects"] += 1
                    continue

                # Register device with System B after successful connection
                if not self._registered:
                    if self.register_device():
                        print("[Bridge] Device registered with System B")
                    else:
                        print("[Bridge] Registration failed, continuing anyway...")

            try:
                # Short timeout so idle_cb is called regularly (ESP8266 no-thread)
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

                # Brief logging: always log writes; log reads only on failure.
                is_write = func_code in (0x06, 0x10)
                addr = ((pdu[1] << 8) | pdu[2]) if len(pdu) >= 3 else 0
                # Resolve actual RTU unit_id — config overrides MBAP if set
                rtu_unit = self._rtu_unit_id if self._rtu_unit_id > 0 else unit_id

                if is_write and func_code == 0x06:
                    val = ((pdu[3] << 8) | pdu[4]) if len(pdu) >= 5 else 0
                    print("[Bridge] FC06 write addr={} val={} unit={}".format(
                        addr, val, rtu_unit))
                elif is_write and func_code == 0x10:
                    cnt = ((pdu[3] << 8) | pdu[4]) if len(pdu) >= 5 else 0
                    print("[Bridge] FC10 write addr={} cnt={} unit={}".format(
                        addr, cnt, rtu_unit))

                response_pdu = self.rtu.forward_pdu(pdu, rtu_unit)

                if response_pdu:
                    if is_write:
                        print("[Bridge] → OK")
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
                    # RTU did not respond
                    print("[Bridge] FC{:02X} addr={} unit={} → RTU no response".format(
                        func_code, addr, rtu_unit))
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

    def _recv_exact(self, length):
        """
        Receive exact number of bytes.

        Args:
            length: Number of bytes to receive.

        Returns:
            Bytes received or None on error.
        """
        data = bytearray()
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except:
                return None
        return bytes(data)

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
