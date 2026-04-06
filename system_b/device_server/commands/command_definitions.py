"""
Command-to-register mappings for different device types.

Defines how high-level commands (e.g., "set_power_limit") map to
Modbus register write operations for each device type.
"""
from enum import Enum
from typing import Any, Dict, List, Optional


class CommandType(str, Enum):
    """Supported command types."""
    # Inverter commands
    SET_POWER_LIMIT = "set_power_limit"
    SET_MODE = "set_mode"
    RESTART = "restart"
    SET_REACTIVE_POWER = "set_reactive_power"

    # Battery commands
    SET_CHARGE_LIMIT = "set_charge_limit"
    SET_DISCHARGE_LIMIT = "set_discharge_limit"
    SET_SOC_LIMITS = "set_soc_limits"
    FORCE_CHARGE = "force_charge"
    FORCE_DISCHARGE = "force_discharge"

    # Meter commands (usually read-only, but some support reset)
    RESET_ENERGY_COUNTER = "reset_energy_counter"


class OperatingMode(int, Enum):
    """Inverter operating modes."""
    AUTO = 0
    MANUAL = 1
    STANDBY = 2
    GRID_TIE = 3
    OFF_GRID = 4


INVERTER_COMMANDS: Dict[str, Dict[str, Any]] = {
    "query_settings": {
        "operation": "read_all_configurable",  # Read all RW registers from register map
        "description": "Query all configurable settings from inverter",
        "groups": ["battery", "grid", "work_mode", "tou_scheduling", "generator", "auxiliary"],
        # Legacy registers for backward compatibility (subset of all registers)
        "registers": [
            {"address": 143, "name": "max_export_power_w", "scale": 1},  # Max Export Power (W)
            {"address": 145, "name": "solar_sell", "scale": 1},  # Solar sell (0=disabled, 1=enabled)
            {"address": 141, "name": "solar_priority", "scale": 1},  # 0=Battery first, 1=Load first
            {"address": 108, "name": "battery_max_charge_current_a", "scale": 1},  # Battery max charge (A)
            {"address": 109, "name": "battery_max_discharge_current_a", "scale": 1},  # Battery max discharge (A)
            {"address": 102, "name": "battery_capacity_ah", "scale": 1},  # Battery capacity (Ah)
        ],
    },
    "update_settings": {
        "operation": "read_modify_write",  # Read current → validate → write changed → verify
        "param": "settings",  # Dict of register_id: new_value
        "param_type": "dict",
        "description": "Update device settings (reads current values, modifies changed, writes changed only)",
        "supports_rollback": True,  # Rollback on write failure
    },
    "set_power_limit": {
        "register": 40001,
        "size": 1,
        "scale": 10,  # Value in % * 10 (e.g., 80% = 800)
        "param": "value",
        "param_type": "int",
        "min_value": 0,
        "max_value": 100,
        "description": "Set power limit percentage (0-100%)",
    },
    "set_mode": {
        "register": 40002,
        "size": 1,
        "values": {
            "auto": OperatingMode.AUTO.value,
            "manual": OperatingMode.MANUAL.value,
            "standby": OperatingMode.STANDBY.value,
            "grid_tie": OperatingMode.GRID_TIE.value,
            "off_grid": OperatingMode.OFF_GRID.value,
        },
        "param": "mode",
        "param_type": "str",
        "description": "Set operating mode (auto, manual, standby, grid_tie, off_grid)",
    },
    "restart": {
        "register": 40010,
        "size": 1,
        "fixed_value": 1,  # Write 1 to trigger restart
        "description": "Restart inverter",
    },
    "set_reactive_power": {
        "register": 40003,
        "size": 1,
        "scale": 10,  # Value in % * 10
        "param": "value",
        "param_type": "int",
        "min_value": -100,
        "max_value": 100,
        "description": "Set reactive power percentage (-100 to 100%)",
    },
}


BATTERY_COMMANDS: Dict[str, Dict[str, Any]] = {
    "query_settings": {
        "operation": "read_all_configurable",
        "description": "Query all configurable settings from battery",
        "groups": ["battery", "protection"],
    },
    "update_settings": {
        "operation": "read_modify_write",
        "param": "settings",
        "param_type": "dict",
        "description": "Update battery settings safely",
        "supports_rollback": True,
    },
    "set_charge_limit": {
        "register": 40100,
        "size": 1,
        "scale": 10,  # Current in A * 10
        "param": "current",
        "param_type": "float",
        "min_value": 0,
        "max_value": 100,
        "description": "Set max charge current (A)",
    },
    "set_discharge_limit": {
        "register": 40101,
        "size": 1,
        "scale": 10,  # Current in A * 10
        "param": "current",
        "param_type": "float",
        "min_value": 0,
        "max_value": 100,
        "description": "Set max discharge current (A)",
    },
    "set_soc_limits": {
        "register": 40102,
        "size": 2,  # Two registers: min_soc, max_soc
        "params": ["min_soc", "max_soc"],
        "param_type": "int",
        "min_value": 0,
        "max_value": 100,
        "description": "Set SOC limits (min%, max%)",
    },
    "force_charge": {
        "register": 40104,
        "size": 1,
        "fixed_value": 1,
        "description": "Force battery to charge mode",
    },
    "force_discharge": {
        "register": 40105,
        "size": 1,
        "fixed_value": 1,
        "description": "Force battery to discharge mode",
    },
}


METER_COMMANDS: Dict[str, Dict[str, Any]] = {
    "query_settings": {
        "operation": "read_all_configurable",
        "description": "Query all configurable settings from meter",
        "groups": ["specification", "advanced"],
    },
    "update_settings": {
        "operation": "read_modify_write",
        "param": "settings",
        "param_type": "dict",
        "description": "Update meter settings safely",
        "supports_rollback": True,
    },
    "reset_energy_counter": {
        "register": 40200,
        "size": 1,
        "fixed_value": 1,
        "description": "Reset energy counter to zero",
    },
}


# =============================================================================
# Voltronic serial command definitions
# =============================================================================
# These map high-level command names to Voltronic serial command templates.
# The adapter sends the command as a CRC-framed serial string and checks the
# response for '(ACK' (success) or '(NAK' (rejected by device).
#
# cmd_template: Python str.format() template.  Placeholders are filled from
#               the validated 'params' dict before CRC and framing are applied.
#
# Applies to PI30, PI18, PI16, PI41, PI30MAX families (standard frame format).
# PI17 (SEC format) commands follow the same semantics but use different
# command names — handled by 'sec_cmd_template' override when present.
#
# Reference: Voltronic PI30 Communication Protocol 2015, PI30MAX 2021.
# =============================================================================

VOLTRONIC_COMMANDS: Dict[str, Dict[str, Any]] = {

    # ------------------------------------------------------------------
    # Source priorities
    # ------------------------------------------------------------------
    "set_output_priority": {
        "cmd_template": "POP{value:02d}",
        "param": "priority",
        "param_type": "int",
        "values": {"utility": 0, "solar": 1, "sbu": 2},
        "min_value": 0,
        "max_value": 2,
        "description": (
            "Set output source priority.  "
            "priority: 0=utility_first, 1=solar_first, 2=SBU"
        ),
    },
    "set_charger_priority": {
        "cmd_template": "PCP{value:02d}",
        "param": "priority",
        "param_type": "int",
        "values": {
            "utility":       0,
            "solar":         1,
            "solar_utility": 2,
            "solar_only":    3,
        },
        "min_value": 0,
        "max_value": 3,
        "description": (
            "Set charger source priority.  "
            "priority: 0=utility_first, 1=solar_first, 2=solar+utility, 3=solar_only"
        ),
    },

    # ------------------------------------------------------------------
    # Charging current limits
    # ------------------------------------------------------------------
    "set_max_charging_current": {
        "cmd_template": "MCHGC{value:03d}",
        "param": "current",
        "param_type": "int",
        "min_value": 10,
        "max_value": 120,
        "description": "Set maximum total charging current (A, 10–120).",
    },
    "set_max_ac_charging_current": {
        "cmd_template": "MUCHGC{value:03d}",
        "param": "current",
        "param_type": "int",
        "min_value": 2,
        "max_value": 100,
        "description": "Set maximum AC (grid) charging current (A, 2–100).",
    },

    # ------------------------------------------------------------------
    # Battery configuration
    # ------------------------------------------------------------------
    "set_battery_type": {
        "cmd_template": "PBATCD{value:02d}",
        "param": "battery_type",
        "param_type": "int",
        "values": {"agm": 0, "flooded": 1, "user": 2},
        "min_value": 0,
        "max_value": 2,
        "description": "Set battery type (0=AGM, 1=Flooded, 2=User-defined).",
    },
    "set_bulk_voltage": {
        "cmd_template": "PBCV{value:.1f}",
        "param": "voltage",
        "param_type": "float",
        "min_value": 20.0,
        "max_value": 62.0,
        "description": "Set battery bulk charge voltage (V, e.g. 56.4).",
    },
    "set_float_voltage": {
        "cmd_template": "PBDV{value:.1f}",
        "param": "voltage",
        "param_type": "float",
        "min_value": 20.0,
        "max_value": 62.0,
        "description": "Set battery float charge voltage (V, e.g. 54.0).",
    },
    "set_low_voltage_cutoff": {
        "cmd_template": "PSDV{value:.1f}",
        "param": "voltage",
        "param_type": "float",
        "min_value": 20.0,
        "max_value": 50.0,
        "description": "Set battery low-voltage shutdown cutoff (V, e.g. 42.0).",
    },
    "set_recharge_voltage": {
        "cmd_template": "PBCVV{value:.1f}",
        "param": "voltage",
        "param_type": "float",
        "min_value": 20.0,
        "max_value": 58.0,
        "description": "Set battery reconnect/recharge trigger voltage (V, e.g. 46.0).",
    },

    # ------------------------------------------------------------------
    # Grid / input
    # ------------------------------------------------------------------
    "set_input_voltage_range": {
        "cmd_template": "PGR{value:02d}",
        "param": "range",
        "param_type": "int",
        "values": {"appliance": 0, "ups": 1},
        "min_value": 0,
        "max_value": 1,
        "description": "Set AC input voltage range (0=Appliance wide range, 1=UPS narrow range).",
    },
    "set_grid_max_charging_current": {
        "cmd_template": "MUCHGC{value:03d}",
        "param": "current",
        "param_type": "int",
        "min_value": 2,
        "max_value": 100,
        "description": "Alias for set_max_ac_charging_current.",
    },

    # ------------------------------------------------------------------
    # Feature flags (enable/disable via PE/PD prefix)
    # ------------------------------------------------------------------
    "enable_buzzer": {
        "cmd_template": "PEa",
        "description": "Enable audible alarm buzzer.",
    },
    "disable_buzzer": {
        "cmd_template": "PDa",
        "description": "Disable audible alarm buzzer.",
    },
    "enable_overload_bypass": {
        "cmd_template": "PEb",
        "description": "Enable overload bypass (load passes through when inverter overloaded).",
    },
    "disable_overload_bypass": {
        "cmd_template": "PDb",
        "description": "Disable overload bypass.",
    },
    "enable_solar_feed_to_grid": {
        "cmd_template": "PEg",
        "description": "Enable solar feed-to-grid (export surplus PV to utility).",
    },
    "disable_solar_feed_to_grid": {
        "cmd_template": "PDg",
        "description": "Disable solar feed-to-grid.",
    },
    "enable_lcd_backlight": {
        "cmd_template": "PEn",
        "description": "Keep LCD backlight on.",
    },
    "disable_lcd_backlight_timeout": {
        "cmd_template": "PDn",
        "description": "Let LCD backlight time out after inactivity.",
    },

    # ------------------------------------------------------------------
    # Output mode (parallel/phase)
    # ------------------------------------------------------------------
    "set_output_mode": {
        "cmd_template": "POPM{value:02d}",
        "param": "mode",
        "param_type": "int",
        "values": {
            "single":    0,
            "parallel":  1,
            "phase_1_3": 2,
            "phase_2_3": 3,
            "phase_3_3": 4,
        },
        "min_value": 0,
        "max_value": 4,
        "description": "Set output mode (0=single, 1=parallel, 2–4=3-phase splits).",
    },

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------
    "restore_factory_defaults": {
        "cmd_template": "PF",
        "description": "Restore all settings to factory defaults.  CAUTION: irreversible.",
    },
}


DEVICE_COMMANDS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "inverter": INVERTER_COMMANDS,
    "battery": BATTERY_COMMANDS,
    "meter": METER_COMMANDS,
}


def get_command_definition(
    device_type: str,
    command_type: str,
) -> Optional[Dict[str, Any]]:
    """
    Get command definition for a device type and command.

    Args:
        device_type: Type of device (inverter, battery, meter)
        command_type: Command name

    Returns:
        Command definition dict or None if not found
    """
    device_commands = DEVICE_COMMANDS.get(device_type.lower(), {})
    return device_commands.get(command_type)


def get_available_commands(device_type: str) -> List[str]:
    """
    Get list of available commands for a device type.

    Args:
        device_type: Type of device

    Returns:
        List of command names
    """
    return list(DEVICE_COMMANDS.get(device_type.lower(), {}).keys())


def validate_command_params(
    command_def: Dict[str, Any],
    params: Dict[str, Any],
) -> tuple[bool, Optional[str]]:
    """
    Validate command parameters against definition.

    Args:
        command_def: Command definition
        params: Parameters to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Fixed value commands don't need params
    if "fixed_value" in command_def:
        return True, None

    # Check for required parameter
    if "param" in command_def:
        param_name = command_def["param"]
        if param_name not in params:
            return False, f"Missing required parameter: {param_name}"

        value = params[param_name]

        # Validate enum values
        if "values" in command_def:
            if value not in command_def["values"]:
                valid_values = list(command_def["values"].keys())
                return False, f"Invalid value '{value}'. Must be one of: {valid_values}"

        # Validate numeric range
        if "min_value" in command_def and "max_value" in command_def:
            try:
                num_value = float(value)
                if num_value < command_def["min_value"] or num_value > command_def["max_value"]:
                    return False, (
                        f"Value {num_value} out of range "
                        f"[{command_def['min_value']}, {command_def['max_value']}]"
                    )
            except (ValueError, TypeError):
                return False, f"Parameter '{param_name}' must be numeric"

    # Check for multi-parameter commands
    if "params" in command_def:
        for param_name in command_def["params"]:
            if param_name not in params:
                return False, f"Missing required parameter: {param_name}"

    return True, None
