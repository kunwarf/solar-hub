"""
Modbus TCP Device Simulator.

Simulates a Modbus TCP device (slave) that:
1. Connects TO the server (like a real data logger)
2. Responds to Modbus READ requests with simulated telemetry
3. Handles Modbus WRITE requests as commands
4. Maintains register state with realistic values

Usage:
    python -m system_b.tools.modbus_device_simulator --server-host localhost --server-port 8502

    # Or as a module
    from system_b.tools.modbus_device_simulator import ModbusDeviceSimulator
    simulator = ModbusDeviceSimulator(server_host="localhost", server_port=8502)
    await simulator.run()
"""
import asyncio
import logging
import random
import signal
import struct
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ModbusDeviceSimulator:
    """
    Simulates a Modbus TCP device that connects to a server.

    Acts as a Modbus slave but initiates the TCP connection
    (like a real data logger connecting to monitoring server).

    Supports:
    - Function 0x03: Read Holding Registers
    - Function 0x04: Read Input Registers
    - Function 0x06: Write Single Register
    - Function 0x10: Write Multiple Registers
    """

    # Register definitions for each device type
    REGISTER_MAPS = {
        "inverter": {
            # Identification registers (read by server to identify device)
            # These match the powdrive protocol definition in protocols.yaml
            "identification": {
                0: {"name": "device_type", "value": 3},  # 3 = Hybrid inverter
                1: {"name": "protocol_version", "value": 1},
                2: {"name": "firmware_version", "value": 100},
                # Serial number registers (3-7, 5 registers, ASCII encoded)
                3: {"name": "serial_1", "ascii": True},
                4: {"name": "serial_2", "ascii": True},
                5: {"name": "serial_3", "ascii": True},
                6: {"name": "serial_4", "ascii": True},
                7: {"name": "serial_5", "ascii": True},
            },
            # Input registers (read-only telemetry) - address 30000+
            "input": {
                30001: {"name": "pv_power", "unit": "W", "min": 0, "max": 12000},
                30002: {"name": "pv_voltage", "unit": "V*10", "min": 0, "max": 6000},
                30003: {"name": "pv_current", "unit": "A*10", "min": 0, "max": 300},
                30004: {"name": "ac_power", "unit": "W", "min": 0, "max": 12000},
                30005: {"name": "ac_voltage", "unit": "V*10", "min": 2100, "max": 2500},
                30006: {"name": "ac_current", "unit": "A*10", "min": 0, "max": 600},
                30007: {"name": "ac_frequency", "unit": "Hz*100", "min": 4950, "max": 5050},
                30008: {"name": "temperature", "unit": "C*10", "min": 200, "max": 650},
                30009: {"name": "efficiency", "unit": "%*10", "min": 900, "max": 990},
                30010: {"name": "energy_today", "unit": "Wh", "min": 0, "max": 100000},
                30011: {"name": "energy_total_hi", "unit": "kWh*10 (high)", "min": 0, "max": 65535},
                30012: {"name": "energy_total_lo", "unit": "kWh*10 (low)", "min": 0, "max": 65535},
                # Serial number (ASCII)
                30100: {"name": "serial_1", "unit": "ASCII", "fixed": True},
                30101: {"name": "serial_2", "unit": "ASCII", "fixed": True},
                30102: {"name": "serial_3", "unit": "ASCII", "fixed": True},
                30103: {"name": "serial_4", "unit": "ASCII", "fixed": True},
                30104: {"name": "serial_5", "unit": "ASCII", "fixed": True},
                30105: {"name": "serial_6", "unit": "ASCII", "fixed": True},
                30106: {"name": "serial_7", "unit": "ASCII", "fixed": True},
                30107: {"name": "serial_8", "unit": "ASCII", "fixed": True},
            },
            # Holding registers (read/write - commands) - address 40000+
            "holding": {
                40001: {"name": "power_limit", "unit": "%*10", "default": 1000},
                40002: {"name": "operating_mode", "unit": "enum", "default": 0},
                40003: {"name": "reactive_power", "unit": "%*10", "default": 0},
                40010: {"name": "restart_cmd", "unit": "bool", "default": 0},
            },
        },
        "battery": {
            # Identification registers for battery (not used for Modbus probing,
            # but included for consistency)
            "identification": {
                0: {"name": "device_type", "value": 10},  # Battery type
                10: {"name": "serial_1", "ascii": True},
                11: {"name": "serial_2", "ascii": True},
                12: {"name": "serial_3", "ascii": True},
                13: {"name": "serial_4", "ascii": True},
            },
            "input": {
                30001: {"name": "soc", "unit": "%*10", "min": 100, "max": 1000},
                30002: {"name": "soh", "unit": "%*10", "min": 800, "max": 1000},
                30003: {"name": "voltage", "unit": "V*10", "min": 450, "max": 580},
                30004: {"name": "current", "unit": "A*10", "min": -1000, "max": 1000},
                30005: {"name": "power", "unit": "W", "min": -5000, "max": 5000},
                30006: {"name": "temperature", "unit": "C*10", "min": 150, "max": 450},
                30007: {"name": "charge_energy_hi", "unit": "Wh (high)", "min": 0, "max": 65535},
                30008: {"name": "charge_energy_lo", "unit": "Wh (low)", "min": 0, "max": 65535},
                30009: {"name": "discharge_energy_hi", "unit": "Wh (high)", "min": 0, "max": 65535},
                30010: {"name": "discharge_energy_lo", "unit": "Wh (low)", "min": 0, "max": 65535},
                30011: {"name": "cycles", "unit": "count", "min": 0, "max": 6000},
                # Serial number
                30100: {"name": "serial_1", "unit": "ASCII", "fixed": True},
                30101: {"name": "serial_2", "unit": "ASCII", "fixed": True},
                30102: {"name": "serial_3", "unit": "ASCII", "fixed": True},
                30103: {"name": "serial_4", "unit": "ASCII", "fixed": True},
            },
            "holding": {
                40100: {"name": "charge_limit", "unit": "A*10", "default": 500},
                40101: {"name": "discharge_limit", "unit": "A*10", "default": 500},
                40102: {"name": "min_soc", "unit": "%", "default": 10},
                40103: {"name": "max_soc", "unit": "%", "default": 100},
                40104: {"name": "force_charge", "unit": "bool", "default": 0},
                40105: {"name": "force_discharge", "unit": "bool", "default": 0},
            },
        },
        "meter": {
            # Identification registers - matches iammeter protocol
            # register 9, expected values [1, 2, 3, 4]
            "identification": {
                9: {"name": "model_type", "value": 1},  # 1 = WEM3080
                56: {"name": "serial_1", "ascii": True},
                57: {"name": "serial_2", "ascii": True},
                58: {"name": "serial_3", "ascii": True},
                59: {"name": "serial_4", "ascii": True},
                60: {"name": "serial_5", "ascii": True},
                61: {"name": "serial_6", "ascii": True},
                62: {"name": "serial_7", "ascii": True},
                63: {"name": "serial_8", "ascii": True},
            },
            "input": {
                30001: {"name": "grid_power", "unit": "W", "min": -10000, "max": 10000},
                30002: {"name": "grid_voltage", "unit": "V*10", "min": 2100, "max": 2500},
                30003: {"name": "grid_current", "unit": "A*10", "min": 0, "max": 600},
                30004: {"name": "grid_frequency", "unit": "Hz*100", "min": 4950, "max": 5050},
                30005: {"name": "import_energy_hi", "unit": "Wh (high)", "min": 0, "max": 65535},
                30006: {"name": "import_energy_lo", "unit": "Wh (low)", "min": 0, "max": 65535},
                30007: {"name": "export_energy_hi", "unit": "Wh (high)", "min": 0, "max": 65535},
                30008: {"name": "export_energy_lo", "unit": "Wh (low)", "min": 0, "max": 65535},
                30009: {"name": "power_factor", "unit": "*1000", "min": 800, "max": 1000},
                # Serial number
                30100: {"name": "serial_1", "unit": "ASCII", "fixed": True},
                30101: {"name": "serial_2", "unit": "ASCII", "fixed": True},
                30102: {"name": "serial_3", "unit": "ASCII", "fixed": True},
                30103: {"name": "serial_4", "unit": "ASCII", "fixed": True},
            },
            "holding": {
                40200: {"name": "reset_energy", "unit": "bool", "default": 0},
            },
        },
    }

    def __init__(
        self,
        server_host: str = "localhost",
        server_port: int = 8502,
        device_type: str = "inverter",
        unit_id: int = 1,
        serial_number: Optional[str] = None,
        update_interval: float = 1.0,
        reconnect_delay: float = 5.0,
    ):
        """
        Initialize the Modbus device simulator.

        Args:
            server_host: Server hostname to connect to
            server_port: Server port to connect to
            device_type: Type of device to simulate (inverter, battery, meter)
            unit_id: Modbus unit ID (slave address)
            serial_number: Device serial number (generated if not provided)
            update_interval: Interval for updating simulated values (seconds)
            reconnect_delay: Delay before reconnection attempt (seconds)
        """
        self.server_host = server_host
        self.server_port = server_port
        self.device_type = device_type.lower()
        self.unit_id = unit_id
        self.serial_number = serial_number or self._generate_serial_number()
        self.update_interval = update_interval
        self.reconnect_delay = reconnect_delay

        # Validate device type
        if self.device_type not in self.REGISTER_MAPS:
            raise ValueError(
                f"Invalid device type: {device_type}. "
                f"Supported: {list(self.REGISTER_MAPS.keys())}"
            )

        # Register storage
        self.input_registers: Dict[int, int] = {}
        self.holding_registers: Dict[int, int] = {}

        # State
        self._running = False
        self._connected = False
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._last_update = datetime.now()

        # Statistics
        self._stats = {
            "read_requests": 0,
            "write_requests": 0,
            "errors": 0,
            "connected_at": None,
        }

        # Initialize registers
        self._init_registers()

    def _generate_serial_number(self) -> str:
        """Generate a realistic serial number."""
        prefix_map = {
            "inverter": "INV",
            "battery": "BAT",
            "meter": "MTR",
        }
        prefix = prefix_map.get(self.device_type, "DEV")
        random_part = "".join(random.choices("0123456789ABCDEF", k=8))
        return f"{prefix}-{random_part}"

    def _init_registers(self) -> None:
        """Initialize register values."""
        register_map = self.REGISTER_MAPS[self.device_type]

        # Initialize identification registers (used for device probing)
        if "identification" in register_map:
            for addr, config in register_map["identification"].items():
                if config.get("ascii"):
                    # Will be set by _set_serial_number_registers
                    self.holding_registers[addr] = 0
                else:
                    self.holding_registers[addr] = config.get("value", 0)
            logger.info(f"Initialized identification registers for {self.device_type}")

        # Initialize input registers
        for addr, config in register_map["input"].items():
            if config.get("fixed"):
                # Serial number registers
                self.input_registers[addr] = 0
            else:
                # Start at midpoint of range
                mid = (config["min"] + config["max"]) // 2
                self.input_registers[addr] = mid

        # Initialize holding registers with defaults
        for addr, config in register_map["holding"].items():
            self.holding_registers[addr] = config.get("default", 0)

        # Set serial number in registers (ASCII encoded)
        self._set_serial_number_registers()

        logger.info(f"Initialized {self.device_type} with serial {self.serial_number}")

    def _set_serial_number_registers(self) -> None:
        """Encode serial number into registers."""
        # Pad serial to 16 characters (8 registers * 2 bytes)
        serial_padded = self.serial_number.ljust(16, "\x00")[:16]

        register_map = self.REGISTER_MAPS[self.device_type]

        # Set serial in identification registers (holding registers at low addresses)
        if "identification" in register_map:
            ident_map = register_map["identification"]
            serial_regs = [addr for addr, cfg in ident_map.items() if cfg.get("ascii")]
            serial_regs.sort()

            for i, addr in enumerate(serial_regs):
                if i * 2 < len(serial_padded):
                    char1 = ord(serial_padded[i * 2])
                    char2 = ord(serial_padded[i * 2 + 1]) if i * 2 + 1 < len(serial_padded) else 0
                    self.holding_registers[addr] = (char1 << 8) | char2

            logger.debug(f"Set serial in identification registers: {serial_regs}")

        # Set serial in input registers (for telemetry reads)
        input_map = register_map["input"]
        serial_regs = [addr for addr, cfg in input_map.items() if "serial" in cfg["name"]]
        serial_regs.sort()

        # Encode 2 characters per register (big-endian)
        for i, addr in enumerate(serial_regs):
            if i * 2 < len(serial_padded):
                char1 = ord(serial_padded[i * 2])
                char2 = ord(serial_padded[i * 2 + 1]) if i * 2 + 1 < len(serial_padded) else 0
                self.input_registers[addr] = (char1 << 8) | char2

    def _update_telemetry(self) -> None:
        """Update simulated telemetry values."""
        now = datetime.now()
        hour = now.hour
        is_daytime = 6 <= hour <= 18
        solar_factor = max(0, 1 - abs(hour - 12) / 6) if is_daytime else 0

        register_map = self.REGISTER_MAPS[self.device_type]["input"]

        for addr, config in register_map.items():
            if config.get("fixed"):
                continue  # Don't update fixed values like serial number

            min_val = config["min"]
            max_val = config["max"]
            current = self.input_registers.get(addr, (min_val + max_val) // 2)

            name = config["name"]

            # Time-based variations
            if "pv" in name or "solar" in name:
                # PV values depend on time of day
                target = int(min_val + (max_val - min_val) * solar_factor)
                new_val = current + random.randint(-100, 100)
                new_val = int(0.9 * new_val + 0.1 * target)  # Smooth towards target
            elif "ac_power" in name and self.device_type == "inverter":
                # AC power follows PV power
                pv_power = self.input_registers.get(30001, 0)
                efficiency = self.input_registers.get(30009, 950) / 1000
                target = int(pv_power * efficiency)
                new_val = current + random.randint(-50, 50)
                new_val = int(0.8 * new_val + 0.2 * target)
            elif "temperature" in name:
                # Temperature changes slowly
                change = random.randint(-5, 5)
                new_val = current + change
            elif "soc" in name:
                # Battery SOC - charge during day, discharge at night
                if is_daytime and solar_factor > 0.3:
                    change = random.randint(0, 10)  # Charging
                else:
                    change = random.randint(-10, 0)  # Discharging
                new_val = current + change
            elif "grid_power" in name:
                # Grid power - negative when exporting
                if is_daytime and solar_factor > 0.3:
                    new_val = random.randint(min_val, 0)  # Exporting
                else:
                    new_val = random.randint(0, max_val // 2)  # Importing
            elif "energy" in name and "hi" not in name and "lo" not in name:
                # Today's energy increases during day
                if is_daytime:
                    new_val = current + random.randint(0, 50)
                else:
                    new_val = current
            elif "cycles" in name:
                # Cycles increase very slowly
                if random.random() < 0.001:
                    new_val = current + 1
                else:
                    new_val = current
            else:
                # Random walk for other values
                change = random.randint(-10, 10)
                new_val = current + change

            # Clamp to valid range
            new_val = max(min_val, min(max_val, new_val))
            self.input_registers[addr] = new_val

    def _handle_read_holding(self, pdu: bytes) -> bytes:
        """Handle Read Holding Registers (0x03)."""
        start_addr, quantity = struct.unpack(">HH", pdu[1:5])

        values = []
        for addr in range(start_addr, start_addr + quantity):
            val = self.holding_registers.get(addr, 0)
            values.append(val)

        # Log the read request with register names
        # Check both identification and holding maps for register names
        register_map = self.REGISTER_MAPS[self.device_type]
        holding_map = register_map.get("holding", {})
        ident_map = register_map.get("identification", {})

        reg_info = []
        for i, addr in enumerate(range(start_addr, start_addr + quantity)):
            config = holding_map.get(addr) or ident_map.get(addr)
            name = config["name"] if config else f"reg_{addr}"
            reg_info.append(f"{name}={values[i]}")

        logger.info(f"[READ HOLDING] addr={start_addr}, qty={quantity} -> {', '.join(reg_info)}")

        byte_count = quantity * 2
        response = struct.pack(">BB", 0x03, byte_count)
        for val in values:
            response += struct.pack(">H", val & 0xFFFF)

        self._stats["read_requests"] += 1
        return response

    def _handle_read_input(self, pdu: bytes) -> bytes:
        """Handle Read Input Registers (0x04)."""
        start_addr, quantity = struct.unpack(">HH", pdu[1:5])

        values = []
        for addr in range(start_addr, start_addr + quantity):
            val = self.input_registers.get(addr, 0)
            values.append(val)

        # Log the read request with register names
        register_map = self.REGISTER_MAPS[self.device_type]["input"]
        reg_info = []
        for i, addr in enumerate(range(start_addr, start_addr + quantity)):
            config = register_map.get(addr)
            name = config["name"] if config else f"reg_{addr}"
            reg_info.append(f"{name}={values[i]}")

        logger.info(f"[READ INPUT] addr={start_addr}, qty={quantity} -> {', '.join(reg_info)}")

        byte_count = quantity * 2
        response = struct.pack(">BB", 0x04, byte_count)
        for val in values:
            response += struct.pack(">H", val & 0xFFFF)

        self._stats["read_requests"] += 1
        return response

    def _handle_write_single(self, pdu: bytes) -> bytes:
        """Handle Write Single Register (0x06)."""
        addr, value = struct.unpack(">HH", pdu[1:5])

        # Store value
        old_value = self.holding_registers.get(addr, 0)
        self.holding_registers[addr] = value

        # Log human-readable command
        register_map = self.REGISTER_MAPS[self.device_type]["holding"]
        config = register_map.get(addr)
        if config:
            name = config["name"]
            unit = config.get("unit", "")
            logger.info(f"[WRITE SINGLE] addr={addr} ({name}): {old_value} -> {value} ({unit})")
        else:
            logger.info(f"[WRITE SINGLE] addr={addr}: {old_value} -> {value}")

        self._stats["write_requests"] += 1

        # Echo request (standard Modbus response)
        return pdu

    def _handle_write_multiple(self, pdu: bytes) -> bytes:
        """Handle Write Multiple Registers (0x10)."""
        start_addr, quantity, byte_count = struct.unpack(">HHB", pdu[1:6])

        # Parse values
        values = []
        for i in range(quantity):
            offset = 6 + i * 2
            value = struct.unpack(">H", pdu[offset:offset + 2])[0]
            values.append(value)

        # Store values and build log message
        register_map = self.REGISTER_MAPS[self.device_type]["holding"]
        changes = []
        for i, value in enumerate(values):
            addr = start_addr + i
            old_value = self.holding_registers.get(addr, 0)
            self.holding_registers[addr] = value
            config = register_map.get(addr)
            if config:
                name = config["name"]
                changes.append(f"{name}: {old_value}->{value}")
            else:
                changes.append(f"reg_{addr}: {old_value}->{value}")

        logger.info(f"[WRITE MULTIPLE] addr={start_addr}, qty={quantity} -> {', '.join(changes)}")

        self._stats["write_requests"] += 1

        # Response: function code + start address + quantity
        response = struct.pack(">BHH", 0x10, start_addr, quantity)
        return response

    def _make_exception(self, function_code: int, exception_code: int) -> bytes:
        """Create Modbus exception response."""
        return struct.pack(">BB", function_code | 0x80, exception_code)

    def _process_request(self, function_code: int, pdu: bytes) -> bytes:
        """Process Modbus request and return response."""
        if function_code == 0x03:
            return self._handle_read_holding(pdu)
        elif function_code == 0x04:
            return self._handle_read_input(pdu)
        elif function_code == 0x06:
            return self._handle_write_single(pdu)
        elif function_code == 0x10:
            return self._handle_write_multiple(pdu)
        else:
            logger.warning(f"Unsupported function code: {function_code}")
            self._stats["errors"] += 1
            return self._make_exception(function_code, 0x01)  # Illegal function

    async def _handle_connection(self) -> None:
        """Handle Modbus TCP communication."""
        logger.info(f"Connected to {self.server_host}:{self.server_port}")
        self._stats["connected_at"] = datetime.now().isoformat()

        try:
            while self._running and self._reader and self._writer:
                try:
                    # Read MBAP header (7 bytes)
                    header = await asyncio.wait_for(
                        self._reader.readexactly(7),
                        timeout=30.0,
                    )
                except asyncio.TimeoutError:
                    # No request received - just update telemetry
                    self._update_telemetry()
                    continue

                if not header:
                    logger.info("Connection closed by server")
                    break

                # Parse MBAP header
                transaction_id, protocol_id, length, unit_id = struct.unpack(
                    ">HHHB", header
                )

                # Read PDU
                pdu = await self._reader.readexactly(length - 1)
                function_code = pdu[0]

                # Process request
                response = self._process_request(function_code, pdu)

                # Build response with MBAP header
                resp_length = len(response) + 1
                resp_header = struct.pack(
                    ">HHHB",
                    transaction_id,
                    0,  # Protocol ID
                    resp_length,
                    unit_id,
                )

                # Send response
                self._writer.write(resp_header + response)
                await self._writer.drain()

                # Periodically update telemetry
                now = datetime.now()
                if (now - self._last_update).total_seconds() >= self.update_interval:
                    self._update_telemetry()
                    self._last_update = now

        except asyncio.IncompleteReadError:
            logger.info("Connection closed by server (incomplete read)")
        except ConnectionError as e:
            logger.warning(f"Connection error: {e}")
        except Exception as e:
            logger.error(f"Error in connection handler: {e}")
            self._stats["errors"] += 1

    async def connect(self) -> bool:
        """Connect to the server."""
        try:
            logger.info(f"Connecting to {self.server_host}:{self.server_port}...")
            self._reader, self._writer = await asyncio.open_connection(
                self.server_host,
                self.server_port,
            )
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._connected = False

    async def run(self) -> None:
        """Run the simulator with automatic reconnection."""
        self._running = True

        logger.info(f"Starting Modbus {self.device_type} simulator")
        logger.info(f"Serial number: {self.serial_number}")
        logger.info(f"Unit ID: {self.unit_id}")
        logger.info(f"Target server: {self.server_host}:{self.server_port}")

        while self._running:
            # Connect to server
            if not self._connected:
                success = await self.connect()
                if not success:
                    logger.info(f"Retrying in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)
                    continue

            # Handle communication
            await self._handle_connection()

            # Disconnected - prepare for reconnection
            await self.disconnect()

            if self._running:
                logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)

    async def stop(self) -> None:
        """Stop the simulator."""
        logger.info("Stopping simulator...")
        self._running = False
        await self.disconnect()

    def get_stats(self) -> Dict[str, Any]:
        """Get simulator statistics."""
        return {
            **self._stats,
            "device_type": self.device_type,
            "serial_number": self.serial_number,
            "unit_id": self.unit_id,
            "connected": self._connected,
            "input_registers_count": len(self.input_registers),
            "holding_registers_count": len(self.holding_registers),
        }

    def get_register_values(self) -> Dict[str, Dict[int, int]]:
        """Get current register values."""
        return {
            "input": dict(self.input_registers),
            "holding": dict(self.holding_registers),
        }


class MultiModbusSimulator:
    """
    Simulate multiple Modbus devices simultaneously.
    """

    def __init__(
        self,
        server_host: str = "localhost",
        server_port: int = 8502,
        devices: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize multi-device simulator.

        Args:
            server_host: Server hostname
            server_port: Server port
            devices: List of device configurations
        """
        self.server_host = server_host
        self.server_port = server_port
        self.simulators: List[ModbusDeviceSimulator] = []

        # Default device configuration
        if devices is None:
            devices = [
                {"device_type": "inverter", "unit_id": 1},
                {"device_type": "battery", "unit_id": 2},
                {"device_type": "meter", "unit_id": 3},
            ]

        # Create simulators
        for config in devices:
            simulator = ModbusDeviceSimulator(
                server_host=self.server_host,
                server_port=self.server_port,
                device_type=config.get("device_type", "inverter"),
                unit_id=config.get("unit_id", 1),
                serial_number=config.get("serial_number"),
            )
            self.simulators.append(simulator)

    async def run(self) -> None:
        """Run all simulators concurrently."""
        logger.info(f"Starting {len(self.simulators)} device simulators")

        tasks = [asyncio.create_task(sim.run()) for sim in self.simulators]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stop all simulators."""
        for simulator in self.simulators:
            await simulator.stop()


async def main():
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Modbus TCP Device Simulator - connects to server and responds to Modbus requests"
    )
    parser.add_argument(
        "--server-host",
        default="localhost",
        help="Server hostname to connect to (default: localhost)",
    )
    parser.add_argument(
        "--server-port",
        type=int,
        default=8502,
        help="Server port to connect to (default: 8502)",
    )
    parser.add_argument(
        "--device-type",
        choices=["inverter", "battery", "meter"],
        default="inverter",
        help="Type of device to simulate (default: inverter)",
    )
    parser.add_argument(
        "--unit-id",
        type=int,
        default=1,
        help="Modbus unit ID / slave address (default: 1)",
    )
    parser.add_argument(
        "--serial-number",
        type=str,
        default=None,
        help="Device serial number (generated if not provided)",
    )
    parser.add_argument(
        "--multi",
        action="store_true",
        help="Simulate multiple devices (1 inverter, 1 battery, 1 meter)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (debug) logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Setup graceful shutdown
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: signal_handler())

    if args.multi:
        simulator = MultiModbusSimulator(
            server_host=args.server_host,
            server_port=args.server_port,
        )
    else:
        simulator = ModbusDeviceSimulator(
            server_host=args.server_host,
            server_port=args.server_port,
            device_type=args.device_type,
            unit_id=args.unit_id,
            serial_number=args.serial_number,
        )

    # Run simulator
    try:
        run_task = asyncio.create_task(simulator.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [run_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await simulator.stop()

    except Exception as e:
        logger.error(f"Simulator error: {e}")
        await simulator.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
