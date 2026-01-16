import asyncio
import logging
import re
import time
import json
from typing import Any, Dict, List, Optional

import serial  # type: ignore

from solarhub.adapters.base import BatteryAdapter
from solarhub.config import BatteryBankConfig
from solarhub.schedulers.models import BatteryBankTelemetry, BatteryUnit
from solarhub.timezone_utils import now_configured_iso


log = logging.getLogger(__name__)


class PytesBatteryAdapter(BatteryAdapter):
    """
    Minimal Pytes battery bank adapter, inspired by the provided pytes_serial.py:
    - Connects over serial and issues 'pwr N' commands to read each battery summary.
    - Aggregates bank-level voltage/current/temperature/SOC.
    - Optionally can be extended to read per-cell data in future.
    """

    def __init__(self, bank_cfg: BatteryBankConfig):
        super().__init__(bank_cfg)
        self.client: Optional[serial.Serial] = None
        self.last_tel: Optional[BatteryBankTelemetry] = None
        # Optional JSON register map for future HA/config exposure
        self.regs: List[Dict[str, Any]] = []
        # Cache for device info from 'info' command
        self.device_info: Optional[Dict[str, Any]] = None
        # Command execution timing
        self._info_called: bool = False  # Only call info on startup
        self._last_stat_time: float = 0.0  # Track last stat command time (5 min interval)
        self._last_soh_time: Dict[int, float] = {}  # Track last soh command time per unit (daily)
        try:
            regfile = getattr(bank_cfg.adapter, 'register_map_file', None)
            if regfile:
                with open(regfile, 'r', encoding='utf-8') as f:
                    self.regs = json.load(f)
                log.debug("Loaded battery register map: %s (%d regs)", regfile, len(self.regs))
        except Exception as e:
            log.debug("Battery register map not loaded: %s", e)

    async def connect(self):
        cfg = self.bank_cfg.adapter
        if not cfg.serial_port:
            raise RuntimeError("Battery adapter requires serial_port")
        # Open serial in a thread-safe way
        def _open():
            return serial.Serial(
                port=cfg.serial_port,
                baudrate=cfg.baudrate,
                parity=serial.PARITY_NONE if cfg.parity.upper() == "N" else serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_ONE if cfg.stopbits == 1 else serial.STOPBITS_TWO,
                bytesize=serial.EIGHTBITS if cfg.bytesize == 8 else serial.SEVENBITS,
                timeout=2,
            )
        self.client = await asyncio.to_thread(_open)
        if not self.client or not self.client.port:
            raise RuntimeError("Failed to open battery serial port")
        log.debug("Connected battery serial on %s", self.client.port)

    async def close(self):
        if self.client and self.client.is_open:
            await asyncio.to_thread(self.client.close)

    async def poll(self) -> BatteryBankTelemetry:
        # Lazy connection - connect if not already connected
        if not self.client or not self.client.is_open:
            await self.connect()
        if not self.client or not self.client.is_open:
            raise RuntimeError("Battery serial not connected")

        cfg = self.bank_cfg.adapter
        
        # Call 'info' command only on startup (first poll)
        if not self._info_called:
            try:
                await self._send_info_command()
                self._info_called = True
                log.debug("Called 'info' command on startup")
            except Exception as e:
                log.debug(f"Could not refresh device info during poll: {e}")
        
        # Call 'stat' command every 5 minutes (300 seconds)
        system_status = None
        current_time = time.time()
        stat_interval = 300.0  # 5 minutes
        if current_time - self._last_stat_time >= stat_interval:
            try:
                system_status = await self._send_stat_command()
                self._last_stat_time = current_time
                log.debug("Called 'stat' command (5 min interval)")
            except Exception as e:
                log.debug(f"Could not get system status during poll: {e}")
        else:
            # Use cached system_status from last stat command if available
            # (stored in extra field of last telemetry)
            if self.last_tel and self.last_tel.extra:
                # Extract SOH and cycle_count from cached stat data
                cached_soh = self.last_tel.extra.get("soh")
                cached_cycles = self.last_tel.extra.get("cycle_count")
                if cached_soh is not None or cached_cycles is not None:
                    system_status = {
                        "soh": cached_soh,
                        "cycle_count": cached_cycles,
                    }
                    log.debug(f"Using cached stat data: soh={cached_soh}, cycles={cached_cycles}")

        def _write_and_wait(cmd: str, min_buf: int = 400, timeout_s: float = 1.2) -> List[str]:
            assert self.client
            ser = self.client
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(cmd.encode("latin-1") + b"\n")
            ser.flush()
            start = time.time()
            buf: List[str] = []
            line = ""
            while True:
                if ser.in_waiting > 0:
                    b = ser.read()
                    try:
                        ch = b.decode("latin-1")
                    except Exception:
                        ch = ""
                    line += ch
                    if b == b"\n":
                        buf.append(line)
                        # stop on command completed marker
                        if "Command completed" in line:
                            break
                        line = ""
                else:
                    if time.time() - start > timeout_s:
                        break
                    # give device a nudge
                    ser.write(b"\n")
                    time.sleep(0.05)
            log.debug(f"Battery command '{cmd}' (pwr/bat inline) returned {len(buf)} lines")
            return buf

        devices: List[BatteryUnit] = []
        cells_data: List[Dict[str, Any]] = []
        # iterate batteries 1..N
        for power in range(1, cfg.batteries + 1):
            lines = await asyncio.to_thread(_write_and_wait, f"pwr {power}", 400, 1.2)
            # Add 500ms delay after each command execution to allow master battery to process
            await asyncio.sleep(0.5)
            if not lines:
                log.warning(f"No response for battery {power}, creating empty unit")
                # Create empty unit with just power number
                unit = BatteryUnit(power=power)
                devices.append(unit)
                continue
            # Log raw response for debugging if this is battery 3 or if response looks unusual
            if power == 3 or len(lines) < 5:
                log.info(f"Battery {power} raw response ({len(lines)} lines): {lines[:15]}")
            else:
                log.debug(f"Battery {power} raw response ({len(lines)} lines): {lines[:5]}")
            
            # parse
            parsed: Dict[str, Any] = {"power": power}
            for s in lines:
                s = s.strip("\r\n")
                if "Voltage         :" in s:
                    parsed["voltage"] = round(int(s[19:27]) / 1000.0, 2)
                elif "Current         :" in s:
                    parsed["current"] = round(int(s[19:27]) / 1000.0, 2)
                elif "Temperature     :" in s:
                    parsed["temperature"] = round(int(s[19:27]) / 1000.0, 1)
                elif "Coulomb         :" in s:
                    parsed["soc"] = int(s[19:27])
                elif "Basic Status    :" in s:
                    parsed["basic_st"] = s[19:27].strip()
                elif "Volt Status     :" in s:
                    parsed["volt_st"] = s[19:27].strip()
                elif "Current Status  :" in s:
                    parsed["current_st"] = s[19:27].strip()
                elif "Tmpr. Status    :" in s:
                    parsed["temp_st"] = s[19:27].strip()
                elif "Coul. Status    :" in s:
                    parsed["coul_st"] = s[19:27].strip()
                elif "Soh. Status     :" in s:
                    parsed["soh_st"] = s[19:27].strip()
                elif "Heater Status   :" in s:
                    parsed["heater_st"] = s[19:27].strip()
                elif "Bat Events      :" in s:
                    try:
                        parsed["bat_events"] = int(s[19:27], 16)
                    except Exception:
                        pass
                elif "Power Events    :" in s:
                    try:
                        parsed["power_events"] = int(s[19:27], 16)
                    except Exception:
                        pass
                elif "System Fault    :" in s:
                    try:
                        parsed["sys_events"] = int(s[19:27], 16)
                    except Exception:
                        pass

            # Get State of Health for this battery unit BEFORE creating BatteryUnit
            # Call 'soh' command once per day (24 hours) per battery unit
            soh_data = None
            current_time = time.time()
            soh_interval = 86400.0  # 24 hours (1 day)
            last_soh_time = self._last_soh_time.get(power, 0.0)
            
            if current_time - last_soh_time >= soh_interval:
                try:
                    soh_data = await self._send_soh_command(power)
                    self._last_soh_time[power] = current_time
                    log.debug(f"Called 'soh' command for battery {power} (daily interval)")
                    # Add 500ms delay after SOH command to allow master battery to process
                    await asyncio.sleep(0.5)
                except Exception as e:
                    log.debug(f"Could not get SOH for battery {power}: {e}", exc_info=True)
            else:
                # Use cached SOH data from last telemetry if available
                if self.last_tel and self.last_tel.devices:
                    for cached_unit in self.last_tel.devices:
                        if cached_unit.power == power:
                            if cached_unit.soh is not None:
                                soh_data = {"soh_percent": cached_unit.soh}
                                log.debug(f"Using cached SOH for battery {power}: {cached_unit.soh}%")
                            if cached_unit.cycles is not None:
                                if soh_data is None:
                                    soh_data = {}
                                soh_data["cycle_count"] = cached_unit.cycles
                                log.debug(f"Using cached cycles for battery {power}: {cached_unit.cycles}")
                            break
            
            # Process SOH data if available
            if soh_data:
                log.debug(f"SOH data retrieved for battery {power}: {soh_data}")
                # Map soh_percent to soh field for BatteryUnit model
                if "soh_percent" in soh_data:
                    parsed["soh"] = soh_data["soh_percent"]
                    log.debug(f"Mapped soh_percent={soh_data['soh_percent']} to parsed['soh'] for battery {power}")
                else:
                    log.debug(f"SOH data for battery {power} missing 'soh_percent' field. Available keys: {list(soh_data.keys())}")
                
                # Map cycle_count to cycles field for BatteryUnit model
                if "cycle_count" in soh_data:
                    parsed["cycles"] = soh_data["cycle_count"]
                    log.debug(f"Mapped cycle_count={soh_data['cycle_count']} to parsed['cycles'] for battery {power}")
                else:
                    log.debug(f"SOH data for battery {power} missing 'cycle_count' field. Available keys: {list(soh_data.keys())}")
            else:
                log.debug(f"No SOH data available for battery {power} (using stat command fallback if available)")
            
            # Also check if system_status from stat command has SOH/cycle data (fallback)
            # The stat command provides bank-level SOH and cycle count
            if system_status:
                # Use stat command SOH if soh command didn't provide it
                if "soh" not in parsed or parsed.get("soh") is None:
                    if "soh" in system_status:
                        parsed["soh"] = system_status["soh"]
                        log.debug(f"Using SOH from stat command for battery {power}: {system_status['soh']}")
                
                # Use stat command cycle_count if soh command didn't provide it
                if "cycles" not in parsed or parsed.get("cycles") is None:
                    if "cycle_count" in system_status:
                        parsed["cycles"] = system_status["cycle_count"]
                        log.debug(f"Using cycle count from stat command for battery {power}: {system_status['cycle_count']}")

            # Check if we got any valid data (at least voltage, current, or soc should be present)
            has_valid_data = parsed.get("voltage") is not None or parsed.get("current") is not None or parsed.get("soc") is not None
            
            if not has_valid_data:
                log.warning(f"Battery {power}: No valid data parsed from response. Response had {len(lines)} lines.")
                if power == 3:  # Extra logging for battery 3
                    log.warning(f"Battery {power} response lines: {[s.strip()[:80] for s in lines[:15]]}")
            
            # Create BatteryUnit with all parsed data (including SOH and cycles)
            log.debug(f"Creating BatteryUnit for battery {power} with parsed data: voltage={parsed.get('voltage')}, current={parsed.get('current')}, soc={parsed.get('soc')}, soh={parsed.get('soh')}, cycles={parsed.get('cycles')}")
            try:
                unit = BatteryUnit(**parsed)
                devices.append(unit)
            except Exception as e:
                log.error(f"Failed to create BatteryUnit for battery {power}: {e}, parsed data: {parsed}")
                # Create minimal unit to prevent crash
                unit = BatteryUnit(power=power)
                devices.append(unit)
            
            # Print single-line summary for this battery
            soh_str = f"SOH={unit.soh}%" if unit.soh is not None else "SOH=N/A"
            cycles_str = f"Cycles={unit.cycles}" if unit.cycles is not None else "Cycles=N/A"
            voltage_str = f"{unit.voltage}V" if unit.voltage is not None else "N/A V"
            current_str = f"{unit.current}A" if unit.current is not None else "N/A A"
            soc_str = f"{unit.soc}%" if unit.soc is not None else "N/A%"
            temp_str = f"{unit.temperature}°C" if unit.temperature is not None else "N/A°C"
            log.debug(f"Battery {power}: {voltage_str}, {current_str}, {soc_str}, {temp_str}, {soh_str}, {cycles_str}")

            # Also read per-cell table for this battery
            try:
                bat_lines = await asyncio.to_thread(_write_and_wait, f"bat {power}", 800, 1.5)
                # Add 500ms delay after each command execution to allow master battery to process
                await asyncio.sleep(0.5)
                if bat_lines:
                    log.debug(f"Cell command response for battery {power}: {len(bat_lines)} lines")
                    stats, cells = self._parse_cell_table(power, bat_lines)
                    # If we found any cells, add to cells_data list with optional stats
                    entry: Dict[str, Any] = {"power": power, "cells": cells}
                    if stats:
                        entry.update(stats)
                    cells_data.append(entry)
                    log.debug(f"Battery {power} cell parsing: {len(cells)} cells found")
                else:
                    log.debug(f"No cell data response for battery {power}")
            except Exception as e:
                log.debug(f"Cell read failed for battery {power}: {e}")
            
            # Add delay before starting next battery to ensure master battery is ready
            # This is especially important when all commands go through the master battery
            if power < cfg.batteries:  # Don't delay after last battery
                await asyncio.sleep(0.3)

        # aggregate bank-level stats (avg voltage/temp/soc, sum current)
        v = [d.voltage for d in devices if d.voltage is not None]
        c = [d.current for d in devices if d.current is not None]
        t = [d.temperature for d in devices if d.temperature is not None]
        s = [d.soc for d in devices if d.soc is not None]
        bank = BatteryBankTelemetry(
            ts=now_configured_iso(),
            id=self.bank_cfg.id,
            batteries_count=cfg.batteries,
            cells_per_battery=cfg.cells_per_battery,
            voltage=round(sum(v) / len(v), 2) if v else None,
            current=round(sum(c), 1) if c else None,
            temperature=round(sum(t) / len(t), 1) if t else None,
            soc=int(sum(s) / len(s)) if s else None,
            devices=devices,
            cells_data=cells_data or None,
            extra={
                "dev_name": cfg.dev_name,
                "manufacturer": cfg.manufacturer,
                "model": cfg.model,
                # Include device info from 'info' command if available
                **(self.device_info or {}),
                # Include system status if available
                **(system_status or {}),
            },
        )

        self.last_tel = bank
        return bank

    # Optional standardized interface stubs for future parity with inverter adapters
    async def read_by_ident(self, ident: str):
        try:
            if self.last_tel and getattr(self.last_tel, 'extra', None):
                key = str(ident).lower()
                return self.last_tel.extra.get(key)
        except Exception:
            pass
        raise NotImplementedError("Battery adapter does not support direct register reads yet")

    async def write_by_ident(self, ident: str, value: Any) -> None:
        raise NotImplementedError("Battery adapter does not support register writes")

    def _parse_cell_table(self, power: int, lines: List[str]) -> (Dict[str, Any], List[Dict[str, Any]]):
        """Parse the 'bat N' tabular output into per-cell list and basic stats.
        Returns (stats_dict, cells_list)
        Based on the working pytes_serial.py implementation.
        """
        import re
        cells: List[Dict[str, Any]] = []
        
        log.debug(f"Parsing cell table for battery {power}, {len(lines)} lines")
        
        # Initialize column indices
        cell_idx = -1
        volt_idx = -1
        curr_idx = -1
        temp_idx = -1
        base_st_idx = -1
        volt_st_idx = -1
        curr_st_idx = -1
        temp_st_idx = -1
        soc_idx = -1
        coulomb_idx = -1
        
        # Find the header line (contains "Battery" and "Volt")
        header_line_idx = -1
        for i, line_str in enumerate(lines):
            if 'Battery' in line_str and 'Volt' in line_str:
                header_line_idx = i
                break
        
        if header_line_idx == -1:
            log.debug(f"No header line found for battery {power}")
            return {}, []
        
        log.debug(f"Found header at line {header_line_idx}")
        
        for i, line_str in enumerate(lines):
            # Last line is command completed message
            if i == len(lines) - 1:
                break
                
            # Process header line
            elif i == header_line_idx:
                line = re.split(r'\s{2,}', line_str.strip())
                log.debug(f"Header line {i}: {line}")
                
                for j, l in enumerate(line):
                    if l == 'Battery':
                        cell_idx = j
                    elif l == 'Volt':
                        volt_idx = j
                    elif l == 'Curr':
                        curr_idx = j
                    elif l == 'Tempr':
                        temp_idx = j
                    elif l == 'Base State':
                        base_st_idx = j
                    elif l == 'Volt. State':
                        volt_st_idx = j
                    elif l == 'Curr. State':
                        curr_st_idx = j
                    elif l == 'Temp. State':
                        temp_st_idx = j
                    elif l == 'SOC':
                        soc_idx = j
                    elif l == 'Coulomb':
                        coulomb_idx = j
                
                # Workaround for Pytes firmware missing SOC column in the header
                if soc_idx == -1 and coulomb_idx != -1:
                    soc_idx = coulomb_idx
                    coulomb_idx = coulomb_idx + 1
                    
                log.debug(f"Column indices: cell={cell_idx}, volt={volt_idx}, temp={temp_idx}, soc={soc_idx}")
                
            # All the other lines are cell data (skip header line)
            elif i != header_line_idx:
                line = re.split(r'\s{2,}', line_str.strip())
                log.debug(f"Processing data line {i}: {line}")
                cell_data = {}
                
                cell_data['power'] = power
                
                try:
                    if cell_idx != -1 and len(line) > cell_idx:
                        cell_data['cell'] = int(line[cell_idx]) + 1
                    if volt_idx != -1 and len(line) > volt_idx:
                        cell_data['voltage'] = int(line[volt_idx]) / 1000.0  # V
                    if curr_idx != -1 and len(line) > curr_idx:
                        cell_data['current'] = int(line[curr_idx]) / 1000.0  # A
                    if temp_idx != -1 and len(line) > temp_idx:
                        cell_data['temperature'] = int(line[temp_idx]) / 1000.0  # deg C
                    if base_st_idx != -1 and len(line) > base_st_idx:
                        cell_data['basic_st'] = line[base_st_idx]
                    if volt_st_idx != -1 and len(line) > volt_st_idx:
                        cell_data['volt_st'] = line[volt_st_idx]
                    if curr_st_idx != -1 and len(line) > curr_st_idx:
                        cell_data['curr_st'] = line[curr_st_idx]
                    if temp_st_idx != -1 and len(line) > temp_st_idx:
                        cell_data['temp_st'] = line[temp_st_idx]
                    if soc_idx != -1 and len(line) > soc_idx:
                        soc_val = line[soc_idx]
                        if soc_val.endswith('%'):
                            soc_val = soc_val[:-1]
                        cell_data['soc'] = int(soc_val)  # %
                    if coulomb_idx != -1 and len(line) > coulomb_idx:
                        coulomb_val = line[coulomb_idx]
                        if coulomb_val.upper().endswith('MAH'):
                            coulomb_val = coulomb_val[:-4]
                        cell_data['coulomb'] = int(coulomb_val) / 1000.0  # Ah
                    
                    # Only add if we have at least cell and voltage
                    if 'cell' in cell_data and 'voltage' in cell_data:
                        cells.append(cell_data)
                        log.debug(f"Added cell {cell_data.get('cell')}: V={cell_data.get('voltage')}, T={cell_data.get('temperature')}")
                        
                except Exception as e:
                    log.debug(f"Failed to parse cell row {i}: {line}, error: {e}")
                    continue

        # compute basic stats if we have data
        stats: Dict[str, Any] = {}
        if cells:
            vvals = [c.get("voltage") for c in cells if c.get("voltage") is not None]
            tvals = [c.get("temperature") for c in cells if c.get("temperature") is not None]
            if vvals:
                stats.update({
                    "voltage_min": round(min(vvals), 3),
                    "voltage_max": round(max(vvals), 3),
                    "voltage_delta": round(max(vvals) - min(vvals), 3),
                })
            if tvals:
                stats.update({
                    "temperature_min": round(min(tvals), 3),
                    "temperature_max": round(max(tvals), 3),
                    "temperature_delta": round(max(tvals) - min(tvals), 3),
                })
        else:
            log.debug(f"No cells parsed for battery {power}")

        return stats, cells
    
    async def _send_command(self, cmd: str, timeout_s: float = 2.0) -> List[str]:
        """
        Generic helper to send a console command and read response.
        
        Args:
            cmd: Command string to send
            timeout_s: Response timeout in seconds
            
        Returns:
            List of response lines
        """
        if not self.client or not self.client.is_open:
            await self.connect()
        
        if not self.client or not self.client.is_open:
            log.debug(f"Battery serial not connected for '{cmd}' command")
            return []
        
        def _write_and_wait(cmd: str, min_buf: int = 400, timeout_s: float = 2.0) -> List[str]:
            assert self.client
            ser = self.client
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(cmd.encode("latin-1") + b"\n")
            ser.flush()
            start = time.time()
            buf: List[str] = []
            line = ""
            while True:
                if ser.in_waiting > 0:
                    b = ser.read()
                    try:
                        ch = b.decode("latin-1")
                    except Exception:
                        ch = ""
                    line += ch
                    if b == b"\n":
                        buf.append(line)
                        # stop on command completed marker
                        if "Command completed" in line:
                            break
                        line = ""
                else:
                    if time.time() - start > timeout_s:
                        break
                    # give device a nudge
                    ser.write(b"\n")
                    time.sleep(0.05)
            return buf
        
        try:
            lines = await asyncio.to_thread(_write_and_wait, cmd, 400, timeout_s)
            log.debug(f"Battery command '{cmd}' returned {len(lines)} lines")
            # Add 500ms delay after command execution to allow master battery to process
            await asyncio.sleep(0.5)
            return lines
        except Exception as e:
            log.debug(f"Error executing '{cmd}' command: {e}")
            return []
    
    async def _send_info_command(self) -> Optional[Dict[str, Any]]:
        """
        Send 'info' command to battery and parse device information.
        
        Based on Pylontech console command specification:
        Returns device info including serial number (Barcode), firmware versions, etc.
        
        Returns:
            Dictionary with parsed device info, or None if command fails
        """
        try:
            lines = await self._send_command("info", timeout_s=2.0)
            if not lines:
                log.debug("No response from 'info' command")
                return None
            
            # Parse info command response
            # Expected format based on Pylontech specification:
            # Device address      : 1
            # Manufacturer        : Pylon
            # Device name         : US2KBPL
            # Board version       : PHANTOMSAV10R03
            # Main Soft version   : B66.6
            # Soft  version       : V2.4
            # Boot  version       : V2.0
            # Comm version        : V2.0
            # Release Date        : 20-05-28
            # Barcode             : HPTBH02240A03193  <-- This is the serial number
            # Specification       : 48V/50AH
            # Cell Number         : 15
            # Max Dischg Curr     : -100000mA
            # Max Charge Curr     : 102000mA
            # EPONPort rate       : 1200
            # Console Port rate   : 115200
            
            info: Dict[str, Any] = {}
            for line in lines:
                line = line.strip("\r\n")
                if ":" not in line:
                    continue
                
                # Split on colon, handling cases where value might contain colons
                parts = line.split(":", 1)
                if len(parts) != 2:
                    continue
                
                key = parts[0].strip()
                value = parts[1].strip()
                
                # Map various field names to standardized keys
                key_lower = key.lower()
                if "device address" in key_lower or "address" in key_lower:
                    try:
                        info["device_address"] = int(value)
                    except ValueError:
                        info["device_address"] = value
                elif "manufacturer" in key_lower:
                    info["manufacturer"] = value
                elif "device name" in key_lower or "name" in key_lower:
                    info["device_name"] = value
                    info["model"] = value  # Also store as model
                elif "board version" in key_lower:
                    info["board_version"] = value
                elif "main soft version" in key_lower or "main software version" in key_lower:
                    info["main_software_version"] = value
                elif "soft version" in key_lower and "main" not in key_lower:
                    info["software_version"] = value
                elif "boot version" in key_lower:
                    info["boot_version"] = value
                elif "comm version" in key_lower or "communication version" in key_lower:
                    info["communication_version"] = value
                elif "release date" in key_lower:
                    info["release_date"] = value
                elif "barcode" in key_lower:
                    info["barcode"] = value
                    info["serial_number"] = value  # Barcode is the serial number
                elif "specification" in key_lower or "spec" in key_lower:
                    info["specification"] = value
                elif "cell number" in key_lower:
                    try:
                        info["cell_number"] = int(value)
                    except ValueError:
                        info["cell_number"] = value
                elif "max dischg curr" in key_lower or "max discharge current" in key_lower:
                    # Parse current value (may be in mA)
                    try:
                        if "ma" in value.lower():
                            info["max_discharge_current_ma"] = int(value.lower().replace("ma", "").strip())
                        else:
                            info["max_discharge_current_ma"] = int(value)
                    except ValueError:
                        info["max_discharge_current"] = value
                elif "max charge curr" in key_lower or "max charge current" in key_lower:
                    # Parse current value (may be in mA)
                    try:
                        if "ma" in value.lower():
                            info["max_charge_current_ma"] = int(value.lower().replace("ma", "").strip())
                        else:
                            info["max_charge_current_ma"] = int(value)
                    except ValueError:
                        info["max_charge_current"] = value
                elif "eponport rate" in key_lower or "epon port rate" in key_lower:
                    try:
                        info["epon_port_rate"] = int(value)
                    except ValueError:
                        info["epon_port_rate"] = value
                elif "console port rate" in key_lower:
                    try:
                        info["console_port_rate"] = int(value)
                    except ValueError:
                        info["console_port_rate"] = value
            
            if info:
                log.debug(f"Parsed device info: {info}")
                self.device_info = info
                return info
            else:
                log.debug("Info command returned no parseable data")
                return None
                
        except Exception as e:
            log.debug(f"Error executing 'info' command: {e}")
            return None
    
    async def _send_soh_command(self, unit: int = 1) -> Optional[Dict[str, Any]]:
        """
        Send 'soh N' command to get State of Health for battery unit.
        
        Based on Pylontech console command specification:
        Returns State of Health percentage and related health metrics.
        
        Args:
            unit: Battery unit number (default: 1)
            
        Returns:
            Dictionary with parsed SOH data, or None if command fails
        """
        try:
            lines = await self._send_command(f"soh {unit}", timeout_s=2.0)
            if not lines:
                log.debug(f"No response from 'soh {unit}' command")
                return None
            
            # Parse SOH command response
            # Response format is a table:
            # Power   N
            # Battery    Voltage    SOHCount   SOHStatus
            # 0          3484       0          Normal
            # ...
            
            log.debug(f"SOH command response for unit {unit}: {lines}")
            
            soh_data: Dict[str, Any] = {"unit": unit}
            soh_counts: List[int] = []
            soh_statuses: List[str] = []
            in_table = False
            
            for line in lines:
                line = line.strip("\r\n")
                if not line:
                    continue
                
                # Check if we're entering the table section
                if "Battery" in line and "Voltage" in line and "SOHCount" in line:
                    in_table = True
                    continue
                
                # Skip command echo and headers
                if line.startswith("soh ") or line.startswith("Power") or line.startswith("pylon>") or line.startswith("@") or "Command completed" in line:
                    continue
                
                # Parse table rows
                if in_table:
                    # Table row format: "0          3484       0          Normal"
                    # Split by whitespace and extract values
                    parts = line.split()
                    if len(parts) >= 4:
                        try:
                            # parts[0] = Battery (cell number)
                            # parts[1] = Voltage (mV)
                            # parts[2] = SOHCount (cycle count for this cell)
                            # parts[3] = SOHStatus
                            cell_num = parts[0]
                            voltage = parts[1]
                            soh_count = int(parts[2])
                            soh_status = parts[3] if len(parts) > 3 else "Normal"
                            soh_counts.append(soh_count)
                            soh_statuses.append(soh_status)
                            log.debug(f"Parsed table row for unit {unit}: cell={cell_num}, voltage={voltage}, soh_count={soh_count}, status={soh_status}")
                        except (ValueError, IndexError) as e:
                            log.debug(f"Failed to parse table row '{line}' for unit {unit}: {e}")
                            continue
                
                # Also try parsing as key:value format (fallback)
                if ":" in line and not in_table:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        key_lower = key.lower()
                        
                        if "soh" in key_lower or "state of health" in key_lower or "health" in key_lower:
                            try:
                                soh_value = value.replace("%", "").strip()
                                soh_data["soh_percent"] = float(soh_value)
                            except ValueError:
                                soh_data["soh"] = value
                        elif "cycle" in key_lower:
                            try:
                                soh_data["cycle_count"] = int(value)
                            except ValueError:
                                soh_data["cycle_count"] = value
                
                # Look for percentage values in non-table lines
                if not in_table:
                    percent_match = re.search(r'(\d+\.?\d*)\s*%', line, re.IGNORECASE)
                    if percent_match and "soh_percent" not in soh_data:
                        try:
                            soh_data["soh_percent"] = float(percent_match.group(1))
                        except ValueError:
                            pass
            
            # Process table data
            if soh_counts:
                log.debug(f"Processing SOH table data for unit {unit}: found {len(soh_counts)} cells with cycle counts: {soh_counts}")
                # Use maximum cycle count from all cells (most conservative)
                max_cycles = max(soh_counts)
                soh_data["cycle_count"] = max_cycles
                # Also store average for reference
                avg_cycles = sum(soh_counts) / len(soh_counts)
                soh_data["avg_cycle_count"] = int(avg_cycles)
                log.debug(f"Cycle count for unit {unit}: max={max_cycles}, avg={avg_cycles}")
                
                # Calculate SOH percentage based on status
                # If all cells are "Normal", assume 100% SOH
                # Otherwise, we might need to infer from other data
                normal_count = sum(1 for s in soh_statuses if s.lower() == "normal")
                log.debug(f"SOH statuses for unit {unit}: {soh_statuses}, normal_count={normal_count}, total={len(soh_statuses)}")
                if normal_count == len(soh_statuses):
                    # All cells normal - assume 100% SOH
                    soh_data["soh_percent"] = 100.0
                    log.debug(f"All cells normal for unit {unit}, setting soh_percent=100.0")
                else:
                    # Some cells not normal - calculate percentage
                    soh_data["soh_percent"] = (normal_count / len(soh_statuses)) * 100.0
                    log.debug(f"Not all cells normal for unit {unit}, calculating soh_percent={soh_data['soh_percent']}%")
                
                log.debug(f"Parsed SOH data for unit {unit}: soh={soh_data.get('soh_percent')}%, cycles={soh_data.get('cycle_count')} (from {len(soh_counts)} cells, max_cycles={max_cycles})")
                return soh_data
            
            # Return data if we found at least SOH or cycles from key:value parsing
            if soh_data.get("soh_percent") is not None or soh_data.get("cycle_count") is not None or "soh" in soh_data:
                log.debug(f"Parsed SOH data for unit {unit}: soh={soh_data.get('soh_percent')}, cycles={soh_data.get('cycle_count')}")
                return soh_data
            else:
                log.debug(f"SOH command returned no parseable data for unit {unit}. Response: {len(lines)} lines")
                return None
                
        except Exception as e:
            log.debug(f"Error executing 'soh {unit}' command: {e}")
            return None
    
    async def _send_stat_command(self) -> Optional[Dict[str, Any]]:
        """
        Send 'stat' or 'status' command to get system status.
        
        Based on Pylontech console command specification:
        Returns system status, alarms, warnings, and operational state.
        
        Returns:
            Dictionary with parsed status data, or None if command fails
        """
        # Try both 'stat' and 'status' commands
        for cmd_name in ["stat", "status"]:
            try:
                lines = await self._send_command(cmd_name, timeout_s=2.0)
                if not lines:
                    continue
                
                # Parse status command response
                status_data: Dict[str, Any] = {}
                for line in lines:
                    line = line.strip("\r\n")
                    if ":" not in line:
                        # Check for status indicators without colons
                        line_lower = line.lower()
                        if "alarm" in line_lower or "warning" in line_lower or "fault" in line_lower:
                            status_data["has_alarm"] = True
                            if "alarms" not in status_data:
                                status_data["alarms"] = []
                            status_data["alarms"].append(line)
                        continue
                    
                    parts = line.split(":", 1)
                    if len(parts) != 2:
                        continue
                    
                    key = parts[0].strip()
                    value = parts[1].strip()
                    key_lower = key.lower()
                    
                    # Parse SOH and cycle count from stat command
                    # Format: [ 42] SOH             :      100
                    # Format: [ 41] CYCLE Times     :       40
                    if "soh" in key_lower and "state of health" not in key_lower:
                        # Extract numeric value from SOH field
                        try:
                            soh_value = value.replace("%", "").strip()
                            status_data["soh"] = float(soh_value)
                            log.debug(f"Parsed SOH from stat command: {status_data['soh']}")
                        except ValueError:
                            log.debug(f"Could not parse SOH value '{value}' from stat command")
                    elif "cycle" in key_lower and "times" in key_lower:
                        # Extract cycle count
                        try:
                            status_data["cycle_count"] = int(value.strip())
                            log.debug(f"Parsed cycle count from stat command: {status_data['cycle_count']}")
                        except ValueError:
                            log.debug(f"Could not parse cycle count value '{value}' from stat command")
                    
                    if "alarm" in key_lower or "warning" in key_lower:
                        status_data["has_alarm"] = True
                        if "alarms" not in status_data:
                            status_data["alarms"] = []
                        status_data["alarms"].append(f"{key}: {value}")
                    elif "status" in key_lower or "state" in key_lower:
                        status_data["system_status"] = value
                    elif "fault" in key_lower:
                        status_data["has_fault"] = True
                        if "faults" not in status_data:
                            status_data["faults"] = []
                        status_data["faults"].append(f"{key}: {value}")
                    elif "error" in key_lower:
                        status_data["has_error"] = True
                        if "errors" not in status_data:
                            status_data["errors"] = []
                        status_data["errors"].append(f"{key}: {value}")
                
                if status_data:
                    log.debug(f"Parsed status data: {status_data}")
                    return status_data
                    
            except Exception as e:
                log.debug(f"Error executing '{cmd_name}' command: {e}")
                continue
        
        log.debug("Neither 'stat' nor 'status' command returned parseable data")
        return None
    
    async def check_connectivity(self) -> bool:
        """
        Check if Pytes battery device is connected and responding using 'info' command.
        
        This method uses the 'info' command to verify connectivity and automatically
        caches device information including serial number for further use.
        
        Returns:
            True if device is connected and responding, False otherwise
        """
        try:
            if not self.client or not self.client.is_open:
                await self.connect()
            
            if not self.client or not self.client.is_open:
                log.debug("Pytes battery client not connected")
                return False
            
            # Use 'info' command to verify device is connected and responding
            # This also caches device info including serial number for further use
            log.debug(f"Checking Pytes battery connectivity using 'info' command on {self.client.port if self.client else 'unknown port'}...")
            info = await self._send_info_command()
            
            if info:
                # Check if we got valid device info (should have at least manufacturer or device name)
                has_valid_info = bool(
                    info.get("manufacturer") or 
                    info.get("device_name") or 
                    info.get("serial_number") or 
                    info.get("barcode")
                )
                
                if has_valid_info:
                    serial_number = info.get("serial_number") or info.get("barcode")
                    log.debug(
                        f"Pytes battery connectivity check passed: device responded with valid info "
                        f"(port: {self.client.port if self.client else 'unknown'}, "
                        f"serial: {serial_number or 'N/A'})"
                    )
                    return True
                else:
                    log.debug(
                        f"Pytes battery responded but no valid device info found "
                        f"(port: {self.client.port if self.client else 'unknown'})"
                    )
                    return False
            else:
                log.debug(
                    f"No response from Pytes battery on 'info' command "
                    f"(port: {self.client.port if self.client else 'unknown'})"
                )
                return False
            
        except Exception as e:
            log.debug(f"Pytes battery connectivity check failed: {e}")
            return False
    
    async def read_serial_number(self) -> Optional[str]:
        """
        Read battery serial number from cached device info.
        
        The serial number is obtained from the 'info' command response (Barcode field),
        which is automatically called and cached by check_connectivity().
        
        Falls back to port-based identifier if device info is not available.
        """
        try:
            # First check connectivity - this will call 'info' command and cache device info
            if not await self.check_connectivity():
                log.debug("Pytes battery connectivity check failed, cannot read serial number")
                return None
            
            # Extract serial number from cached device info
            if self.device_info:
                serial_number = self.device_info.get("serial_number") or self.device_info.get("barcode")
                if serial_number:
                    serial_number = str(serial_number).strip()
                    if serial_number and len(serial_number) >= 3:  # Valid serial number
                        log.debug(f"Read serial number from cached device info: {serial_number}")
                        return serial_number
                    else:
                        log.debug(f"Serial number from device info too short or invalid: '{serial_number}'")
            
            # Fallback: use port-based identifier if device info doesn't have serial number
            cfg = self.bank_cfg.adapter
            if cfg.serial_port:
                port_id = cfg.serial_port.replace("/dev/tty", "").replace("COM", "")
                # Create identifier: PYTES-USB0-4 (type-port-batteries)
                identifier = f"PYTES-{port_id}-{cfg.batteries}"
                log.debug(f"Serial number not available in device info, using port-based identifier: {identifier}")
                return identifier
            
            # Last resort: use battery count only if no port available
            log.debug("No serial_port configured for Pytes battery, using fallback identifier")
            return f"PYTES-UNKNOWN-{cfg.batteries}"
            
        except Exception as e:
            log.debug(f"Error reading serial number from Pytes battery: {e}")
            # Fallback to port-based identifier on error
            try:
                cfg = self.bank_cfg.adapter
                if cfg.serial_port:
                    port_id = cfg.serial_port.replace("/dev/tty", "").replace("COM", "")
                    return f"PYTES-{port_id}-{cfg.batteries}"
            except Exception:
                pass
            return None


