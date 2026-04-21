"""
Home Assistant MQTT Discovery helpers.

Pure functions — no I/O, no state.  All topic strings and discovery
payloads are constructed here so the publisher module stays clean.

HA Discovery protocol reference:
https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery
"""
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Per-device-type metric definitions
# state_class "measurement"       = live value
# state_class "total_increasing"  = cumulative counter (resets at midnight/restart)
# ---------------------------------------------------------------------------

# Sensors published for inverter-type devices (Senergy, Powdrive, Deye, Voltronic …)
INVERTER_METRICS: List[Dict[str, Any]] = [
    # ── Live power ──────────────────────────────────────────────────────────
    {"key": "pv_power_w",        "name": "Solar Power",   "device_class": "power",       "unit": "W",   "state_class": "measurement"},
    {"key": "grid_power_w",      "name": "Grid Power",    "device_class": "power",       "unit": "W",   "state_class": "measurement"},
    {"key": "load_power_w",      "name": "Load Power",    "device_class": "power",       "unit": "W",   "state_class": "measurement"},
    {"key": "battery_power_w",   "name": "Battery Power", "device_class": "power",       "unit": "W",   "state_class": "measurement"},
    # ── Battery state (as seen by the inverter) ──────────────────────────────
    {"key": "battery_soc_percent", "name": "Battery SoC",     "device_class": "battery", "unit": "%",   "state_class": "measurement"},
    {"key": "battery_voltage_v",   "name": "Battery Voltage",  "device_class": "voltage", "unit": "V",   "state_class": "measurement"},
    # ── Grid ────────────────────────────────────────────────────────────────
    {"key": "grid_voltage_v",    "name": "Grid Voltage",    "device_class": "voltage",   "unit": "V",   "state_class": "measurement"},
    {"key": "grid_frequency_hz", "name": "Grid Frequency",  "device_class": "frequency", "unit": "Hz",  "state_class": "measurement"},
    # ── Temperatures ────────────────────────────────────────────────────────
    {"key": "inverter_temp_c",   "name": "Inverter Temperature", "device_class": "temperature", "unit": "°C", "state_class": "measurement"},
    {"key": "battery_temp_c",    "name": "Battery Temperature",  "device_class": "temperature", "unit": "°C", "state_class": "measurement"},
    # ── Energy today (daily counters, reset at midnight) ────────────────────
    {"key": "pv_energy_today_kwh",            "name": "Solar Energy Today",           "device_class": "energy", "unit": "kWh", "state_class": "total_increasing"},
    {"key": "grid_import_today_kwh",          "name": "Grid Import Today",            "device_class": "energy", "unit": "kWh", "state_class": "total_increasing"},
    {"key": "grid_export_today_kwh",          "name": "Grid Export Today",            "device_class": "energy", "unit": "kWh", "state_class": "total_increasing"},
    {"key": "load_energy_today_kwh",          "name": "Load Energy Today",            "device_class": "energy", "unit": "kWh", "state_class": "total_increasing"},
    {"key": "battery_charge_today_kwh",       "name": "Battery Charge Today",         "device_class": "energy", "unit": "kWh", "state_class": "total_increasing"},
    {"key": "battery_discharge_today_kwh",    "name": "Battery Discharge Today",      "device_class": "energy", "unit": "kWh", "state_class": "total_increasing"},
    # ── Energy total (lifetime counters) ────────────────────────────────────
    # state_class "total" + last_reset_epoch prevents HA from counting the full
    # lifetime total as new energy when the device reconnects after being offline.
    # HA computes delta from the last known value, not from 0.
    {"key": "pv_energy_total_kwh",            "name": "Solar Energy Total",           "device_class": "energy", "unit": "kWh", "state_class": "total", "last_reset_template": "{{ value_json.last_reset_epoch }}"},
    {"key": "grid_import_total_kwh",          "name": "Grid Import Total",            "device_class": "energy", "unit": "kWh", "state_class": "total", "last_reset_template": "{{ value_json.last_reset_epoch }}"},
    {"key": "grid_export_total_kwh",          "name": "Grid Export Total",            "device_class": "energy", "unit": "kWh", "state_class": "total", "last_reset_template": "{{ value_json.last_reset_epoch }}"},
    {"key": "load_energy_total_kwh",          "name": "Load Energy Total",            "device_class": "energy", "unit": "kWh", "state_class": "total", "last_reset_template": "{{ value_json.last_reset_epoch }}"},
    {"key": "battery_charge_total_kwh",       "name": "Battery Charge Total",         "device_class": "energy", "unit": "kWh", "state_class": "total", "last_reset_template": "{{ value_json.last_reset_epoch }}"},
    {"key": "battery_discharge_total_kwh",    "name": "Battery Discharge Total",      "device_class": "energy", "unit": "kWh", "state_class": "total", "last_reset_template": "{{ value_json.last_reset_epoch }}"},
]

# Sensors published for battery-type devices (JK BMS, Pylontech, …)
BATTERY_METRICS: List[Dict[str, Any]] = [
    # ── Live state ──────────────────────────────────────────────────────────
    {"key": "battery_soc_percent",  "name": "State of Charge", "device_class": "battery",     "unit": "%",  "state_class": "measurement"},
    {"key": "battery_voltage_v",    "name": "Voltage",          "device_class": "voltage",     "unit": "V",  "state_class": "measurement"},
    {"key": "battery_current_a",    "name": "Current",          "device_class": "current",     "unit": "A",  "state_class": "measurement"},
    {"key": "battery_power_w",      "name": "Power",            "device_class": "power",       "unit": "W",  "state_class": "measurement"},
    {"key": "battery_temp_c",       "name": "Temperature",      "device_class": "temperature", "unit": "°C", "state_class": "measurement"},
    {"key": "battery_soh_percent",  "name": "State of Health",  "device_class": None, "unit": "%",  "state_class": "measurement"},
    {"key": "battery_cycle_count",  "name": "Cycle Count",      "device_class": None, "unit": None, "state_class": "total_increasing"},
    # Energy counters — calculated by the publisher via Redis accumulator (today)
    # and TimescaleDB integration (total), since JK BMS/Pylontech have no
    # hardware kWh registers.
    {"key": "battery_charge_today_kwh",    "name": "Charge Energy Today",    "device_class": "energy", "unit": "kWh", "state_class": "total_increasing"},
    {"key": "battery_discharge_today_kwh", "name": "Discharge Energy Today", "device_class": "energy", "unit": "kWh", "state_class": "total_increasing"},
    {"key": "battery_charge_total_kwh",    "name": "Charge Energy Total",    "device_class": "energy", "unit": "kWh", "state_class": "total", "last_reset_template": "{{ value_json.last_reset_epoch }}"},
    {"key": "battery_discharge_total_kwh", "name": "Discharge Energy Total", "device_class": "energy", "unit": "kWh", "state_class": "total", "last_reset_template": "{{ value_json.last_reset_epoch }}"},
]

# Fallback when device_type is unknown — broad set covering both types
_FALLBACK_METRICS: List[Dict[str, Any]] = INVERTER_METRICS + [
    m for m in BATTERY_METRICS
    if m["key"] not in {x["key"] for x in INVERTER_METRICS}
]

# Keep HA_METRICS as an alias for backwards compatibility
HA_METRICS = _FALLBACK_METRICS


def get_metrics_for_device_type(device_type: str) -> List[Dict[str, Any]]:
    """Return the appropriate metric list for the given device_type string."""
    dt = (device_type or "").lower()
    if dt == "inverter":
        return INVERTER_METRICS
    if dt == "battery":
        return BATTERY_METRICS
    return _FALLBACK_METRICS


def get_stale_metric_keys(device_type: str) -> List[str]:
    """
    Return metric keys that exist in the fallback set but NOT in the device's
    actual metric set.  The publisher sends empty retained payloads to these
    topics so HA removes the orphaned sensor entities.
    """
    active_keys = {m["key"] for m in get_metrics_for_device_type(device_type)}
    all_keys = {m["key"] for m in _FALLBACK_METRICS}
    return list(all_keys - active_keys)


# ---------------------------------------------------------------------------
# Topic builders
# ---------------------------------------------------------------------------

def build_state_topic(ha_username: str, device_serial: str) -> str:
    """Topic where System B publishes telemetry JSON."""
    return f"solarhub/ha/{ha_username}/{device_serial}/state"


def build_availability_topic(ha_username: str, device_serial: str) -> str:
    """Topic where System B publishes online/offline status."""
    return f"solarhub/ha/{ha_username}/{device_serial}/availability"


def build_discovery_topic(ha_username: str, device_serial: str, metric_key: str) -> str:
    """Topic for HA MQTT Discovery config payload (retained)."""
    unique_id = f"solarhub_{ha_username}_{device_serial}_{metric_key}"
    return f"homeassistant/sensor/{unique_id}/config"


def build_discovery_payload(
    ha_username: str,
    device_serial: str,
    device_name: str,
    manufacturer: str,
    model: str,
    metric: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the HA MQTT Discovery config payload for one sensor.

    HA parses this once and creates the sensor entity automatically.
    """
    unique_id = f"solarhub_{ha_username}_{device_serial}_{metric['key']}"
    state_topic = build_state_topic(ha_username, device_serial)
    availability_topic = build_availability_topic(ha_username, device_serial)

    payload: Dict[str, Any] = {
        "name": f"{device_name} {metric['name']}",
        "unique_id": unique_id,
        "state_topic": state_topic,
        "value_template": f"{{{{ value_json.{metric['key']} }}}}",
        "availability_topic": availability_topic,
        "payload_available": "online",
        "payload_not_available": "offline",
        "state_class": metric["state_class"],
        "device": {
            "identifiers": [f"solarhub_{device_serial}"],
            "name": device_name,
            "manufacturer": manufacturer or "Solar Hub",
            "model": model or "Inverter",
            "serial_number": device_serial,
            "via_device": f"solarhub_{ha_username}",
        },
    }

    if metric.get("unit") is not None:
        payload["unit_of_measurement"] = metric["unit"]

    if metric.get("device_class"):
        payload["device_class"] = metric["device_class"]

    if metric.get("last_reset_template"):
        payload["last_reset_value_template"] = metric["last_reset_template"]

    return payload
