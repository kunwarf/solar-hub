/**
 * Powdrive / Deye inverter settings schema.
 *
 * Mirrors system_b/device_server/settings_schema.py → POWDRIVE_SCHEMA.
 * Keep in sync when register maps change.
 */

import type { SettingGroup } from "../shared/types";

export const POWDRIVE_SCHEMA: SettingGroup[] = [
  {
    id: "battery",
    label: "Battery",
    fields: [
      { key: "battery_capacity_ah", label: "Battery Capacity", type: "number", unit: "Ah", min: 10, max: 2000, step: 1, scale: 1 },
      { key: "battery_max_charge_current_a", label: "Max Charge Current", type: "number", unit: "A", min: 0, max: 200, step: 1 },
      { key: "battery_max_discharge_current_a", label: "Max Discharge Current", type: "number", unit: "A", min: 0, max: 200, step: 1 },
      { key: "battery_equalization_voltage_v", label: "Equalization Voltage", type: "number", unit: "V", min: 40, max: 63, step: 0.1 },
      { key: "battery_floating_voltage_v", label: "Float Voltage", type: "number", unit: "V", min: 40, max: 62, step: 0.1 },
      { key: "battery_shutdown_voltage_v", label: "Shutdown Voltage", type: "number", unit: "V", min: 20, max: 50, step: 0.1, description: "Battery voltage at which inverter shuts down" },
      { key: "battery_restart_voltage_v", label: "Restart Voltage", type: "number", unit: "V", min: 20, max: 52, step: 0.1 },
      { key: "battery_low_voltage_v", label: "Low Battery Alarm Voltage", type: "number", unit: "V", min: 20, max: 52, step: 0.1 },
      { key: "battery_shutdown_capacity_pct", label: "Shutdown SOC", type: "number", unit: "%", min: 0, max: 30, step: 1, description: "Battery SOC at which inverter shuts down" },
      { key: "battery_restart_capacity_pct", label: "Restart SOC", type: "number", unit: "%", min: 0, max: 50, step: 1 },
      { key: "battery_low_capacity_pct", label: "Low Battery Alarm SOC", type: "number", unit: "%", min: 0, max: 50, step: 1 },
      { key: "battery_equalization_day_cycle", label: "Equalization Cycle", type: "number", unit: "days", min: 1, max: 90, step: 1 },
      { key: "battery_equalization_time", label: "Equalization Duration", type: "number", unit: "min", min: 5, max: 900, step: 5 },
      { key: "battery_mode_source", label: "Battery Mode Source", type: "enum", options: { "0": "Lead-acid", "1": "Lithium" }, destructive: true },
      { key: "lithium_battery_type", label: "Lithium Battery Brand", type: "enum", options: { "0": "Pylon", "1": "Wattsonic", "2": "Dyness", "3": "BYD", "4": "Other" }, destructive: true },
    ],
  },
  {
    id: "charger",
    label: "Charger",
    fields: [
      { key: "ac_charge_battery", label: "AC Charge Battery", type: "bool", description: "Allow grid to charge battery" },
      { key: "grid_charge_battery_current_a", label: "Max Grid Charge Current", type: "number", unit: "A", min: 0, max: 120, step: 1 },
      { key: "grid_charging_start_voltage_v", label: "Grid Charge Start Voltage", type: "number", unit: "V", min: 20, max: 58, step: 0.1 },
      { key: "grid_charging_start_capacity_pct", label: "Grid Charge Start SOC", type: "number", unit: "%", min: 0, max: 100, step: 1 },
    ],
  },
  {
    id: "grid",
    label: "Grid & Export",
    fields: [
      { key: "solar_sell", label: "Solar Feed-to-Grid", type: "bool", description: "Allow exporting solar to utility" },
      { key: "max_export_power_w", label: "Max Export Power", type: "number", unit: "W", min: 0, max: 20000, step: 100 },
      { key: "max_solar_sell_power_w", label: "Max Solar Sell Power", type: "number", unit: "W", min: 0, max: 20000, step: 100 },
      { key: "zero_export_power_w", label: "Zero Export Threshold", type: "number", unit: "W", min: 0, max: 500, step: 10 },
      { key: "tou_selling", label: "TOU Selling", type: "bool", description: "Enable Time-of-Use selling to grid" },
      { key: "grid_standard", label: "Grid Standard", type: "enum", options: { "0": "VDE0126 (DE)", "1": "AS4777 (AU)", "2": "G83 (UK)", "3": "CEI0-21 (IT)", "4": "NRS097 (ZA)", "5": "VDE4105 (DE)", "6": "Custom" }, destructive: true, description: "Grid connection standard. Inverter may restart." },
      { key: "grid_type_setting", label: "Grid Phase", type: "enum", options: { "0": "Single-phase", "1": "Split-phase", "2": "Three-phase" } },
      { key: "grid_phase_sequence", label: "Phase Sequence", type: "enum", options: { "0": "ABC", "1": "ACB" } },
      { key: "limit_control_function", label: "Export Limit Control", type: "enum", options: { "0": "Disabled", "1": "Grid CT", "2": "Inverter CT" } },
      { key: "external_ct_direction", label: "CT Clamp Direction", type: "enum", options: { "0": "Normal", "1": "Reversed" }, description: "Reverse if export/import readings are swapped" },
    ],
  },
  {
    id: "inverter",
    label: "Inverter / Output",
    fields: [
      { key: "solar_priority", label: "Solar Priority", type: "enum", options: { "0": "Battery First", "1": "Load First" } },
      { key: "gen_peak_shaving_power_w", label: "Generator Peak Shaving", type: "number", unit: "W", min: 0, max: 20000, step: 100 },
      { key: "grid_peak_shaving_power_w", label: "Grid Peak Shaving", type: "number", unit: "W", min: 0, max: 20000, step: 100 },
    ],
  },
  {
    id: "generator",
    label: "Generator",
    fields: [
      { key: "generator_charge_enabled", label: "Generator Charges Battery", type: "bool" },
      { key: "generator_port_usage", label: "Generator Port Usage", type: "enum", options: { "0": "Generator", "1": "Grid" } },
      { key: "generator_max_run_time_h", label: "Max Run Time", type: "number", unit: "h", min: 1, max: 24, step: 1 },
      { key: "generator_down_time_h", label: "Min Off Time", type: "number", unit: "h", min: 1, max: 24, step: 1 },
      { key: "generator_charging_start_voltage_v", label: "Gen Charge Start Voltage", type: "number", unit: "V", min: 20, max: 55, step: 0.1 },
      { key: "generator_charging_start_capacity_pct", label: "Gen Charge Start SOC", type: "number", unit: "%", min: 0, max: 100, step: 1 },
      { key: "generator_charge_battery_current_a", label: "Gen Max Charge Current", type: "number", unit: "A", min: 0, max: 120, step: 1 },
      { key: "generator_connected_to_grid_input", label: "Generator on Grid Input", type: "bool", description: "Generator is connected to AC-input (grid) port" },
    ],
  },
  {
    id: "schedule",
    label: "TOU Schedule",
    fields: [
      ...[1, 2, 3, 4, 5, 6].flatMap((i) => [
        { key: `prog${i}_time`, label: `Program ${i} Start Time`, type: "number" as const, unit: "HHMM", min: 0, max: 2359, step: 1, description: "Format: HHMM (e.g. 0600 = 06:00)" },
        { key: `prog${i}_power_w`, label: `Program ${i} Power Limit`, type: "number" as const, unit: "W", min: 0, max: 20000, step: 100 },
        { key: `prog${i}_voltage_v`, label: `Program ${i} Voltage`, type: "number" as const, unit: "V", min: 40, max: 62, step: 0.1 },
        { key: `prog${i}_capacity_pct`, label: `Program ${i} SOC Limit`, type: "number" as const, unit: "%", min: 0, max: 100, step: 1 },
        { key: `prog${i}_charge_mode`, label: `Program ${i} Charge Mode`, type: "enum" as const, options: { "0": "No charge/discharge", "1": "Charge", "2": "Discharge", "3": "Grid priority" } },
      ]),
    ],
  },
  {
    id: "protection",
    label: "Protection",
    fields: [
      { key: "solar_arc_fault_mode", label: "Arc Fault Detection", type: "enum", options: { "0": "Disabled", "1": "Enabled" } },
      { key: "smartload_off_voltage_v", label: "Smart Load Off Voltage", type: "number", unit: "V", min: 20, max: 55, step: 0.1 },
      { key: "smartload_off_capacity_pct", label: "Smart Load Off SOC", type: "number", unit: "%", min: 0, max: 100, step: 1 },
      { key: "smartload_on_voltage_v", label: "Smart Load On Voltage", type: "number", unit: "V", min: 20, max: 58, step: 0.1 },
      { key: "smartload_on_capacity_pct", label: "Smart Load On SOC", type: "number", unit: "%", min: 0, max: 100, step: 1 },
    ],
  },
];
