/**
 * Senergy inverter settings schema.
 *
 * Field keys match the raw register IDs produced by System B's Senergy
 * register map (system_b/device_server/register_maps/senergy_registers.json).
 * Do not rename keys here without also updating the register map — the
 * backend uses these strings verbatim as the ``id`` of each writable
 * register.
 *
 * Key differences from Powdrive:
 *  - Senergy stores time-of-use start/end times as ``hour * 256 + minute``
 *    (max ≈ 6047), NOT the ``hour * 100 + minute`` HHMM format Powdrive uses.
 *    Fields are exposed as raw numbers here; a dedicated TOU editor can
 *    format them for humans later.
 *  - Battery sign convention: positive battery power = discharging.
 */

import type { SettingGroup } from "../shared/types";

const CHARGE_WINDOWS = [1, 2, 3] as const;
const DISCHARGE_WINDOWS = [1, 2, 3] as const;

const TIME_MAX = 6047; // 23 * 256 + 59

const FREQUENCY_OPTIONS = {
  "0": "Off",
  "1": "Once",
  "2": "Everyday",
  "3": "Weekdays",
  "4": "Weekends",
} as const;

const BATTERY_TYPE_OPTIONS = {
  "0": "Lead-acid",
  "1": "Lithium (generic)",
  "2": "Pylon",
  "3": "Other",
} as const;

const HYBRID_WORK_MODE_OPTIONS = {
  "0": "Self-Consumption",
  "1": "Backup Priority",
  "2": "Feed-in Priority",
  "3": "Time-of-Use",
} as const;

const OFF_GRID_MODE_OPTIONS = {
  "0": "Disabled",
  "1": "Enabled",
} as const;

const POWER_LIMIT_MODE_OPTIONS = {
  "0": "Disabled",
  "1": "Soft limit",
  "2": "Hard limit",
} as const;

export const SENERGY_SCHEMA: SettingGroup[] = [
  {
    id: "battery",
    label: "Battery",
    sign_note:
      "Senergy sign convention: positive battery power = discharging, " +
      "negative = charging. This is the opposite of Powdrive / Deye.",
    fields: [
      { key: "battery_ah_ah_", label: "Battery Capacity", type: "number", unit: "Ah", min: 10, max: 2000, step: 1 },
      { key: "battery_type_selection", label: "Battery Chemistry", type: "enum", options: BATTERY_TYPE_OPTIONS, destructive: true },
      { key: "max_charger_current", label: "Max Charge Current", type: "number", unit: "A", min: 0, max: 200, step: 1 },
      { key: "max_discharge_current", label: "Max Discharge Current", type: "number", unit: "A", min: 0, max: 200, step: 1 },
      { key: "stop_charge_voltage", label: "Stop Charge Voltage", type: "number", unit: "V", min: 40, max: 62, step: 0.1, description: "Battery voltage at which charging stops" },
      { key: "stop_discharge_voltage", label: "Stop Discharge Voltage", type: "number", unit: "V", min: 20, max: 55, step: 0.1, description: "Battery voltage at which discharge stops" },
      { key: "capacity_of_charger_end_soc_", label: "Charger End SOC", type: "number", unit: "%", min: 0, max: 100, step: 1, description: "Target SOC when charging is considered complete" },
      { key: "capacity_of_discharger_end_eod_", label: "Discharger End SOC (EOD)", type: "number", unit: "%", min: 0, max: 100, step: 1, description: "End-of-discharge SOC floor" },
      { key: "off_grid_start_up_battery_capacity", label: "Off-Grid Startup SOC", type: "number", unit: "%", min: 0, max: 100, step: 1, description: "SOC required to start inverter in off-grid mode" },
    ],
  },
  {
    id: "charger",
    label: "Charger & Grid",
    fields: [
      { key: "grid_charge", label: "Grid Charge Enable", type: "enum", options: { "0": "Disabled", "1": "Enabled" }, description: "Allow the grid to charge the battery" },
      { key: "max_charge_power", label: "Max Charge Power", type: "number", unit: "W", min: 0, max: 20000, step: 100 },
      { key: "max_discharge_power", label: "Max Discharge Power", type: "number", unit: "W", min: 0, max: 20000, step: 100 },
      { key: "maximum_grid_charge_power", label: "Max Grid Charge Power", type: "number", unit: "W", min: 0, max: 20000, step: 100 },
      { key: "capacity_of_grid_charger_end", label: "Grid Charger End SOC", type: "number", unit: "%", min: 0, max: 100, step: 1, description: "SOC at which grid-charging stops" },
    ],
  },
  {
    id: "work_mode",
    label: "Work Mode",
    fields: [
      { key: "hybrid_work_mode", label: "Hybrid Work Mode", type: "enum", options: HYBRID_WORK_MODE_OPTIONS, description: "How the inverter balances solar / battery / grid" },
      { key: "off_grid_mode", label: "Off-Grid Mode", type: "enum", options: OFF_GRID_MODE_OPTIONS },
      { key: "inverter_control", label: "Inverter Control", type: "number", min: 0, max: 65535, step: 1, description: "Vendor control-word (see Senergy manual)" },
      { key: "power_limit_mode", label: "Power Limit Mode", type: "enum", options: POWER_LIMIT_MODE_OPTIONS },
    ],
  },
  {
    id: "tou_charge",
    label: "TOU — Charge Windows",
    fields: CHARGE_WINDOWS.flatMap((i) => [
      { key: `charge_start_time_${i}`, label: `Window ${i} Start Time`, type: "number" as const, min: 0, max: TIME_MAX, step: 1, description: "Encoded as (hour × 256 + minute)" },
      { key: `charge_end_time_${i}`, label: `Window ${i} End Time`, type: "number" as const, min: 0, max: TIME_MAX, step: 1, description: "Encoded as (hour × 256 + minute)" },
      { key: `charge_frequency_${i}`, label: `Window ${i} Frequency`, type: "enum" as const, options: FREQUENCY_OPTIONS },
      { key: `charge_power_${i}`, label: `Window ${i} Power`, type: "number" as const, unit: "W", min: 0, max: 20000, step: 100 },
      { key: `charger_end_soc_${i}`, label: `Window ${i} End SOC`, type: "number" as const, unit: "%", min: 0, max: 100, step: 1 },
    ]),
  },
  {
    id: "tou_discharge",
    label: "TOU — Discharge Windows",
    fields: DISCHARGE_WINDOWS.flatMap((i) => [
      { key: `discharge_start_time_${i}`, label: `Window ${i} Start Time`, type: "number" as const, min: 0, max: TIME_MAX, step: 1, description: "Encoded as (hour × 256 + minute)" },
      { key: `discharge_end_time_${i}`, label: `Window ${i} End Time`, type: "number" as const, min: 0, max: TIME_MAX, step: 1, description: "Encoded as (hour × 256 + minute)" },
      { key: `discharge_frequency_${i}`, label: `Window ${i} Frequency`, type: "enum" as const, options: FREQUENCY_OPTIONS },
      { key: `discharge_power_${i}`, label: `Window ${i} Power`, type: "number" as const, unit: "W", min: 0, max: 20000, step: 100 },
      { key: `discharge_end_soc_${i}`, label: `Window ${i} End SOC`, type: "number" as const, unit: "%", min: 0, max: 100, step: 1 },
    ]),
  },
  {
    id: "system",
    label: "System",
    fields: [
      { key: "modbus_address", label: "Modbus Address", type: "number", min: 1, max: 247, step: 1, destructive: true, description: "Changing this will disconnect the datalogger until the address is updated on the ESP32 too" },
      { key: "bms_comm_address", label: "BMS Comm Address", type: "number", min: 0, max: 255, step: 1 },
    ],
  },
];
