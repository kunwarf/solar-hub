/**
 * Powdrive / Deye profile — grounded in POWDRIVE_SCHEMA
 * (system_b/device_server/settings_schema.py, 76 fields across 7 groups).
 *
 * Home cards (4): strategy (solar_priority), reserve, gridCharging, gridExport.
 * Hub groups: identity, currentLimits, voltageThresholds, equalization,
 * inverter, generator, schedule, smartLoad, protection, installer.
 *
 * TOU schedule (6 programs × 5 fields) is modelled here as a flat "fields"
 * section rather than the reference's 6-window grid — a proper window UI
 * is deferred (see reference for the pattern when we come back to it).
 * Powdrive and Deye share this profile (same hardware family).
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
  Sliders,
  AlertTriangle,
  Cpu,
  Flame,
} from "lucide-react";
import type { DeviceProfile } from "./types";

const zone = (from: number, to: number, color: string) => ({ from, to, color });
const RED = "#f43f5e";
const AMBER = "#f59e0b";
const GREEN = "#10b981";
const BLUE = "#3b82f6";
const GRAY = "#a1a1aa";

// Prog fields expand to 30 flat fields for the schedule group.
const progFields = (min: number, max: number, prop: string, unit: string, step = 1) =>
  [1, 2, 3, 4, 5, 6].map((i) => ({
    key: `prog${i}_${prop}`,
    label: `Prog ${i} — ${prop.replace(/_/g, " ")}`,
    type: "number" as const,
    unit,
    step,
  }));

export const powdriveProfile: DeviceProfile = {
  id: "powdrive",
  name: "Powdrive Hybrid",
  sourceNote: "Grounded in POWDRIVE_SCHEMA + powdrive_registers.json + Sunsynk V1.18 protocol",

  strategies: [
    { id: "0", label: "Battery First", icon: BatteryCharging, blurb: "Charge battery before covering load or exporting" },
    { id: "1", label: "Load First", icon: Sun, blurb: "Cover home load directly from solar first" },
  ],
  strategyPreview: {
    "0": "Solar power charges your battery first; only once it's satisfied does the system cover home load or export.",
    "1": "Solar power covers your home's load first; the battery only charges from whatever is left over.",
  },

  sections: {
    /* ===================================================================
       HOME CARDS
       =================================================================== */
    reserve: {
      kind: "slider",
      icon: createElement(BatteryCharging, { className: "w-5 h-5" }),
      title: "Battery backup reserve",
      description: "Keep some battery in reserve for grid outages",
      fields: [
        {
          key: "battery_shutdown_capacity_pct",
          label: "Shutdown SOC (reserve floor)",
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
      ],
      preview: (v) =>
        `Battery is protected below ${v.battery_shutdown_capacity_pct}% and resumes discharging above ${v.battery_restart_capacity_pct}%.`,
    },

    gridCharging: {
      kind: "slider",
      icon: createElement(PlugZap, { className: "w-5 h-5" }),
      title: "Grid charging",
      description: "Allow grid electricity to charge your battery",
      fields: [
        { key: "ac_charge_battery", type: "toggle", label: "AC (grid) charge enabled" },
        {
          key: "grid_charge_battery_current_a",
          label: "Max charging current",
          min: 0,
          max: 120,
          unit: " A",
          formatValue: (v) => `${v} A`,
          zones: [zone(0, 20, GRAY), zone(20, 60, GREEN), zone(60, 100, AMBER), zone(100, 120, RED)],
        },
        {
          key: "grid_charging_start_capacity_pct",
          label: "Start when battery below (SOC)",
          min: 0,
          max: 100,
          unit: "%",
          zones: [zone(0, 100, BLUE)],
        },
      ],
      preview: (v) =>
        v.ac_charge_battery
          ? `Grid power will charge your battery at up to ${v.grid_charge_battery_current_a} A whenever it falls below ${v.grid_charging_start_capacity_pct}%.`
          : "Your battery will only be charged by solar power — grid charging is off.",
    },

    gridExport: {
      kind: "slider",
      icon: createElement(Upload, { className: "w-5 h-5" }),
      title: "Grid export",
      description: "Sell excess solar back to the grid",
      fields: [
        { key: "solar_sell", type: "toggle", label: "Feed solar to grid" },
        {
          key: "max_export_power_w",
          label: "Maximum export power",
          min: 0,
          max: 20000,
          step: 100,
          unit: " W",
          formatValue: (v) => `${v.toLocaleString()} W`,
        },
        {
          key: "zero_export_power_w",
          label: "Zero-export headroom",
          min: 0,
          max: 500,
          step: 10,
          unit: " W",
          alwaysVisible: true,
          zones: [zone(0, 500, GRAY)],
        },
      ],
      preview: (v) =>
        v.solar_sell
          ? `Your inverter will sell up to ${(v.max_export_power_w as number).toLocaleString()} W to the grid.`
          : `Solar will not be sold to the grid — export held near ${(v.zero_export_power_w as number).toLocaleString()} W.`,
    },

    /* ===================================================================
       HUB GROUPS
       =================================================================== */
    identity: {
      kind: "fields",
      tier: "default",
      icon: createElement(BatteryCharging, { className: "w-5 h-5" }),
      title: "Battery selection",
      description: "Chemistry, brand, and capacity.",
      fields: [
        { key: "battery_capacity_ah", label: "Battery capacity", type: "number", unit: "Ah", step: 1 },
        {
          key: "battery_mode_source",
          label: "Battery chemistry",
          type: "select",
          destructive: true,
          options: ["Lead-acid", "Lithium"],
          description: "Changing chemistry resets voltage thresholds and can affect safety behavior.",
        },
        {
          key: "lithium_battery_type",
          label: "Lithium battery brand",
          type: "select",
          destructive: true,
          options: ["Pylon", "Wattsonic", "Dyness", "BYD", "Other"],
        },
      ],
    },

    currentLimits: {
      kind: "fields",
      tier: "default",
      icon: createElement(Zap, { className: "w-5 h-5" }),
      title: "Current limits",
      description: "How fast the inverter is allowed to charge or discharge.",
      fields: [
        { key: "battery_max_charge_current_a", label: "Max charge current", type: "number", unit: "A", step: 1 },
        { key: "battery_max_discharge_current_a", label: "Max discharge current", type: "number", unit: "A", step: 1 },
      ],
    },

    voltageThresholds: {
      kind: "fields",
      tier: "default",
      icon: createElement(Sliders, { className: "w-5 h-5" }),
      title: "Voltage thresholds",
      description: "Voltage floors and ceilings for charge/discharge decisions.",
      fields: [
        { key: "battery_floating_voltage_v", label: "Float voltage", type: "number", unit: "V", step: 0.1 },
        { key: "battery_low_voltage_v", label: "Low-battery alarm", type: "number", unit: "V", step: 0.1 },
        {
          key: "battery_shutdown_voltage_v",
          label: "Shutdown voltage",
          type: "number",
          unit: "V",
          step: 0.1,
          description: "Battery voltage at which inverter shuts down",
        },
        { key: "battery_restart_voltage_v", label: "Restart voltage", type: "number", unit: "V", step: 0.1 },
        { key: "battery_low_capacity_pct", label: "Low-battery alarm SOC", type: "number", unit: "%", step: 1 },
      ],
    },

    equalization: {
      kind: "fields",
      tier: "default",
      icon: createElement(Zap, { className: "w-5 h-5" }),
      title: "Equalization",
      description: "Periodic higher-voltage charge used by lead-acid banks. Ignore for lithium.",
      fields: [
        { key: "battery_equalization_voltage_v", label: "Equalization voltage", type: "number", unit: "V", step: 0.1 },
        { key: "battery_equalization_day_cycle", label: "Cycle interval", type: "number", unit: "days", step: 1 },
        { key: "battery_equalization_time", label: "Duration", type: "number", unit: "min", step: 5 },
      ],
    },

    chargerAdvanced: {
      kind: "fields",
      tier: "default",
      icon: createElement(PlugZap, { className: "w-5 h-5" }),
      title: "Grid charge — voltage mode",
      description: "Only used when battery control is voltage-based (not SOC).",
      fields: [
        { key: "grid_charging_start_voltage_v", label: "Grid charge start voltage", type: "number", unit: "V", step: 0.1 },
      ],
    },

    inverter: {
      kind: "fields",
      tier: "default",
      icon: createElement(Cpu, { className: "w-5 h-5" }),
      title: "Peak shaving",
      description: "Cap on how much power the inverter draws from grid or generator.",
      fields: [
        { key: "gen_peak_shaving_power_w", label: "Generator peak shaving", type: "number", unit: "W", step: 100 },
        { key: "grid_peak_shaving_power_w", label: "Grid peak shaving", type: "number", unit: "W", step: 100 },
      ],
    },

    generator: {
      kind: "fields",
      tier: "default",
      icon: createElement(Flame, { className: "w-5 h-5" }),
      title: "Generator",
      description: "Optional backup generator behavior.",
      fields: [
        { key: "generator_charge_enabled", label: "Generator charges battery", type: "toggle" },
        {
          key: "generator_port_usage",
          label: "Generator port role",
          type: "select",
          options: ["Generator", "Grid"],
        },
        { key: "generator_max_run_time_h", label: "Max run time", type: "number", unit: "h", step: 1 },
        { key: "generator_down_time_h", label: "Min off time", type: "number", unit: "h", step: 1 },
        { key: "generator_charging_start_voltage_v", label: "Charge start voltage", type: "number", unit: "V", step: 0.1 },
        { key: "generator_charging_start_capacity_pct", label: "Charge start SOC", type: "number", unit: "%", step: 1 },
        { key: "generator_charge_battery_current_a", label: "Charge current", type: "number", unit: "A", step: 1 },
        {
          key: "generator_connected_to_grid_input",
          label: "Generator on grid input",
          type: "toggle",
          description: "Generator is wired into the AC-input (grid) port",
        },
      ],
    },

    schedule: {
      kind: "fields",
      tier: "default",
      icon: createElement(Clock, { className: "w-5 h-5" }),
      title: "TOU schedule (6 programs)",
      description: "Time-of-Use windows for charging and discharging. Values map to Powdrive Prog 1–6 registers.",
      fields: [
        ...progFields(0, 2359, "time", "HHMM"),
        ...progFields(0, 20000, "power_w", "W", 100),
        ...progFields(40, 62, "voltage_v", "V", 0.1),
        ...progFields(0, 100, "capacity_pct", "%"),
        ...[1, 2, 3, 4, 5, 6].map((i) => ({
          key: `prog${i}_charge_mode`,
          label: `Prog ${i} — charge mode`,
          type: "select" as const,
          options: ["No charge/discharge", "Charge", "Discharge", "Grid priority"],
        })),
      ],
    },

    smartLoad: {
      kind: "fields",
      tier: "default",
      icon: createElement(PlugZap, { className: "w-5 h-5" }),
      title: "Smart load",
      description: "Optional load circuit switched by battery level.",
      fields: [
        { key: "smartload_off_voltage_v", label: "Turn off below voltage", type: "number", unit: "V", step: 0.1 },
        { key: "smartload_off_capacity_pct", label: "Turn off below SOC", type: "number", unit: "%", step: 1 },
        { key: "smartload_on_voltage_v", label: "Turn on above voltage", type: "number", unit: "V", step: 0.1 },
        { key: "smartload_on_capacity_pct", label: "Turn on above SOC", type: "number", unit: "%", step: 1 },
      ],
    },

    protection: {
      kind: "fields",
      tier: "default",
      icon: createElement(Shield, { className: "w-5 h-5" }),
      title: "Protection",
      description: "Fault detection and auto-recovery behavior.",
      fields: [
        {
          key: "solar_arc_fault_mode",
          label: "Solar arc-fault detection",
          type: "select",
          options: ["Disabled", "Enabled"],
        },
      ],
    },

    installer: {
      kind: "fields",
      tier: "installer",
      icon: createElement(AlertTriangle, { className: "w-5 h-5" }),
      title: "Installer settings",
      description: "Grid-code compliance thresholds and export-limit metering config.",
      fields: [
        {
          key: "grid_standard",
          label: "Grid standard",
          type: "select",
          destructive: true,
          options: [
            "VDE0126 (DE)",
            "AS4777 (AU)",
            "G83 (UK)",
            "CEI0-21 (IT)",
            "NRS097 (ZA)",
            "VDE4105 (DE)",
            "Custom",
          ],
          description: "Grid connection standard. Inverter may restart when changed.",
        },
        {
          key: "grid_type_setting",
          label: "Grid phase",
          type: "select",
          options: ["Single-phase", "Split-phase", "Three-phase"],
        },
        {
          key: "grid_phase_sequence",
          label: "Phase sequence",
          type: "select",
          options: ["ABC", "ACB"],
        },
        {
          key: "limit_control_function",
          label: "Export limit control",
          type: "select",
          options: ["Disabled", "Grid CT", "Inverter CT"],
        },
        {
          key: "external_ct_direction",
          label: "CT clamp direction",
          type: "select",
          options: ["Normal", "Reversed"],
          description: "Reverse if import/export readings appear swapped.",
        },
        { key: "max_solar_sell_power_w", label: "Max solar sell power", type: "number", unit: "W", step: 100 },
        { key: "tou_selling", label: "TOU selling", type: "toggle" },
        {
          key: "solar_priority",
          label: "Solar priority (default)",
          type: "select",
          options: ["Battery First", "Load First"],
          description: "Duplicates the Energy strategy card; changing here changes both.",
        },
      ],
    },
  },

  homeCardIds: ["strategy", "reserve", "gridCharging", "gridExport"],
  hubGroupIds: [
    "identity",
    "currentLimits",
    "voltageThresholds",
    "equalization",
    "chargerAdvanced",
    "inverter",
    "generator",
    "schedule",
    "smartLoad",
    "protection",
    "installer",
  ],

  defaults: {
    strategy: "1",
    reserve: { battery_shutdown_capacity_pct: 20, battery_restart_capacity_pct: 30 },
    gridCharging: {
      ac_charge_battery: false,
      grid_charge_battery_current_a: 50,
      grid_charging_start_capacity_pct: 20,
    },
    gridExport: { solar_sell: true, max_export_power_w: 8000, zero_export_power_w: 20 },
    identity: {
      battery_capacity_ah: 280,
      battery_mode_source: "Lithium",
      lithium_battery_type: "Pylon",
    },
    currentLimits: { battery_max_charge_current_a: 100, battery_max_discharge_current_a: 100 },
    voltageThresholds: {
      battery_floating_voltage_v: 53.6,
      battery_low_voltage_v: 47.0,
      battery_shutdown_voltage_v: 44.0,
      battery_restart_voltage_v: 50.0,
      battery_low_capacity_pct: 20,
    },
    equalization: {
      battery_equalization_voltage_v: 55.0,
      battery_equalization_day_cycle: 30,
      battery_equalization_time: 60,
    },
    chargerAdvanced: { grid_charging_start_voltage_v: 48.0 },
    inverter: { gen_peak_shaving_power_w: 8000, grid_peak_shaving_power_w: 8000 },
    generator: {
      generator_charge_enabled: false,
      generator_port_usage: "Generator",
      generator_max_run_time_h: 12,
      generator_down_time_h: 1,
      generator_charging_start_voltage_v: 48.0,
      generator_charging_start_capacity_pct: 20,
      generator_charge_battery_current_a: 40,
      generator_connected_to_grid_input: false,
    },
    schedule: Object.fromEntries(
      [1, 2, 3, 4, 5, 6].flatMap((i) => [
        [`prog${i}_time`, i * 400],
        [`prog${i}_power_w`, 3000],
        [`prog${i}_voltage_v`, 52.0],
        [`prog${i}_capacity_pct`, 80],
        [`prog${i}_charge_mode`, "No charge/discharge"],
      ]),
    ),
    smartLoad: {
      smartload_off_voltage_v: 47.0,
      smartload_off_capacity_pct: 20,
      smartload_on_voltage_v: 53.0,
      smartload_on_capacity_pct: 60,
    },
    protection: { solar_arc_fault_mode: "Enabled" },
    installer: {
      grid_standard: "AS4777 (AU)",
      grid_type_setting: "Single-phase",
      grid_phase_sequence: "ABC",
      limit_control_function: "Grid CT",
      external_ct_direction: "Normal",
      max_solar_sell_power_w: 8000,
      tou_selling: false,
      solar_priority: "Load First",
    },
  },
};
