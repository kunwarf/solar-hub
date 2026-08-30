"""
WiFi management for ESP8266 Data Logger.

Handles WiFi connection (STA mode) and Access Point (AP mode) for configuration.
The network module API is identical between ESP8266 and ESP32 MicroPython.
"""
import network
import time

from config import load_wifi, AP_PASSWORD, get_ap_ssid


class WiFiManager:
    """Manages WiFi connections and AP mode."""

    def __init__(self):
        self.sta = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)
        self._ap_active = False

    def connect_sta(self, timeout_s=15):
        """
        Try to connect to WiFi using saved credentials.

        Args:
            timeout_s: Connection timeout in seconds.

        Returns:
            True if connected, False otherwise.
        """
        wifi_cfg = load_wifi()
        ssid = (wifi_cfg.get("ssid") or "").strip()
        password = wifi_cfg.get("password") or ""

        if not ssid:
            print("[WiFi] No SSID configured")
            return False

        # Reset WiFi interface to clean state
        try:
            self.sta.disconnect()
        except:
            pass

        # Deactivate and reactivate to reset internal state
        self.sta.active(False)
        time.sleep(0.5)
        self.sta.active(True)
        time.sleep(0.5)

        # Disable WiFi power-save.  See esp32_datalogger/wifi_manager.py for
        # rationale — modem-sleep adds ~100-500ms latency to inbound frames.
        # ESP8266 exposes the same API but PM_NONE may not exist in older
        # builds; try the constant, else fall back to no-op.
        try:
            self.sta.config(pm=network.WLAN.PM_NONE)
            print("[WiFi] Power-save disabled (PM_NONE)")
        except (AttributeError, OSError, ValueError) as pm_err:
            print("[WiFi] Could not disable power-save:", pm_err)

        # Max TX power (ESP8266 max ~20.5 dBm).  Small free gain.
        try:
            self.sta.config(txpower=20)
        except (AttributeError, OSError, ValueError):
            pass

        if self.sta.isconnected():
            print("[WiFi] Already connected to", self.sta.config("essid"))
            try:
                print("[WiFi] RSSI={} dBm".format(self.sta.status("rssi")))
            except (AttributeError, OSError, ValueError):
                pass
            return True

        print("[WiFi] Connecting to:", ssid)

        try:
            self.sta.connect(ssid, password)
        except OSError as e:
            print("[WiFi] Connection error:", e)
            # Retry after full reset
            self.sta.active(False)
            time.sleep(1)
            self.sta.active(True)
            time.sleep(0.5)
            try:
                self.sta.connect(ssid, password)
            except OSError as e2:
                print("[WiFi] Retry failed:", e2)
                return False

        start = time.time()
        while time.time() - start < timeout_s:
            if self.sta.isconnected():
                ip = self.sta.ifconfig()[0]
                print("[WiFi] Connected! IP:", ip)
                return True
            time.sleep(0.5)

        print("[WiFi] Connection failed")
        return False

    def start_ap(self):
        """Start Access Point for configuration."""
        ssid = get_ap_ssid()

        self.ap.active(True)
        self.ap.config(
            essid=ssid,
            password=AP_PASSWORD,
            authmode=network.AUTH_WPA2_PSK
        )

        self._ap_active = True
        print("[WiFi] AP Started:")
        print("  SSID:", ssid)
        print("  Password:", AP_PASSWORD)
        print("  IP: 192.168.4.1")
        print("  Config URL: http://192.168.4.1/")

        return ssid

    def stop_ap(self):
        """Stop Access Point."""
        self.ap.active(False)
        self._ap_active = False
        print("[WiFi] AP Stopped")

    def is_connected(self):
        """Check if connected to WiFi."""
        return self.sta.isconnected()

    def is_ap_active(self):
        """Check if AP is active."""
        return self._ap_active or self.ap.active()

    def get_ip(self):
        """Get current IP address."""
        if self.sta.isconnected():
            return self.sta.ifconfig()[0]
        return None

    def get_status(self):
        """Get WiFi status information."""
        return {
            "sta_connected": self.sta.isconnected(),
            "sta_ip": self.sta.ifconfig()[0] if self.sta.isconnected() else None,
            "sta_ssid": self.sta.config("essid") if self.sta.isconnected() else None,
            "ap_active": self.ap.active(),
            "ap_ssid": get_ap_ssid() if self.ap.active() else None,
            "ap_ip": "192.168.4.1" if self.ap.active() else None,
        }

    def disconnect(self):
        """Disconnect from WiFi."""
        self.sta.disconnect()
        print("[WiFi] Disconnected")
