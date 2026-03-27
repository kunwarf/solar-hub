"""
Configuration management for ESP8266 Data Logger.

ESP8266 UART note: UART0 only (GPIO1=TX, GPIO3=RX, fixed).
tx_pin/rx_pin in config are informational only.
"""
import json

CONFIG_FILE = "config.json"
WIFI_FILE = "wifi.json"
AP_PREFIX = "SolarLogger-"
AP_PASSWORD = "12345678"

# mqtt and tcp_server sections removed — never instantiated on ESP8266,
# they only waste ~550 bytes that get copied on every get_config() call.
DEFAULT_CONFIG = {
    "mode": "modbus_bridge",  # modbus_bridge | serial_bridge

    "rtu": {
        "uart_id": 0,
        "de_pin": 4,
        "re_pin": 5,
        "unit_id": 1,
        "baudrate": 9600,
        "parity": "N",
        "stop_bits": 1,
        "data_bits": 8,
        "timeout_ms": 1000,
    },

    "modbus_bridge": {
        "server_host": "182.180.150.107",
        "server_port": 8502,
        "reconnect_delay": 5,
        "keepalive_interval": 1,
    },

    "api": {
        "base_url": "http://182.180.150.107:8001",
        "register_endpoint": "/api/v1/devices/self-register",
    },

    "serial": {
        "uart_id": 0,
        "de_pin": -1,
        "re_pin": 5,
        "baudrate": 115200,
        "parity": "N",
        "stop_bits": 1,
        "data_bits": 8,
        "response_timeout_ms": 5000,
        "prompt": "pylon>",
        "line_ending": "\r\n",
        "passive": False,
        "frame_header": [0x55, 0xAA, 0xEB, 0x90],
        "max_frame_len": 512,
    },

    "serial_bridge": {
        "server_host": "",
        "server_port": 8502,
        "reconnect_delay": 5,
        "keepalive_interval": 1,
    },

    "device": {
        "serial": "",
        "name": "",
        "type": "inverter",
        "manufacturer": "SolarHub",
        "firmware_version": "1.0.0",
        "protocol": "modbus_tcp",
        "model": "",
    }
}


def load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default if default is not None else {}


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def load_config():
    return load_json(CONFIG_FILE, {})


def save_config(config):
    save_json(CONFIG_FILE, config)


def load_wifi():
    return load_json(WIFI_FILE, {})


def save_wifi(ssid, password):
    save_json(WIFI_FILE, {"ssid": ssid, "password": password})


def merge_config(user_config):
    config = {}
    for key, value in DEFAULT_CONFIG.items():
        if isinstance(value, dict):
            config[key] = value.copy()
            if key in user_config and isinstance(user_config[key], dict):
                config[key].update(user_config[key])
        else:
            config[key] = user_config.get(key, value)
    return config


def get_config():
    return merge_config(load_config())


def get_device_id():
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        mac = wlan.config("mac")
        return "{:02X}{:02X}{:02X}{:02X}{:02X}{:02X}".format(*mac)
    except:
        return "UNKNOWN"


def get_ap_ssid():
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
