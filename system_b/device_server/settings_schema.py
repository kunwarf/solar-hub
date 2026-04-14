"""
Per-family settings schema for Powdrive/Deye, Senergy, and Voltronic inverters.

Each family exposes different writable registers or named commands.
This module defines the human-readable metadata (label, group, unit, type,
min/max, enum options, scale, destructive flag) used by:

1. The GET /api/v1/devices/settings-schema/{protocol} endpoint (System A proxies this).
2. Frontend pages to render the correct controls for each field without an
   extra device round-trip.

Data is STATIC (register layout does not change across firmware minor versions).
If a register is renamed in a major firmware update, bump the schema version.
"""

from typing import Any, Dict, List, Literal, Optional

# Schema version — bump if fields change meaning
SCHEMA_VERSION = "1.0.0"

FieldType = Literal["number", "enum", "bool"]


def _field(
    key: str,
    label: str,
    type_: FieldType,
    unit: str = "",
    min_: Optional[float] = None,
    max_: Optional[float] = None,
    step: float = 1.0,
    scale: float = 1.0,
    options: Optional[Dict[str, Any]] = None,
    description: str = "",
    destructive: bool = False,
    writable: bool = True,
) -> Dict[str, Any]:
    """Build a single field descriptor."""
    f: Dict[str, Any] = {
        "key": key,
        "label": label,
        "type": type_,
        "unit": unit,
        "scale": scale,
        "writable": writable,
        "destructive": destructive,
    }
    if description:
        f["description"] = description
    if min_ is not None:
        f["min"] = min_
    if max_ is not None:
        f["max"] = max_
    if type_ == "number":
        f["step"] = step
    if options is not None:
        f["options"] = options
    return f


# =============================================================================
# POWDRIVE / DEYE SCHEMA
# =============================================================================

POWDRIVE_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "battery",
        "label": "Battery",
        "fields": [
            _field("battery_capacity_ah", "Battery Capacity", "number", unit="Ah", min_=10, max_=2000, step=1),
            _field("battery_max_charge_current_a", "Max Charge Current", "number", unit="A", min_=0, max_=200, step=1),
            _field("battery_max_discharge_current_a", "Max Discharge Current", "number", unit="A", min_=0, max_=200, step=1),
            _field("battery_equalization_voltage_v", "Equalization Voltage", "number", unit="V", min_=40.0, max_=63.0, step=0.1),
            _field("battery_floating_voltage_v", "Float Voltage", "number", unit="V", min_=40.0, max_=62.0, step=0.1),
            _field("battery_shutdown_voltage_v", "Shutdown Voltage", "number", unit="V", min_=20.0, max_=50.0, step=0.1,
                   description="Battery voltage at which inverter shuts down", destructive=False),
            _field("battery_restart_voltage_v", "Restart Voltage", "number", unit="V", min_=20.0, max_=52.0, step=0.1),
            _field("battery_low_voltage_v", "Low Battery Alarm Voltage", "number", unit="V", min_=20.0, max_=52.0, step=0.1),
            _field("battery_shutdown_capacity_pct", "Shutdown SOC", "number", unit="%", min_=0, max_=30, step=1,
                   description="Battery SOC (%) at which inverter shuts down"),
            _field("battery_restart_capacity_pct", "Restart SOC", "number", unit="%", min_=0, max_=50, step=1),
            _field("battery_low_capacity_pct", "Low Battery Alarm SOC", "number", unit="%", min_=0, max_=50, step=1),
            _field("battery_equalization_day_cycle", "Equalization Cycle (days)", "number", unit="days", min_=1, max_=90, step=1),
            _field("battery_equalization_time", "Equalization Duration", "number", unit="min", min_=5, max_=900, step=5),
            _field("battery_mode_source", "Battery Mode Source", "enum", options={
                "0": "Lead-acid", "1": "Lithium"
            }, description="Select battery chemistry profile", destructive=True),
            _field("lithium_battery_type", "Lithium Battery Brand", "enum", options={
                "0": "Pylon", "1": "Wattsonic", "2": "Dyness", "3": "BYD", "4": "Other"
            }, destructive=True),
        ],
    },
    {
        "id": "charger",
        "label": "Charger",
        "fields": [
            _field("ac_charge_battery", "AC Charge Battery", "bool", description="Allow grid to charge battery"),
            _field("grid_charge_battery_current_a", "Max Grid Charge Current", "number", unit="A", min_=0, max_=120, step=1),
            _field("grid_charging_start_voltage_v", "Grid Charge Start Voltage", "number", unit="V", min_=20.0, max_=58.0, step=0.1),
            _field("grid_charging_start_capacity_pct", "Grid Charge Start SOC", "number", unit="%", min_=0, max_=100, step=1),
        ],
    },
    {
        "id": "grid",
        "label": "Grid & Export",
        "fields": [
            _field("solar_sell", "Solar Feed-to-Grid", "bool", description="Allow exporting solar to utility"),
            _field("max_export_power_w", "Max Export Power", "number", unit="W", min_=0, max_=20000, step=100),
            _field("max_solar_sell_power_w", "Max Solar Sell Power", "number", unit="W", min_=0, max_=20000, step=100),
            _field("zero_export_power_w", "Zero Export Threshold", "number", unit="W", min_=0, max_=500, step=10,
                   description="Permitted export headroom (≤ this value is treated as zero-export)"),
            _field("tou_selling", "TOU Selling", "bool", description="Enable Time-of-Use selling to grid"),
            _field("grid_standard", "Grid Standard", "enum", options={
                "0": "VDE0126 (DE)", "1": "AS4777 (AU)", "2": "G83 (UK)", "3": "CEI0-21 (IT)",
                "4": "NRS097 (ZA)", "5": "VDE4105 (DE)", "6": "Custom"
            }, destructive=True, description="Grid connection standard. Inverter may restart."),
            _field("grid_type_setting", "Grid Phase", "enum", options={"0": "Single-phase", "1": "Split-phase", "2": "Three-phase"}),
            _field("grid_phase_sequence", "Phase Sequence", "enum", options={"0": "ABC", "1": "ACB"}),
            _field("limit_control_function", "Export Limit Control", "enum", options={
                "0": "Disabled", "1": "Grid CT", "2": "Inverter CT"
            }),
            _field("external_ct_direction", "CT Clamp Direction", "enum", options={"0": "Normal", "1": "Reversed"},
                   description="Reverse if export/import readings are swapped"),
        ],
    },
    {
        "id": "inverter",
        "label": "Inverter / Output",
        "fields": [
            _field("solar_priority", "Solar Priority", "enum", options={
                "0": "Battery First", "1": "Load First"
            }, description="When to route solar: charge battery or power load first"),
            _field("gen_peak_shaving_power_w", "Generator Peak Shaving", "number", unit="W", min_=0, max_=20000, step=100),
            _field("grid_peak_shaving_power_w", "Grid Peak Shaving", "number", unit="W", min_=0, max_=20000, step=100),
        ],
    },
    {
        "id": "generator",
        "label": "Generator",
        "fields": [
            _field("generator_charge_enabled", "Generator Charges Battery", "bool"),
            _field("generator_port_usage", "Generator Port Usage", "enum", options={"0": "Generator", "1": "Grid"}),
            _field("generator_max_run_time_h", "Max Run Time", "number", unit="h", min_=1, max_=24, step=1),
            _field("generator_down_time_h", "Min Off Time", "number", unit="h", min_=1, max_=24, step=1),
            _field("generator_charging_start_voltage_v", "Gen Charge Start Voltage", "number", unit="V", min_=20.0, max_=55.0, step=0.1),
            _field("generator_charging_start_capacity_pct", "Gen Charge Start SOC", "number", unit="%", min_=0, max_=100, step=1),
            _field("generator_charge_battery_current_a", "Gen Max Charge Current", "number", unit="A", min_=0, max_=120, step=1),
            _field("generator_connected_to_grid_input", "Generator on Grid Input", "bool",
                   description="Generator is connected to AC-input (grid) port"),
        ],
    },
    {
        "id": "schedule",
        "label": "TOU Schedule",
        "fields": [
            # Prog 1–6 time, power, voltage, capacity, charge_mode
            *[
                _field(f"prog{i}_time",  f"Program {i} Start Time", "number", unit="HHMM",
                       min_=0, max_=2359, step=1, description="Format: HHMM (e.g. 0600 = 06:00)")
                for i in range(1, 7)
            ],
            *[
                _field(f"prog{i}_power_w", f"Program {i} Power Limit", "number", unit="W", min_=0, max_=20000, step=100)
                for i in range(1, 7)
            ],
            *[
                _field(f"prog{i}_voltage_v", f"Program {i} Voltage", "number", unit="V", min_=40.0, max_=62.0, step=0.1)
                for i in range(1, 7)
            ],
            *[
                _field(f"prog{i}_capacity_pct", f"Program {i} SOC Limit", "number", unit="%", min_=0, max_=100, step=1)
                for i in range(1, 7)
            ],
            *[
                _field(f"prog{i}_charge_mode", f"Program {i} Charge Mode", "enum",
                       options={"0": "No charge/discharge", "1": "Charge", "2": "Discharge", "3": "Grid priority"})
                for i in range(1, 7)
            ],
        ],
    },
    {
        "id": "protection",
        "label": "Protection",
        "fields": [
            _field("solar_arc_fault_mode", "Arc Fault Detection", "enum", options={"0": "Disabled", "1": "Enabled"}),
            _field("smartload_off_voltage_v", "Smart Load Off Voltage", "number", unit="V", min_=20.0, max_=55.0, step=0.1),
            _field("smartload_off_capacity_pct", "Smart Load Off SOC", "number", unit="%", min_=0, max_=100, step=1),
            _field("smartload_on_voltage_v", "Smart Load On Voltage", "number", unit="V", min_=20.0, max_=58.0, step=0.1),
            _field("smartload_on_capacity_pct", "Smart Load On SOC", "number", unit="%", min_=0, max_=100, step=1),
        ],
    },
]


# =============================================================================
# SENERGY SCHEMA
# =============================================================================

SENERGY_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "battery",
        "label": "Battery",
        "sign_note": "Senergy sign convention: positive battery power = discharging, negative = charging.",
        "fields": [
            _field("battery_capacity_ah", "Battery Capacity", "number", unit="Ah", min_=10, max_=2000, step=1),
            _field("battery_max_charge_current_a", "Max Charge Current", "number", unit="A", min_=0, max_=200, step=1),
            _field("battery_max_discharge_current_a", "Max Discharge Current", "number", unit="A", min_=0, max_=200, step=1),
            _field("battery_bulk_voltage_v", "Bulk Charge Voltage", "number", unit="V",
                   min_=40.0, max_=62.0, step=0.1, scale=0.1,
                   description="Target absorption charge voltage"),
            _field("battery_float_voltage_v", "Float Charge Voltage", "number", unit="V",
                   min_=40.0, max_=62.0, step=0.1, scale=0.1),
            _field("battery_low_voltage_v", "Low Battery Alarm Voltage", "number", unit="V",
                   min_=20.0, max_=55.0, step=0.1, scale=0.1),
            _field("battery_shutdown_voltage_v", "Shutdown Voltage", "number", unit="V",
                   min_=20.0, max_=50.0, step=0.1, scale=0.1,
                   description="Battery voltage at which inverter shuts down"),
            _field("battery_restart_voltage_v", "Restart Voltage", "number", unit="V",
                   min_=20.0, max_=52.0, step=0.1, scale=0.1),
            _field("battery_shutdown_capacity_pct", "Shutdown SOC", "number", unit="%", min_=0, max_=30, step=1),
            _field("battery_restart_capacity_pct", "Restart SOC", "number", unit="%", min_=0, max_=50, step=1),
            _field("battery_type", "Battery Chemistry", "enum", options={
                "0": "Lead-acid", "1": "Lithium (generic)", "2": "Pylon", "3": "BYD", "4": "Other"
            }, destructive=True),
        ],
    },
    {
        "id": "grid_code",
        "label": "Grid Code",
        "fields": [
            _field("grid_standard", "Grid Standard / Country Code", "enum", options={
                "0": "VDE0126 (DE)", "1": "AS4777 (AU)", "2": "G83 (UK)", "3": "CEI0-21 (IT)",
                "4": "NRS097 (ZA)", "5": "Custom"
            }, destructive=True,
               description="Inverter may restart when changing grid code. Only change if required by local regulations."),
            _field("grid_frequency_set", "Grid Nominal Frequency", "enum", options={"50": "50 Hz", "60": "60 Hz"}),
            _field("grid_voltage_set", "Grid Nominal Voltage", "enum", options={
                "220": "220 V", "230": "230 V", "240": "240 V"
            }),
            _field("anti_island_enable", "Anti-Islanding", "bool",
                   description="Enable anti-islanding protection (required by most grid codes)"),
        ],
    },
    {
        "id": "charger",
        "label": "Charger",
        "fields": [
            _field("ac_charge_enable", "AC Charge Enable", "bool", description="Allow grid to charge battery"),
            _field("ac_charge_current_a", "AC Charge Max Current", "number", unit="A", min_=0, max_=120, step=1),
            _field("ac_charge_start_soc_pct", "AC Charge Start SOC", "number", unit="%", min_=0, max_=100, step=1),
            _field("ac_charge_end_soc_pct", "AC Charge End SOC", "number", unit="%", min_=0, max_=100, step=1),
        ],
    },
    {
        "id": "work_mode",
        "label": "Work Mode",
        "fields": [
            _field("work_mode", "Work Mode", "enum", options={
                "0": "Self-Consumption",
                "1": "Backup Priority",
                "2": "Feed-in Priority",
                "3": "Time-of-Use",
            }, description="Determines how the inverter balances solar, battery, and grid"),
            _field("export_limit_enable", "Export Limit", "bool", description="Limit power fed to grid"),
            _field("export_limit_power_w", "Export Limit Power", "number", unit="W", min_=0, max_=20000, step=100),
            _field("priority_load_soc_pct", "Priority Load SOC", "number", unit="%", min_=0, max_=100, step=1,
                   description="SOC below which load is powered from grid rather than battery"),
        ],
    },
    {
        "id": "protection",
        "label": "Protection",
        "fields": [
            _field("over_load_restart", "Overload Auto Restart", "bool"),
            _field("over_temp_restart", "Over-Temperature Auto Restart", "bool"),
            _field("backflow_protect", "Backflow Protection", "bool",
                   description="Prevent power from flowing back into PV panels"),
        ],
    },
]


# =============================================================================
# VOLTRONIC SCHEMA  (command-oriented, not register-based)
# =============================================================================

VOLTRONIC_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "output",
        "label": "Output",
        "fields": [
            _field("set_output_priority", "Output Source Priority", "enum", options={
                "utility": "Utility First",
                "solar": "Solar First",
                "sbu": "Solar → Battery → Utility (SBU)",
            }, description="Determines which source powers the output when multiple are available"),
            _field("set_output_mode", "Output Mode", "enum", options={
                "single": "Single unit",
                "parallel": "Parallel",
                "phase_1_3": "Phase 1 of 3",
                "phase_2_3": "Phase 2 of 3",
                "phase_3_3": "Phase 3 of 3",
            }),
        ],
    },
    {
        "id": "charger",
        "label": "Charger",
        "fields": [
            _field("set_charger_priority", "Charger Source Priority", "enum", options={
                "utility": "Utility First",
                "solar": "Solar First",
                "solar_utility": "Solar + Utility",
                "solar_only": "Solar Only",
            }),
            _field("set_max_charging_current", "Max Total Charging Current", "number",
                   unit="A", min_=10, max_=120, step=1),
            _field("set_max_ac_charging_current", "Max AC (Grid) Charging Current", "number",
                   unit="A", min_=2, max_=100, step=1),
        ],
    },
    {
        "id": "battery",
        "label": "Battery",
        "fields": [
            _field("set_battery_type", "Battery Type", "enum", options={
                "agm": "AGM",
                "flooded": "Flooded / Wet",
                "user": "User-defined",
            }, destructive=True, description="Changing battery type resets voltage thresholds."),
            _field("set_bulk_voltage", "Bulk Charge Voltage", "number",
                   unit="V", min_=20.0, max_=62.0, step=0.1),
            _field("set_float_voltage", "Float Charge Voltage", "number",
                   unit="V", min_=20.0, max_=62.0, step=0.1),
            _field("set_low_voltage_cutoff", "Low Voltage Cutoff", "number",
                   unit="V", min_=20.0, max_=50.0, step=0.1,
                   description="Battery voltage below which output disconnects"),
            _field("set_recharge_voltage", "Re-charge Trigger Voltage", "number",
                   unit="V", min_=20.0, max_=58.0, step=0.1,
                   description="Battery must rise above this voltage before reconnecting from cutoff"),
        ],
    },
    {
        "id": "grid",
        "label": "Grid",
        "fields": [
            _field("set_input_voltage_range", "AC Input Voltage Range", "enum", options={
                "appliance": "Appliance (wide range)",
                "ups": "UPS (narrow range)",
            }, description="Narrow range rejects brownouts; wide range tolerates voltage sag"),
            _field("set_grid_max_charging_current", "Grid Max Charging Current", "number",
                   unit="A", min_=2, max_=100, step=1),
        ],
    },
    {
        "id": "system",
        "label": "System",
        "fields": [
            _field("enable_buzzer", "Buzzer", "bool", description="Enable/disable audible alarm"),
            _field("enable_overload_bypass", "Overload Bypass", "bool",
                   description="Pass load through directly when inverter is overloaded"),
            _field("enable_solar_feed_to_grid", "Solar Feed-to-Grid", "bool",
                   description="Allow excess solar to be exported to utility"),
            _field("enable_lcd_backlight", "LCD Backlight Always On", "bool"),
            _field("restore_factory_defaults", "Restore Factory Defaults", "bool",
                   destructive=True,
                   description="WARNING: Resets ALL settings to factory defaults. Cannot be undone."),
        ],
    },
]


# =============================================================================
# Registry
# =============================================================================

SCHEMAS_BY_PROTOCOL: Dict[str, Any] = {
    # Powdrive and Deye share the same Modbus register layout
    "powdrive": {"version": SCHEMA_VERSION, "family": "powdrive", "groups": POWDRIVE_SCHEMA},
    "deye": {"version": SCHEMA_VERSION, "family": "powdrive", "groups": POWDRIVE_SCHEMA},
    "senergy": {"version": SCHEMA_VERSION, "family": "senergy", "groups": SENERGY_SCHEMA},
    "voltronic_pi30": {"version": SCHEMA_VERSION, "family": "voltronic", "groups": VOLTRONIC_SCHEMA},
    "voltronic_pi18": {"version": SCHEMA_VERSION, "family": "voltronic", "groups": VOLTRONIC_SCHEMA},
    "voltronic_pi16": {"version": SCHEMA_VERSION, "family": "voltronic", "groups": VOLTRONIC_SCHEMA},
    "voltronic_pi17": {"version": SCHEMA_VERSION, "family": "voltronic", "groups": VOLTRONIC_SCHEMA},
    "voltronic_pi34": {"version": SCHEMA_VERSION, "family": "voltronic", "groups": VOLTRONIC_SCHEMA},
}


def get_schema(protocol_id: str) -> Optional[Dict[str, Any]]:
    """Return settings schema for a given protocol ID, or None if unknown."""
    return SCHEMAS_BY_PROTOCOL.get(protocol_id.lower())
