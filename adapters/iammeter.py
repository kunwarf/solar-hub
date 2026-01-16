"""
IAMMeter Modbus/TCP Adapter

Supports IAMMeter Wi-Fi energy meters (WEM3080, WEM3080T, etc.) via Modbus/TCP.
These devices monitor bidirectional energy flow and provide grid import/export data.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pymodbus.client import AsyncModbusTcpClient
from solarhub.adapters.base import MeterAdapter, JsonRegisterMixin
from solarhub.schedulers.models import MeterTelemetry
from solarhub.timezone_utils import now_configured_iso
import logging
import json

log = logging.getLogger(__name__)


class IAMMeterAdapter(MeterAdapter, JsonRegisterMixin):
    """
    IAMMeter adapter using Modbus/TCP protocol.
    
    IAMMeter devices provide:
    - Voltage (V)
    - Current (A)
    - Active Power (W) - positive = import, negative = export
    - Active Energy (kWh) - cumulative
    - Frequency (Hz)
    - Power Factor
    
    Register addresses are based on typical IAMMeter Modbus maps.
    These may vary by model - check device documentation.
    """
    
    def __init__(self, meter_cfg):
        super().__init__(meter_cfg)
        self.client: Optional[AsyncModbusTcpClient] = None
        self.host = meter_cfg.adapter.host
        self.port = meter_cfg.adapter.port or 502
        self.unit_id = meter_cfg.adapter.unit_id or 1
        # Read prefer_legacy_registers from config (Pydantic model attribute)
        # Try direct access first (Pydantic model), then fallback to getattr
        if hasattr(meter_cfg.adapter, 'prefer_legacy_registers'):
            self.prefer_legacy_registers = bool(meter_cfg.adapter.prefer_legacy_registers)
        else:
            self.prefer_legacy_registers = getattr(meter_cfg.adapter, 'prefer_legacy_registers', False)
        log.info(f"IAMMeter {meter_cfg.id}: prefer_legacy_registers = {self.prefer_legacy_registers} (type: {type(self.prefer_legacy_registers).__name__})")
        
        # Initialize JsonRegisterMixin
        self.regs: List[Dict[str, Any]] = []
        self.addr_offset: int = getattr(meter_cfg.adapter, "addr_offset", 0) or 0
        
        # Load register map from JSON file
        regfile = getattr(meter_cfg.adapter, 'register_map_file', None)
        if regfile:
            try:
                self.load_register_map(regfile)
                log.info(f"Loaded IAMMeter register map: {regfile} ({len(self.regs)} registers)")
            except Exception as e:
                log.warning(f"Could not load IAMMeter register map {regfile}: {e}")
                self.regs = []
        else:
            # Fallback: use default register map path
            import os
            # Path: solarhub/adapters/iammeter.py -> go up 2 levels to project root -> register_maps/
            default_regfile = os.path.join(os.path.dirname(__file__), "..", "..", "register_maps", "iammeter_registers.json")
            default_regfile = os.path.abspath(default_regfile)
            if os.path.exists(default_regfile):
                try:
                    self.load_register_map(default_regfile)
                    log.info(f"Loaded default IAMMeter register map: {default_regfile} ({len(self.regs)} registers)")
                except Exception as e:
                    log.warning(f"Could not load default IAMMeter register map: {e}", exc_info=True)
                    self.regs = []
            else:
                log.warning(f"Default IAMMeter register map not found at: {default_regfile}. Please specify register_map_file in config.")
        
        # Legacy register map for backward compatibility (if JSON not loaded)
        adapter_cfg = meter_cfg.adapter
        self.registers = {
            # Voltage (V) - typically 1 register, scale 10
            "voltage": adapter_cfg.voltage_register if hasattr(adapter_cfg, 'voltage_register') and adapter_cfg.voltage_register is not None else 0x0000,
            "voltage_scale": adapter_cfg.voltage_scale if hasattr(adapter_cfg, 'voltage_scale') and adapter_cfg.voltage_scale is not None else 100,
            
            # Current (A) - typically 1 register, scale 100
            "current": adapter_cfg.current_register if hasattr(adapter_cfg, 'current_register') and adapter_cfg.current_register is not None else 0x0001,
            "current_scale": adapter_cfg.current_scale if hasattr(adapter_cfg, 'current_scale') and adapter_cfg.current_scale is not None else 100,
            
            # Active Power (W) - typically 2 registers (signed 32-bit)
            "power": adapter_cfg.power_register if hasattr(adapter_cfg, 'power_register') and adapter_cfg.power_register is not None else 0x0002,
            
            # Active Energy (kWh) - typically 2 registers (unsigned 32-bit)
            "energy": adapter_cfg.energy_register if hasattr(adapter_cfg, 'energy_register') and adapter_cfg.energy_register is not None else 0x0004,
            "energy_scale": adapter_cfg.energy_scale if hasattr(adapter_cfg, 'energy_scale') and adapter_cfg.energy_scale is not None else 1000,
            
            # Frequency (Hz) - typically 1 register, scale 100
            "frequency": adapter_cfg.frequency_register if hasattr(adapter_cfg, 'frequency_register') and adapter_cfg.frequency_register is not None else 0x0006,
            "frequency_scale": adapter_cfg.frequency_scale if hasattr(adapter_cfg, 'frequency_scale') and adapter_cfg.frequency_scale is not None else 100,
            
            # Power Factor - typically 1 register, scale 1000
            "power_factor": adapter_cfg.power_factor_register if hasattr(adapter_cfg, 'power_factor_register') and adapter_cfg.power_factor_register is not None else 0x0007,
            "power_factor_scale": adapter_cfg.power_factor_scale if hasattr(adapter_cfg, 'power_factor_scale') and adapter_cfg.power_factor_scale is not None else 1000,
        }
        
        # Track last energy reading for daily reset calculation
        self._last_energy_kwh: Optional[float] = None
        self._last_energy_timestamp: Optional[datetime] = None
        self._daily_energy_wh: float = 0.0
        # Track forward and reverse energy separately for import/export
        self._last_forward_energy_kwh: Optional[float] = None
        self._last_reverse_energy_kwh: Optional[float] = None
        self._daily_forward_energy_wh: float = 0.0
        self._daily_reverse_energy_wh: float = 0.0
        
        log.info(f"IAMMeter adapter initialized for {meter_cfg.id} at {self.host}:{self.port} (registers loaded: {len(self.regs)})")
    
    async def connect(self):
        """Connect to IAMMeter via Modbus/TCP."""
        try:
            from pymodbus.client import AsyncModbusTcpClient
            self.client = AsyncModbusTcpClient(
                host=self.host,
                port=self.port,
            )
            ok = await self.client.connect()
            if ok and self.client.connected:
                log.info(f"Connected to IAMMeter {self.meter_cfg.id} at {self.host}:{self.port}")
            else:
                raise RuntimeError(f"Failed to connect to IAMMeter at {self.host}:{self.port}")
        except Exception as e:
            log.error(f"Error connecting to IAMMeter {self.meter_cfg.id}: {e}", exc_info=True)
            raise
    
    async def check_connectivity(self) -> bool:
        """
        Check if IAMMeter device is connected and responding.
        
        Uses serial number register (0x38) as connectivity check since it's
        a reliable register that should always be available.
        """
        try:
            if not self.client or not self.client.connected:
                await self.connect()
            
            if not self.client or not self.client.connected:
                log.debug("IAMMeter client not connected")
                return False
            
            # Try reading serial number register as connectivity check
            # This is more reliable than voltage register and confirms device identity
            try:
                serial_addr = 0x38  # 56 decimal
                result = await self.client.read_holding_registers(
                    address=serial_addr,
                    count=8,  # 8 registers for serial number
                    device_id=self.unit_id
                )
                if result and not result.isError() and result.registers:
                    log.debug("IAMMeter connectivity check passed: device responded with serial number register")
                    return True
            except Exception as e:
                log.debug(f"IAMMeter connectivity check via serial number register failed: {e}")
                # Fallback: try voltage register if serial number read fails
                try:
                    result = await self.client.read_holding_registers(
                        address=self.registers["voltage"],
                        count=1,
                        device_id=self.unit_id
                    )
                    if result and not result.isError() and result.registers:
                        log.debug("IAMMeter connectivity check passed: device responded with voltage register")
                        return True
                except Exception as e2:
                    log.debug(f"IAMMeter connectivity check via voltage register also failed: {e2}")
            
            return False
        except Exception as e:
            log.debug(f"IAMMeter connectivity check failed: {e}")
            return False
    
    async def read_serial_number(self) -> Optional[str]:
        """
        Read device serial number from Modbus holding registers.
        
        IAMMeter serial number is stored at address 0x38 (56 decimal),
        as 8 registers (16 bytes) containing ASCII-encoded serial number.
        
        Returns:
            Serial number string if successfully read, None otherwise
        """
        try:
            if not self.client or not self.client.connected:
                await self.connect()
            
            if not self.client or not self.client.connected:
                log.debug("IAMMeter client not connected, cannot read serial number")
                return None
            
            # Read serial number from address 0x38 (56 decimal), 8 registers
            serial_addr = 0x38  # 56 decimal
            try:
                result = await self.client.read_holding_registers(
                    address=serial_addr,
                    count=8,  # 8 registers = 16 bytes
                    device_id=self.unit_id
                )
                
                if result and not result.isError() and result.registers:
                    # Decode ASCII from registers
                    # Each register is 2 bytes (big-endian)
                    serial_bytes = bytearray()
                    for reg in result.registers:
                        # Extract high and low bytes
                        serial_bytes.append((reg >> 8) & 0xFF)
                        serial_bytes.append(reg & 0xFF)
                    
                    # Convert to string, removing null bytes and whitespace
                    serial_number = serial_bytes.split(b'\x00')[0].decode('ascii', errors='ignore').strip()
                    
                    if serial_number and len(serial_number) >= 3:  # Valid serial number
                        log.info(f"Read IAMMeter serial number: {serial_number}")
                        return serial_number
                    else:
                        log.debug(f"IAMMeter serial number too short or invalid: '{serial_number}'")
                        return None
                else:
                    log.debug("IAMMeter serial number read returned no data or error")
                    return None
                    
            except Exception as e:
                log.warning(f"Error reading IAMMeter serial number from register 0x{serial_addr:02X}: {e}")
                return None
                
        except Exception as e:
            log.warning(f"Error reading IAMMeter serial number: {e}")
            return None
    
    async def close(self):
        """Close Modbus/TCP connection."""
        if self.client:
            try:
                await self.client.close()
            except Exception as e:
                log.warning(f"Error closing IAMMeter connection: {e}")
            self.client = None
            log.info(f"Closed IAMMeter connection for {self.meter_cfg.id}")
    
    def _decode_signed_32bit(self, regs: list) -> int:
        """Decode signed 32-bit integer from two 16-bit registers (big-endian)."""
        if not regs or len(regs) < 2:
            return 0
        # Combine two 16-bit registers into 32-bit
        value = (regs[0] << 16) | regs[1]
        # Check sign bit and convert to signed
        if value & 0x80000000:
            value = value - 0x100000000
        return value
    
    def _decode_unsigned_32bit(self, regs: list) -> int:
        """Decode unsigned 32-bit integer from two 16-bit registers (big-endian)."""
        if not regs or len(regs) < 2:
            return 0
        return (regs[0] << 16) | regs[1]
    
    async def _read_holding_regs(self, address: int, count: int) -> List[int]:
        """
        Read holding registers via Modbus/TCP.
        Required by JsonRegisterMixin.
        """
        if not self.client or not self.client.connected:
            await self.connect()
        
        if not self.client or not self.client.connected:
            raise RuntimeError("IAMMeter client not connected")
        
        result = await self.client.read_holding_registers(
            address=address,
            count=count,
            device_id=self.unit_id
        )
        
        if result.isError():
            raise RuntimeError(f"Modbus read error @{address}")
        
        return list(result.registers) if result.registers else []
    
    async def _write_holding_u16(self, addr: int, value: int) -> None:
        """IAMMeter is read-only, writes not supported."""
        raise NotImplementedError("IAMMeter devices are read-only")
    
    async def _write_holding_u16_list(self, addr: int, values: List[int]) -> None:
        """IAMMeter is read-only, writes not supported."""
        raise NotImplementedError("IAMMeter devices are read-only")
    
    async def poll(self) -> MeterTelemetry:
        """
        Poll IAMMeter device and return Telemetry.
        
        If register map JSON is loaded, reads all registers from the map.
        Otherwise falls back to legacy hardcoded register reading.
        """
        if not self.client or not self.client.connected:
            await self.connect()
        
        try:
            # SECTION 1: Read all registers from JSON map if available
            all_registers_data: Dict[str, Any] = {}
            try:
                if self.regs:
                    try:
                        all_registers_data = await self.read_all_registers()
                        log.debug(f"IAMMeter {self.meter_cfg.id}: Read {len(all_registers_data)} registers from JSON map")
                        # Log all register IDs that were successfully read
                        if all_registers_data:
                            log.debug(f"IAMMeter {self.meter_cfg.id}: Successfully read register IDs: {sorted(all_registers_data.keys())}")
                        # Debug: Log key register values for troubleshooting
                        for reg_id in ["voltage_phase_a_legacy", "voltage_phase_a", "current_phase_a_legacy", "current_phase_a", 
                                     "sum_power_legacy", "total_power", "active_power_phase_a_legacy", "active_power_phase_a",
                                     "frequency_legacy", "frequency"]:
                            if reg_id in all_registers_data:
                                log.debug(f"IAMMeter {self.meter_cfg.id}: {reg_id} = {all_registers_data[reg_id]} (type: {type(all_registers_data[reg_id]).__name__})")
                            else:
                                log.debug(f"IAMMeter {self.meter_cfg.id}: {reg_id} NOT found in all_registers_data")
                    except Exception as e:
                        log.warning(f"IAMMeter {self.meter_cfg.id}: [SECTION 1] Failed to read all registers from JSON map: {e}", exc_info=True)
                        all_registers_data = {}
                else:
                    log.warning(f"IAMMeter {self.meter_cfg.id}: No register map loaded (self.regs is empty)")
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 1] Error in register reading setup: {e}", exc_info=True)
                all_registers_data = {}
            
            # SECTION 2: Extract key values for Telemetry object (use JSON map values if available and non-zero, else fallback)
            # Order depends on prefer_legacy_registers flag
            # Voltage - try legacy first if prefer_legacy_registers is True, else try extended first
            voltage = 0.0
            try:
                if self.prefer_legacy_registers:
                    # Legacy first
                    if "voltage_phase_a_legacy" in all_registers_data and all_registers_data["voltage_phase_a_legacy"] is not None:
                        try:
                            voltage_val = float(all_registers_data["voltage_phase_a_legacy"])
                            if voltage_val != 0.0:
                                voltage = voltage_val
                        except (ValueError, TypeError):
                            pass
                    if voltage == 0.0 and "voltage_phase_a" in all_registers_data and all_registers_data["voltage_phase_a"] is not None:
                        try:
                            voltage_val = float(all_registers_data["voltage_phase_a"])
                            if voltage_val != 0.0:
                                voltage = voltage_val
                        except (ValueError, TypeError):
                            pass
                else:
                    # Extended first (default)
                    if "voltage_phase_a" in all_registers_data and all_registers_data["voltage_phase_a"] is not None:
                        try:
                            voltage_val = float(all_registers_data["voltage_phase_a"])
                            if voltage_val != 0.0:
                                voltage = voltage_val
                        except (ValueError, TypeError):
                            pass
                    if voltage == 0.0 and "voltage_phase_a_legacy" in all_registers_data and all_registers_data["voltage_phase_a_legacy"] is not None:
                        try:
                            voltage_val = float(all_registers_data["voltage_phase_a_legacy"])
                            if voltage_val != 0.0:
                                voltage = voltage_val
                        except (ValueError, TypeError):
                            pass
                if voltage == 0.0 and self.registers.get("voltage") is not None:
                    voltage_reg = await self.client.read_holding_registers(
                        address=self.registers["voltage"], count=1, device_id=self.unit_id
                    )
                    if voltage_reg.registers and voltage_reg.registers[0] != 0:
                        voltage = voltage_reg.registers[0] / float(self.registers["voltage_scale"])
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 2] Error reading voltage: {e}", exc_info=True)
                voltage = 0.0
            
            # SECTION 3: Current - try legacy first if prefer_legacy_registers is True, else try extended first
            # IMPORTANT: Extended registers (72+) may return 0.0 even when legacy registers have valid data
            current = None
            try:
                # Log what current registers are available
                current_reg_ids = ["current_phase_a_legacy", "current_phase_a"]
                available_current_regs = {reg_id: all_registers_data.get(reg_id) for reg_id in current_reg_ids if reg_id in all_registers_data}
                if available_current_regs:
                    log.debug(f"IAMMeter {self.meter_cfg.id}: Available current registers: {available_current_regs}")
                else:
                    log.warning(f"IAMMeter {self.meter_cfg.id}: No current registers found in all_registers_data")
                
                if self.prefer_legacy_registers:
                    # Legacy first
                    if "current_phase_a_legacy" in all_registers_data and all_registers_data["current_phase_a_legacy"] is not None:
                        try:
                            current_val = float(all_registers_data["current_phase_a_legacy"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: current_phase_a_legacy raw value = {current_val}")
                            if current_val >= 0:  # Allow 0 and positive values
                                current = current_val
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert current_phase_a_legacy: {e}")
                            pass
                    if current is None and "current_phase_a" in all_registers_data and all_registers_data["current_phase_a"] is not None:
                        try:
                            current_val = float(all_registers_data["current_phase_a"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: current_phase_a raw value = {current_val}")
                            if current_val >= 0:  # Allow 0 and positive values
                                current = current_val
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert current_phase_a: {e}")
                            pass
                else:
                    # Extended first (default) - but check if value is actually valid (not just 0.0 from uninitialized register)
                    extended_current_read = False
                    if "current_phase_a" in all_registers_data and all_registers_data["current_phase_a"] is not None:
                        try:
                            current_val = float(all_registers_data["current_phase_a"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: current_phase_a raw value = {current_val}")
                            if current_val > 0:  # Only use if positive (extended registers often return 0 when not supported)
                                current = current_val
                                extended_current_read = True
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert current_phase_a: {e}")
                            pass
                    
                    # Fallback to legacy registers if extended returned 0 or None
                    if not extended_current_read:
                        if "current_phase_a_legacy" in all_registers_data and all_registers_data["current_phase_a_legacy"] is not None:
                            try:
                                current_val = float(all_registers_data["current_phase_a_legacy"])
                                log.debug(f"IAMMeter {self.meter_cfg.id}: current_phase_a_legacy raw value = {current_val}")
                                if current_val >= 0:  # Allow 0 and positive values from legacy
                                    current = current_val
                            except (ValueError, TypeError) as e:
                                log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert current_phase_a_legacy: {e}")
                                pass
                    
                    # Final fallback to direct register read
                    if current is None and self.registers.get("current") is not None:
                        log.debug(f"IAMMeter {self.meter_cfg.id}: Trying legacy current register at address {self.registers['current']}")
                        current_reg = await self.client.read_holding_registers(
                            address=self.registers["current"], count=1, device_id=self.unit_id
                        )
                        if current_reg.registers and len(current_reg.registers) > 0:
                            current_raw = current_reg.registers[0]
                            log.debug(f"IAMMeter {self.meter_cfg.id}: Legacy current register raw = {current_raw}")
                            if current_raw is not None:
                                current = current_raw / float(self.registers["current_scale"])
                                log.debug(f"IAMMeter {self.meter_cfg.id}: Legacy current register scaled = {current}")
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 3] Error reading current: {e}", exc_info=True)
                current = None
            
            # SECTION 4: Power - order depends on prefer_legacy_registers flag
            # Power can be negative (export) or positive (import), so we need to accept all values
            # IMPORTANT: Extended registers (72+) may return 0.0 even when legacy registers have valid data
            # We need to check if extended register value is actually 0 (valid reading) vs missing/invalid
            power_w = None
            try:
                # Log what power registers are available
                power_reg_ids = ["sum_power_legacy", "total_power", "active_power_phase_a_legacy", "active_power_phase_a"]
                available_power_regs = {reg_id: all_registers_data.get(reg_id) for reg_id in power_reg_ids if reg_id in all_registers_data}
                if available_power_regs:
                    log.debug(f"IAMMeter {self.meter_cfg.id}: Available power registers: {available_power_regs}")
                else:
                    log.warning(f"IAMMeter {self.meter_cfg.id}: No power registers found in all_registers_data. Available keys: {list(all_registers_data.keys())[:20]}")
                
                if self.prefer_legacy_registers:
                    # Legacy first
                    if "sum_power_legacy" in all_registers_data and all_registers_data["sum_power_legacy"] is not None:
                        try:
                            power_val = int(all_registers_data["sum_power_legacy"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: sum_power_legacy raw value = {power_val}")
                            power_w = power_val  # Accept all values including 0 and negative
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert sum_power_legacy: {e}")
                            pass
                    if power_w is None and "active_power_phase_a_legacy" in all_registers_data and all_registers_data["active_power_phase_a_legacy"] is not None:
                        try:
                            power_val = int(all_registers_data["active_power_phase_a_legacy"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: active_power_phase_a_legacy raw value = {power_val}")
                            power_w = power_val  # Accept all values including 0 and negative
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert active_power_phase_a_legacy: {e}")
                            pass
                    if power_w is None and "total_power" in all_registers_data and all_registers_data["total_power"] is not None:
                        try:
                            power_val = int(all_registers_data["total_power"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: total_power raw value = {power_val}")
                            power_w = power_val  # Accept all values including 0 and negative
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert total_power: {e}")
                            pass
                    if power_w is None and "active_power_phase_a" in all_registers_data and all_registers_data["active_power_phase_a"] is not None:
                        try:
                            power_val = int(all_registers_data["active_power_phase_a"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: active_power_phase_a raw value = {power_val}")
                            power_w = power_val  # Accept all values including 0 and negative
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert active_power_phase_a: {e}")
                            pass
                else:
                    # Extended first (default) - but check if value is actually valid (not just 0.0 from uninitialized register)
                    # Extended registers may return 0.0 when they're not supported, so we need to check legacy if extended is 0
                    extended_power_read = False
                    if "total_power" in all_registers_data and all_registers_data["total_power"] is not None:
                        try:
                            power_val = int(all_registers_data["total_power"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: total_power raw value = {power_val}")
                            if power_val != 0:  # Only use if non-zero (extended registers often return 0 when not supported)
                                power_w = power_val
                                extended_power_read = True
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert total_power: {e}")
                            pass
                    if not extended_power_read and "active_power_phase_a" in all_registers_data and all_registers_data["active_power_phase_a"] is not None:
                        try:
                            power_val = int(all_registers_data["active_power_phase_a"])
                            log.debug(f"IAMMeter {self.meter_cfg.id}: active_power_phase_a raw value = {power_val}")
                            if power_val != 0:  # Only use if non-zero
                                power_w = power_val
                                extended_power_read = True
                        except (ValueError, TypeError) as e:
                            log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert active_power_phase_a: {e}")
                            pass
                    
                    # Fallback to legacy registers if extended returned 0 or None
                    if not extended_power_read:
                        if "sum_power_legacy" in all_registers_data and all_registers_data["sum_power_legacy"] is not None:
                            try:
                                power_val = int(all_registers_data["sum_power_legacy"])
                                log.debug(f"IAMMeter {self.meter_cfg.id}: sum_power_legacy raw value = {power_val}")
                                power_w = power_val  # Accept all values including 0 and negative from legacy
                            except (ValueError, TypeError) as e:
                                log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert sum_power_legacy: {e}")
                                pass
                        if power_w is None and "active_power_phase_a_legacy" in all_registers_data and all_registers_data["active_power_phase_a_legacy"] is not None:
                            try:
                                power_val = int(all_registers_data["active_power_phase_a_legacy"])
                                log.debug(f"IAMMeter {self.meter_cfg.id}: active_power_phase_a_legacy raw value = {power_val}")
                                power_w = power_val  # Accept all values including 0 and negative from legacy
                            except (ValueError, TypeError) as e:
                                log.warning(f"IAMMeter {self.meter_cfg.id}: Failed to convert active_power_phase_a_legacy: {e}")
                                pass
                    
                    # Final fallback to direct register read
                    if power_w is None and self.registers.get("power") is not None:
                        log.debug(f"IAMMeter {self.meter_cfg.id}: Trying legacy power register at address {self.registers['power']}")
                        power_reg = await self.client.read_holding_registers(
                            address=self.registers["power"], count=2, device_id=self.unit_id
                        )
                        if power_reg.registers and len(power_reg.registers) >= 2:
                            decoded_power = self._decode_signed_32bit(power_reg.registers)
                            log.debug(f"IAMMeter {self.meter_cfg.id}: Legacy power register decoded = {decoded_power}")
                            if decoded_power is not None:  # Accept all values including 0 and negative
                                power_w = int(decoded_power)
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 4] Error reading power: {e}", exc_info=True)
                power_w = None
            
            # Log power reading for debugging
            if power_w is not None:
                log.info(f"IAMMeter {self.meter_cfg.id}: Power read = {power_w}W")
            else:
                log.warning(f"IAMMeter {self.meter_cfg.id}: Power could not be read from any register")
            
            # SECTION 5: Energy - order depends on prefer_legacy_registers flag
            energy_kwh = 0.0
            try:
                if self.prefer_legacy_registers:
                    # Legacy first
                    if "sum_forward_energy_pulses" in all_registers_data and all_registers_data["sum_forward_energy_pulses"] is not None:
                        try:
                            energy_val = float(all_registers_data["sum_forward_energy_pulses"])
                            if energy_val != 0.0:
                                energy_kwh = energy_val
                        except (ValueError, TypeError):
                            pass
                    if energy_kwh == 0.0 and "forward_energy_phase_a_pulses" in all_registers_data and all_registers_data["forward_energy_phase_a_pulses"] is not None:
                        try:
                            energy_val = float(all_registers_data["forward_energy_phase_a_pulses"])
                            if energy_val != 0.0:
                                energy_kwh = energy_val
                        except (ValueError, TypeError):
                            pass
                    if energy_kwh == 0.0 and "total_active_energy_forward" in all_registers_data and all_registers_data["total_active_energy_forward"] is not None:
                        try:
                            energy_val = float(all_registers_data["total_active_energy_forward"])
                            if energy_val != 0.0:
                                energy_kwh = energy_val
                        except (ValueError, TypeError):
                            pass
                else:
                    # Extended first (default)
                    if "total_active_energy_forward" in all_registers_data and all_registers_data["total_active_energy_forward"] is not None:
                        try:
                            energy_val = float(all_registers_data["total_active_energy_forward"])
                            if energy_val != 0.0:
                                energy_kwh = energy_val
                        except (ValueError, TypeError):
                            pass
                    if energy_kwh == 0.0 and "sum_forward_energy_pulses" in all_registers_data and all_registers_data["sum_forward_energy_pulses"] is not None:
                        try:
                            energy_val = float(all_registers_data["sum_forward_energy_pulses"])
                            if energy_val != 0.0:
                                energy_kwh = energy_val
                        except (ValueError, TypeError):
                            pass
                    if energy_kwh == 0.0 and "forward_energy_phase_a_pulses" in all_registers_data and all_registers_data["forward_energy_phase_a_pulses"] is not None:
                        try:
                            energy_val = float(all_registers_data["forward_energy_phase_a_pulses"])
                            if energy_val != 0.0:
                                energy_kwh = energy_val
                        except (ValueError, TypeError):
                            pass
                    if energy_kwh == 0.0 and self.registers.get("energy") is not None:
                        energy_reg = await self.client.read_holding_registers(
                            address=self.registers["energy"], count=2, device_id=self.unit_id
                        )
                        if energy_reg.registers and len(energy_reg.registers) >= 2:
                            energy_wh_raw = self._decode_unsigned_32bit(energy_reg.registers)
                            if energy_wh_raw != 0 and self.registers.get("energy_scale") is not None:
                                try:
                                    energy_scale = float(self.registers["energy_scale"])
                                    if energy_scale != 0:
                                        energy_kwh = energy_wh_raw / energy_scale
                                except (ValueError, TypeError, ZeroDivisionError):
                                    pass
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 5] Error reading energy: {e}", exc_info=True)
                energy_kwh = 0.0
            
            # SECTION 6: Frequency - order depends on prefer_legacy_registers flag
            frequency = 50.0  # Default
            try:
                if self.prefer_legacy_registers:
                    # Legacy first
                    if "frequency_legacy" in all_registers_data and all_registers_data["frequency_legacy"] is not None:
                        try:
                            freq_val = float(all_registers_data["frequency_legacy"])
                            if freq_val != 0.0:
                                frequency = freq_val
                        except (ValueError, TypeError):
                            pass
                    if frequency == 50.0 and "frequency" in all_registers_data and all_registers_data["frequency"] is not None:
                        try:
                            freq_val = float(all_registers_data["frequency"])
                            if freq_val != 0.0:
                                frequency = freq_val
                        except (ValueError, TypeError):
                            pass
                else:
                    # Extended first (default)
                    if "frequency" in all_registers_data and all_registers_data["frequency"] is not None:
                        try:
                            freq_val = float(all_registers_data["frequency"])
                            if freq_val != 0.0:
                                frequency = freq_val
                        except (ValueError, TypeError):
                            pass
                    if frequency == 50.0 and "frequency_legacy" in all_registers_data and all_registers_data["frequency_legacy"] is not None:
                        try:
                            freq_val = float(all_registers_data["frequency_legacy"])
                            if freq_val != 0.0:
                                frequency = freq_val
                        except (ValueError, TypeError):
                            pass
                    if frequency == 50.0 and self.registers.get("frequency") is not None:
                        freq_reg = await self.client.read_holding_registers(
                            address=self.registers["frequency"], count=1, device_id=self.unit_id
                        )
                        if freq_reg.registers and freq_reg.registers[0] != 0:
                            frequency = freq_reg.registers[0] / float(self.registers["frequency_scale"])
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 6] Error reading frequency: {e}", exc_info=True)
                frequency = 50.0
            
            # SECTION 7: Power Factor - order depends on prefer_legacy_registers flag
            power_factor = 1.0  # Default
            try:
                if self.prefer_legacy_registers:
                    # Legacy first
                    if "power_factor_phase_a_legacy" in all_registers_data and all_registers_data["power_factor_phase_a_legacy"] is not None:
                        try:
                            pf_val = float(all_registers_data["power_factor_phase_a_legacy"])
                            if pf_val != 0.0:
                                power_factor = pf_val
                        except (ValueError, TypeError):
                            pass
                    if power_factor == 1.0 and "power_factor_phase_a" in all_registers_data and all_registers_data["power_factor_phase_a"] is not None:
                        try:
                            pf_val = float(all_registers_data["power_factor_phase_a"])
                            if pf_val != 0.0:
                                power_factor = pf_val
                        except (ValueError, TypeError):
                            pass
                else:
                    # Extended first (default)
                    if "power_factor_phase_a" in all_registers_data and all_registers_data["power_factor_phase_a"] is not None:
                        try:
                            pf_val = float(all_registers_data["power_factor_phase_a"])
                            if pf_val != 0.0:
                                power_factor = pf_val
                        except (ValueError, TypeError):
                            pass
                    if power_factor == 1.0 and "power_factor_phase_a_legacy" in all_registers_data and all_registers_data["power_factor_phase_a_legacy"] is not None:
                        try:
                            pf_val = float(all_registers_data["power_factor_phase_a_legacy"])
                            if pf_val != 0.0:
                                power_factor = pf_val
                        except (ValueError, TypeError):
                            pass
                    if power_factor == 1.0 and self.registers.get("power_factor") is not None:
                        pf_reg = await self.client.read_holding_registers(
                            address=self.registers["power_factor"], count=1, device_id=self.unit_id
                        )
                        if pf_reg.registers and pf_reg.registers[0] != 0:
                            power_factor = pf_reg.registers[0] / float(self.registers["power_factor_scale"])
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 7] Error reading power factor: {e}", exc_info=True)
                power_factor = 1.0
            
            # SECTION 8: Read forward and reverse energy directly from registers
            # Forward energy = import (consuming from grid)
            # Reverse energy = export (feeding to grid)
            forward_energy_kwh = 0.0
            reverse_energy_kwh = 0.0
            try:
                if self.prefer_legacy_registers:
                    # Legacy first - read sum values
                    if "sum_forward_energy_pulses" in all_registers_data and all_registers_data["sum_forward_energy_pulses"] is not None:
                        try:
                            val = float(all_registers_data["sum_forward_energy_pulses"])
                            if val > 0:
                                forward_energy_kwh = val
                        except (ValueError, TypeError):
                            pass
                    if "sum_reverse_energy_pulses" in all_registers_data and all_registers_data["sum_reverse_energy_pulses"] is not None:
                        try:
                            val = float(all_registers_data["sum_reverse_energy_pulses"])
                            if val > 0:
                                reverse_energy_kwh = val
                        except (ValueError, TypeError):
                            pass
                else:
                    # Extended first
                    if "total_active_energy_forward" in all_registers_data and all_registers_data["total_active_energy_forward"] is not None:
                        try:
                            val = float(all_registers_data["total_active_energy_forward"])
                            if val > 0:
                                forward_energy_kwh = val
                        except (ValueError, TypeError):
                            pass
                    if "total_active_energy_reverse" in all_registers_data and all_registers_data["total_active_energy_reverse"] is not None:
                        try:
                            val = float(all_registers_data["total_active_energy_reverse"])
                            if val > 0:
                                reverse_energy_kwh = val
                        except (ValueError, TypeError):
                            pass
                    # Fallback to legacy if extended is zero
                    if forward_energy_kwh == 0.0 and "sum_forward_energy_pulses" in all_registers_data and all_registers_data["sum_forward_energy_pulses"] is not None:
                        try:
                            val = float(all_registers_data["sum_forward_energy_pulses"])
                            if val > 0:
                                forward_energy_kwh = val
                        except (ValueError, TypeError):
                            pass
                    if reverse_energy_kwh == 0.0 and "sum_reverse_energy_pulses" in all_registers_data and all_registers_data["sum_reverse_energy_pulses"] is not None:
                        try:
                            val = float(all_registers_data["sum_reverse_energy_pulses"])
                            if val > 0:
                                reverse_energy_kwh = val
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 8] Error reading forward/reverse energy: {e}", exc_info=True)
            
            # SECTION 9: Calculate daily import/export energy (track reset at midnight)
            now = datetime.now()
            grid_import_wh = 0
            grid_export_wh = 0
            try:
                # Check if we've crossed midnight - reset daily counters
                if self._last_energy_timestamp is not None:
                    if now.date() != self._last_energy_timestamp.date():
                        # New day - reset daily energy
                        self._daily_forward_energy_wh = 0.0
                        self._daily_reverse_energy_wh = 0.0
                        log.info(f"IAMMeter {self.meter_cfg.id}: Daily energy reset for new day")
                
                # Calculate daily forward energy (import)
                if forward_energy_kwh > 0:
                    if self._last_forward_energy_kwh is not None:
                        forward_delta_kwh = forward_energy_kwh - self._last_forward_energy_kwh
                        if forward_delta_kwh >= 0:  # Only count positive changes (avoid rollover)
                            self._daily_forward_energy_wh += forward_delta_kwh * 1000  # Convert to Wh
                        else:
                            # Energy decreased (possible rollover) - reset to current value
                            self._daily_forward_energy_wh = forward_energy_kwh * 1000
                    else:
                        # First reading - start with current value
                        self._daily_forward_energy_wh = forward_energy_kwh * 1000
                    grid_import_wh = int(self._daily_forward_energy_wh)
                    self._last_forward_energy_kwh = forward_energy_kwh
                
                # Calculate daily reverse energy (export)
                if reverse_energy_kwh > 0:
                    if self._last_reverse_energy_kwh is not None:
                        reverse_delta_kwh = reverse_energy_kwh - self._last_reverse_energy_kwh
                        if reverse_delta_kwh >= 0:  # Only count positive changes (avoid rollover)
                            self._daily_reverse_energy_wh += reverse_delta_kwh * 1000  # Convert to Wh
                        else:
                            # Energy decreased (possible rollover) - reset to current value
                            self._daily_reverse_energy_wh = reverse_energy_kwh * 1000
                    else:
                        # First reading - start with current value
                        self._daily_reverse_energy_wh = reverse_energy_kwh * 1000
                    grid_export_wh = int(self._daily_reverse_energy_wh)
                    self._last_reverse_energy_kwh = reverse_energy_kwh
                
                # Update timestamp
                self._last_energy_timestamp = now
                
                log.debug(f"IAMMeter {self.meter_cfg.id}: Forward={forward_energy_kwh}kWh, Reverse={reverse_energy_kwh}kWh, "
                         f"Daily Import={grid_import_wh}Wh, Daily Export={grid_export_wh}Wh")
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 9] Error calculating daily import/export: {e}", exc_info=True)
                grid_import_wh = 0
                grid_export_wh = 0
            
            # SECTION 10: Create Telemetry object with all register data in extra field
            try:
                extra_data: Dict[str, Any] = {
                    "power_factor": power_factor,
                    "energy_kwh": energy_kwh,
                    "device_type": "iammeter",
                    "host": self.host,
                    "port": self.port,
                }
                
                # Include all registers from JSON map in extra field
                if all_registers_data:
                    extra_data["registers"] = all_registers_data
                    log.debug(f"IAMMeter {self.meter_cfg.id}: Including {len(all_registers_data)} register values in telemetry")
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 10] Error creating extra_data: {e}", exc_info=True)
                extra_data = {"device_type": "iammeter", "error": str(e)}
            
            # SECTION 11: Ensure all values are not None before creating Telemetry
            try:
                # Set defaults only if values are truly None (not if they're 0)
                if voltage is None:
                    voltage = 0.0
                # current can remain None if not read
                if frequency is None:
                    frequency = 50.0
                if energy_kwh is None:
                    energy_kwh = 0.0
                # power_w can remain None if not read (will be set to 0 later for telemetry)
                
                # Safe comparisons - ensure values are not None and are numbers before comparing
                # Convert to float first to ensure they're numbers
                grid_voltage_v = None
                try:
                    if voltage is not None:
                        voltage_float = float(voltage)
                        if voltage_float > 0:  # Voltage should be positive
                            grid_voltage_v = voltage_float
                except (ValueError, TypeError):
                    grid_voltage_v = None
                
                grid_current_a = None
                try:
                    if current is not None:
                        current_float = float(current)
                        if current_float >= 0:  # Current can be 0 or positive (allow 0)
                            grid_current_a = current_float
                except (ValueError, TypeError):
                    grid_current_a = None
                
                # Log current reading for debugging
                if grid_current_a is not None:
                    log.debug(f"IAMMeter {self.meter_cfg.id}: Current read = {grid_current_a}A")
                else:
                    log.warning(f"IAMMeter {self.meter_cfg.id}: Current could not be read (current={current})")
                
                grid_frequency_hz = None
                try:
                    if frequency is not None:
                        frequency_float = float(frequency)
                        if frequency_float > 0:
                            grid_frequency_hz = frequency_float
                except (ValueError, TypeError):
                    grid_frequency_hz = None
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 11] Error preparing telemetry values: {e}", exc_info=True)
                grid_voltage_v = None
                grid_current_a = None
                grid_frequency_hz = None
            
            # SECTION 12: Extract phase-specific data from all_registers_data
            voltage_phase_a = None
            voltage_phase_b = None
            voltage_phase_c = None
            current_phase_a = None
            current_phase_b = None
            current_phase_c = None
            power_phase_a = None
            power_phase_b = None
            power_phase_c = None
            
            try:
                # Read phase-specific voltage
                if "voltage_phase_a_legacy" in all_registers_data:
                    try:
                        val = float(all_registers_data["voltage_phase_a_legacy"])
                        if val > 0:
                            voltage_phase_a = val
                    except (ValueError, TypeError):
                        pass
                if "voltage_phase_b_legacy" in all_registers_data:
                    try:
                        val = float(all_registers_data["voltage_phase_b_legacy"])
                        if val > 0:
                            voltage_phase_b = val
                    except (ValueError, TypeError):
                        pass
                if "voltage_phase_c_legacy" in all_registers_data:
                    try:
                        val = float(all_registers_data["voltage_phase_c_legacy"])
                        if val > 0:
                            voltage_phase_c = val
                    except (ValueError, TypeError):
                        pass
                
                # Read phase-specific current
                if "current_phase_a_legacy" in all_registers_data:
                    try:
                        val = float(all_registers_data["current_phase_a_legacy"])
                        if val > 0:
                            current_phase_a = val
                    except (ValueError, TypeError):
                        pass
                if "current_phase_b_legacy" in all_registers_data:
                    try:
                        val = float(all_registers_data["current_phase_b_legacy"])
                        if val > 0:
                            current_phase_b = val
                    except (ValueError, TypeError):
                        pass
                if "current_phase_c_legacy" in all_registers_data:
                    try:
                        val = float(all_registers_data["current_phase_c_legacy"])
                        if val > 0:
                            current_phase_c = val
                    except (ValueError, TypeError):
                        pass
                
                # Read phase-specific power
                if "active_power_phase_a_legacy" in all_registers_data:
                    try:
                        val = int(all_registers_data["active_power_phase_a_legacy"])
                        if val != 0:
                            power_phase_a = val
                    except (ValueError, TypeError):
                        pass
                if "active_power_phase_b_legacy" in all_registers_data:
                    try:
                        val = int(all_registers_data["active_power_phase_b_legacy"])
                        if val != 0:
                            power_phase_b = val
                    except (ValueError, TypeError):
                        pass
                if "active_power_phase_c_legacy" in all_registers_data:
                    try:
                        val = int(all_registers_data["active_power_phase_c_legacy"])
                        if val != 0:
                            power_phase_c = val
                    except (ValueError, TypeError):
                        pass
                
                # Use average voltage if available, or fall back to phase A
                if grid_voltage_v is None or grid_voltage_v == 0:
                    voltages = [v for v in [voltage_phase_a, voltage_phase_b, voltage_phase_c] if v is not None and v > 0]
                    if voltages:
                        grid_voltage_v = sum(voltages) / len(voltages)
                    elif voltage_phase_a is not None and voltage_phase_a > 0:
                        grid_voltage_v = voltage_phase_a
                
                # Sum current from all phases
                if grid_current_a is None or grid_current_a == 0:
                    currents = [c for c in [current_phase_a, current_phase_b, current_phase_c] if c is not None and c > 0]
                    if currents:
                        grid_current_a = sum(currents)
                    elif current_phase_a is not None and current_phase_a > 0:
                        grid_current_a = current_phase_a
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 12a] Error extracting phase data: {e}", exc_info=True)
            
            # SECTION 12: Create and return MeterTelemetry object
            try:
                # Ensure power_w is an integer (0 if None, otherwise use value)
                final_power_w = int(power_w) if power_w is not None else 0
                
                telemetry = MeterTelemetry(
                    ts=now_configured_iso(),
                    id=self.meter_cfg.id,
                    grid_power_w=final_power_w,
                    grid_voltage_v=grid_voltage_v,
                    grid_current_a=grid_current_a,
                    grid_frequency_hz=grid_frequency_hz,
                    grid_import_wh=grid_import_wh,
                    grid_export_wh=grid_export_wh,
                    energy_kwh=energy_kwh,
                    power_factor=power_factor,
                    voltage_phase_a=voltage_phase_a,
                    voltage_phase_b=voltage_phase_b,
                    voltage_phase_c=voltage_phase_c,
                    current_phase_a=current_phase_a,
                    current_phase_b=current_phase_b,
                    current_phase_c=current_phase_c,
                    power_phase_a=power_phase_a,
                    power_phase_b=power_phase_b,
                    power_phase_c=power_phase_c,
                    array_id=self.meter_cfg.array_id,
                    extra=extra_data
                )
                
                log.debug(
                    f"IAMMeter {self.meter_cfg.id} poll: "
                    f"Power={power_w}W, Voltage={voltage}V, Current={current}A, "
                    f"Energy={energy_kwh}kWh, ImportΔ={grid_import_wh}Wh, ExportΔ={grid_export_wh}Wh"
                )
                
                return telemetry
            except Exception as e:
                log.error(f"IAMMeter {self.meter_cfg.id}: [SECTION 12] Error creating MeterTelemetry object: {e}", exc_info=True)
                # Return minimal telemetry on error
                return MeterTelemetry(
                    ts=now_configured_iso(),
                    id=self.meter_cfg.id,
                    array_id=self.meter_cfg.array_id,
                    extra={"error": str(e), "device_type": "iammeter", "section": "12"}
                )
            
        except Exception as e:
            log.error(f"Error polling IAMMeter {self.meter_cfg.id}: {e}", exc_info=True)
            # Return minimal telemetry on error
            return MeterTelemetry(
                ts=now_configured_iso(),
                id=self.meter_cfg.id,
                array_id=self.meter_cfg.array_id,
                extra={"error": str(e), "device_type": "iammeter"}
            )

