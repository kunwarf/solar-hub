/**
 * Voltronic profile — grounded in VOLTRONIC_SCHEMA
 * (system_b/device_server/settings_schema.py, 17 fields across 5 groups).
 *
 * Voltronic uses named text commands (POP01, MCHGC040, PEg, etc.), not
 * Modbus registers.  Each field maps to a distinct command handled by
 * ModbusCommandExecutor's Voltronic path.  From the UI's point of view
 * this is identical to Modbus — patch(k, v) → update({k: v}) — so no
 * component changes needed.
 *
 * Voltronic has no battery-SOC concept (voltage-mode only) and no export
 * power slider (feed-to-grid is a simple toggle), so the Reserve and
 * Export cards degrade gracefully.
 */
import { createElement } from "react";
import {
  BatteryCharging,
  Zap,
  PlugZap,
  Upload,
  Sun,
  Shield,
  Sliders,
  AlertTriangle,
  Cpu,
  Volume2,
} from "lucide-react";
import type { DeviceProfile } from "./types";

const zone = (from: number, to: number, color: string) => ({ from, to, color });
const AMBER = "#f59e0b";
const GREEN = "#10b981";
const GRAY = "#a1a1aa";

export const voltronicProfile: DeviceProfile = {
  id: "voltronic",
  name: "Voltronic Hybrid",
  sourceNote: "Grounded in VOLTRONIC_SCHEMA — command-based serial protocol",

  // Voltronic's set_output_priority values are enum strings, not numeric.
  strategies: [
    { id: "utility", label: "Utility First", icon: PlugZap, blurb: "Grid powers loads by default; solar and battery help when available" },
    { id: "solar", label: "Solar First", icon: Sun, blurb: "Solar powers loads first, grid fills in when solar is weak" },
    { id: "sbu", label: "Solar → Battery → Utility", icon: BatteryCharging, blurb: "Battery covers loads when solar isn't enough, utility is last resort" },
  ],
  strategyPreview: {
    utility: "Grid is the primary source; solar and battery only help when they can.",
    solar: "Solar covers loads first; grid fills in the gap when solar is insufficient.",
    sbu: "SBU mode: solar first, then battery, and only fall back to utility if both are exhausted.",
  },

  sections: {
    /* ===================================================================
       HOME CARDS
       =================================================================== */
    reserve: {
      kind: "slider",
      icon: createElement(BatteryCharging, { className: "w-5 h-5" }),
      title: "Battery cutoff voltages",
      description: "Voltronic uses voltage thresholds (no SOC).  Below cutoff, output disconnects.",
      fields: [
        {
          key: "set_low_voltage_cutoff",
          label: "Low-voltage cutoff",
          min: 20.0,
          max: 50.0,
          step: 0.1,
          unit: " V",
          formatValue: (v) => `${v.toFixed(1)} V`,
          zones: [zone(20, 44, "#f43f5e"), zone(44, 48, AMBER), zone(48, 50, GREEN)],
        },
        {
          key: "set_recharge_voltage",
          label: "Reconnect (recharge trigger)",
          min: 20.0,
          max: 58.0,
          step: 0.1,
          unit: " V",
          formatValue: (v) => `${v.toFixed(1)} V`,
          minFrom: { key: "set_low_voltage_cutoff", offset: 2 },
          zones: [zone(20, 58, GREEN)],
        },
      ],
      preview: (v) =>
        `Output disconnects when battery drops to ${(v.set_low_voltage_cutoff as number).toFixed(1)} V and reconnects when it climbs back above ${(v.set_recharge_voltage as number).toFixed(1)} V.`,
    },

    gridCharging: {
      kind: "slider",
      icon: createElement(PlugZap, { className: "w-5 h-5" }),
      title: "Grid charging",
      description: "How aggressively grid power charges the battery.",
      fields: [
        {
          key: "set_max_ac_charging_current",
          label: "Max AC (grid) charge current",
          min: 2,
          max: 100,
          unit: " A",
          formatValue: (v) => `${v} A`,
          zones: [zone(2, 20, GRAY), zone(20, 60, GREEN), zone(60, 100, AMBER)],
        },
        {
          key: "set_max_charging_current",
          label: "Max total charge current",
          min: 10,
          max: 120,
          unit: " A",
          formatValue: (v) => `${v} A`,
          zones: [zone(10, 30, GRAY), zone(30, 80, GREEN), zone(80, 120, AMBER)],
        },
      ],
      preview: (v) =>
        `Grid contributes up to ${v.set_max_ac_charging_current} A to the battery; total charge (solar + grid combined) is capped at ${v.set_max_charging_current} A.`,
    },

    gridExport: {
      kind: "fields",
      icon: createElement(Upload, { className: "w-5 h-5" }),
      title: "Grid export",
      description: "Voltronic exports via a single toggle (no power limit).",
      fields: [
        {
          key: "enable_solar_feed_to_grid",
          label: "Feed solar surplus to grid",
          type: "toggle",
          description: "When on, excess PV beyond battery + load is exported to utility.",
        },
      ],
      preview: (v) =>
        v.enable_solar_feed_to_grid
          ? "Excess solar beyond battery + load is exported to the grid."
          : "Solar is limited to serving loads and charging the battery; nothing exports.",
    },

    /* ===================================================================
       HUB GROUPS
       =================================================================== */
    identity: {
      kind: "fields",
      tier: "default",
      icon: createElement(BatteryCharging, { className: "w-5 h-5" }),
      title: "Battery selection",
      description: "Battery chemistry — resets voltage defaults on change.",
      fields: [
        {
          key: "set_battery_type",
          label: "Battery type",
          type: "select",
          destructive: true,
          options: ["AGM", "Flooded / Wet", "User-defined"],
          description: "Changing battery type resets voltage thresholds.",
        },
      ],
    },

    voltageThresholds: {
      kind: "fields",
      tier: "default",
      icon: createElement(Sliders, { className: "w-5 h-5" }),
      title: "Charge voltage targets",
      description: "Bulk and float voltages.  Values interact with battery type.",
      fields: [
        { key: "set_bulk_voltage", label: "Bulk voltage", type: "number", unit: "V", step: 0.1 },
        { key: "set_float_voltage", label: "Float voltage", type: "number", unit: "V", step: 0.1 },
      ],
    },

    output: {
      kind: "fields",
      tier: "default",
      icon: createElement(Cpu, { className: "w-5 h-5" }),
      title: "Output mode",
      description: "Single unit vs parallel vs three-phase splits.",
      fields: [
        {
          key: "set_output_mode",
          label: "Output mode",
          type: "select",
          options: ["Single unit", "Parallel", "Phase 1 of 3", "Phase 2 of 3", "Phase 3 of 3"],
        },
      ],
    },

    charger: {
      kind: "fields",
      tier: "default",
      icon: createElement(PlugZap, { className: "w-5 h-5" }),
      title: "Charger priority",
      description: "Which source charges the battery.",
      fields: [
        {
          key: "set_charger_priority",
          label: "Charger source priority",
          type: "select",
          options: ["Utility First", "Solar First", "Solar + Utility", "Solar Only"],
        },
      ],
    },

    grid: {
      kind: "fields",
      tier: "default",
      icon: createElement(Zap, { className: "w-5 h-5" }),
      title: "Grid input",
      description: "AC input voltage acceptance range.",
      fields: [
        {
          key: "set_input_voltage_range",
          label: "AC input voltage range",
          type: "select",
          options: ["Appliance (wide range)", "UPS (narrow range)"],
          description: "Narrow range rejects brownouts; wide range tolerates voltage sag.",
        },
        {
          key: "set_grid_max_charging_current",
          label: "Grid max charge current (alias)",
          type: "number",
          unit: "A",
          step: 1,
          description: "Alias for AC charge current on some Voltronic firmwares.",
        },
      ],
    },

    features: {
      kind: "fields",
      tier: "default",
      icon: createElement(Volume2, { className: "w-5 h-5" }),
      title: "System features",
      description: "Buzzer, bypass, LCD, and other on/off flags.",
      fields: [
        { key: "enable_buzzer", label: "Audible alarm", type: "toggle" },
        {
          key: "enable_overload_bypass",
          label: "Overload bypass",
          type: "toggle",
          description: "Pass loads through directly when the inverter is overloaded.",
        },
        {
          key: "enable_lcd_backlight",
          label: "LCD backlight always on",
          type: "toggle",
        },
      ],
    },

    installer: {
      kind: "fields",
      tier: "installer",
      icon: createElement(AlertTriangle, { className: "w-5 h-5" }),
      title: "Installer settings",
      description: "One-way destructive operations.",
      fields: [
        {
          key: "restore_factory_defaults",
          label: "Restore factory defaults",
          type: "toggle",
          destructive: true,
          description: "WARNING: Resets ALL settings to factory defaults. Cannot be undone.",
        },
      ],
    },
  },

  homeCardIds: ["strategy", "reserve", "gridCharging", "gridExport"],
  hubGroupIds: ["identity", "voltageThresholds", "output", "charger", "grid", "features", "installer"],

  defaults: {
    strategy: "sbu",
    reserve: { set_low_voltage_cutoff: 46.0, set_recharge_voltage: 50.0 },
    gridCharging: { set_max_ac_charging_current: 30, set_max_charging_current: 60 },
    gridExport: { enable_solar_feed_to_grid: false },
    identity: { set_battery_type: "User-defined" },
    voltageThresholds: { set_bulk_voltage: 56.4, set_float_voltage: 54.0 },
    output: { set_output_mode: "Single unit" },
    charger: { set_charger_priority: "Solar First" },
    grid: { set_input_voltage_range: "Appliance (wide range)", set_grid_max_charging_current: 30 },
    features: {
      enable_buzzer: true,
      enable_overload_bypass: false,
      enable_lcd_backlight: false,
    },
    installer: { restore_factory_defaults: false },
  },
};
