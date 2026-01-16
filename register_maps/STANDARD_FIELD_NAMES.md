# Standardized Field Names

This document defines the standardized field names used throughout the solar monitoring system. All device adapters must map their device-specific register names to these standard names.

## Field Naming Convention

- **Power**: `*_power_w` (watts)
- **Voltage**: `*_voltage_v` (volts)
- **Current**: `*_current_a` (amperes)
- **Temperature**: `*_temp_c` (celsius)
- **Percentage**: `*_pct` (percent)
- **Frequency**: `*_frequency_hz` (hertz)
- **Energy**: `today_*_energy` or `total_*_energy` (kWh)
- **Time**: `*_time` (ISO 8601 format)

## Standard Field Names

### Power Flows
- `pv_power_w` - Total PV power (watts)
- `pv1_power_w` - PV1/MPPT1 power (watts)
- `pv2_power_w` - PV2/MPPT2 power (watts)
- `pv3_power_w` - PV3/MPPT3 power (watts)
- `pv4_power_w` - PV4/MPPT4 power (watts)
- `load_power_w` - Total load power (watts)
- `grid_power_w` - Grid power (watts, positive = import, negative = export)
- `batt_power_w` - Battery power (watts, positive = charging, negative = discharging)

### Three-Phase Load Data
- `load_l1_power_w` - Load phase L1 power (watts)
- `load_l2_power_w` - Load phase L2 power (watts)
- `load_l3_power_w` - Load phase L3 power (watts)
- `load_l1_voltage_v` - Load phase L1 voltage (volts)
- `load_l2_voltage_v` - Load phase L2 voltage (volts)
- `load_l3_voltage_v` - Load phase L3 voltage (volts)
- `load_l1_current_a` - Load phase L1 current (amperes)
- `load_l2_current_a` - Load phase L2 current (amperes)
- `load_l3_current_a` - Load phase L3 current (amperes)
- `load_frequency_hz` - Load frequency (hertz)

### Three-Phase Grid Data
- `grid_l1_power_w` - Grid phase L1 power (watts)
- `grid_l2_power_w` - Grid phase L2 power (watts)
- `grid_l3_power_w` - Grid phase L3 power (watts)
- `grid_l1_voltage_v` - Grid phase L1 voltage (volts)
- `grid_l2_voltage_v` - Grid phase L2 voltage (volts)
- `grid_l3_voltage_v` - Grid phase L3 voltage (volts)
- `grid_l1_current_a` - Grid phase L1 current (amperes)
- `grid_l2_current_a` - Grid phase L2 current (amperes)
- `grid_l3_current_a` - Grid phase L3 current (amperes)
- `grid_frequency_hz` - Grid frequency (hertz)
- `grid_line_voltage_ab_v` - Grid line voltage AB (volts)
- `grid_line_voltage_bc_v` - Grid line voltage BC (volts)
- `grid_line_voltage_ca_v` - Grid line voltage CA (volts)

### Battery Data
- `batt_soc_pct` - Battery state of charge (percent)
- `batt_voltage_v` - Battery voltage (volts)
- `batt_current_a` - Battery current (amperes, positive = charging, negative = discharging)
- `batt_temp_c` - Battery temperature (celsius)

### Inverter Data
- `inverter_mode` - Inverter operating mode (string)
- `inverter_temp_c` - Inverter temperature (celsius)
- `error_code` - Error code (integer or string)

### Device Information
- `device_model` - Device model (string)
- `device_serial_number` - Device serial number (string)
- `rated_power_w` - Rated power (watts)

### Energy Totals
- `today_energy` - Today's total energy generation (kWh)
- `total_energy` - Total energy generation (kWh)
- `today_load_energy` - Today's load energy consumption (kWh)
- `today_import_energy` - Today's grid import energy (kWh)
- `today_export_energy` - Today's grid export energy (kWh)
- `today_battery_charge_energy` - Today's battery charge energy (kWh)
- `today_battery_discharge_energy` - Today's battery discharge energy (kWh)
- `today_peak_power` - Today's peak power (watts)

### Configuration
- `off_grid_mode` - Off-grid mode status (boolean)

## Usage in Register JSON

Each register in the JSON file should include a `standard_id` field that maps to one of the standard field names above:

```json
{
  "id": "device_specific_name",
  "standard_id": "pv_power_w",
  "name": "PV Power",
  "addr": 625,
  "kind": "holding",
  "type": "S16",
  "size": 1,
  "unit": "W",
  "rw": "RO"
}
```

If `standard_id` is not provided, the register `id` is used as-is (for backward compatibility).

## Benefits

1. **Consistency**: All devices use the same field names internally
2. **Maintainability**: Changes to device adapters don't affect higher layers
3. **Extensibility**: Easy to add new devices without changing smart scheduler or API
4. **Clarity**: Clear separation between device-specific and standardized data

