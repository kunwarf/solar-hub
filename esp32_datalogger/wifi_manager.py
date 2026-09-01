"""
WiFi management for ESP32 Data Logger.

Handles WiFi connection (STA mode) and Access Point (AP mode) for configuration.
"""
import network
import time

# Route print through the ring-buffer logger so [WiFi] lines are visible
# via the device's web UI, not just the serial console.  Other modules
# (modbus_bridge, serial_bridge, etc.) already use this pattern.
try:
    from log_buffer import log_print as print
except ImportError:
    pass  # fall back to stdout in test/host environments

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

        # Disable WiFi power-save.  ESP32 defaults to modem-sleep, which
        # holds RX buffered at the AP between DTIM intervals and adds
        # ~100-500ms latency to any inbound packet.  For a device that
        # polls every 5s and must respond to Modbus TCP within a few
        # hundred ms, PM_NONE is the right tradeoff.
        # Try 3 API variants because MicroPython builds differ:
        #   1. pm=WLAN.PM_NONE  (modern, 1.20+)
        #   2. pm=0             (raw int, some 1.19 builds)
        #   3. 'pm', 0          (older tuple-style config, rare)
        pm_ok = False
        for attempt in ("attr", "int", "tuple"):
            try:
                if attempt == "attr":
                    self.sta.config(pm=network.WLAN.PM_NONE)
                elif attempt == "int":
                    self.sta.config(pm=0)
                elif attempt == "tuple":
                    self.sta.config('pm', 0)
                pm_ok = True
                print("[WiFi] Power-save disabled (PM_NONE via {})".format(attempt))
                break
            except (AttributeError, OSError, ValueError, TypeError) as pm_err:
                continue
        if not pm_ok:
            print("[WiFi] Could not disable power-save on this MicroPython build")

        # Max out TX power.  ESP32 default is 19.5 dBm; supported max on
        # most boards is 20.5 dBm.  Free gain — a couple dB can be the
        # difference between marginal signal and reliable link when the
        # device is far from the AP.
        try:
            self.sta.config(txpower=20)
        except (AttributeError, OSError, ValueError):
            pass  # Not exposed on older builds — harmless.

        if self.sta.isconnected():
            print("[WiFi] Already connected to", self.sta.config("essid"))
            self._log_link_quality()
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
                # Optional static IP: if wifi.json specifies static_ip,
                # netmask, gateway, dns, apply them.  Skipping DHCP removes
                # ~500ms from every reconnect AND eliminates the periodic
                # DHCP-renew traffic that can bounce off a congested AP.
                # To enable, add to wifi.json:
                #   {"ssid":"…","password":"…",
                #    "static_ip":"192.168.88.246",
                #    "netmask":"255.255.255.0",
                #    "gateway":"192.168.88.1",
                #    "dns":"192.168.88.1"}
                static_ip = wifi_cfg.get("static_ip")
                if static_ip:
                    try:
                        self.sta.ifconfig((
                            static_ip,
                            wifi_cfg.get("netmask", "255.255.255.0"),
                            wifi_cfg.get("gateway", "192.168.88.1"),
                            wifi_cfg.get("dns", "192.168.88.1"),
                        ))
                        print("[WiFi] Static IP applied:", static_ip)
                    except Exception as ip_err:
                        print("[WiFi] Static IP config failed:", ip_err)

                ip = self.sta.ifconfig()[0]
                print("[WiFi] Connected! IP:", ip)
                self._log_link_quality()
                return True
            time.sleep(0.5)

        print("[WiFi] Connection failed")
        return False

    def _log_link_quality(self):
        """
        Print RSSI, BSSID, channel after association so weak-signal cases
        show up in logs.  RSSI thresholds:
          -50 to -60 dBm  excellent — full link speed
          -60 to -70 dBm  good      — normal operation
          -70 to -75 dBm  fair      — some retries, occasional loss
          -75 to -85 dBm  poor      — frequent retries, high loss
          below -85 dBm  unusable  — connection will drop
        """
        try:
            rssi = self.sta.status("rssi")
        except (AttributeError, OSError, ValueError):
            rssi = "?"
        try:
            bssid = ":".join("{:02x}".format(b) for b in self.sta.config("bssid"))
        except (AttributeError, OSError, ValueError):
            bssid = "?"
        try:
            channel = self.sta.config("channel")
        except (AttributeError, OSError, ValueError):
            channel = "?"
        print("[WiFi] RSSI={} dBm  BSSID={}  channel={}".format(rssi, bssid, channel))

    def start_ap(self):
        """Start Access Point for configuration."""
        ssid = get_ap_ssid()

        self.ap.active(True)
        self.ap.config(
            essid=ssid,
            password=AP_PASSWORD,
            authmode=network.AUTH_WPA_WPA2_PSK
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
        """Get WiFi status information — includes PM state and RSSI so
        we can verify PM_NONE actually engaged after boot."""
        pm_state = None
        rssi = None
        bssid = None
        channel = None
        if self.sta.isconnected():
            # Read current power-save mode; if the build doesn't support
            # querying, report None so we know it's opaque.
            for key in ("pm", "channel", "bssid"):
                try:
                    val = self.sta.config(key)
                    if key == "pm":
                        pm_state = val
                    elif key == "channel":
                        channel = val
                    elif key == "bssid":
                        bssid = ":".join("{:02x}".format(b) for b in val)
                except (AttributeError, OSError, ValueError, TypeError):
                    pass
            try:
                rssi = self.sta.status("rssi")
            except (AttributeError, OSError, ValueError):
                pass
        # sys.implementation identifies the MicroPython build for diagnostic
        try:
            import sys
            mpy_version = "{}.{}.{}".format(*sys.implementation.version)
        except Exception:
            mpy_version = "?"
        return {
            "sta_connected": self.sta.isconnected(),
            "sta_ip": self.sta.ifconfig()[0] if self.sta.isconnected() else None,
            "sta_ssid": self.sta.config("essid") if self.sta.isconnected() else None,
            "sta_rssi_dbm": rssi,
            "sta_bssid": bssid,
            "sta_channel": channel,
            "sta_pm_state": pm_state,  # 0=none, 1=min, 2=max modem sleep
            "ap_active": self.ap.active(),
            "ap_ssid": get_ap_ssid() if self.ap.active() else None,
            "ap_ip": "192.168.4.1" if self.ap.active() else None,
            "mpy_version": mpy_version,
        }

    def disconnect(self):
        """Disconnect from WiFi."""
        self.sta.disconnect()
        print("[WiFi] Disconnected")
