"""
Powdrive hybrid inverter simulator.

Simulates a Powdrive hybrid inverter with realistic behavior:
- PV power follows sun curve
- Battery charges during day, discharges at night
- Load varies throughout the day
"""
import math
import random
from datetime import datetime
from typing import Dict, Any, Optional

from .modbus_simulator import ModbusTCPSimulator


class PowdriveSimulator(ModbusTCPSimulator):
    """
    Simulates a Powdrive hybrid inverter.

    Provides realistic telemetry data based on time of day
    and responds to Modbus TCP requests.
    """

    # Register addresses from powdrive_registers.json
    REG_INVERTER_TYPE = 0
    REG_MODBUS_ADDRESS = 1
    REG_PROTOCOL_VERSION = 2
    REG_SERIAL_START = 3  # 5 registers for serial
    REG_RATED_POWER = 20  # U32, 2 registers

    REG_WORKING_MODE = 500
    REG_INVERTER_TEMP = 540
    REG_HEAT_SINK_TEMP = 541
    REG_FAULT_WORD_0 = 555
    REG_POWER_ON_OFF = 551
    REG_GRID_STATUS = 552

    REG_BATTERY_TEMP = 586
    REG_BATTERY_VOLTAGE = 587
    REG_BATTERY_SOC = 588
    REG_BATTERY_POWER = 590
    REG_BATTERY_CURRENT = 591

    REG_GRID_VOLTAGE = 598
    REG_GRID_FREQUENCY = 609
    REG_GRID_POWER = 625
    REG_LOAD_POWER = 653

    REG_PV1_POWER = 672
    REG_PV2_POWER = 673
    REG_PV1_VOLTAGE = 676
    REG_PV1_CURRENT = 677
    REG_PV2_VOLTAGE = 678
    REG_PV2_CURRENT = 679

    # Energy counters
    REG_PV_ENERGY_TODAY = 529
    REG_LOAD_ENERGY_TODAY = 526
    REG_GRID_IMPORT_TODAY = 520
    REG_GRID_EXPORT_TODAY = 521
    REG_BATTERY_CHARGE_TODAY = 514
    REG_BATTERY_DISCHARGE_TODAY = 515
    REG_PV_ENERGY_TOTAL = 534  # U32

    def __init__(
        self,
        serial_number: str = "PD12K00001",
        rated_power_w: int = 12000,
        battery_capacity_pct: float = 75.0,
        unit_id: int = 1,
    ):
        """
        Initialize Powdrive simulator.

        Args:
            serial_number: Device serial number.
            rated_power_w: Rated power in watts.
            battery_capacity_pct: Initial battery SOC.
            unit_id: Modbus unit ID.
        """
        super().__init__(
            register_map={},
            unit_id=unit_id,
            serial_number=serial_number,
            name=f"Powdrive({serial_number})",
        )

        # Configuration
        self.rated_power_w = rated_power_w
        self.max_pv_power_w = rated_power_w  # Max PV input

        # State variables
        self.battery_soc = battery_capacity_pct
        self.battery_power_w = 0
        self.pv1_power_w = 0
        self.pv2_power_w = 0
        self.grid_power_w = 0
        self.load_power_w = 1000
        self.grid_voltage_v = 230.0
        self.grid_frequency_hz = 50.0
        self.battery_voltage_v = 51.2
        self.inverter_temp_c = 35.0

        # Energy counters (kWh * 10 for 0.1 scale)
        self.energy_pv_today = 0.0
        self.energy_load_today = 0.0
        self.energy_grid_import_today = 0.0
        self.energy_grid_export_today = 0.0
        self.energy_battery_charge_today = 0.0
        self.energy_battery_discharge_today = 0.0
        self.energy_pv_total = 1000.0  # Start with some history

        # Initialize registers
        self._init_registers()

    def _init_registers(self) -> None:
        """Initialize register map with device info."""
        # Device info
        self.set_register(self.REG_INVERTER_TYPE, 3)  # Hybrid Inverter
        self.set_register(self.REG_MODBUS_ADDRESS, self.unit_id)
        self.set_register(self.REG_PROTOCOL_VERSION, 100)  # Version 1.00

        # Serial number (5 registers, ASCII encoded)
        self.set_serial_number_registers(
            self.REG_SERIAL_START,
            self.serial_number,
            num_registers=5
        )

        # Rated power (U32)
        rated_scaled = int(self.rated_power_w * 10)  # 0.1 scale
        self.set_register(self.REG_RATED_POWER, rated_scaled >> 16)
        self.set_register(self.REG_RATED_POWER + 1, rated_scaled & 0xFFFF)

        # Working mode: Normal
        self.set_register(self.REG_WORKING_MODE, 2)
        self.set_register(self.REG_POWER_ON_OFF, 1)  # On
        self.set_register(self.REG_GRID_STATUS, 0x07)  # All relays on

        # Clear faults
        for i in range(4):
            self.set_register(self.REG_FAULT_WORD_0 + i, 0)

        # Update dynamic values
        self._update_registers()

    def _update_registers(self) -> None:
        """Update register values from state."""
        # Battery
        self.set_register(self.REG_BATTERY_SOC, int(self.battery_soc))
        self.set_register(self.REG_BATTERY_VOLTAGE, int(self.battery_voltage_v * 100))
        self.set_register(self.REG_BATTERY_POWER, int(self.battery_power_w))
        battery_current = self.battery_power_w / self.battery_voltage_v if self.battery_voltage_v > 0 else 0
        self.set_register(self.REG_BATTERY_CURRENT, int(battery_current * 100))
        self.set_register(self.REG_BATTERY_TEMP, int(25 * 10))

        # Grid
        self.set_register(self.REG_GRID_VOLTAGE, int(self.grid_voltage_v * 10))
        self.set_register(self.REG_GRID_FREQUENCY, int(self.grid_frequency_hz * 100))
        self.set_register(self.REG_GRID_POWER, int(self.grid_power_w) & 0xFFFF)

        # Load
        self.set_register(self.REG_LOAD_POWER, int(self.load_power_w) & 0xFFFF)

        # PV
        self.set_register(self.REG_PV1_POWER, int(self.pv1_power_w))
        self.set_register(self.REG_PV2_POWER, int(self.pv2_power_w))

        # PV voltage/current (simulate MPPT tracking)
        if self.pv1_power_w > 0:
            pv1_voltage = 350 + random.uniform(-10, 10)
            pv1_current = self.pv1_power_w / pv1_voltage
            self.set_register(self.REG_PV1_VOLTAGE, int(pv1_voltage * 10))
            self.set_register(self.REG_PV1_CURRENT, int(pv1_current * 10))
        else:
            self.set_register(self.REG_PV1_VOLTAGE, 0)
            self.set_register(self.REG_PV1_CURRENT, 0)

        if self.pv2_power_w > 0:
            pv2_voltage = 340 + random.uniform(-10, 10)
            pv2_current = self.pv2_power_w / pv2_voltage
            self.set_register(self.REG_PV2_VOLTAGE, int(pv2_voltage * 10))
            self.set_register(self.REG_PV2_CURRENT, int(pv2_current * 10))
        else:
            self.set_register(self.REG_PV2_VOLTAGE, 0)
            self.set_register(self.REG_PV2_CURRENT, 0)

        # Temperatures
        self.set_register(self.REG_INVERTER_TEMP, int(self.inverter_temp_c * 10))
        self.set_register(self.REG_HEAT_SINK_TEMP, int((self.inverter_temp_c + 5) * 10))

        # Energy counters (scale 0.1 kWh)
        self.set_register(self.REG_PV_ENERGY_TODAY, int(self.energy_pv_today * 10))
        self.set_register(self.REG_LOAD_ENERGY_TODAY, int(self.energy_load_today * 10))
        self.set_register(self.REG_GRID_IMPORT_TODAY, int(self.energy_grid_import_today * 10))
        self.set_register(self.REG_GRID_EXPORT_TODAY, int(self.energy_grid_export_today * 10))
        self.set_register(self.REG_BATTERY_CHARGE_TODAY, int(self.energy_battery_charge_today * 10))
        self.set_register(self.REG_BATTERY_DISCHARGE_TODAY, int(self.energy_battery_discharge_today * 10))

        # Total PV energy (U32)
        total_scaled = int(self.energy_pv_total * 10)
        self.set_register(self.REG_PV_ENERGY_TOTAL, total_scaled >> 16)
        self.set_register(self.REG_PV_ENERGY_TOTAL + 1, total_scaled & 0xFFFF)

    def simulate_tick(self, dt: float) -> None:
        """
        Update simulation state based on time of day.

        Args:
            dt: Time delta in seconds since last tick.
        """
        now = datetime.now()
        hour = now.hour + now.minute / 60.0

        # PV power follows sun curve (sunrise ~6am, sunset ~6pm)
        if 6 <= hour <= 18:
            # Sinusoidal curve peaking at noon
            sun_angle = (hour - 6) / 12.0 * math.pi
            sun_factor = math.sin(sun_angle)

            # Add some variability (clouds, etc.)
            variability = 1.0 + random.uniform(-0.15, 0.15)

            total_pv = self.max_pv_power_w * sun_factor * variability
            total_pv = max(0, total_pv)

            # Split between PV1 and PV2
            self.pv1_power_w = total_pv * 0.55
            self.pv2_power_w = total_pv * 0.45
        else:
            self.pv1_power_w = 0
            self.pv2_power_w = 0

        total_pv_power = self.pv1_power_w + self.pv2_power_w

        # Load varies throughout day
        base_load = 800
        if 7 <= hour <= 9:  # Morning peak
            load_factor = 2.5
        elif 18 <= hour <= 22:  # Evening peak
            load_factor = 3.5
        elif 0 <= hour <= 6:  # Night
            load_factor = 0.6
        else:  # Day
            load_factor = 1.5

        self.load_power_w = base_load * load_factor * (1 + random.uniform(-0.1, 0.1))

        # Power flow logic
        pv_excess = total_pv_power - self.load_power_w

        if pv_excess > 0:
            # Excess PV: charge battery first, then export
            if self.battery_soc < 100:
                # Battery can absorb power
                max_charge = 5000  # Max charge rate
                charge_power = min(pv_excess, max_charge, (100 - self.battery_soc) * 100)
                self.battery_power_w = charge_power  # Positive = charging
                self.grid_power_w = -(pv_excess - charge_power)  # Negative = export
            else:
                # Battery full, export all excess
                self.battery_power_w = 0
                self.grid_power_w = -pv_excess
        else:
            # Deficit: discharge battery first, then import
            deficit = -pv_excess
            if self.battery_soc > 20:
                # Battery can supply power
                max_discharge = 5000  # Max discharge rate
                available = (self.battery_soc - 20) * 100
                discharge_power = min(deficit, max_discharge, available)
                self.battery_power_w = -discharge_power  # Negative = discharging
                self.grid_power_w = deficit - discharge_power  # Positive = import
            else:
                # Battery low, import from grid
                self.battery_power_w = 0
                self.grid_power_w = deficit

        # Update battery SOC based on power flow
        # Assume 25.6kWh battery capacity
        battery_capacity_wh = 25600
        energy_delta_wh = self.battery_power_w * (dt / 3600)
        soc_delta = (energy_delta_wh / battery_capacity_wh) * 100
        self.battery_soc = max(0, min(100, self.battery_soc + soc_delta))

        # Update battery voltage based on SOC
        # Linear approximation: 48V at 0%, 54V at 100%
        self.battery_voltage_v = 48.0 + (self.battery_soc / 100) * 6.0

        # Update energy counters
        energy_hours = dt / 3600

        if total_pv_power > 0:
            self.energy_pv_today += (total_pv_power / 1000) * energy_hours
            self.energy_pv_total += (total_pv_power / 1000) * energy_hours

        self.energy_load_today += (self.load_power_w / 1000) * energy_hours

        if self.grid_power_w > 0:
            self.energy_grid_import_today += (self.grid_power_w / 1000) * energy_hours
        else:
            self.energy_grid_export_today += (-self.grid_power_w / 1000) * energy_hours

        if self.battery_power_w > 0:
            self.energy_battery_charge_today += (self.battery_power_w / 1000) * energy_hours
        else:
            self.energy_battery_discharge_today += (-self.battery_power_w / 1000) * energy_hours

        # Update temperature based on power throughput
        power_factor = (total_pv_power + abs(self.battery_power_w)) / self.rated_power_w
        ambient_temp = 25.0
        self.inverter_temp_c = ambient_temp + power_factor * 20 + random.uniform(-1, 1)

        # Add some grid variability
        self.grid_voltage_v = 230.0 + random.uniform(-3, 3)
        self.grid_frequency_hz = 50.0 + random.uniform(-0.05, 0.05)

        # Update registers
        self._update_registers()

    def reset_daily_counters(self) -> None:
        """Reset daily energy counters (call at midnight)."""
        self.energy_pv_today = 0.0
        self.energy_load_today = 0.0
        self.energy_grid_import_today = 0.0
        self.energy_grid_export_today = 0.0
        self.energy_battery_charge_today = 0.0
        self.energy_battery_discharge_today = 0.0

    def inject_fault(self, fault_code: int) -> None:
        """
        Inject a fault for testing.

        Args:
            fault_code: Fault code (bit position in fault word).
        """
        current = self.get_register(self.REG_FAULT_WORD_0)
        self.set_register(self.REG_FAULT_WORD_0, current | (1 << fault_code))
        self.set_register(self.REG_WORKING_MODE, 4)  # Fault mode

    def clear_faults(self) -> None:
        """Clear all faults."""
        for i in range(4):
            self.set_register(self.REG_FAULT_WORD_0 + i, 0)
        self.set_register(self.REG_WORKING_MODE, 2)  # Normal mode

    def get_state(self) -> Dict[str, Any]:
        """Get current simulator state."""
        return {
            "serial_number": self.serial_number,
            "battery_soc": self.battery_soc,
            "battery_power_w": self.battery_power_w,
            "pv_power_w": self.pv1_power_w + self.pv2_power_w,
            "grid_power_w": self.grid_power_w,
            "load_power_w": self.load_power_w,
            "grid_voltage_v": self.grid_voltage_v,
            "inverter_temp_c": self.inverter_temp_c,
            "energy_pv_today_kwh": self.energy_pv_today,
            "energy_pv_total_kwh": self.energy_pv_total,
        }
