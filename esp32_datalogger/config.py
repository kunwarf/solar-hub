"""
Configuration management for ESP32 Data Logger.

Handles loading, saving, and merging configuration from JSON files.
"""
import json

# File paths
CONFIG_FILE = "config.json"
WIFI_FILE = "wifi.json"

# Access Point settings
AP_PREFIX = "SolarLogger-"
AP_PASSWORD = "12345678"

# Default configuration
DEFAULT_CONFIG = {
    "mode": "modbus_bridge",  # modbus_bridge | tcp_server | mqtt

    # Modbus RTU settings (connection to inverter)
    "rtu": {
        "uart_id": 1,
        "tx_pin": 17,
        "rx_pin": 16,
        "de_pin": 4,        # RS485 direction pin (optional, 0 to disable)
        "unit_id": 1,
        "baudrate": 9600,
        "parity": "N",      # N/E/O
        "stop_bits": 1,
        "data_bits": 8,
        "timeout_ms": 1000,
    },

    # Modbus Bridge mode (connect TO server, forward RTU requests)
    "modbus_bridge": {
        "server_host": "182.180.150.107",
        "server_port": 8502,
        "reconnect_delay": 5,
        "keepalive_interval": 30,
    },

    # TCP Server mode (local Modbus TCP server)
    "tcp_server": {
        "port": 502,
    },

    # MQTT mode (publish telemetry)
    "mqtt": {
        "host": "",
        "port": 1883,
        "user": "",
        "password": "",
        "topic_base": "solarlogger",
        "poll_s": 10,
    },

    # Device info
    "device": {
        "name": "",
        "serial": "",
    }
}


def load_json(path, default=None):
    """Load JSON file, return default if not found."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default if default is not None else {}


def save_json(path, data):
    """Save data to JSON file."""
    with open(path, "w") as f:
        json.dump(data, f)


def load_config():
    """Load configuration from file."""
    return load_json(CONFIG_FILE, {})


def save_config(config):
    """Save configuration to file."""
    save_json(CONFIG_FILE, config)


def load_wifi():
    """Load WiFi credentials."""
    return load_json(WIFI_FILE, {})


def save_wifi(ssid, password):
    """Save WiFi credentials."""
    save_json(WIFI_FILE, {"ssid": ssid, "password": password})


def merge_config(user_config):
    """Merge user config with defaults."""
    config = {}

    # Copy defaults
    for key, value in DEFAULT_CONFIG.items():
        if isinstance(value, dict):
            config[key] = value.copy()
            if key in user_config and isinstance(user_config[key], dict):
                config[key].update(user_config[key])
        else:
            config[key] = user_config.get(key, value)

    return config


def get_config():
    """Get merged configuration."""
    return merge_config(load_config())


def get_device_id():
    """Generate device ID from MAC address."""
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        mac = wlan.config("mac")
        return "{:02X}{:02X}{:02X}{:02X}{:02X}{:02X}".format(*mac)
    except:
        return "UNKNOWN"


def get_ap_ssid():
    """Get AP SSID based on MAC."""
    try:
        import network
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        mac = ap.config("mac")
        return "{}{}{}{}".format(AP_PREFIX,
            "{:02X}".format(mac[3]),
            "{:02X}".format(mac[4]),
            "{:02X}".format(mac[5]))
    except:
        return AP_PREFIX + "XXX"
