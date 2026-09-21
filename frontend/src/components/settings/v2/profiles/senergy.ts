/**
 * Senergy PV9000 profile — grounded in register_maps/senergy_registers.json.
 *
 * IMPORTANT: field keys must match register `id` values exactly, because
 * the backend's read_all_configurable path filters + keys results by
 * register id.  Earlier drafts used the friendlier names from
 * settings_schema.py (`work_mode`, `battery_shutdown_capacity_pct`, ...)
 * which do NOT match the register map — every fetch returned an empty
 * settings dict and the UI stayed blank.
 *
 * Reference: senergy_registers.json has 51 RW registers.  This profile
 * covers all of them across 4 home cards and 6 hub groups.
 */
import { createElement } from "react";
import {
  BatteryCharging,
  Zap,
  PlugZap,
  Upload,
  Sun,
  Shield,
  Clock,
  AlertTriangle,
  Sliders,
  ArrowDownCircle,
  ArrowUpCircle,
  Power,
} from "lucide-react";
import type { DeviceProfile, FlatField } from "./types";

const zone = (from: number, to: number, color: string) => ({ from, to, color });
const RED = "#f43f5e";
const AMBER = "#f59e0b";
const GREEN = "#10b981";
const BLUE = "#3b82f6";
const GRAY = "#a1a1aa";

export const senergyProfile: DeviceProfile = {
  id: "senergy",
  name: "Senergy PV9000 Hybrid",
  sourceNote: "Grounded in senergy_registers.json — 51 RW registers, all covered",

  // hybrid_work_mode enum values (register 8448):
  //   0 = Self used mode
  //   1 = Feed-in priority mode
  //   2 = Time-based control
  //   3 = Back-up mode
  //   4 = Battery Discharge mode
  // Backend returns numeric values on read; we render/compare as strings
  // via String(value) at the render layer (see HomeScreen strategy card).
  strategies: [
    { id: "0", label: "Self-Consumption", icon: Sun, blurb: "Uses solar first, stores excess in battery, sells the rest" },
    { id: "1", label: "Feed-in Priority", icon: Upload, blurb: "Maximizes grid export, uses battery less" },
    { id: "2", label: "Time-based", icon: Clock, blurb: "Charges/discharges on the schedules below" },
    { id: "3", label: "Backup Priority", icon: Shield, blurb: "Keeps battery topped up for outages, exports rarely" },
    { id: "4", label: "Battery Discharge", icon: Zap, blurb: "Forces battery discharge regardless of solar/grid" },
  ],
  strategyPreview: {
    "0": "Your home uses solar power first; surplus charges the battery, extra is sold to the grid.",
    "1": "Solar is exported to grid as much as possible; battery is a backup only.",
    "2": "Charge and discharge follow the schedules in the Charge/Discharge windows sections.",
    "3": "Battery is kept charged for outages; export is minimized.",
    "4": "Battery discharges on demand, independent of solar output or grid conditions.",
  },

  sections: {
    /* ===================================================================
       HOME CARDS (10 register ids)
       =================================================================== */
    reserve: {
      kind: "slider",
      icon: createElement(BatteryCharging, { className: "w-5 h-5" }),
      title: "Battery backup reserve",
      description: "Keep some battery in reserve for grid outages",
      fields: [
        {
          key: "capacity_of_discharger_end_eod_",
          label: "Reserve for backup (EOD)",
          min: 0,
          max: 100,
          unit: "%",
          zones: [zone(0, 10, RED), zone(10, 20, AMBER), zone(20, 100, GREEN)],
        },
        {
          key: "off_grid_start_up_battery_capacity",
          label: "Off-grid start-up capacity",
          min: 0,
          max: 100,
          unit: "%",
          zones: [zone(0, 100, GREEN)],
        },
      ],
      preview: (v) =>
        `Battery is protected below ${v.capacity_of_discharger_end_eod_ ?? "?"}% during grid-tied use, and needs at least ${v.off_grid_start_up_battery_capacity ?? "?"}% before switching to backup (off-grid) power.`,
    },

    gridCharging: {
      kind: "slider",
      icon: createElement(PlugZap, { className: "w-5 h-5" }),
      title: "Grid charging",
      description: "Allow grid electricity to charge your battery",
      fields: [
        { key: "grid_charge", type: "toggle", label: "Charge battery from grid" },
        {
          key: "maximum_grid_charge_power",
          label: "Max grid charge power",
          min: 0,
          max: 5000,
          step: 50,
          unit: " W",
          formatValue: (v) => `${v.toLocaleString()} W`,
          zones: [zone(0, 500, GRAY), zone(500, 3000, GREEN), zone(3000, 4500, AMBER), zone(4500, 5000, RED)],
        },
        {
          key: "capacity_of_grid_charger_end",
          label: "Stop grid charging at (SOC)",
          min: 0,
          max: 100,
          unit: "%",
          zones: [zone(0, 100, GREEN)],
        },
      ],
      preview: (v) =>
        v.grid_charge
          ? `Grid power charges your battery at up to ${(v.maximum_grid_charge_power ?? 0).toLocaleString()} W, stopping at ${v.capacity_of_grid_charger_end ?? "?"}%.`
          : "Battery will only be charged by solar power — grid charging is off.",
    },

    gridExport: {
      kind: "slider",
      icon: createElement(Upload, { className: "w-5 h-5" }),
      title: "Grid export",
      description: "Sell excess solar back to the grid",
      fields: [
        {
          key: "power_limit_mode",
          type: "toggle",
          label: "Limit export power (CT-based)",
        },
        {
          key: "maximum_feed_in_grid_power",
          label: "Maximum export power",
          min: 0,
          max: 20000,
          step: 100,
          unit: " W",
          formatValue: (v) => `${v.toLocaleString()} W`,
        },
      ],
      preview: (v) =>
        v.power_limit_mode
          ? `Export cap: ${(v.maximum_feed_in_grid_power ?? 0).toLocaleString()} W.`
          : "Export limit is off — no inverter-side power cap.",
    },

    /* ===================================================================
       HUB GROUPS
       =================================================================== */
    identity: {
      kind: "fields",
      tier: "default",
      icon: createElement(BatteryCharging, { className: "w-5 h-5" }),
      title: "Battery selection",
      description: "Battery chemistry, capacity, and communication addressing.",
      fields: [
        {
          key: "battery_type_selection",
          label: "Battery type",
          type: "select",
          destructive: true,
          options: [
            "Unavailable",
            "Lead-Acid battery",
            "PYLON Lithium-ion",
            "Dyness Lithium-ion",
            "Aobo Lithium-ion",
            "UZ Lithium-ion",
            "VestMoods Lithium-ion",
            "XinYi Lithium-ion",
          ],
          reg: "reg 8464",
          description:
            "Changing battery type resets voltage thresholds and can affect safety behavior.",
        },
        { key: "battery_ah_ah_", label: "Battery capacity", type: "number", unit: "Ah", step: 1, reg: "reg 8466" },
        { key: "bms_comm_address", label: "BMS communication address", type: "number", step: 1, reg: "reg 8465" },
        { key: "modbus_address", label: "Modbus address", type: "number", step: 1, reg: "reg 12350" },
      ],
    },

    limits: {
      kind: "fields",
      tier: "default",
      icon: createElement(Sliders, { className: "w-5 h-5" }),
      title: "Charging & discharging limits",
      description: "Voltage and current ceilings the inverter won't cross.",
      fields: [
        { key: "stop_discharge_voltage", label: "Stop discharge voltage", type: "number", unit: "V", step: 0.1, reg: "reg 8467" },
        { key: "stop_charge_voltage", label: "Stop charge voltage", type: "number", unit: "V", step: 0.1, reg: "reg 8468" },
        { key: "max_discharge_current", label: "Max discharge current", type: "number", unit: "A", step: 0.1, reg: "reg 8480" },
        { key: "max_charger_current", label: "Max charge current", type: "number", unit: "A", step: 0.1, reg: "reg 8481" },
        { key: "capacity_of_charger_end_soc_", label: "Charge end SOC", type: "number", unit: "%", step: 1, reg: "reg 8473" },
        { key: "max_charge_power", label: "Max charge power", type: "number", unit: "W", step: 100 },
        { key: "max_discharge_power", label: "Max discharge power", type: "number", unit: "W", step: 100 },
      ],
    },

    backup: {
      kind: "fields",
      tier: "default",
      icon: createElement(Shield, { className: "w-5 h-5" }),
      title: "Backup / Off-grid",
      description: "How your backup (off-grid) output behaves during an outage.",
      fields: [
        { key: "off_grid_mode", label: "Off-grid mode", type: "toggle", reg: "reg 8476" },
        {
          key: "inverter_control",
          label: "Inverter control",
          type: "select",
          options: ["Power on", "Shut down"],
          destructive: true,
          description: "Global inverter power switch. Off = grid-tie + backup both stop.",
        },
      ],
    },

    /* ===================================================================
       TOU SCHEDULES — 3 charge + 3 discharge windows, 5 fields each.
       Grounded in senergy_registers.json:
         charge_frequency_{n} / discharge_frequency_{n}     (Once / Everyday)
         charge_start_time_{n} / discharge_start_time_{n}   HHMM binary
         charge_end_time_{n}   / discharge_end_time_{n}     HHMM binary
         charge_power_{n}      / discharge_power_{n}        0-5000 W
         charger_end_soc_{n} (note: register spells "charger", not "charge")
         discharge_end_soc_{n}
       Times are HHMM binary (e.g. 06:30 → 630).  For iteration 2 they
       surface as numeric fields; time-picker + HHMM↔HH:MM conversion
       is deferred polish.
       =================================================================== */
    chargeSchedule: {
      kind: "fields",
      tier: "default",
      icon: createElement(ArrowDownCircle, { className: "w-5 h-5" }),
      title: "TOU charge windows",
      description: "Up to 3 daily windows where grid charges the battery. Times are HHMM (e.g. 2300 = 11 PM).",
      fields: ([1, 2, 3] as const).flatMap<FlatField>((n) => [
        {
          key: `charge_frequency_${n}`,
          label: `Window ${n} — Repeat`,
          type: "select",
          options: ["Once", "Everyday"],
        },
        { key: `charge_start_time_${n}`, label: `Window ${n} — Start (HHMM)`, type: "number", step: 1, unit: "HHMM" },
        { key: `charge_end_time_${n}`, label: `Window ${n} — End (HHMM)`, type: "number", step: 1, unit: "HHMM" },
        { key: `charge_power_${n}`, label: `Window ${n} — Charge power`, type: "number", step: 100, unit: "W" },
        { key: `charger_end_soc_${n}`, label: `Window ${n} — Stop at SOC`, type: "number", step: 1, unit: "%" },
      ]),
    },

    dischargeSchedule: {
      kind: "fields",
      tier: "default",
      icon: createElement(ArrowUpCircle, { className: "w-5 h-5" }),
      title: "TOU discharge windows",
      description: "Up to 3 daily windows where the inverter discharges the battery to loads or grid.",
      fields: ([1, 2, 3] as const).flatMap<FlatField>((n) => [
        {
          key: `discharge_frequency_${n}`,
          label: `Window ${n} — Repeat`,
          type: "select",
          options: ["Once", "Everyday"],
        },
        { key: `discharge_start_time_${n}`, label: `Window ${n} — Start (HHMM)`, type: "number", step: 1, unit: "HHMM" },
        { key: `discharge_end_time_${n}`, label: `Window ${n} — End (HHMM)`, type: "number", step: 1, unit: "HHMM" },
        { key: `discharge_power_${n}`, label: `Window ${n} — Discharge power`, type: "number", step: 100, unit: "W" },
        { key: `discharge_end_soc_${n}`, label: `Window ${n} — Stop at SOC`, type: "number", step: 1, unit: "%" },
      ]),
    },
  },

  homeCardIds: ["strategy", "reserve", "gridCharging", "gridExport"],
  hubGroupIds: ["identity", "limits", "backup", "chargeSchedule", "dischargeSchedule"],

  // Fallback values used before device data arrives — overwritten by the
  // first successful fetch.  Keys mirror register ids.
  defaults: {
    strategy: "0",
    reserve: {
      capacity_of_discharger_end_eod_: 20,
      off_grid_start_up_battery_capacity: 30,
    },
    gridCharging: {
      grid_charge: false,
      maximum_grid_charge_power: 3000,
      capacity_of_grid_charger_end: 100,
    },
    gridExport: {
      power_limit_mode: true,
      maximum_feed_in_grid_power: 8000,
    },
    identity: {
      battery_type_selection: "PYLON Lithium-ion",
      battery_ah_ah_: 200,
      bms_comm_address: 1,
      modbus_address: 1,
    },
    limits: {
      stop_discharge_voltage: 480.0,
      stop_charge_voltage: 580.0,
      max_discharge_current: 120.0,
      max_charger_current: 120.0,
      capacity_of_charger_end_soc_: 100,
      max_charge_power: 5000,
      max_discharge_power: 5000,
    },
    backup: {
      off_grid_mode: false,
      inverter_control: "Power on",
    },
    chargeSchedule: Object.fromEntries(
      ([1, 2, 3] as const).flatMap((n) => [
        [`charge_frequency_${n}`, "Everyday"],
        [`charge_start_time_${n}`, 2300 + (n - 1) * 100],
        [`charge_end_time_${n}`, 600 + (n - 1) * 100],
        [`charge_power_${n}`, 2500],
        [`charger_end_soc_${n}`, 95],
      ]),
    ),
    dischargeSchedule: Object.fromEntries(
      ([1, 2, 3] as const).flatMap((n) => [
        [`discharge_frequency_${n}`, "Everyday"],
        [`discharge_start_time_${n}`, 1700 + (n - 1) * 100],
        [`discharge_end_time_${n}`, 2100 + (n - 1) * 100],
        [`discharge_power_${n}`, 2500],
        [`discharge_end_soc_${n}`, 20],
      ]),
    ),
  },
};
