"""
ESP32 Solar Data Logger - Main Entry Point.

This application:
1. Creates a WiFi hotspot for initial configuration
2. Connects to configured WiFi network
3. Establishes TCP connection to System B server
4. Forwards Modbus TCP requests from server to inverter via RTU
5. Returns RTU responses back to server

Usage:
    - On first boot, connect to "SolarLogger-XXXXXX" WiFi (password: 12345678)
    - Open http://192.168.4.1 to configure WiFi and server settings
    - After configuration, device will connect to WiFi and server automatically
"""
import time
import _thread

from config import get_config, get_device_id, AP_PASSWORD, get_ap_ssid
from wifi_manager import WiFiManager
from modbus_rtu import ModbusRTU
from modbus_bridge import ModbusBridge
from web_server import WebServer


# Global instances
wifi = None
rtu = None
bridge = None
web = None

# Control flags
_bridge_running = False
_serial_bridge_running = False
_web_running = False


def main():
    """Main entry point."""
    global wifi, rtu, bridge, web

    print("\n" + "=" * 50)
    print("Solar Data Logger")
    print("Device ID:", get_device_id())
    print("=" * 50 + "\n")

    # Load configuration
    config = get_config()
    mode = config.get("mode", "modbus_bridge")
    print("[Main] Mode:", mode)

    # Initialize WiFi manager
    wifi = WiFiManager()

    # Try to connect to saved WiFi
    connected = wifi.connect_sta(timeout_s=15)

    if not connected:
        # Start AP mode for configuration
        print("[Main] Starting configuration AP...")
        ap_ssid = wifi.start_ap()
        print("[Main] Connect to WiFi: {} (password: {})".format(ap_ssid, AP_PASSWORD))
        print("[Main] Then open http://192.168.4.1/")

    if mode == "serial_bridge":
        # Serial bridge mode — deferred imports save heap in Modbus mode
        from serial_port import SerialPort
        from serial_bridge import SerialBridge

        serial = SerialPort(config["serial"])
        bridge = SerialBridge(serial, config)

        web = WebServer(wifi, serial_bridge=bridge)
    else:
        # Modbus bridge mode (default)
        rtu = ModbusRTU(config["rtu"])
        bridge = ModbusBridge(rtu, config)
        web = WebServer(wifi, bridge, rtu)

    web.start()

    # Start web server in background
    _thread.start_new_thread(web_server_loop, ())

    # Main loop
    if mode == "modbus_bridge":
        run_bridge_mode(config)
    elif mode == "serial_bridge":
        run_serial_bridge_mode(config)
    else:
        print("[Main] Unknown mode:", mode)
        # Keep running web server
        while True:
            time.sleep(1)


def web_server_loop():
    """Web server background loop."""
    global _web_running
    _web_running = True

    while _web_running:
        try:
            web.handle_requests()
        except Exception as e:
            print("[Web] Error:", e)
            time.sleep(1)


def run_serial_bridge_mode(config):
    """Run in serial command bridge mode (for batteries)."""
    global _serial_bridge_running

    serial_bridge_cfg = config.get("serial_bridge", {})
    reconnect_delay = serial_bridge_cfg.get("reconnect_delay", 5)

    print("[Main] Serial bridge mode - connecting to {}:{}".format(
        serial_bridge_cfg.get("server_host", ""),
        serial_bridge_cfg.get("server_port", 8502)
    ))

    _serial_bridge_running = True

    while _serial_bridge_running:
        if not wifi.is_connected():
            print("[Main] WiFi disconnected, reconnecting...")
            if not wifi.connect_sta(timeout_s=15):
                print("[Main] WiFi reconnection failed, retrying in {}s".format(
                    reconnect_delay))
                time.sleep(reconnect_delay)
                continue

        try:
            bridge.run()
        except Exception as e:
            print("[Main] Serial bridge error:", e)
            time.sleep(reconnect_delay)


def run_bridge_mode(config):
    """Run in Modbus bridge mode."""
    global _bridge_running

    bridge_cfg = config.get("modbus_bridge", {})
    reconnect_delay = bridge_cfg.get("reconnect_delay", 5)

    print("[Main] Bridge mode - connecting to {}:{}".format(
        bridge_cfg.get("server_host", ""),
        bridge_cfg.get("server_port", 8502)
    ))

    _bridge_running = True

    while _bridge_running:
        # Check WiFi connection
        if not wifi.is_connected():
            print("[Main] WiFi disconnected, reconnecting...")
            if not wifi.connect_sta(timeout_s=15):
                print("[Main] WiFi reconnection failed, retrying in {}s".format(reconnect_delay))
                time.sleep(reconnect_delay)
                continue

        # Run bridge (this blocks until disconnected)
        try:
            bridge.run()
        except Exception as e:
            print("[Main] Bridge error:", e)
            time.sleep(reconnect_delay)


def stop():
    """Stop all services."""
    global _bridge_running, _serial_bridge_running, _web_running

    _bridge_running = False
    _serial_bridge_running = False
    _web_running = False

    if bridge:
        bridge.disconnect()
    if web:
        web.stop()


# Auto-run on boot
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Main] Interrupted")
        stop()
    except Exception as e:
        print("[Main] Fatal error:", e)
        import sys
        sys.print_exception(e)

