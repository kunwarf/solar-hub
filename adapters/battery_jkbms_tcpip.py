"""
JK BMS RS485 Adapter (TCP/IP or Modbus RTU)

Based on jkbms-rs485-addon (https://github.com/jean-luc1203/jkbms-rs485-addon).
Connects to JK-BMS via either:
- RS485-to-TCP/IP gateway (Ethernet or WiFi)
- Direct RS485 serial connection (Modbus RTU)

This adapter:
- Supports both TCP/IP gateway and direct serial connections
- Passively listens to RS485-2 bus communication
- Parses Modbus RTU frames and 55AAEB90 data frames
- Aggregates battery status and configuration data

Configuration (TCP/IP):
    type: jkbms_tcpip
    connection_type: tcpip  # or "rtu" for serial
    host: 192.168.1.100  # RS485 gateway IP address
    port: 8899           # RS485 gateway TCP port
    batteries: 3
    cells_per_battery: 16
    bms_broadcasting: true
    poll_timeout: 2.0

Configuration (Modbus RTU):
    type: jkbms_tcpip
    connection_type: rtu  # or "tcpip" for gateway
    serial_port: /dev/ttyUSB0  # Serial port (e.g., COM3 on Windows)
    baudrate: 115200
    batteries: 3
    cells_per_battery: 16
    bms_broadcasting: true
    poll_timeout: 2.0
"""

import asyncio
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import serial  # type: ignore
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

from solarhub.adapters.base import BatteryAdapter
from solarhub.config import BatteryBankConfig
from solarhub.schedulers.models import BatteryBankTelemetry, BatteryUnit

log = logging.getLogger(__name__)

# ---- JK RS485-2 Modbus protocol constants -----------------------------------

MODBUS_PATTERN = bytes([0x10, 0x16])
DATA_FRAME_START = bytes([0x55, 0xAA, 0xEB, 0x90])

FRAME_TYPE_CONFIG = 0x01
FRAME_TYPE_STATUS = 0x02
MODBUS_REQUEST = 0x20

RECV_BUFFER_SIZE = 4096
READ_TIMEOUT = 1.0
MAX_MODBUS_FRAME_LENGTH = 512

CELL_NOMINAL_VOLTAGE = 3.2  # V

# (field_name, offset, length, scale, is_numeric)
CONFIG_FIELDS = [
    ('smart_sleep_voltage', 6, 4, 1000.0, True),
    ('cell_undervoltage_protection', 10, 4, 1000.0, True),
    ('cell_undervoltage_recovery', 14, 4, 1000.0, True),
    ('cell_overvoltage_protection', 18, 4, 1000.0, True),
    ('cell_overvoltage_recovery', 22, 4, 1000.0, True),
    ('balance_trigger_voltage', 26, 4, 1000.0, True),
    ('cell_soc100_voltage', 30, 4, 1000.0, True),
    ('cell_soc0_voltage', 34, 4, 1000.0, True),
    ('cell_request_charge_voltage', 38, 4, 1000.0, True),
    ('cell_request_float_voltage', 42, 4, 1000.0, True),
    ('power_off_voltage', 46, 4, 1000.0, True),
    ('max_charge_current', 50, 4, 1000.0, True),
    ('charge_overcurrent_delay', 54, 4, 1.0, True),
    ('charge_overcurrent_recovery', 58, 4, 1.0, True),
    ('max_discharge_current', 62, 4, 1000.0, True),
    ('discharge_overcurrent_delay', 66, 4, 1.0, True),
    ('discharge_overcurrent_recovery', 70, 4, 1.0, True),
    ('short_circuit_recovery', 74, 4, 1.0, True),
    ('max_balance_current', 78, 4, 1000.0, True),
    ('charge_overtemp_protection', 82, 4, 10.0, True),
    ('charge_overtemp_recovery', 86, 4, 10.0, True),
    ('discharge_overtemp_protection', 90, 4, 10.0, True),
    ('discharge_overtemp_recovery', 94, 4, 10.0, True),
    ('charge_undertemp_protection', 98, 4, 10.0, True),
    ('charge_undertemp_recovery', 102, 4, 10.0, True),
    ('power_tube_overtemp_protection', 106, 4, 10.0, True),
    ('power_tube_overtemp_recovery', 110, 4, 10.0, True),
    ('cell_count', 114, 4, 1.0, True),
    ('charging_switch', 118, 1, None, False),
    ('discharging_switch', 122, 1, None, False),
    ('balance_switch', 126, 1, None, False),
    ('total_battery_capacity', 130, 4, 1000.0, True),
    ('short_circuit_delay', 134, 4, 1.0, True),
    ('balance_starting_voltage', 138, 4, 1000.0, True),
    ('wire_resistance_1', 158, 4, 1000.0, True),
    ('device_address', 270, 4, 1.0, True),
]


# ---- low-level helpers ------------------------------------------------------

def read_int_le(data: bytes, offset: int, length: int,
                signed: bool = False, scale: float = 1.0) -> Optional[float]:
    if offset + length > len(data):
        return None
    value = int.from_bytes(data[offset:offset + length], "little", signed=signed)
    return value / scale if scale != 1.0 else float(value)


def read_bool(data: bytes, offset: int) -> Optional[bool]:
    if offset >= len(data):
        return None
    return bool(data[offset])


def read_bit_flag(data: bytes, offset: int, bit: int) -> Optional[bool]:
    if offset >= len(data):
        return None
    return bool((data[offset] >> bit) & 1)


def modbus_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def find_pattern(data: bytes, pattern: bytes, start_pos: int = 0) -> int:
    try:
        return data.index(pattern, start_pos)
    except ValueError:
        return -1


# ---- Modbus frame parsing (RS485-2) ----------------------------------------

def parse_modbus_frame(data: bytes) -> Optional[Tuple[int, int, bytes, bool, int]]:
    """
    Try to parse a Modbus frame starting at byte 0 of `data`.

    Returns:
        (battery_id, frame_type, payload, crc_valid, frame_length)
    or None if no valid frame starting at data[0].
    """
    if len(data) < 6:
        return None

    battery_id = data[0]
    if data[1:3] != MODBUS_PATTERN:
        return None

    frame_type = data[3]
    max_check = min(len(data), MAX_MODBUS_FRAME_LENGTH)

    for end_pos in range(6, max_check + 1):
        frame_without_crc = data[:end_pos - 2]
        received_crc = (data[end_pos - 1] << 8) | data[end_pos - 2]
        calculated_crc = modbus_crc16(frame_without_crc)

        if received_crc == calculated_crc:
            payload = data[4:end_pos - 2]
            return battery_id, frame_type, payload, True, end_pos

    return None


# ---- JK "data frames" (55 AA EB 90) parsing --------------------------------

def parse_frame_type_01(frame_data: bytes, cells_per_battery: int = 16) -> dict:
    """Configuration frame."""
    result = {"type": "configuration"}

    if len(frame_data) < 286:
        return result

    for field_name, offset, length, scale, is_numeric in CONFIG_FIELDS:
        if is_numeric:
            value = read_int_le(frame_data, offset, length, signed=True, scale=scale)
            if value is not None:
                result[field_name] = int(value) if scale == 1.0 else value
        else:
            value = read_bool(frame_data, offset)
            if value is not None:
                result[field_name] = value

    if len(frame_data) >= 284:
        result["display_always_on"] = read_bit_flag(frame_data, 282, 4)
        result["smart_sleep_switch"] = read_bit_flag(frame_data, 282, 7)
        result["disable_pcl_module"] = read_bit_flag(frame_data, 282, 8)
        result["timed_stored_data"] = read_bit_flag(frame_data, 283, 1)

    # derived: what we *expect* from JK, given your pack
    result["expected_cells"] = cells_per_battery
    result["nominal_cell_voltage"] = CELL_NOMINAL_VOLTAGE
    result["nominal_pack_voltage"] = cells_per_battery * CELL_NOMINAL_VOLTAGE
    return result


def parse_frame_type_02(frame_data: bytes, cells_per_battery: int = 16) -> dict:
    """Status frame: voltages, temps, SOC, etc."""
    result = {"type": "status", "cell_voltages": []}

    # Parse cells
    for cell in range(cells_per_battery):
        offset = 6 + cell * 2
        voltage = read_int_le(frame_data, offset, 2, signed=False, scale=1000.0)
        if voltage is not None:
            result["cell_voltages"].append(round(voltage, 3))
        else:
            result["cell_voltages"].append(None)

    if len(frame_data) < 236:
        # still return partial result
        return result

    cell_resistances: List[float] = []
    for cell in range(cells_per_battery):
        offset = 80 + cell * 2
        resistance = read_int_le(frame_data, offset, 2, signed=True, scale=1000.0)
        if resistance is not None:
            cell_resistances.append(resistance)
    result["cell_resistances"] = cell_resistances

    result["mos_temp"] = read_int_le(frame_data, 144, 2, signed=True, scale=10.0)
    result["power"] = read_int_le(frame_data, 154, 4, signed=False, scale=1000.0)
    result["current"] = read_int_le(frame_data, 158, 4, signed=True, scale=1000.0)
    result["temp1"] = read_int_le(frame_data, 162, 2, signed=True, scale=10.0)
    result["temp2"] = read_int_le(frame_data, 164, 2, signed=True, scale=10.0)
    result["temp3"] = read_int_le(frame_data, 254, 2, signed=True, scale=10.0)
    result["temp4"] = read_int_le(frame_data, 258, 2, signed=True, scale=10.0)
    result["balance_current"] = read_int_le(frame_data, 170, 2, signed=True, scale=1000.0)
    result["balance_action"] = read_bool(frame_data, 172)
    if len(frame_data) > 173:
        result["soc"] = frame_data[173]
    result["remaining_capacity"] = read_int_le(frame_data, 174, 4, signed=True, scale=1000.0)
    result["total_capacity"] = read_int_le(frame_data, 178, 4, signed=True, scale=1000.0)
    result["cycle_count"] = read_int_le(frame_data, 182, 4, signed=True, scale=1.0)
    result["cycle_capacity"] = read_int_le(frame_data, 186, 4, signed=True, scale=100.0)
    if len(frame_data) > 190:
        result["soh"] = frame_data[190]
    result["total_runtime"] = read_int_le(frame_data, 194, 4, signed=False, scale=1.0)
    result["charge_switch"] = read_bool(frame_data, 198)
    result["discharge_switch"] = read_bool(frame_data, 199)
    result["balance_switch"] = read_bool(frame_data, 200)
    result["pack_voltage"] = read_int_le(frame_data, 234, 2, signed=False, scale=100.0)

    # Derived stats from your assumptions
    result["nominal_pack_voltage"] = cells_per_battery * CELL_NOMINAL_VOLTAGE
    if result["cell_voltages"]:
        valid_cells = [v for v in result["cell_voltages"] if v is not None]
        if valid_cells:
            result["avg_cell_voltage"] = round(sum(valid_cells) / len(valid_cells), 4)

    return result


def parse_data_frame(data: bytes, cells_per_battery: int = 16) -> Optional[dict]:
    """Parse JK data frame that starts with 55 AA EB 90."""
    if len(data) < 5 or data[:4] != DATA_FRAME_START:
        return None

    frame_type = data[4]
    payload = data  # we already start at 0

    if frame_type == FRAME_TYPE_CONFIG:
        return parse_frame_type_01(payload, cells_per_battery)
    elif frame_type == FRAME_TYPE_STATUS:
        return parse_frame_type_02(payload, cells_per_battery)
    else:
        return {"type": frame_type, "unknown_type": True}


# ---- frame detection & processing --------------------------------------------

def find_next_frame_start(data: bytes, start_pos: int = 0):
    """
    Scan buffer for either JK data frame start (55 AA EB 90)
    or Modbus pattern (xx 10 16 ...) and return earliest one.
    """
    data_pos = find_pattern(data, DATA_FRAME_START, start_pos)

    modbus_pos = -1
    for i in range(start_pos, len(data) - 2):
        if data[i + 1:i + 3] == MODBUS_PATTERN:
            modbus_pos = i
            break

    if data_pos >= 0 and (modbus_pos < 0 or data_pos < modbus_pos):
        return data_pos, "data"
    elif modbus_pos >= 0:
        return modbus_pos, "modbus"
    else:
        return -1, None


# ---- Connection wrapper for TCP/IP and Serial --------------------------------

class ConnectionWrapper:
    """Unified wrapper for TCP/IP socket or serial port connections."""
    
    def __init__(self, conn: Union[socket.socket, 'serial.Serial']):
        self.conn = conn
        self.is_tcp = isinstance(conn, socket.socket)
        if self.is_tcp:
            # Set timeout for blocking socket operations
            self.conn.settimeout(READ_TIMEOUT)
            # Keep socket in blocking mode - we use thread pool for all operations
        else:
            self.conn.timeout = READ_TIMEOUT
    
    async def recv(self, size: int) -> bytes:
        """Receive data from connection (async)."""
        try:
            if self.is_tcp:
                # Use thread pool for TCP socket recv to avoid blocking the event loop
                # Even with non-blocking sockets, sock_recv can cause issues
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.conn.recv, size)
            else:
                # Serial port - use thread pool for blocking I/O
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, self.conn.read, size)
        except (socket.timeout, serial.SerialTimeoutException):
            return b''
        except Exception as e:
            log.debug(f"Connection recv error: {e}")
            return b''
    
    def close(self) -> None:
        """Close connection."""
        try:
            if self.is_tcp:
                self.conn.close()
            else:
                self.conn.close()
        except Exception:
            pass


# ---- Adapter implementation --------------------------------------------------

class JKBMSTcpipAdapter(BatteryAdapter):
    """
    JK BMS RS485 Adapter (TCP/IP or Modbus RTU)
    
    Connects to JK-BMS via either:
    - RS485-to-TCP/IP gateway (Ethernet or WiFi) - connection_type: "tcpip"
    - Direct RS485 serial connection (Modbus RTU) - connection_type: "rtu"
    
    Passively listens to RS485-2 bus communication and parses battery data.
    
    Configuration (TCP/IP):
        type: jkbms_tcpip
        connection_type: tcpip
        host: 192.168.1.100
        port: 8899
        batteries: 3
        cells_per_battery: 16
        bms_broadcasting: true
        poll_timeout: 2.0
    
    Configuration (Modbus RTU):
        type: jkbms_tcpip
        connection_type: rtu
        serial_port: /dev/ttyUSB0
        baudrate: 115200
        batteries: 3
        cells_per_battery: 16
        bms_broadcasting: true
        poll_timeout: 2.0
    """
    
    def __init__(self, bank_cfg: BatteryBankConfig):
        super().__init__(bank_cfg)
        
        self.last_tel: Optional[BatteryBankTelemetry] = None
        
        cfg = bank_cfg.adapter
        
        # Determine connection type
        connection_type = getattr(cfg, 'connection_type', None)
        
        # Auto-detect connection type if not specified
        if connection_type is None:
            if hasattr(cfg, 'host') and cfg.host and hasattr(cfg, 'port') and cfg.port:
                connection_type = "tcpip"
            elif hasattr(cfg, 'serial_port') and cfg.serial_port:
                connection_type = "rtu"
            else:
                raise ValueError("Cannot determine connection type. Specify connection_type='tcpip' or 'rtu', "
                               "or provide host/port (for TCP/IP) or serial_port (for RTU)")
        
        connection_type = connection_type.lower()
        if connection_type not in ("tcpip", "rtu"):
            raise ValueError(f"Invalid connection_type: {connection_type}. Must be 'tcpip' or 'rtu'")
        
        self.connection_type = connection_type
        
        # Connection parameters based on type
        if connection_type == "tcpip":
            if not hasattr(cfg, 'host') or not cfg.host:
                raise ValueError("host is required for TCP/IP connection")
            if not hasattr(cfg, 'port') or not cfg.port:
                raise ValueError("port is required for TCP/IP connection")
            self.host = cfg.host
            self.port = cfg.port
            self.serial_port = None
            self.baudrate = None
        else:  # rtu
            if not hasattr(cfg, 'serial_port') or not cfg.serial_port:
                raise ValueError("serial_port is required for Modbus RTU connection")
            if not SERIAL_AVAILABLE:
                raise ImportError("pyserial package is required for Modbus RTU support. Install with: pip install pyserial")
            self.host = None
            self.port = None
            self.serial_port = cfg.serial_port
            self.baudrate = getattr(cfg, 'baudrate', 115200)
            self.parity = getattr(cfg, 'parity', 'N')
            self.stopbits = getattr(cfg, 'stopbits', 1)
            self.bytesize = getattr(cfg, 'bytesize', 8)
        
        self.batteries_expected = cfg.batteries
        self.cells_per_battery = cfg.cells_per_battery
        self.poll_timeout = getattr(cfg, 'poll_timeout', 2.0)
        self.bms_broadcasting = getattr(cfg, 'bms_broadcasting', True)
        
        if not self.bms_broadcasting:
            log.warning("JKBMS RS485 Adapter requires bms_broadcasting=true. Enabling it.")
            self.bms_broadcasting = True
        
        # Connection and data storage
        self.raw_conn: Optional[Union[socket.socket, 'serial.Serial']] = None
        self.conn: Optional[ConnectionWrapper] = None
        self.batteries: Dict[int, Dict] = {}  # Latest data per battery_id
        self.current_battery_id: Optional[int] = None
        self._listening_task: Optional[asyncio.Task] = None
        self._stop_listening = False
        
        conn_desc = f"{self.host}:{self.port}" if connection_type == "tcpip" else f"{self.serial_port}@{self.baudrate}"
        log.info(f"JKBMS RS485 Adapter initialized ({connection_type}): {conn_desc}, "
                 f"batteries={self.batteries_expected}, cells={self.cells_per_battery}")
    
    async def connect(self):
        """Connect to RS485 gateway via TCP/IP or serial port."""
        # Check if we need to restart listening loop
        if self.raw_conn is not None:
            # Connection exists, but check if listening loop is alive
            if self._listening_task and self._listening_task.done():
                log.warning("JK BMS: Connection exists but listening loop died, restarting...")
                # Clean up dead task
                try:
                    await self._listening_task
                except Exception as e:
                    log.debug(f"JK BMS: Exception from dead listening task: {e}")
                self._listening_task = None
                # Restart listening loop
                self._stop_listening = False
                self._listening_task = asyncio.create_task(self._listen_loop())
                log.info("JK BMS: Restarted listening loop for existing connection")
                return
            elif not self._listening_task:
                # Connection exists but no listening loop - restart it
                log.warning("JK BMS: Connection exists but no listening loop, starting...")
                self._stop_listening = False
                self._listening_task = asyncio.create_task(self._listen_loop())
                log.info("JK BMS: Started listening loop for existing connection")
                return
            else:
                log.debug("JK BMS: Already connected and listening loop is running")
                return
        
        try:
            if self.connection_type == "tcpip":
                log.info(f"Connecting to RS485 gateway at {self.host}:{self.port}...")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)  # Connection timeout
                # Keep socket in blocking mode - we'll use thread pool for all operations
                
                loop = asyncio.get_event_loop()
                # Use thread pool for connect to avoid blocking the event loop
                await loop.run_in_executor(None, sock.connect, (self.host, self.port))
                self.raw_conn = sock
                self.conn = ConnectionWrapper(sock)
                log.info(f"Connected to RS485 gateway at {self.host}:{self.port}")
            else:  # rtu
                log.info(f"Connecting to RS485 serial port {self.serial_port} at {self.baudrate} baud...")
                
                # Open serial port in thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                ser = await loop.run_in_executor(
                    None,
                    lambda: serial.Serial(
                        port=self.serial_port,
                        baudrate=self.baudrate,
                        timeout=READ_TIMEOUT,
                        bytesize=serial.EIGHTBITS if self.bytesize == 8 else serial.SEVENBITS,
                        parity=serial.PARITY_NONE if self.parity.upper() == "N" else serial.PARITY_EVEN,
                        stopbits=serial.STOPBITS_ONE if self.stopbits == 1 else serial.STOPBITS_TWO,
                    )
                )
                self.raw_conn = ser
                self.conn = ConnectionWrapper(ser)
                log.info(f"Connected to RS485 serial port {self.serial_port} at {self.baudrate} baud")
            
            # Start background listening task
            self._stop_listening = False
            self._connect_time = time.time()
            self._listening_task = asyncio.create_task(self._listen_loop())
            log.info(f"Started listening task for JK BMS RS485 adapter ({self.connection_type}) - expecting {self.batteries_expected} battery/batteries")
            
        except Exception as e:
            if self.raw_conn:
                try:
                    if self.connection_type == "tcpip":
                        self.raw_conn.close()
                    else:
                        self.raw_conn.close()
                except:
                    pass
                self.raw_conn = None
            conn_desc = f"{self.host}:{self.port}" if self.connection_type == "tcpip" else self.serial_port
            raise RuntimeError(f"Failed to connect to RS485 device {conn_desc}: {e}")
    
    async def close(self):
        """Close connection and stop listening."""
        self._stop_listening = True
        
        if self._listening_task:
            self._listening_task.cancel()
            try:
                await self._listening_task
            except asyncio.CancelledError:
                pass
            self._listening_task = None
        
        if self.conn:
            self.conn.close()
            self.conn = None
        
        if self.raw_conn:
            try:
                if self.connection_type == "tcpip":
                    self.raw_conn.close()
                else:
                    # Serial port - close in thread pool
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.raw_conn.close)
            except Exception:
                pass
            self.raw_conn = None
        
        log.debug(f"Closed JK BMS RS485 connection ({self.connection_type})")
    
    async def _listen_loop(self):
        """Background task that continuously listens and parses frames."""
        buffer = b""
        last_log_time = 0.0
        last_status_log_time = 0.0
        
        log.info(f"JK BMS listening loop started for {self.connection_type} connection")
        
        while not self._stop_listening:
            try:
                if not self.conn:
                    await asyncio.sleep(0.1)
                    continue
                
                # Log connection status periodically (every 30 seconds)
                current_time = time.time()
                if current_time - last_log_time >= 30.0:
                    conn_status = "connected" if self.conn is not None else "disconnected"
                    batteries_status = f"{len(self.batteries)}/{self.batteries_expected}"
                    time_elapsed = int((current_time - (getattr(self, '_connect_time', current_time))) / 60)
                    data_received = getattr(self, '_data_received_count', 0)
                    empty_chunks = getattr(self, '_empty_chunk_count', 0)
                    log.info(f"JK BMS listening loop active: conn={conn_status}, batteries_discovered={batteries_status}, current_battery_id={self.current_battery_id}, elapsed={time_elapsed}m, data_chunks={data_received}, empty_chunks={empty_chunks}")
                    if len(self.batteries) == 0:
                        if data_received == 0:
                            log.warning(f"JK BMS: No batteries discovered and NO DATA RECEIVED after {time_elapsed} minutes. Check RS485 gateway connection, network, and BMS broadcasting.")
                        else:
                            log.warning(f"JK BMS: No batteries discovered after {time_elapsed} minutes despite receiving {data_received} data chunks. Check data format/parsing.")
                    last_log_time = current_time
                
                # Log detailed status every 5 minutes
                if current_time - last_status_log_time >= 300.0:
                    if self.conn:
                        log.debug(f"JK BMS status: listening_loop=running, connection=active, batteries={len(self.batteries)}, buffer_size={len(buffer)}")
                    else:
                        log.warning(f"JK BMS status: listening_loop=running, connection=None (should not happen)")
                    last_status_log_time = current_time
                
                # Use a small timeout to avoid blocking for too long
                # This allows other tasks to run
                try:
                    chunk = await asyncio.wait_for(self.conn.recv(RECV_BUFFER_SIZE), timeout=0.1)
                except asyncio.TimeoutError:
                    # No data available, yield to other tasks
                    await asyncio.sleep(0.01)
                    continue
                
                if not chunk:
                    await asyncio.sleep(0.1)
                    continue
                
                # Log when we receive data (throttled - only log first few times)
                if len(chunk) > 0:
                    if not hasattr(self, '_data_received_count'):
                        self._data_received_count = 0
                    self._data_received_count += 1
                    if self._data_received_count <= 10:
                        # Log first 10 chunks with hex dump for debugging
                        hex_preview = chunk[:32].hex() if len(chunk) >= 32 else chunk.hex()
                        log.debug(f"JK BMS received {len(chunk)} bytes of data (chunk #{self._data_received_count}): {hex_preview}...")
                    elif self._data_received_count % 100 == 0:
                        log.debug(f"JK BMS received {len(chunk)} bytes of data (total chunks: {self._data_received_count})")
                else:
                    # Log when we get empty chunks (might indicate connection issue)
                    if not hasattr(self, '_empty_chunk_count'):
                        self._empty_chunk_count = 0
                    self._empty_chunk_count += 1
                    if self._empty_chunk_count <= 5:
                        log.warning(f"JK BMS received empty chunk (count: {self._empty_chunk_count}) - connection may be idle or broken")
                
                buffer += chunk
                pos = 0
                
                while pos < len(buffer):
                    next_pos, kind = find_next_frame_start(buffer, pos)
                    if next_pos < 0:
                        # no more full frames; keep tail in buffer
                        break
                    
                    if kind == "modbus":
                        data_slice = buffer[next_pos:]
                        parsed = parse_modbus_frame(data_slice)
                        if parsed:
                            battery_id, frame_type_byte, payload, crc_valid, frame_len = parsed
                            
                            # Normalise battery_id if JK does the 15 -> 0 wrap hack
                            if battery_id == 15:
                                battery_id = 0
                            
                            # Limit to our expected batteries
                            if battery_id < self.batteries_expected:
                                # We use Modbus requests to detect that master is now talking to another BMS.
                                if frame_type_byte == MODBUS_REQUEST:
                                    self.current_battery_id = battery_id
                            
                            pos = next_pos + frame_len
                        else:
                            pos = next_pos + 1
                    
                    elif kind == "data":
                        # JK data frame (55 AA EB 90 ...)
                        slice_data = buffer[next_pos:]
                        end_pos = len(slice_data)
                        next_frame_pos, _ = find_next_frame_start(slice_data, 1)
                        if next_frame_pos > 0:
                            end_pos = next_frame_pos
                        
                        frame_bytes = slice_data[:end_pos]
                        parsed = parse_data_frame(frame_bytes, self.cells_per_battery)
                        if parsed:
                            frame_type = parsed.get("type", "unknown")
                            # make sure we know which battery this belongs to
                            # Fallback: if we don't have current_battery_id yet, treat as 0
                            b_id = self.current_battery_id if self.current_battery_id is not None else 0
                            
                            if b_id < self.batteries_expected:
                                is_new_battery = b_id not in self.batteries
                                if is_new_battery:
                                    self.batteries[b_id] = {
                                        "battery_id": b_id,
                                        "battery_index": b_id + 1,
                                        "cells_per_battery": self.cells_per_battery,
                                        "nominal_cell_voltage": CELL_NOMINAL_VOLTAGE,
                                        "nominal_pack_voltage": self.cells_per_battery * CELL_NOMINAL_VOLTAGE,
                                    }
                                    log.info(f"JK-BMS: Discovered battery {b_id + 1}/{self.batteries_expected}")
                                
                                # merge frame
                                entry = self.batteries[b_id]
                                entry["timestamp"] = int(time.time())
                                
                                # drop meta keys
                                frame_copy = {
                                    k: v
                                    for k, v in parsed.items()
                                    if k not in ("type", "battery_id", "timestamp")
                                }
                                
                                if frame_type == "configuration":
                                    entry.setdefault("configuration", {}).update(frame_copy)
                                elif frame_type == "status":
                                    entry.setdefault("status", {}).update(frame_copy)
                                    # Log telemetry update for status frames (throttled to avoid excessive logging)
                                    # Only log if we have meaningful data and it's been a while since last log
                                    status_data = entry.get("status", {})
                                    # Use pack_voltage (the actual field name) instead of voltage
                                    voltage = status_data.get("pack_voltage") or frame_copy.get("pack_voltage") or 0
                                    current = status_data.get("current") or frame_copy.get("current") or 0
                                    soc = status_data.get("soc") or frame_copy.get("soc") or 0
                                    # Calculate temperature from temp fields
                                    temps = []
                                    for temp_key in ['temp1', 'temp2', 'temp3', 'temp4', 'mos_temp']:
                                        t = status_data.get(temp_key) or frame_copy.get(temp_key)
                                        if t is not None:
                                            temps.append(t)
                                    temp = round(sum(temps) / len(temps), 1) if temps else 0
                                    
                                    # Throttle logging - only log every 5 seconds per battery
                                    last_log_time = entry.get("_last_log_time", 0)
                                    current_time = time.time()
                                    if (voltage or current or soc or temp) and (current_time - last_log_time) >= 5.0:
                                        log.debug(f"JK-BMS Battery {b_id + 1}: V={voltage:.2f}V | I={current:.2f}A | SOC={soc:.0f}% | T={temp:.1f}°C")
                                        entry["_last_log_time"] = current_time
                                else:
                                    entry.setdefault("other_frames", []).append(
                                        {"frame_type": frame_type, "data": frame_copy}
                                    )
                            
                            pos = next_pos + end_pos
                        else:
                            pos = next_pos + end_pos
                
                # keep unprocessed tail
                buffer = buffer[pos:]
                
            except asyncio.CancelledError:
                log.info("JK BMS listening loop cancelled")
                break
            except Exception as e:
                log.error(f"JK BMS: Error in listening loop: {e}", exc_info=True)
                # Don't exit on error - try to continue listening
                # But if connection is lost, we should exit
                if not self.conn:
                    log.error("JK BMS: Connection lost, exiting listening loop")
                    break
                await asyncio.sleep(0.1)
        
        log.info("JK BMS listening loop exited")
    
    async def poll(self) -> BatteryBankTelemetry:
        """
        Poll batteries and return aggregated telemetry.
        
        Note: This does NOT wait for data - the listening loop runs continuously
        in the background and collects data. This method just returns the latest
        available data immediately.
        """
        from solarhub.timezone_utils import now_configured_iso
        
        # No need to wait - listening loop is running in background
        # Just return the latest data immediately
        
        devices: List[BatteryUnit] = []
        cells_data: List[Dict[str, Any]] = []
        
        # Process discovered batteries
        for battery_id in sorted(self.batteries.keys()):
            # Validate battery_id is within expected range
            if battery_id < 0 or battery_id >= self.batteries_expected:
                log.warning(f"JK BMS: Skipping invalid battery_id {battery_id} (expected 0-{self.batteries_expected-1})")
                continue
            
            data = self.batteries[battery_id]
            status = data.get('status', {})
            config = data.get('configuration', {})
            
            # Extract values
            voltage = status.get('pack_voltage')
            current = status.get('current')
            power = status.get('power')
            soc = status.get('soc')
            soh = status.get('soh')
            cycles = status.get('cycle_count')
            
            # Calculate average temperature
            temps = []
            for temp_key in ['temp1', 'temp2', 'temp3', 'temp4', 'mos_temp']:
                t = status.get(temp_key)
                if t is not None:
                    temps.append(t)
            temperature = round(sum(temps) / len(temps), 1) if temps else None
            
            # Cell voltages
            cell_voltages = status.get('cell_voltages', [])
            valid_cells = [v for v in cell_voltages if v is not None]
            
            # Debug logging for cell data
            if len(valid_cells) == 0 and len(cell_voltages) > 0:
                log.debug(f"JK BMS Battery {battery_id + 1}: Found {len(cell_voltages)} cell_voltages but all are None")
            elif len(valid_cells) > 0:
                log.debug(f"JK BMS Battery {battery_id + 1}: Found {len(valid_cells)} valid cells out of {len(cell_voltages)} total")
            
            # Create BatteryUnit
            # Note: 'power' field should be the battery unit index (1-based: 1, 2, 3, ...)
            # This is used by the frontend to identify and match cells to battery units
            battery_unit_index = battery_id + 1  # Convert 0-based battery_id to 1-based index
            
            # Validate battery_unit_index is within reasonable range
            if battery_unit_index < 1 or battery_unit_index > self.batteries_expected:
                log.error(f"JK BMS: Invalid battery_unit_index {battery_unit_index} for battery_id {battery_id} (expected 1-{self.batteries_expected})")
                continue
            device = BatteryUnit(
                power=battery_unit_index,  # Battery unit index (1, 2, 3, ...), not power in watts
                voltage=voltage,
                current=current,
                temperature=temperature,
                soc=float(soc) if soc is not None else None,
                soh=float(soh) if soh is not None else None,
                cycles=int(cycles) if cycles is not None else None,
            )
            devices.append(device)
            
            # Create cells_data entry
            # Note: 'power' field should match BatteryUnit.power (battery unit index 1, 2, 3, ...)
            # This is used by the frontend to match cells to the correct battery unit
            cell_data = {
                "battery_id": battery_id,
                "battery_index": battery_unit_index,
                "power": battery_unit_index,  # Match BatteryUnit.power (1-based index) for frontend matching
                "voltage": voltage,
                "current": current,
                "soc": soc,
                "soh": soh,
                "temperature": temperature,
                "cycles": cycles,
                "cells": []
            }
            
            for cell_idx, cell_voltage in enumerate(cell_voltages):
                if cell_voltage is not None:
                    # Validate cell index is within expected range
                    cell_number = cell_idx + 1
                    if cell_number < 1 or cell_number > self.cells_per_battery:
                        log.warning(f"JK BMS Battery {battery_unit_index}: Skipping invalid cell index {cell_number} (expected 1-{self.cells_per_battery})")
                        continue
                    
                    # Validate cell voltage is reasonable (typically 2.5V to 4.5V per cell)
                    if cell_voltage < 2.0 or cell_voltage > 5.0:
                        log.warning(f"JK BMS Battery {battery_unit_index} Cell {cell_number}: Suspicious cell voltage {cell_voltage}V (expected 2.0-5.0V)")
                        # Still include it, but log the warning
                    
                    cell_data["cells"].append({
                        "cell": cell_number,  # Database expects 'cell', not 'cell_id'
                        "voltage": cell_voltage,
                    })
            
            # Add voltage statistics for frontend display
            if valid_cells:
                cell_data["cell_voltages"] = valid_cells
                cell_data["voltage_min"] = round(min(valid_cells), 3)
                cell_data["voltage_max"] = round(max(valid_cells), 3)
                cell_data["voltage_delta"] = round(max(valid_cells) - min(valid_cells), 3)
                cell_data["cell_delta"] = round(max(valid_cells) - min(valid_cells), 3)
                cell_data["cell_count"] = len(valid_cells)
                log.debug(f"JK BMS Battery {battery_id + 1}: Added {len(cell_data['cells'])} cells to cells_data")
            else:
                log.debug(f"JK BMS Battery {battery_id + 1}: No valid cells found, cell_data will have empty cells array")
            
            # Always append cell_data, even if cells array is empty (for debugging)
            cells_data.append(cell_data)
        
        # Aggregate bank-level values
        voltages = [d.voltage for d in devices if d.voltage is not None]
        currents = [d.current for d in devices if d.current is not None]
        temperatures = [d.temperature for d in devices if d.temperature is not None]
        socs = [d.soc for d in devices if d.soc is not None]
        
        cfg = self.bank_cfg.adapter
        bank = BatteryBankTelemetry(
            ts=now_configured_iso(),
            id=self.bank_cfg.id,
            batteries_count=len(devices) if devices else self.batteries_expected,
            cells_per_battery=self.cells_per_battery,
            voltage=round(sum(voltages) / len(voltages), 2) if voltages else None,
            current=round(sum(currents), 1) if currents else None,
            temperature=round(sum(temperatures) / len(temperatures), 1) if temperatures else None,
            soc=int(sum(socs) / len(socs)) if socs else None,
            devices=devices,
            cells_data=cells_data if cells_data else None,  # Set to None if empty list
            extra={
                "dev_name": cfg.dev_name,
                "manufacturer": cfg.manufacturer,
                "model": cfg.model,
                "connection_type": self.connection_type,
                "host": self.host if self.connection_type == "tcpip" else None,
                "port": self.port if self.connection_type == "tcpip" else None,
                "serial_port": self.serial_port if self.connection_type == "rtu" else None,
                "baudrate": self.baudrate if self.connection_type == "rtu" else None,
                "batteries_discovered": len(self.batteries),
            },
        )
        
        self.last_tel = bank
        return bank
    
    async def check_connectivity(self) -> bool:
        """
        Check if adapter is connected and listening loop is running.
        
        Returns True only if:
        - Socket/serial connection is established
        - Listening loop is running (not done/cancelled)
        - Either batteries have been discovered OR we're still within discovery timeout
        """
        if not self.raw_conn:
            log.debug("JK BMS: No connection (raw_conn is None)")
            return False
        
        # Check socket/serial connection
        try:
            if self.connection_type == "tcpip":
                if hasattr(self.raw_conn, 'getpeername'):
                    try:
                        self.raw_conn.getpeername()
                    except (OSError, AttributeError):
                        log.debug("JK BMS: Socket getpeername() failed")
                        return False
                else:
                    log.debug("JK BMS: Socket has no getpeername method")
                    return False
            else:  # rtu
                if hasattr(self.raw_conn, 'is_open'):
                    if not self.raw_conn.is_open:
                        log.debug("JK BMS: Serial port is not open")
                        return False
                else:
                    log.debug("JK BMS: Serial port has no is_open attribute")
                    return False
        except Exception as e:
            log.debug(f"JK BMS: Connection check exception: {e}")
            return False
        
        # Check listening loop status
        if not self._listening_task:
            log.debug("JK BMS: No listening task")
            return False
        
        if self._listening_task.done():
            # Check if it was cancelled or raised an exception
            try:
                await self._listening_task
            except asyncio.CancelledError:
                log.debug("JK BMS: Listening task was cancelled")
            except Exception as e:
                log.warning(f"JK BMS: Listening task died with exception: {e}")
            return False
        
        # If we have discovered batteries, we're definitely connected and working
        if len(self.batteries) > 0:
            log.debug(f"JK BMS: Connected, listening loop running, {len(self.batteries)} battery/batteries discovered")
            return True
        
        # If loop is running but no batteries yet, check timeout
        if hasattr(self, '_connect_time'):
            time_since_connect = time.time() - self._connect_time
            if time_since_connect < 60:  # Give 60 seconds for discovery
                log.debug(f"JK BMS: Connected, listening loop running, waiting for battery discovery ({int(time_since_connect)}s elapsed)")
                return True  # Still waiting for discovery
            else:
                log.warning(f"JK BMS: Connected but no batteries discovered after {int(time_since_connect)}s - may indicate connection issue")
                # Still return True if loop is running - connection might be fine, just no data yet
                return True
        
        # Loop is running, assume connected (fallback)
        log.debug("JK BMS: Connected, listening loop running (no connect_time recorded)")
        return True
