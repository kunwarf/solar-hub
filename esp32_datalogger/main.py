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
import gc
import time
import _thread

from config import get_config, get_device_id, AP_PASSWORD, get_ap_ssid
from wifi_manager import WiFiManager


# Global instances
wifi = None
rtu = None
bridge = None
web = None
ota = None
cmd_client = None
watchdog = None

# Control flags
_bridge_running = False
_serial_bridge_running = False
_web_running = False
_ota_running = False
_cmd_poll_running = False
_watchdog_running = False


def main():
    """Main entry point."""
    global wifi, rtu, bridge, web

    print("\n" + "=" * 50)
    print("Solar Data Logger")
    print("=" * 50 + "\n")

    # Load configuration
    config = get_config()
    mode = config.get("mode", "modbus_bridge")
    print("[Main] Mode:", mode)

    # Free heap before WiFi init — heavy imports above can fragment memory
    gc.collect()

    # Initialize WiFi manager
    # NOTE: get_device_id() must NOT be called before this — it calls
    # network.WLAN().active(True) which does a partial WiFi init that
    # exhausts RX buffers and leaves the driver broken for the real init.
    wifi = WiFiManager()
    print("Device ID:", get_device_id())

    # Try to connect to saved WiFi
    connected = wifi.connect_sta(timeout_s=15)

    if not connected:
        # Start AP mode for configuration
        print("[Main] Starting configuration AP...")
        ap_ssid = wifi.start_ap()
        print("[Main] Connect to WiFi: {} (password: {})".format(ap_ssid, AP_PASSWORD))
        print("[Main] Then open http://192.168.4.1/")

    # Deferred imports — load after WiFi is up to avoid heap fragmentation
    gc.collect()
    if mode == "serial_bridge":
        from serial_port import SerialPort
        from serial_bridge import SerialBridge
        from web_server import WebServer

        serial = SerialPort(config["serial"])
        bridge = SerialBridge(serial, config)
        web = WebServer(wifi, serial_bridge=bridge)
    else:
        from modbus_rtu import ModbusRTU
        from modbus_bridge import ModbusBridge
        from web_server import WebServer

        rtu = ModbusRTU(config["rtu"])
        bridge = ModbusBridge(rtu, config)
        web = WebServer(wifi, bridge, rtu)

    web.start()

    # Start web server in background
    _thread.start_new_thread(web_server_loop, ())

    # Deferred OTA client init — after WiFi is up.  Own module so the
    # import failing (e.g. after a broken update) doesn't block the bridge.
    global ota
    try:
        from ota_client import OTAClient
        ota = OTAClient(config)
        _thread.start_new_thread(ota_loop, ())
        print("[Main] OTA check loop started")
    except Exception as e:
        print("[Main] OTA init failed (bridge will run without OTA):", e)

    # Datalogger command poll loop — receives reboot_datalogger etc. from
    # System B.  Isolated in its own thread + try/except so a broken update
    # can't jam the bridge or the OTA path that recovers it.
    global cmd_client
    try:
        from command_client import CommandClient
        cmd_client = CommandClient(config, get_device_id_fn=bridge.get_device_id)
        _thread.start_new_thread(command_poll_loop, ())
        print("[Main] Datalogger command poll loop started")
    except Exception as e:
        print("[Main] Command client init failed (bridge will run without remote commands):", e)

    # Firmware watchdog — reboots the ESP32 if no successful transmit to
    # System B in `watchdog.no_transmit_threshold_sec` seconds (default 10 min).
    # Cooldown-guarded so a truly-broken environment doesn't boot-loop.
    # Isolated so a broken watchdog can't take down the bridge.
    global watchdog
    try:
        from watchdog import Watchdog
        watchdog = Watchdog(
            config,
            get_last_activity_fn=bridge.get_last_activity_ts,
            get_wifi_connected_fn=wifi.is_connected,
        )
        _thread.start_new_thread(watchdog_loop, ())
        print("[Main] Firmware watchdog started")
    except Exception as e:
        print("[Main] Watchdog init failed (bridge will run without watchdog):", e)

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


def command_poll_loop():
    """
    Background datalogger-command polling loop.

    Wakes every 30 s and queries System B for pending datalogger-scope
    commands.  Kept in its own function so a stall in the poll HTTP call
    can't jam the bridge or the OTA path.

    First check is delayed 15 s so we don't race the bridge's own
    register_device() call — get_device_id() returns None until then.
    """
    global _cmd_poll_running
    _cmd_poll_running = True
    time.sleep(15)
    while _cmd_poll_running:
        try:
            if cmd_client:
                cmd_client.poll_once()
        except Exception as e:
            print("[Cmd] Loop error:", e)
        time.sleep(30)


def watchdog_loop():
    """
    Background firmware watchdog loop.

    Wakes every 60 s and checks whether the bridge has successfully
    transmitted to System B recently.  If not, and WiFi is up, and the
    cooldown has elapsed, triggers machine.reset().  Isolated in its own
    thread so a bug here can't take down the bridge or block recovery.

    Delayed start: 30 s after boot so slow-registering devices don't get
    tripped by a "no activity since boot" false positive on the first
    check.  The threshold is 10 min anyway, so this delay mostly protects
    the log output from noise.
    """
    global _watchdog_running
    _watchdog_running = True
    time.sleep(30)
    while _watchdog_running:
        try:
            if watchdog:
                watchdog.check_once()
        except Exception as e:
            print("[Watchdog] Loop error:", e)
        time.sleep(60)


def ota_loop():
    """
    Background OTA polling loop.

    Wakes every 60 s and calls `ota.run_background_check()`.  The OTAClient
    guards its own poll interval via `should_check()` (default 300 s), so
    this frequent wake-up just yields quickly when there's nothing due.
    When an update IS available and applied, `apply_update()` calls
    machine.reset() and this thread never returns.

    Kept in its own function (not folded into web_server_loop) so a stall
    in the OTA HTTP call can't jam the local /api/files/upload endpoint
    that operators use to bootstrap a bricked device.
    """
    global _ota_running
    _ota_running = True
    # Small delay so the first check doesn't race with the bridge's own
    # register_device() call on freshly booted devices.
    time.sleep(10)
    while _ota_running:
        try:
            if ota and ota.run_background_check():
                # Update was applied; device is rebooting.
                break
        except Exception as e:
            print("[OTA] Loop error:", e)
        time.sleep(60)


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
    global _bridge_running, _serial_bridge_running, _web_running, _ota_running, _cmd_poll_running, _watchdog_running

    _bridge_running = False
    _serial_bridge_running = False
    _web_running = False
    _ota_running = False
    _cmd_poll_running = False
    _watchdog_running = False

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
        # Hard reset recovers from WiFi OOM after unclean shutdown (ESP32S3)
        import machine
        print("[Main] Resetting in 3s...")
        time.sleep(3)
        machine.reset()
