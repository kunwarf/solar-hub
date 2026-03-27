"""
ESP8266 Solar Data Logger - Main Entry Point.

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

ESP8266 vs ESP32 differences
------------------------------
1. No _thread module — the ESP8266 is single-core and MicroPython does not
   expose a threading API.  The web server runs cooperatively: bridge.run()
   and serial_bridge.run() accept an idle_cb argument that is called every
   time the bridge socket recv times out (keepalive_interval, default 1 s).
   This gives the web server a chance to handle one request per second.

2. UART pins are fixed — UART0: TX=GPIO1, RX=GPIO3.  The tx_pin/rx_pin
   fields in config are stored for reference but ignored by machine.UART().

3. Less RAM (~80 KB) — static buffers in serial_port.py are reduced to
   2 KB (vs 12 KB on ESP32).  Avoid large allocations in the main path.

4. machine.reset() works identically; used for fatal error recovery.
"""
import gc
import time

from config import get_config, get_device_id, AP_PASSWORD, get_ap_ssid
from wifi_manager import WiFiManager


# Global instances
wifi = None
rtu = None
bridge = None
web = None


def main():
    """Main entry point."""
    global wifi, rtu, bridge, web

    print("\n" + "=" * 50)
    print("Solar Data Logger (ESP8266)")
    print("=" * 50 + "\n")

    # Read mode from raw JSON first — avoids building the full merged config dict
    # (~2KB) during the critical import window when heap space is tightest.
    try:
        import ujson
        with open("config.json") as _f:
            mode = ujson.load(_f).get("mode", "modbus_bridge")
        del ujson, _f
    except Exception:
        mode = "modbus_bridge"
    gc.collect()

    print("[Main] Mode:", mode)

    # Import modules BEFORE WiFi connects and before get_config().
    # get_config() builds a ~2KB merged dict — deferring it to after all
    # imports keeps that memory free during the critical compilation window.
    # Import order: largest file first (most free heap available).
    # NOTE: get_device_id() must NOT be called before WiFiManager() — it calls
    # network.WLAN().active(True) which can leave the driver in a broken state.
    gc.collect()
    if mode == "serial_bridge":
        from serial_bridge import SerialBridge
        gc.collect()
        from serial_port import SerialPort
        gc.collect()
        from web_server import WebServer
        gc.collect()
    else:
        from modbus_bridge import ModbusBridge
        gc.collect()
        from modbus_rtu import ModbusRTU
        gc.collect()
        from web_server import WebServer
        gc.collect()

    # Now load full config — heap is in good shape after all imports
    config = get_config()
    gc.collect()

    # Now initialise WiFi
    wifi = WiFiManager()
    print("Device ID:", get_device_id())

    connected = wifi.connect_sta(timeout_s=15)

    if not connected:
        print("[Main] Starting configuration AP...")
        ap_ssid = wifi.start_ap()
        print("[Main] Connect to WiFi: {} (password: {})".format(ap_ssid, AP_PASSWORD))
        print("[Main] Then open http://192.168.4.1/")

    gc.collect()
    if mode == "serial_bridge":
        serial = SerialPort(config["serial"])
        bridge = SerialBridge(serial, config)
        web = WebServer(wifi, serial_bridge=bridge)
    else:
        rtu = ModbusRTU(config["rtu"])
        bridge = ModbusBridge(rtu, config)
        web = WebServer(wifi, bridge, rtu)

    web.start()

    # Run the selected mode.
    # On ESP8266 there is no background thread for the web server.
    # Instead, bridge.run() / serial_bridge.run() call web.handle_requests()
    # via the idle_cb on every socket recv timeout (~1 s).
    if mode == "modbus_bridge":
        run_bridge_mode(config)
    elif mode == "serial_bridge":
        run_serial_bridge_mode(config)
    else:
        print("[Main] Unknown mode:", mode)
        # Fallback: just serve the web interface
        _run_web_only()


def _run_web_only():
    """Serve the web interface when mode is unknown (idle loop)."""
    print("[Main] Running web-only mode")
    while True:
        try:
            web.handle_requests()
        except Exception as e:
            print("[Web] Error:", e)
        time.sleep_ms(50)


def run_serial_bridge_mode(config):
    """
    Run in serial command bridge mode (for batteries).

    The web server is serviced via idle_cb inside bridge.run().
    """
    serial_bridge_cfg = config.get("serial_bridge", {})
    reconnect_delay = serial_bridge_cfg.get("reconnect_delay", 5)

    print("[Main] Serial bridge mode - connecting to {}:{}".format(
        serial_bridge_cfg.get("server_host", ""),
        serial_bridge_cfg.get("server_port", 8502)
    ))

    while True:
        if not wifi.is_connected():
            print("[Main] WiFi disconnected, reconnecting...")
            if not wifi.connect_sta(timeout_s=15):
                print("[Main] WiFi reconnection failed, retrying in {}s".format(
                    reconnect_delay))
                # Service web while waiting for WiFi
                _sleep_with_web(reconnect_delay)
                continue

        try:
            # idle_cb is called every keepalive_interval seconds so the
            # web server stays responsive without a background thread.
            bridge.run(idle_cb=web.handle_requests)
        except Exception as e:
            print("[Main] Serial bridge error:", e)
            _sleep_with_web(reconnect_delay)


def run_bridge_mode(config):
    """
    Run in Modbus bridge mode.

    The web server is serviced via idle_cb inside bridge.run().
    """
    bridge_cfg = config.get("modbus_bridge", {})
    reconnect_delay = bridge_cfg.get("reconnect_delay", 5)

    print("[Main] Bridge mode - connecting to {}:{}".format(
        bridge_cfg.get("server_host", ""),
        bridge_cfg.get("server_port", 8502)
    ))

    while True:
        # Check WiFi connection
        if not wifi.is_connected():
            print("[Main] WiFi disconnected, reconnecting...")
            if not wifi.connect_sta(timeout_s=15):
                print("[Main] WiFi reconnection failed, retrying in {}s".format(
                    reconnect_delay))
                _sleep_with_web(reconnect_delay)
                continue

        # Run bridge (blocks until disconnected, calls web.handle_requests
        # on each keepalive_interval timeout — default 1 s)
        try:
            bridge.run(idle_cb=web.handle_requests)
        except Exception as e:
            print("[Main] Bridge error:", e)
            _sleep_with_web(reconnect_delay)


def _sleep_with_web(seconds):
    """
    Sleep for the given number of seconds while still servicing the web server.

    On ESP8266 there is no background thread, so we poll the web server
    in a tight loop during reconnect/retry delays.
    """
    deadline = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        try:
            web.handle_requests()
        except Exception:
            pass
        time.sleep_ms(100)


def stop():
    """Stop all services."""
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
        import machine
        print("[Main] Resetting in 3s...")
        time.sleep(3)
        machine.reset()
