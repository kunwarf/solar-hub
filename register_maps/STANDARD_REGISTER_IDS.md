# Standard Register ID and Name Convention

This document defines the standard register IDs and names that should be used across all inverter register maps to ensure consistency and compatibility.

## Naming Convention

Format: `{component}_{measurement}_{unit}`

### Units Suffix
- `_w` - Watts (power)
- `_v` - Volts (voltage)
- `_a` - Amperes (current)
- `_hz` - Hertz (frequency)
- `_pct` - Percent
- `_c` - Celsius (temperature)
- `_kwh` - Kilowatt-hours (energy)
- `_ah` - Ampere-hours (capacity)

## Core Telemetry Registers

### Battery
- `battery_voltage_v` - Battery Voltage (V)
- `battery_current_a` - Battery Current (A)
- `battery_power_w` - Battery Power (W, signed)
- `battery_soc_pct` - Battery State of Charge (%)
- `battery_temp_c` - Battery Temperature (°C)

### Grid
- `grid_power_w` - Grid Power (W, signed)
- `grid_voltage_v` - Grid Voltage (V)
- `grid_current_a` - Grid Current (A)
- `grid_frequency_hz` - Grid Frequency (Hz)

### PV/Solar
- `pv1_power_w` - PV1 Power (W)
- `pv1_voltage_v` - PV1 Voltage (V)
- `pv1_current_a` - PV1 Current (A)
- `pv2_power_w` - PV2 Power (W)
- `pv2_voltage_v` - PV2 Voltage (V)
- `pv2_current_a` - PV2 Current (A)
- `pv3_power_w` - PV3 Power (W) [if applicable]
- `pv3_voltage_v` - PV3 Voltage (V) [if applicable]
- `pv3_current_a` - PV3 Current (A) [if applicable]

### Load
- `load_power_w` - Load Power (W)

### Inverter
- `inverter_power_w` - Inverter Output Power (W)
- `inverter_voltage_v` - Inverter Voltage (V)
- `inverter_current_a` - Inverter Current (A)
- `inverter_frequency_hz` - Inverter Frequency (Hz)
- `inverter_temp_c` - Inverter Temperature (°C)
- `inverter_mode` - Inverter Mode (enum/string)
- `error_code` - Error Code (bit enum)

### Energy (Today)
- `pv_energy_today_kwh` - PV Energy Today (kWh)
- `load_energy_today_kwh` - Load Energy Today (kWh)
- `grid_import_energy_today_kwh` - Grid Import Energy Today (kWh)
- `grid_export_energy_today_kwh` - Grid Export Energy Today (kWh)
- `battery_charge_energy_today_kwh` - Battery Charge Energy Today (kWh)
- `battery_discharge_energy_today_kwh` - Battery Discharge Energy Today (kWh)

### Energy (Total)
- `pv_energy_total_kwh` - PV Energy Total (kWh)
- `load_energy_total_kwh` - Load Energy Total (kWh)
- `grid_import_energy_total_kwh` - Grid Import Energy Total (kWh)
- `grid_export_energy_total_kwh` - Grid Export Energy Total (kWh)
- `battery_charge_energy_total_kwh` - Battery Charge Energy Total (kWh)
- `battery_discharge_energy_total_kwh` - Battery Discharge Energy Total (kWh)

### Device Information
- `device_serial_number` - Device Serial Number (ASCII)
- `device_model` - Device Model (ASCII)
- `rated_power_w` - Rated Power (W)
- `inverter_type` - Inverter Type (enum)

## Configuration Registers (RW)

### Battery Configuration
- `battery_type` - Battery Type (enum)
- `battery_capacity_ah` - Battery Capacity (Ah)
- `battery_absorption_voltage_v` - Battery Absorption Voltage (V)
- `battery_floating_voltage_v` - Battery Floating Voltage (V)
- `battery_equalization_voltage_v` - Battery Equalization Voltage (V)
- `battery_max_charge_current_a` - Maximum Charge Current (A)
- `battery_max_discharge_current_a` - Maximum Discharge Current (A)
- `battery_shutdown_voltage_v` - Battery Shutdown Voltage (V)
- `battery_restart_voltage_v` - Battery Restart Voltage (V)
- `battery_shutdown_capacity_pct` - Battery Shutdown Capacity (%)
- `battery_restart_capacity_pct` - Battery Restart Capacity (%)

### Grid Configuration
- `max_export_power_w` - Maximum Export Power (W)
- `zero_export_power_w` - Zero Export Power (W)

### TOU Windows
- `charge_start_time_{1-3}` - Charge Window Start Time (HH:MM)
- `charge_end_time_{1-3}` - Charge Window End Time (HH:MM)
- `charge_power_{1-3}` - Charge Window Power (W)
- `charge_end_soc_{1-3}` - Charge Window End SOC (%)
- `discharge_start_time_{1-3}` - Discharge Window Start Time (HH:MM)
- `discharge_end_time_{1-3}` - Discharge Window End Time (HH:MM)
- `discharge_power_{1-3}` - Discharge Window Power (W)
- `discharge_end_soc_{1-3}` - Discharge Window End SOC (%)

### Powdrive-Specific TOU Windows (Bidirectional)
- `prog{1-5}_time` - Program Window Start Time (HH:MM)
- `prog{1-5}_power_w` - Program Window Power (W)
- `prog{1-5}_capacity_pct` - Program Window Target SOC (%)
- `prog{1-5}_voltage_v` - Program Window Target Voltage (V)
- `prog{1-5}_charge_mode` - Program Window Charge Mode (enum)

## Notes

1. **Address, Type, Scale, etc. are inverter-specific** - Only `id` and `name` must be standardized
2. **Missing registers** - Not all inverters will have all registers. Use the standard IDs for registers that exist.
3. **Inverter-specific registers** - Some registers may be unique to specific inverters. Use descriptive IDs following the naming convention.
4. **Backward compatibility** - When updating existing register maps, ensure the adapter code can handle both old and new IDs during transition.

