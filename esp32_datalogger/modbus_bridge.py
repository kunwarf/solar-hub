"""
Modbus TCP Bridge for ESP32 Data Logger.

Connects TO the server and forwards Modbus TCP requests to RTU devices.
The server sends READ/WRITE requests, this bridge forwards them to the
inverter via Modbus RTU and returns the responses.
"""
import socket
import struct
import time

from config import get_config


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

                # Log request
                func_code = pdu[0]
                print("[Bridge] RX: TID={} UID={} FC={:02X} len={}".format(
                    transaction_id, unit_id, func_code, len(pdu)
                ))

                # Forward to RTU and get response
                response_pdu = self.rtu.forward_pdu(pdu, unit_id)

                if response_pdu:
                    # Build response
                    resp_length = len(response_pdu) + 1  # +1 for unit_id
                    resp_header = struct.pack(
                        ">HHHB",
                        transaction_id,
                        0,  # Protocol ID
                        resp_length,
                        unit_id
                    )

                    # Send response
                    self.socket.sendall(resp_header + response_pdu)
                    self.stats["responses"] += 1

                    print("[Bridge] TX: TID={} FC={:02X} len={}".format(
                        transaction_id, response_pdu[0], len(response_pdu)
                    ))
                else:
                    # Send exception response (gateway target device failed)
                    exc_pdu = bytes([func_code | 0x80, 0x0B])  # Gateway target failed
                    resp_header = struct.pack(
                        ">HHHB",
                        transaction_id,
                        0,
                        3,  # 1 (unit) + 2 (exception PDU)
                        unit_id
                    )
                    self.socket.sendall(resp_header + exc_pdu)
                    self.stats["errors"] += 1
                    print("[Bridge] TX: Exception 0x0B (gateway target failed)")

            except OSError as e:
                # In MicroPython, timeout raises OSError with ETIMEDOUT (110)
                if e.args[0] == 110:  # ETIMEDOUT
                    print("[Bridge] Keepalive timeout, checking connection...")
                    continue
                else:
                    print("[Bridge] Socket error:", e)
                    self.stats["errors"] += 1
                    self._cleanup_socket()
                    time.sleep(1)

            except Exception as e:
                print("[Bridge] Error:", e)
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

