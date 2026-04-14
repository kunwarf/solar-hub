/**
 * Senergy inverter settings schema.
 *
 * Mirrors system_b/device_server/settings_schema.py → SENERGY_SCHEMA.
 * Key differences from Powdrive:
 *  - Some voltage fields have scale = 0.1 (register stores tenths of volts)
 *  - Battery sign convention: positive = discharging
 */

import type { SettingGroup } from "../shared/types";

export const SENERGY_SCHEMA: SettingGroup[] = [
  {
    id: "battery",
    label: "Battery",
    sign_note:
      "Senergy sign convention: positive battery power = discharging, negative = charging. " +
      "This is the opposite of Powdrive/Deye.",
    fields: [
      { key: "battery_capacity_ah", label: "Battery Capacity", type: "number", unit: "Ah", min: 10, max: 2000, step: 1 },
      { key: "battery_max_charge_current_a", label: "Max Charge Current", type: "number", unit: "A", min: 0, max: 200, step: 1 },
      { key: "battery_max_discharge_current_a", label: "Max Discharge Current", type: "number", unit: "A", min: 0, max: 200, step: 1 },
      { key: "battery_bulk_voltage_v", label: "Bulk Charge Voltage", type: "number", unit: "V", min: 40, max: 62, step: 0.1, scale: 0.1, description: "Target absorption charge voltage" },
      { key: "battery_float_voltage_v", label: "Float Charge Voltage", type: "number", unit: "V", min: 40, max: 62, step: 0.1, scale: 0.1 },
      { key: "battery_low_voltage_v", label: "Low Battery Alarm Voltage", type: "number", unit: "V", min: 20, max: 55, step: 0.1, scale: 0.1 },
      { key: "battery_shutdown_voltage_v", label: "Shutdown Voltage", type: "number", unit: "V", min: 20, max: 50, step: 0.1, scale: 0.1, description: "Battery voltage at which inverter shuts down" },
      { key: "battery_restart_voltage_v", label: "Restart Voltage", type: "number", unit: "V", min: 20, max: 52, step: 0.1, scale: 0.1 },
      { key: "battery_shutdown_capacity_pct", label: "Shutdown SOC", type: "number", unit: "%", min: 0, max: 30, step: 1 },
      { key: "battery_restart_capacity_pct", label: "Restart SOC", type: "number", unit: "%", min: 0, max: 50, step: 1 },
      {
        key: "battery_type", label: "Battery Chemistry", type: "enum",
        options: { "0": "Lead-acid", "1": "Lithium (generic)", "2": "Pylon", "3": "BYD", "4": "Other" },
        destructive: true,
      },
    ],
  },
  {
    id: "grid_code",
    label: "Grid Code",
    fields: [
      {
        key: "grid_standard", label: "Grid Standard / Country Code", type: "enum",
        options: { "0": "VDE0126 (DE)", "1": "AS4777 (AU)", "2": "G83 (UK)", "3": "CEI0-21 (IT)", "4": "NRS097 (ZA)", "5": "Custom" },
        destructive: true,
        description: "Inverter may restart when changing grid code. Only change if required by local regulations.",
      },
      { key: "grid_frequency_set", label: "Grid Nominal Frequency", type: "enum", options: { "50": "50 Hz", "60": "60 Hz" } },
      { key: "grid_voltage_set", label: "Grid Nominal Voltage", type: "enum", options: { "220": "220 V", "230": "230 V", "240": "240 V" } },
      { key: "anti_island_enable", label: "Anti-Islanding", type: "bool", description: "Enable anti-islanding protection (required by most grid codes)" },
    ],
  },
  {
    id: "charger",
    label: "Charger",
    fields: [
      { key: "ac_charge_enable", label: "AC Charge Enable", type: "bool", description: "Allow grid to charge battery" },
      { key: "ac_charge_current_a", label: "AC Charge Max Current", type: "number", unit: "A", min: 0, max: 120, step: 1 },
      { key: "ac_charge_start_soc_pct", label: "AC Charge Start SOC", type: "number", unit: "%", min: 0, max: 100, step: 1 },
      { key: "ac_charge_end_soc_pct", label: "AC Charge End SOC", type: "number", unit: "%", min: 0, max: 100, step: 1 },
    ],
  },
  {
    id: "work_mode",
    label: "Work Mode",
    fields: [
      {
        key: "work_mode", label: "Work Mode", type: "enum",
        options: {
          "0": "Self-Consumption",
          "1": "Backup Priority",
          "2": "Feed-in Priority",
          "3": "Time-of-Use",
        },
        description: "Determines how the inverter balances solar, battery, and grid",
      },
      { key: "export_limit_enable", label: "Export Limit", type: "bool", description: "Limit power fed to grid" },
      { key: "export_limit_power_w", label: "Export Limit Power", type: "number", unit: "W", min: 0, max: 20000, step: 100 },
      { key: "priority_load_soc_pct", label: "Priority Load SOC", type: "number", unit: "%", min: 0, max: 100, step: 1, description: "SOC below which load is powered from grid" },
    ],
  },
  {
    id: "protection",
    label: "Protection",
    fields: [
      { key: "over_load_restart", label: "Overload Auto Restart", type: "bool" },
      { key: "over_temp_restart", label: "Over-Temperature Auto Restart", type: "bool" },
      { key: "backflow_protect", label: "Backflow Protection", type: "bool", description: "Prevent power from flowing back into PV panels" },
    ],
  },
];
