"""
JK BMS Bluetooth Low-Energy (BLE) Adapter

Based on batmon-ha project (https://github.com/fl4p/batmon-ha).
Connects to JK BMS devices via Bluetooth Low-Energy using the JK02 protocol.

Key Features:
- Connects via BLE (no USB/Serial/RS485 needed)
- Supports multiple batteries, each with its own MAC address
- Supports JK02 protocol (24s and 32s versions)
- Reads cell voltages, temperatures, SOC, current, power, etc.
- Can control charge/discharge/balance switches

References:
- https://github.com/fl4p/batmon-ha
- https://github.com/jblance/mpp-solar/blob/master/mppsolar/protocols/jk02.py
- https://github.com/syssi/esphome-jk-bms
"""

import asyncio
import logging
import time
from typing import Optional, Dict, List, Tuple, Any, TYPE_CHECKING, Union
from collections import defaultdict
from typing import Callable

try:
    from bleak import BleakClient, BleakScanner
    from bleak.backends.characteristic import BleakGATTCharacteristic
    import bleak.exc
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    # Define dummy types for type hints when bleak is not available
    BleakGATTCharacteristic = Any
    BleakClient = Any
    BleakScanner = Any

from solarhub.adapters.base import BatteryAdapter
from solarhub.config import BatteryBankConfig
from solarhub.schedulers.models import BatteryBankTelemetry, BatteryUnit
from solarhub.timezone_utils import now_configured_iso

log = logging.getLogger(__name__)

# JK BMS BLE Constants
SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
HEADER_RESPONSE = bytes([0x55, 0xAA, 0xEB, 0x90])
HEADER_COMMAND = bytes([0xAA, 0x55, 0x90, 0xEB])
MIN_RESPONSE_SIZE = 300
MAX_RESPONSE_SIZE = 320
TIMEOUT = 8.0


def calc_crc(message_bytes: bytes) -> int:
    """Calculate JK BMS CRC (simple sum)."""
    return sum(message_bytes) & 0xFF


def _jk_command(address: int, value: List[int] = ()) -> bytes:
    """Build JK BMS command frame."""
    n = len(value)
    assert n <= 13, f"val {value} too long"
    frame = bytes([0xAA, 0x55, 0x90, 0xEB, address, n])
    frame += bytes(value)
    frame += bytes([0] * (13 - n))
    frame += bytes([calc_crc(frame)])
    return frame


def read_str(buf: bytes, offset: int, encoding: str = 'utf-8') -> str:
    """Read null-terminated string from buffer."""
    try:
        end = buf.index(0x00, offset)
        return buf[offset:end].decode(encoding=encoding)
    except (ValueError, IndexError):
        return ""


class FuturesPool:
    """Simple futures pool for managing async responses."""
    def __init__(self):
        self._futures: Dict[Any, asyncio.Future] = {}
        self._results: Dict[Any, Any] = {}
    
    def set_result(self, key: Any, value: Any):
        """Set result for a key."""
        self._results[key] = value
        if key in self._futures:
            if not self._futures[key].done():
                self._futures[key].set_result(value)
    
    async def wait_for(self, key: Any, timeout: float):
        """Wait for result with timeout."""
        if key in self._results:
            return self._results[key]
        
        if key not in self._futures:
            self._futures[key] = asyncio.Future()
        
        try:
            return await asyncio.wait_for(self._futures[key], timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Timeout waiting for response {key}")
    
    async def acquire_timeout(self, key: Any, timeout: float):
        """Context manager for acquiring and waiting."""
        class Context:
            def __init__(self, pool, key):
                self.pool = pool
                self.key = key
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
        return Context(self, key)
    
    def clear(self):
        """Clear all futures and results."""
        self._futures.clear()
        self._results.clear()


class JKBMSBleBattery:
    """Represents a single JK BMS battery connected via Bluetooth."""
    
    def __init__(self, address: str, battery_id: int, bt_adapter: Optional[str], bt_pin: Optional[str], 
                 bt_keep_alive: bool, bt_timeout: float):
        self.address = address
        self.battery_id = battery_id
        self.bt_adapter = bt_adapter
        self.bt_pin = bt_pin
        self.bt_keep_alive = bt_keep_alive
        self.bt_timeout = bt_timeout
        
        self.client: Optional[BleakClient] = None
        self._buffer = bytearray()
        self._resp_table: Dict[int, Tuple[bytearray, float]] = {}
        self._fetch_futures = FuturesPool()
        self._callbacks: Dict[int, List[Callable[[bytes], None]]] = defaultdict(list)
        self.char_handle_notify: Optional[Any] = None
        self.char_handle_write: Optional[Any] = None
        self.num_cells: Optional[int] = None
        self.is_new_11fw_32s: Optional[bool] = None
        self._has_float_charger: Optional[bool] = None
        self._connect_time = 0.0
    
    async def connect(self):
        """Connect to this battery via Bluetooth."""
        if not BLEAK_AVAILABLE:
            raise ImportError("bleak package is required for Bluetooth support")
        
        try:
            kwargs = {}
            if self.bt_adapter:
                kwargs['adapter'] = self.bt_adapter
            
            self.client = BleakClient(
                self.address,
                disconnected_callback=self._on_disconnect,
                **kwargs
            )
            
            try:
                await asyncio.wait_for(self.client.connect(timeout=self.bt_timeout), timeout=self.bt_timeout + 1)
            except (getattr(bleak.exc, 'BleakDeviceNotFoundError', bleak.exc.BleakError), Exception) as e:
                error_msg = str(e)
                # Check if it's a "Operation already in progress" error - don't retry with scanner
                if "InProgress" in error_msg or "already in progress" in error_msg.lower():
                    log.warning(f"Battery {self.battery_id} ({self.address}): BlueZ operation already in progress, will retry later")
                    raise  # Re-raise to be handled by caller
                log.info(f"Battery {self.battery_id} ({self.address}): Normal connect failed ({e}), trying with scanner")
                await self._connect_with_scanner()
            
            # Find service and characteristics
            service = None
            for s in self.client.services:
                if s.uuid.startswith(SERVICE_UUID.split('-')[0]):
                    service = s
                    break
            
            if not service:
                raise RuntimeError(f"Service {SERVICE_UUID} not found")
            
            # Find write characteristic
            self.char_handle_write = None
            for char in service.characteristics:
                if char.uuid == CHAR_UUID or (hasattr(char, 'handle') and char.handle == 0x03):
                    if 'write' in char.properties:
                        self.char_handle_write = char
                        break
            
            if not self.char_handle_write:
                raise RuntimeError(f"Write characteristic {CHAR_UUID} not found")
            
            # Find notify characteristic
            self.char_handle_notify = None
            for char in service.characteristics:
                if hasattr(char, 'handle') and char.handle == 0x05:
                    if 'notify' in char.properties:
                        self.char_handle_notify = char
                        break
            
            if not self.char_handle_notify:
                for char in service.characteristics:
                    if char.uuid == CHAR_UUID and 'notify' in char.properties:
                        self.char_handle_notify = char
                        break
            
            if not self.char_handle_notify:
                raise RuntimeError(f"Notify characteristic not found")
            
            # Start notifications
            await self.client.start_notify(self.char_handle_notify, self._notification_handler)
            
            # Initialize device
            await self._q(cmd=0x97, resp=0x03)  # Device info
            await self._q(cmd=0x96, resp=(0x02, 0x01))  # Device state
            
            # Get number of cells
            if 0x01 in self._resp_table:
                buf, _ = self._resp_table[0x01]
                self.num_cells = buf[114] if len(buf) > 114 else 16
                assert 0 < self.num_cells <= 24, f"num_cells unexpected {self.num_cells}"
            
            self._connect_time = time.time()
            log.info(f"Connected to JK BMS battery {self.battery_id} via BLE at {self.address}")
            
        except Exception as e:
            log.error(f"Failed to connect to battery {self.battery_id} ({self.address}): {e}", exc_info=True)
            if self.client:
                try:
                    await self.client.disconnect()
                except:
                    pass
                self.client = None
            raise
    
    async def _connect_with_scanner(self):
        """Connect using scanner."""
        log.info(f"Scanning for battery {self.battery_id} ({self.address})...")
        # Wait before scanning to avoid conflicts with other Bluetooth operations
        await asyncio.sleep(2.0)
        try:
            devices = await BleakScanner.discover(timeout=5.0)
            
            # Log all discovered devices for debugging
            if devices:
                log.info(f"Found {len(devices)} Bluetooth device(s) during scan:")
                for device in devices:
                    name = device.name if hasattr(device, 'name') and device.name else "Unknown"
                    address = device.address if hasattr(device, 'address') else "Unknown"
                    rssi = device.rssi if hasattr(device, 'rssi') else None
                    rssi_str = f", RSSI: {rssi} dBm" if rssi is not None else ""
                    log.info(f"  - Address: {address}, Name: {name}{rssi_str}")
                    
                    # Check if this is our target device
                    if address.upper() == self.address.upper():
                        log.info(f"  ✓ Found target device: {self.address} ({name})")
            else:
                log.warning(f"No Bluetooth devices found during scan (looking for {self.address})")
            
            # Check if target device was found
            target_found = any(
                device.address.upper() == self.address.upper() 
                for device in devices 
                if hasattr(device, 'address')
            )
            
            if not target_found:
                log.error(f"Target device {self.address} not found in scan results. Available devices listed above.")
                raise bleak.exc.BleakDeviceNotFoundError(
                    self.address, 
                    f"Device with address {self.address} was not found in scan results"
                )
            
            # Wait after scanning before connecting
            await asyncio.sleep(1.0)
            await asyncio.wait_for(self.client.connect(timeout=self.bt_timeout), timeout=self.bt_timeout + 1)
        except Exception as e:
            error_msg = str(e)
            if "InProgress" in error_msg or "already in progress" in error_msg.lower():
                log.warning(f"Battery {self.battery_id} ({self.address}): Scanner operation in progress, will retry later")
            raise
    
    def _on_disconnect(self, client):
        """Handle Bluetooth disconnection."""
        if self.bt_keep_alive and self._connect_time:
            log.warning(f"Battery {self.battery_id} BLE disconnected after {time.time() - self._connect_time:.1f}s")
        self._fetch_futures.clear()
    
    def _notification_handler(self, sender: Any, data: bytearray):
        """Handle BLE notification data."""
        if data[0:4] == HEADER_RESPONSE:
            self._buffer.clear()
        
        self._buffer += data
        
        if len(self._buffer) >= MIN_RESPONSE_SIZE:
            if len(self._buffer) > MAX_RESPONSE_SIZE:
                log.warning(f"Battery {self.battery_id}: Buffer longer than expected {len(self._buffer)} bytes")
            
            crc_comp = calc_crc(self._buffer[0:MIN_RESPONSE_SIZE - 1])
            crc_expected = self._buffer[MIN_RESPONSE_SIZE - 1]
            
            if crc_comp != crc_expected:
                if HEADER_RESPONSE in self._buffer:
                    idx = self._buffer.index(HEADER_RESPONSE)
                    self._buffer = self._buffer[idx:]
                    crc_comp = calc_crc(self._buffer[0:MIN_RESPONSE_SIZE - 1])
                    crc_expected = self._buffer[MIN_RESPONSE_SIZE - 1]
            
            if crc_comp == crc_expected:
                self._decode_msg(bytearray(self._buffer))
            else:
                log.error(f"Battery {self.battery_id}: CRC check failed")
            
            self._buffer.clear()
    
    def _decode_msg(self, buf: bytearray):
        """Decode received message."""
        if len(buf) < 5:
            return
        
        resp_type = buf[4]
        self._resp_table[resp_type] = (buf, time.time())
        self._fetch_futures.set_result(resp_type, buf)
        
        callbacks = self._callbacks.get(resp_type, [])
        for cb in callbacks:
            try:
                cb(buf)
            except Exception as e:
                log.error(f"Battery {self.battery_id} callback error: {e}")
    
    async def _q(self, cmd: int, resp):
        """Send query command and wait for response."""
        await asyncio.sleep(0.1)
        
        resp_keys = (resp,) if not isinstance(resp, tuple) else resp
        
        frame = _jk_command(cmd, [])
        await self.client.write_gatt_char(self.char_handle_write, data=frame)
        
        for resp_key in resp_keys:
            try:
                return await self._fetch_futures.wait_for(resp_key, self.bt_timeout)
            except TimeoutError:
                continue
        raise TimeoutError(f"No response received for command {cmd}")
    
    async def close(self):
        """Close Bluetooth connection."""
        if self.client:
            try:
                if self.char_handle_notify:
                    await self.client.stop_notify(self.char_handle_notify)
                await self.client.disconnect()
            except Exception as e:
                log.warning(f"Error closing battery {self.battery_id} BLE connection: {e}")
            self.client = None
    
    def _decode_sample(self, buf: bytearray, t_buf: float) -> Dict[str, Any]:
        """Decode BMS sample from response buffer."""
        if 0x01 not in self._resp_table:
            return {}
        
        buf_set, _ = self._resp_table[0x01]
        
        offset = 0
        if self.is_new_11fw_32s is None:
            self.is_new_11fw_32s = True
        
        if self.is_new_11fw_32s:
            offset = 32
        
        i16 = lambda i: int.from_bytes(buf[i:(i + 2)], byteorder='little', signed=True)
        u32 = lambda i: int.from_bytes(buf[i:(i + 4)], byteorder='little', signed=False)
        f32u = lambda i: u32(i) * 1e-3
        f32s = lambda i: int.from_bytes(buf[i:(i + 4)], byteorder='little', signed=True) * 1e-3
        
        temp = lambda x: None if x == -2000 else (x / 10.0)
        
        temperatures = [temp(i16(130 + offset)), temp(i16(132 + offset))]
        if self.is_new_11fw_32s:
            temperatures += [temp(i16(224 + offset)), temp(i16(226 + offset))]
        
        cell_voltages = []
        if self.num_cells:
            for i in range(self.num_cells):
                offset_cell = 6 + (i * 2)
                if offset_cell + 2 <= len(buf):
                    voltage = int.from_bytes(buf[offset_cell:offset_cell + 2], byteorder='little', signed=False) / 1000.0
                    if 2.0 <= voltage <= 4.5:
                        cell_voltages.append(round(voltage, 3))
                    else:
                        cell_voltages.append(None)
                else:
                    cell_voltages.append(None)
        
        return {
            'voltage': f32u(118 + offset),
            'current': f32s(126 + offset),  # Inverted: positive = charging, negative = discharging
            'soc': buf[141 + offset] if len(buf) > 141 + offset else None,
            'remaining_capacity': f32u(142 + offset),
            'total_capacity': f32u(146 + offset),
            'cycle_capacity': f32u(154 + offset),
            'num_cycles': u32(150 + offset),
            'temperatures': temperatures,
            'mos_temp': i16((112 if self.is_new_11fw_32s else 134) + offset) / 10.0,
            'balance_current': i16(138 + offset) / 1000.0,
            'uptime': float(u32(162 + offset)),
            'cell_voltages': cell_voltages,
            'charge_switch': bool(buf_set[118]) if len(buf_set) > 118 else None,
            'discharge_switch': bool(buf_set[122]) if len(buf_set) > 122 else None,
            'balance_switch': bool(buf_set[126]) if len(buf_set) > 126 else None,
        }
    
    async def poll(self) -> Dict[str, Any]:
        """Poll this battery and return sample data."""
        if not self.client or not self.client.is_connected:
            try:
                await self.connect()
            except Exception as e:
                # If connection fails, log and return empty data
                log.warning(f"Battery {self.battery_id} ({self.address}) connection failed during poll: {e}")
                return {}
        
        if 0x02 not in self._resp_table:
            await self._q(cmd=0x96, resp=0x02)
        
        if self.is_new_11fw_32s is None:
            try:
                await self._q(cmd=0x97, resp=0x03)
                if 0x03 in self._resp_table:
                    buf, _ = self._resp_table[0x03]
                    sw_version_str = read_str(buf, 6 + 16 + 8)
                    if sw_version_str:
                        try:
                            fw_major = int(sw_version_str.split('.')[0])
                            self.is_new_11fw_32s = fw_major >= 11
                            log.info(f"Battery {self.battery_id} firmware {sw_version_str}, using {'32s' if self.is_new_11fw_32s else '24s'} protocol")
                        except:
                            self.is_new_11fw_32s = True
            except Exception as e:
                log.warning(f"Battery {self.battery_id}: Could not determine firmware version: {e}")
                self.is_new_11fw_32s = True
        
        if 0x02 not in self._resp_table:
            raise RuntimeError(f"No status data available for battery {self.battery_id}")
        
        buf, t_buf = self._resp_table[0x02]
        return self._decode_sample(buf, t_buf)


class JKBMSBleAdapter(BatteryAdapter):
    """
    JK BMS Bluetooth Low-Energy Adapter
    
    Connects to one or more JK BMS devices via BLE using the JK02 protocol.
    Supports both 24s (firmware < 11.x) and 32s (firmware >= 11.x) versions.
    
    Can handle multiple batteries, each with its own Bluetooth MAC address.
    """
    
    def __init__(self, bank_cfg: BatteryBankConfig):
        super().__init__(bank_cfg)
        
        if not BLEAK_AVAILABLE:
            raise ImportError("bleak package is required for Bluetooth support. Install with: pip install bleak")
        
        self.last_tel: Optional[BatteryBankTelemetry] = None
        
        cfg = bank_cfg.adapter
        
        # Support both single address and list of addresses
        if cfg.bt_addresses:
            self.bt_addresses = cfg.bt_addresses
        elif cfg.bt_address:
            self.bt_addresses = [cfg.bt_address]
        else:
            raise ValueError("Either bt_address or bt_addresses is required for jkbms_ble adapter")
        
        self.bt_adapter = cfg.bt_adapter
        self.bt_pin = cfg.bt_pin
        self.bt_keep_alive = getattr(cfg, 'bt_keep_alive', True)
        self.bt_timeout = getattr(cfg, 'bt_timeout', TIMEOUT)
        
        # Create a battery object for each MAC address
        self.batteries: Dict[int, JKBMSBleBattery] = {}
        for idx, address in enumerate(self.bt_addresses):
            self.batteries[idx] = JKBMSBleBattery(
                address=address,
                battery_id=idx,
                bt_adapter=self.bt_adapter,
                bt_pin=self.bt_pin,
                bt_keep_alive=self.bt_keep_alive,
                bt_timeout=self.bt_timeout
            )
        
        log.info(f"JKBMS BLE Adapter initialized for {len(self.batteries)} battery/batteries: {self.bt_addresses}")
    
    async def connect(self):
        """Connect to all batteries via Bluetooth."""
        # Connect to batteries sequentially to avoid BlueZ "Operation already in progress" errors
        # BlueZ doesn't allow multiple simultaneous scan/connect operations
        connected = 0
        failed = []
        
        for battery_id, battery in sorted(self.batteries.items()):
            try:
                # Add delay between connections to avoid BlueZ conflicts
                if connected > 0:
                    await asyncio.sleep(2.0)  # Wait 2 seconds between connections
                
                await battery.connect()
                connected += 1
                log.info(f"Successfully connected to battery {battery_id} ({battery.address})")
            except Exception as e:
                error_msg = str(e)
                # Check if it's a "Operation already in progress" error
                if "InProgress" in error_msg or "already in progress" in error_msg.lower():
                    log.warning(f"Battery {battery_id} ({battery.address}): BlueZ operation in progress, will retry later")
                    # Don't count this as a failure - we'll retry on next poll
                else:
                    log.error(f"Failed to connect to battery {battery_id} ({battery.address}): {e}")
                    failed.append((battery_id, battery.address, error_msg))
        
        if connected == 0:
            # If all batteries failed and they're all "not found", try power cycling Bluetooth
            all_not_found = all("not found" in err.lower() for _, _, err in failed)
            if all_not_found and len(failed) > 0:
                adapter_name = self.bt_adapter or "hci0"
                log.warning(f"All batteries not found. Attempting Bluetooth power cycle on {adapter_name}...")
                power_cycle_success = await self.power_cycle_bluetooth(adapter_name)
                if power_cycle_success:
                    log.info("Bluetooth power cycle completed. Retrying connections...")
                    await asyncio.sleep(3.0)  # Wait for Bluetooth to stabilize
                    # Retry connections after power cycle
                    for battery_id, battery in sorted(self.batteries.items()):
                        try:
                            if connected > 0:
                                await asyncio.sleep(2.0)
                            await battery.connect()
                            connected += 1
                            log.info(f"Successfully connected to battery {battery_id} ({battery.address}) after power cycle")
                        except Exception as e:
                            log.warning(f"Battery {battery_id} ({battery.address}) still failed after power cycle: {e}")
            
            if connected == 0:
                if failed:
                    error_details = "; ".join([f"{addr}: {err}" for _, addr, err in failed])
                    raise RuntimeError(f"Failed to connect to any battery: {error_details}")
                else:
                    raise RuntimeError("Failed to connect to any battery (all operations in progress)")
        
        log.info(f"Connected to {connected}/{len(self.batteries)} batteries")
        
        # If some failed but we have at least one connected, log warning but don't fail
        if len(failed) > 0:
            log.warning(f"{len(failed)} battery/batteries failed to connect, but {connected} connected successfully")
    
    async def close(self):
        """Close all Bluetooth connections."""
        tasks = [battery.close() for battery in self.batteries.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        log.debug("Closed all JK BMS BLE connections")
    
    async def poll(self) -> BatteryBankTelemetry:
        """Poll all batteries and return aggregated telemetry."""
        devices: List[BatteryUnit] = []
        cells_data: List[Dict[str, Any]] = []
        
        # Poll batteries sequentially to avoid BlueZ conflicts
        # BlueZ doesn't handle multiple simultaneous operations well
        results = {}
        for battery_id, battery in sorted(self.batteries.items()):
            try:
                # Add small delay between polls to avoid conflicts
                if len(results) > 0:
                    await asyncio.sleep(0.3)
                results[battery_id] = await battery.poll()
            except Exception as e:
                results[battery_id] = e
        
        # Process results - continue with available batteries even if some fail
        successful_polls = 0
        failed_polls = 0
        
        for battery_id, battery in sorted(self.batteries.items()):
            result = results.get(battery_id)
            if result is None:
                continue
            if isinstance(result, Exception):
                error_msg = str(result)
                failed_polls += 1
                # If it's a connection error, try to reconnect
                if "not connected" in error_msg.lower() or "InProgress" in error_msg or "not found" in error_msg.lower():
                    log.info(f"Battery {battery.battery_id} ({battery.address}) connection issue, attempting reconnect...")
                    try:
                        await asyncio.sleep(1.0)  # Wait before reconnecting
                        await battery.connect()
                        # Retry poll after reconnection
                        try:
                            result = await battery.poll()
                            # If reconnection and retry succeeded, process the result below
                        except Exception as retry_e:
                            log.warning(f"Failed to poll battery {battery.battery_id} ({battery.address}) after reconnect: {retry_e}")
                            continue
                    except Exception as reconnect_e:
                        log.warning(f"Failed to reconnect battery {battery.battery_id} ({battery.address}): {reconnect_e}")
                        continue
                else:
                    log.warning(f"Failed to poll battery {battery.battery_id} ({battery.address}): {result}")
                    continue
            
            # If we got here after reconnection, result is now valid data
            sample = result
            if not sample:
                continue
            
            successful_polls += 1
            
            # Build telemetry for this battery
            cell_voltages = sample.get('cell_voltages', [])
            valid_cells = [v for v in cell_voltages if v is not None]
            
            pack_voltage = sample.get('voltage')
            if pack_voltage is None and valid_cells:
                pack_voltage = sum(valid_cells)
            
            temps = sample.get('temperatures', [])
            valid_temps = [t for t in temps if t is not None]
            avg_temp = sum(valid_temps) / len(valid_temps) if valid_temps else None
            
            # Get current (already inverted: positive = charging, negative = discharging)
            current = sample.get('current', 0) if sample.get('current') is not None else None
            # Calculate power: P = V * I (positive = charging, negative = discharging)
            power = None
            if pack_voltage is not None and current is not None:
                power = pack_voltage * current  # Watts
            
            # Log individual battery telemetry
            log.info(f"Battery {battery_id} ({battery.address}): "
                    f"V={round(pack_voltage, 2) if pack_voltage else 'N/A'}V, "
                    f"I={round(current, 2) if current is not None else 'N/A'}A, "
                    f"P={round(power, 1) if power is not None else 'N/A'}W, "
                    f"SOC={round(sample.get('soc', 0), 1) if sample.get('soc') is not None else 'N/A'}%, "
                    f"T={round(avg_temp, 1) if avg_temp is not None else 'N/A'}°C")
            
            # Create battery unit
            # Note: 'power' field should be the battery unit index (1-based: 1, 2, 3, ...)
            # This is used by the frontend to identify and match cells to battery units
            # Match the TCP/IP adapter behavior: use battery_id + 1 for 1-based indexing
            battery_unit_index = battery_id + 1  # Convert 0-based battery_id to 1-based index
            device = BatteryUnit(
                power=battery_unit_index,  # Battery unit index (1, 2, 3, ...), not power in watts
                voltage=round(pack_voltage, 2) if pack_voltage is not None else None,
                current=round(current, 2) if current is not None else None,
                temperature=round(avg_temp, 1) if avg_temp is not None else None,
                soc=float(sample.get('soc', 0)) if sample.get('soc') is not None else None,
                soh=None,
                cycles=int(sample.get('num_cycles', 0)) if sample.get('num_cycles') is not None else None,
            )
            devices.append(device)
            
            # Create cell data
            if valid_cells:
                cell_temps = valid_temps if valid_temps else [avg_temp] if avg_temp else []
                cells = []
                for cell_idx, cell_voltage in enumerate(cell_voltages):
                    if cell_voltage is not None:
                        cell_temp = None
                        if cell_temps:
                            if len(cell_temps) == 1:
                                cell_temp = cell_temps[0]
                            else:
                                cell_temp = cell_temps[cell_idx % len(cell_temps)]
                        
                        cells.append({
                            'power': battery_unit_index,  # Match BatteryUnit.power (1-based index)
                            'cell': cell_idx + 1,
                            'voltage': round(cell_voltage, 3),
                            'temperature': round(cell_temp, 1) if cell_temp is not None else None,
                        })
                
                cell_data_entry = {
                    'power': battery_unit_index,  # Match BatteryUnit.power (1-based index) for frontend matching
                    'battery_id': battery_id,  # Keep 0-based battery_id for internal reference
                    'battery_index': battery_unit_index,  # 1-based index for consistency
                    'cell_count': len(valid_cells),
                    'cells': cells,
                    'cell_voltages': valid_cells,
                    'min_cell_voltage': min(valid_cells) if valid_cells else None,
                    'max_cell_voltage': max(valid_cells) if valid_cells else None,
                    'voltage_delta': (max(valid_cells) - min(valid_cells)) if valid_cells else None,
                    'cell_delta': (max(valid_cells) - min(valid_cells)) if valid_cells else None,
                }
                
                if valid_temps:
                    cell_data_entry['temperature_min'] = round(min(valid_temps), 1)
                    cell_data_entry['temperature_max'] = round(max(valid_temps), 1)
                    cell_data_entry['temperature_delta'] = round(max(valid_temps) - min(valid_temps), 1)
                
                if sample.get('balance_current') is not None:
                    cell_data_entry['balance_current'] = round(sample['balance_current'], 3)
                if sample.get('charge_switch') is not None:
                    cell_data_entry['charge_switch'] = sample['charge_switch']
                if sample.get('discharge_switch') is not None:
                    cell_data_entry['discharge_switch'] = sample['discharge_switch']
                if sample.get('balance_switch') is not None:
                    cell_data_entry['balance_switch'] = sample['balance_switch']
                if sample.get('uptime') is not None:
                    cell_data_entry['total_runtime'] = int(sample['uptime'])
                
                cells_data.append(cell_data_entry)
        
        # Log polling results
        if successful_polls > 0:
            if failed_polls > 0:
                log.info(f"Battery bank poll: {successful_polls}/{len(self.batteries)} batteries successful, {failed_polls} failed - using available data")
            else:
                log.debug(f"Battery bank poll: {successful_polls}/{len(self.batteries)} batteries successful")
        else:
            log.warning(f"Battery bank poll: No batteries successfully polled ({failed_polls} failed)")
        
        # Calculate bank-level aggregates from available batteries
        if devices:
            voltages = [d.voltage for d in devices if d.voltage is not None]
            currents = [d.current for d in devices if d.current is not None]
            temps = [d.temperature for d in devices if d.temperature is not None]
            socs = [d.soc for d in devices if d.soc is not None]
            
            # Voltage: average across all batteries
            bank_voltage = sum(voltages) / len(voltages) if voltages else None
            # Current: sum across all batteries (total current flow)
            bank_current = sum(currents) if currents else None
            # Temperature: average across all batteries
            bank_temp = sum(temps) / len(temps) if temps else None
            # SOC: average across all batteries
            bank_soc = sum(socs) / len(socs) if socs else None
            
            # Power: sum of individual battery powers (P = V * I for each, then sum)
            # Or calculate from bank voltage and current: P = V_bank * I_total
            bank_power = None
            if bank_voltage is not None and bank_current is not None:
                bank_power = bank_voltage * bank_current  # Total power in Watts
            
            # Log accumulated telemetry
            log.info(f"Battery Bank {self.bank_cfg.id} (Accumulated): "
                    f"V_avg={round(bank_voltage, 2) if bank_voltage else 'N/A'}V, "
                    f"I_total={round(bank_current, 2) if bank_current is not None else 'N/A'}A, "
                    f"P_total={round(bank_power, 1) if bank_power is not None else 'N/A'}W, "
                    f"SOC_avg={round(bank_soc, 1) if bank_soc is not None else 'N/A'}%, "
                    f"T_avg={round(bank_temp, 1) if bank_temp is not None else 'N/A'}°C, "
                    f"Batteries={len(devices)}/{len(self.batteries)}")
        else:
            # No devices available - return empty telemetry but still valid structure
            bank_voltage = None
            bank_current = None
            bank_temp = None
            bank_soc = None
            bank_power = None
            log.warning(f"Battery bank poll: No battery data available (all {len(self.batteries)} batteries failed)")
        
        # Determine cells per battery
        cells_per_battery = 0
        if cells_data:
            cells_per_battery = max(c['cell_count'] for c in cells_data)
        
        # Create telemetry with power in extra field
        extra = {}
        if bank_power is not None:
            extra['power'] = round(bank_power, 1)  # Total power in Watts
        
        tel = BatteryBankTelemetry(
            ts=now_configured_iso(),
            id=self.bank_cfg.id,
            batteries_count=len(devices),
            cells_per_battery=cells_per_battery if cells_per_battery else self.bank_cfg.adapter.cells_per_battery,
            voltage=round(bank_voltage, 2) if bank_voltage is not None else None,
            current=round(bank_current, 2) if bank_current is not None else None,
            temperature=round(bank_temp, 1) if bank_temp is not None else None,
            soc=round(bank_soc, 1) if bank_soc is not None else None,
            devices=devices,
            cells_data=cells_data if cells_data else None,
            extra=extra if extra else None,
        )
        
        self.last_tel = tel
        return tel
    
    async def check_connectivity(self) -> bool:
        """Check if at least one BMS is connected and responding."""
        try:
            # Check if at least one battery is connected
            for battery in self.batteries.values():
                if battery.client and battery.client.is_connected:
                    try:
                        await battery._q(cmd=0x96, resp=0x02)
                        return True
                    except Exception:
                        continue
            return False
        except Exception:
            return False
    
    async def power_cycle_bluetooth(self, adapter_name: str = "hci0") -> bool:
        """
        Power cycle Bluetooth adapter using bluetoothctl or hciconfig.
        
        Args:
            adapter_name: Bluetooth adapter name (e.g., "hci0")
        
        Returns:
            True if power cycle was successful, False otherwise
        """
        import subprocess
        
        try:
            log.info(f"Power cycling Bluetooth adapter {adapter_name}...")
            
            # Try using bluetoothctl first (more reliable)
            try:
                # Turn off
                result = subprocess.run(
                    ["bluetoothctl", "power", "off"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode != 0:
                    log.warning(f"bluetoothctl power off failed: {result.stderr}")
                else:
                    log.debug("Bluetooth powered off via bluetoothctl")
                
                await asyncio.sleep(1.0)  # Wait 1 second
                
                # Turn on
                result = subprocess.run(
                    ["bluetoothctl", "power", "on"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode != 0:
                    log.warning(f"bluetoothctl power on failed: {result.stderr}")
                    return False
                else:
                    log.debug("Bluetooth powered on via bluetoothctl")
                
                await asyncio.sleep(2.0)  # Wait 2 seconds for Bluetooth to stabilize
                log.info(f"Bluetooth adapter {adapter_name} power cycled successfully")
                return True
                
            except FileNotFoundError:
                # bluetoothctl not available, try hciconfig
                log.debug("bluetoothctl not found, trying hciconfig...")
                try:
                    # Turn off
                    result = subprocess.run(
                        ["sudo", "hciconfig", adapter_name, "down"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode != 0:
                        log.warning(f"hciconfig down failed: {result.stderr}")
                    else:
                        log.debug(f"Bluetooth adapter {adapter_name} powered down via hciconfig")
                    
                    await asyncio.sleep(1.0)  # Wait 1 second
                    
                    # Turn on
                    result = subprocess.run(
                        ["sudo", "hciconfig", adapter_name, "up"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode != 0:
                        log.warning(f"hciconfig up failed: {result.stderr}")
                        return False
                    else:
                        log.debug(f"Bluetooth adapter {adapter_name} powered up via hciconfig")
                    
                    await asyncio.sleep(2.0)  # Wait 2 seconds for Bluetooth to stabilize
                    log.info(f"Bluetooth adapter {adapter_name} power cycled successfully via hciconfig")
                    return True
                    
                except FileNotFoundError:
                    log.error("Neither bluetoothctl nor hciconfig found. Cannot power cycle Bluetooth.")
                    return False
                except Exception as e:
                    log.error(f"Error power cycling Bluetooth with hciconfig: {e}")
                    return False
                    
        except Exception as e:
            log.error(f"Error power cycling Bluetooth adapter {adapter_name}: {e}", exc_info=True)
            return False
