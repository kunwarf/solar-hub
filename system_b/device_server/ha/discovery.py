"""
Home Assistant MQTT Discovery helpers.

Pure functions — no I/O, no state.  All topic strings and discovery
payloads are constructed here so the publisher module stays clean.

HA Discovery protocol reference:
https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery
"""
from typing import Any, Dict, List

# HA metrics we publish per device.
# state_class "measurement" = live value, "total_increasing" = cumulative counter
HA_METRICS: List[Dict[str, Any]] = [
    {
        "key": "battery_soc_percent",
        "name": "Battery SoC",
        "device_class": "battery",
        "unit": "%",
        "state_class": "measurement",
    },
    {
        "key": "battery_voltage_v",
        "name": "Battery Voltage",
        "device_class": "voltage",
        "unit": "V",
        "state_class": "measurement",
    },
    {
        "key": "battery_power_w",
        "name": "Battery Power",
        "device_class": "power",
        "unit": "W",
        "state_class": "measurement",
    },
    {
        "key": "pv_power_w",
        "name": "Solar Power",
        "device_class": "power",
        "unit": "W",
        "state_class": "measurement",
    },
    {
        "key": "grid_power_w",
        "name": "Grid Power",
        "device_class": "power",
        "unit": "W",
        "state_class": "measurement",
    },
    {
        "key": "load_power_w",
        "name": "Load Power",
        "device_class": "power",
        "unit": "W",
        "state_class": "measurement",
    },
    {
        "key": "pv_energy_today_kwh",
        "name": "Solar Energy Today",
        "device_class": "energy",
        "unit": "kWh",
        "state_class": "total_increasing",
    },
    {
        "key": "grid_import_today_kwh",
        "name": "Grid Import Today",
        "device_class": "energy",
        "unit": "kWh",
        "state_class": "total_increasing",
    },
    {
        "key": "load_energy_today_kwh",
        "name": "Load Energy Today",
        "device_class": "energy",
        "unit": "kWh",
        "state_class": "total_increasing",
    },
    {
        "key": "inverter_temp_c",
        "name": "Inverter Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
    },
    {
        "key": "battery_temp_c",
        "name": "Battery Temperature",
        "device_class": "temperature",
        "unit": "°C",
        "state_class": "measurement",
    },
    {
        "key": "grid_frequency_hz",
        "name": "Grid Frequency",
        "device_class": "frequency",
        "unit": "Hz",
        "state_class": "measurement",
    },
    {
        "key": "grid_voltage_v",
        "name": "Grid Voltage",
        "device_class": "voltage",
        "unit": "V",
        "state_class": "measurement",
    },
]


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
        "unit_of_measurement": metric["unit"],
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

    if metric.get("device_class"):
        payload["device_class"] = metric["device_class"]

    return payload
