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
