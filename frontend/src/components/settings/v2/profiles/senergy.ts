/**
 * Senergy PV9000 profile — covers ALL 26 fields defined in
 * system_b/device_server/settings_schema.py::SENERGY_SCHEMA.
 *
 * Home cards (10 fields): strategy, reserve (3), gridCharging (4), gridExport (2).
 * Hub groups (16 fields): identity (2), currentLimits (2), voltageThresholds (5),
 * protection (3), installer (4).
 *
 * Field metadata (min/max/unit/enum options/descriptions) is grounded in
 * SENERGY_SCHEMA — see the backend file for the authoritative values.
 * Zones + strategy blurbs + preview lines are UI-layer concerns not present
 * in the backend schema and live here.
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
} from "lucide-react";
import type { DeviceProfile } from "./types";

const zone = (from: number, to: number, color: string) => ({ from, to, color });
const RED = "#f43f5e";
const AMBER = "#f59e0b";
const GREEN = "#10b981";
const BLUE = "#3b82f6";
const GRAY = "#a1a1aa";

export const senergyProfile: DeviceProfile = {
  id: "senergy",
  name: "Senergy PV9000 Hybrid",
  sourceNote: "Grounded in SENERGY_SCHEMA + senergy_registers.json + PV9000 protocol",

  strategies: [
    { id: "0", label: "Self-Consumption", icon: Sun, blurb: "Uses solar first, stores excess in battery, sells the rest" },
    { id: "1", label: "Backup Priority", icon: Shield, blurb: "Keeps battery topped up for outages, exports rarely" },
    { id: "2", label: "Feed-in Priority", icon: Upload, blurb: "Maximizes grid export, uses battery less" },
    { id: "3", label: "Time-of-Use", icon: Clock, blurb: "Charges/discharges on hourly tariff (advanced)" },
  ],
  strategyPreview: {
    "0": "Your home uses solar power first; any surplus charges the battery, and only extra beyond that is sold to the grid.",
    "1": "The system keeps your battery charged for outages and rarely exports power to the grid.",
    "2": "Solar power is sold to the grid as much as possible, with the battery used only as a backup.",
    "3": "Charging and discharging follow the schedule set in the Time-of-Use section.",
  },

  sections: {
    /* ===================================================================
       HOME CARDS (10 fields — fetched on Home mount)
       =================================================================== */
    reserve: {
      kind: "slider",
      icon: createElement(BatteryCharging, { className: "w-5 h-5" }),
      title: "Battery backup reserve",
      description: "Keep some battery in reserve for grid outages",
      fields: [
        {
          key: "battery_shutdown_capacity_pct",
          label: "Reserve for backup",
          min: 0,
          max: 30,
          unit: "%",
          zones: [zone(0, 10, RED), zone(10, 20, AMBER), zone(20, 30, GREEN)],
        },
        {
          key: "battery_restart_capacity_pct",
          label: "Restart discharging at",
          min: 0,
          max: 50,
          unit: "%",
          minFrom: { key: "battery_shutdown_capacity_pct", offset: 5 },
          zones: [zone(0, 50, GREEN)],
        },
        {
          key: "priority_load_soc_pct",
          label: "Priority load falls back to grid below",
          min: 0,
          max: 100,
          unit: "%",
          zones: [zone(0, 100, GREEN)],
        },
      ],
      preview: (v) =>
        `Battery is protected below ${v.battery_shutdown_capacity_pct}% and resumes discharge above ${v.battery_restart_capacity_pct}%. Priority loads switch to grid supply below ${v.priority_load_soc_pct}%.`,
    },

    gridCharging: {
      kind: "slider",
      icon: createElement(PlugZap, { className: "w-5 h-5" }),
      title: "Grid charging",
      description: "Allow grid electricity to charge your battery",
      fields: [
        { key: "ac_charge_enable", type: "toggle", label: "Charge battery from grid" },
        {
          key: "ac_charge_current_a",
          label: "Max charging current",
          min: 0,
          max: 120,
          unit: " A",
          formatValue: (v) => `${v} A`,
          zones: [zone(0, 20, GRAY), zone(20, 60, GREEN), zone(60, 100, AMBER), zone(100, 120, RED)],
        },
        {
          key: "ac_charge_start_soc_pct",
          label: "Start when battery below",
          min: 0,
          max: 100,
          unit: "%",
          zones: [zone(0, 100, BLUE)],
        },
        {
          key: "ac_charge_end_soc_pct",
          label: "Stop when battery reaches",
          min: 0,
          max: 100,
          unit: "%",
          minFrom: { key: "ac_charge_start_soc_pct", offset: 1 },
          zones: [zone(0, 100, GREEN)],
        },
      ],
      preview: (v) =>
        v.ac_charge_enable
          ? `Grid power will charge your battery at up to ${v.ac_charge_current_a} A whenever it falls below ${v.ac_charge_start_soc_pct}%, stopping at ${v.ac_charge_end_soc_pct}%.`
          : "Your battery will only be charged by solar power — grid charging is off.",
    },

    gridExport: {
      kind: "slider",
      icon: createElement(Upload, { className: "w-5 h-5" }),
      title: "Grid export",
      description: "Sell excess solar back to the grid",
      fields: [
        { key: "export_limit_enable", type: "toggle", label: "Limit maximum export power" },
        {
          key: "export_limit_power_w",
          label: "Maximum export power",
          min: 0,
          max: 20000,
          step: 100,
          unit: " W",
          formatValue: (v) => `${v.toLocaleString()} W`,
        },
      ],
      preview: (v) =>
        v.export_limit_enable
          ? `Your inverter will cap grid export at ${(v.export_limit_power_w as number).toLocaleString()} W.`
          : "Excess solar can be exported without an inverter-side limit.",
    },

    /* ===================================================================
       HUB GROUPS (16 fields — fetched only when opened)
       =================================================================== */
    identity: {
      kind: "fields",
      tier: "default",
      icon: createElement(BatteryCharging, { className: "w-5 h-5" }),
      title: "Battery selection",
      description: "What kind of battery is connected, and its size.",
      fields: [
        {
          key: "battery_capacity_ah",
          label: "Battery capacity",
          type: "number",
          unit: "Ah",
          step: 1,
        },
        {
          key: "battery_type",
          label: "Battery chemistry",
          type: "select",
          destructive: true,
          options: ["Lead-acid", "Lithium (generic)", "Pylon", "BYD", "Other"],
          description:
            "Changing chemistry resets voltage thresholds and can affect battery safety behavior.",
        },
      ],
    },

    currentLimits: {
      kind: "fields",
      tier: "default",
      icon: createElement(Zap, { className: "w-5 h-5" }),
      title: "Battery current limits",
      description: "How fast the inverter is allowed to charge or discharge the battery.",
      fields: [
        { key: "battery_max_charge_current_a", label: "Max charge current", type: "number", unit: "A", step: 1 },
        { key: "battery_max_discharge_current_a", label: "Max discharge current", type: "number", unit: "A", step: 1 },
      ],
    },

    voltageThresholds: {
      kind: "fields",
      tier: "default",
      icon: createElement(Sliders, { className: "w-5 h-5" }),
      title: "Battery voltage thresholds",
      description: "Voltage ceilings and floors the inverter uses for charge/discharge decisions.",
      fields: [
        {
          key: "battery_bulk_voltage_v",
          label: "Bulk charge voltage",
          type: "number",
          unit: "V",
          step: 0.1,
          description: "Target absorption charge voltage",
        },
        { key: "battery_float_voltage_v", label: "Float charge voltage", type: "number", unit: "V", step: 0.1 },
        { key: "battery_low_voltage_v", label: "Low-voltage alarm", type: "number", unit: "V", step: 0.1 },
        {
          key: "battery_shutdown_voltage_v",
          label: "Shutdown voltage",
          type: "number",
          unit: "V",
          step: 0.1,
          description: "Battery voltage at which inverter shuts down",
        },
        { key: "battery_restart_voltage_v", label: "Restart voltage", type: "number", unit: "V", step: 0.1 },
      ],
    },

    protection: {
      kind: "fields",
      tier: "default",
      icon: createElement(Shield, { className: "w-5 h-5" }),
      title: "Protection",
      description: "Automatic recovery behavior after faults.",
      fields: [
        { key: "over_load_restart", label: "Overload auto-restart", type: "toggle" },
        { key: "over_temp_restart", label: "Over-temperature auto-restart", type: "toggle" },
        {
          key: "backflow_protect",
          label: "Backflow protection",
          type: "toggle",
          description: "Prevent power from flowing back into PV panels",
        },
      ],
    },

    installer: {
      kind: "fields",
      tier: "installer",
      icon: createElement(AlertTriangle, { className: "w-5 h-5" }),
      title: "Installer settings",
      description: "Grid-code compliance thresholds set to match local regulations.",
      fields: [
        {
          key: "grid_standard",
          label: "Grid standard",
          type: "select",
          destructive: true,
          options: ["VDE0126 (DE)", "AS4777 (AU)", "G83 (UK)", "CEI0-21 (IT)", "NRS097 (ZA)", "Custom"],
          description:
            "Inverter may restart when changing grid code. Only change if required by local regulations.",
        },
        {
          key: "grid_frequency_set",
          label: "Grid nominal frequency",
          type: "select",
          options: ["50", "60"],
          unit: "Hz",
        },
        {
          key: "grid_voltage_set",
          label: "Grid nominal voltage",
          type: "select",
          options: ["220", "230", "240"],
          unit: "V",
        },
        {
          key: "anti_island_enable",
          label: "Anti-islanding protection",
          type: "toggle",
          description: "Enable anti-islanding protection (required by most grid codes)",
        },
      ],
    },
  },

  homeCardIds: ["strategy", "reserve", "gridCharging", "gridExport"],
  hubGroupIds: ["identity", "currentLimits", "voltageThresholds", "protection", "installer"],

  // Reasonable safe defaults so the UI has something to render before the
  // first fetch completes.  Overwritten by real device values on load.
  defaults: {
    strategy: "0",
    reserve: {
      battery_shutdown_capacity_pct: 20,
      battery_restart_capacity_pct: 30,
      priority_load_soc_pct: 40,
    },
    gridCharging: {
      ac_charge_enable: false,
      ac_charge_current_a: 30,
      ac_charge_start_soc_pct: 20,
      ac_charge_end_soc_pct: 80,
    },
    gridExport: {
      export_limit_enable: true,
      export_limit_power_w: 5000,
    },
    identity: { battery_capacity_ah: 200, battery_type: "Lithium (generic)" },
    currentLimits: { battery_max_charge_current_a: 50, battery_max_discharge_current_a: 50 },
    voltageThresholds: {
      battery_bulk_voltage_v: 56.4,
      battery_float_voltage_v: 54.0,
      battery_low_voltage_v: 46.0,
      battery_shutdown_voltage_v: 42.0,
      battery_restart_voltage_v: 48.0,
    },
    protection: { over_load_restart: true, over_temp_restart: true, backflow_protect: true },
    installer: {
      grid_standard: "AS4777 (AU)",
      grid_frequency_set: "50",
      grid_voltage_set: "230",
      anti_island_enable: true,
    },
  },
};

/** The strategy key on draft/saved is a top-level string (not an object), so
 *  Apply/Reset diff it by reference equality. */
export const SENERGY_STRATEGY_KEY = "work_mode";
