"""ESP8266 Solar Data Logger."""
import gc
import time

# Global instances (set inside main)
wifi = None
rtu = None
bridge = None
web = None


def main():
    global wifi, rtu, bridge, web

    print("\n" + "=" * 40)
    print("Solar Data Logger (ESP8266)")
    print("=" * 40 + "\n")

    # Step 1: Read mode cheaply — raw JSON only, no full config dict yet.
    # Keeping imports minimal here means the heap has had only ONE compilation
    # cycle (main.py itself) before the large mode-specific modules compile.
    try:
        import ujson
        with open("config.json") as _f:
            mode = ujson.load(_f).get("mode", "modbus_bridge")
        del ujson, _f
    except Exception:
        mode = "modbus_bridge"
    gc.collect()

    print("[Main] Mode:", mode)

    # Step 2: Import mode-specific modules on the cleanest possible heap.
    # Order: largest file first (most free heap at that moment).
    # config.py and wifi_manager.py are deliberately NOT imported yet —
    # their compilation cycles would fragment the heap before this point.
    gc.collect()
    print("Free:", gc.mem_free(), "Alloc:", gc.mem_alloc())
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

    # Step 3: Now import config and wifi — heap is fragmented by this point
    # but only small modules remain, so contiguous requirements are modest.
    from config import get_config, get_device_id, AP_PASSWORD
    gc.collect()
    from wifi_manager import WiFiManager
    gc.collect()

    config = get_config()
    gc.collect()

    # Step 4: Initialise WiFi
    # NOTE: get_device_id() must NOT be called before WiFiManager() — it calls
    # network.WLAN().active(True) which can leave the driver in a broken state.
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

    if mode == "modbus_bridge":
        run_bridge_mode(config)
    elif mode == "serial_bridge":
        run_serial_bridge_mode(config)
    else:
        print("[Main] Unknown mode:", mode)
        _run_web_only()


def _run_web_only():
    print("[Main] Running web-only mode")
    while True:
        try:
            web.handle_requests()
        except Exception as e:
            print("[Web] Error:", e)
        time.sleep_ms(50)


def run_serial_bridge_mode(config):
    serial_bridge_cfg = config.get("serial_bridge", {})
    reconnect_delay = serial_bridge_cfg.get("reconnect_delay", 5)
    print("[Main] Serial bridge mode - connecting to {}:{}".format(
        serial_bridge_cfg.get("server_host", ""),
        serial_bridge_cfg.get("server_port", 8502)))
    while True:
        if not wifi.is_connected():
            print("[Main] WiFi disconnected, reconnecting...")
            if not wifi.connect_sta(timeout_s=15):
                print("[Main] WiFi reconnection failed, retrying in {}s".format(reconnect_delay))
                _sleep_with_web(reconnect_delay)
                continue
        try:
            bridge.run(idle_cb=web.handle_requests)
        except Exception as e:
            print("[Main] Serial bridge error:", e)
            _sleep_with_web(reconnect_delay)


def run_bridge_mode(config):
    bridge_cfg = config.get("modbus_bridge", {})
    reconnect_delay = bridge_cfg.get("reconnect_delay", 5)
    print("[Main] Bridge mode - connecting to {}:{}".format(
        bridge_cfg.get("server_host", ""),
        bridge_cfg.get("server_port", 8502)))
    while True:
        if not wifi.is_connected():
            print("[Main] WiFi disconnected, reconnecting...")
            if not wifi.connect_sta(timeout_s=15):
                print("[Main] WiFi reconnection failed, retrying in {}s".format(reconnect_delay))
                _sleep_with_web(reconnect_delay)
                continue
        try:
            bridge.run(idle_cb=web.handle_requests)
        except Exception as e:
            print("[Main] Bridge error:", e)
            _sleep_with_web(reconnect_delay)


def _sleep_with_web(seconds):
    deadline = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        try:
            web.handle_requests()
        except Exception:
            pass
        time.sleep_ms(100)


def stop():
    if bridge:
        bridge.disconnect()
    if web:
        web.stop()


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
