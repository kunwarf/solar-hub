"""
Firmware self-watchdog for ESP32 datalogger.

Detects a stuck/half-open TCP session to System B and reboots the device
when no successful transmit has happened in `no_transmit_threshold_sec`.

Why this is needed (and why it goes in firmware rather than on the server):
- Server-side auto-reboot needs to reach the ESP32's local /reboot endpoint
  by LAN IP.  Devices have DHCP, no static IPs, and prod LAN L2 fragmentation
  makes some IPs unreachable — the devices most likely to need recovery are
  precisely the ones the server can't reach.
- Firmware self-watchdog only depends on what the device itself observes
  (its own send timestamps + WiFi state) and always works.

Guard rails:
- WiFi guard: only reboot if WiFi is UP.  If WiFi is down the WiFi manager
  already owns reconnect; a reboot would fight it and could boot-loop
  through AP-down periods.
- Cooldown: minimum `reboot_cooldown_sec` between watchdog-triggered
  reboots, persisted in `/last_watchdog_reset.txt` so it survives the
  reboot itself.  Without this a truly-broken device would boot-loop
  every ~10 minutes.
- Enable flag: `watchdog.enabled` in config.  Set to False to disarm
  remotely (via OTA config push or web UI) if the watchdog ever misfires.

Config knobs (all under the "watchdog" key in config.json):
- enabled:                     bool, default True
- no_transmit_threshold_sec:   int,  default 600  (10 min)
- reboot_cooldown_sec:         int,  default 1800 (30 min)
"""
import time

try:
    from log_buffer import log_print as print
except ImportError:
    pass


class Watchdog:
    """
    Firmware watchdog that reboots the ESP32 if the TCP session to System B
    goes stale.

    Usage:
        wd = Watchdog(config,
                      get_last_activity_fn=bridge.get_last_activity_ts,
                      get_wifi_connected_fn=wifi.is_connected)
        # In a background thread:
        while True:
            wd.check_once()
            time.sleep(60)
    """

    COOLDOWN_FILE = "last_watchdog_reset.txt"

    def __init__(self, config, get_last_activity_fn, get_wifi_connected_fn):
        wd_cfg = config.get("watchdog", {}) or {}
        self.enabled = bool(wd_cfg.get("enabled", True))
        self.no_transmit_threshold_sec = int(wd_cfg.get("no_transmit_threshold_sec", 600))
        self.reboot_cooldown_sec = int(wd_cfg.get("reboot_cooldown_sec", 1800))
        self._get_last_activity = get_last_activity_fn
        self._get_wifi_connected = get_wifi_connected_fn

        print("[Watchdog] enabled={} threshold={}s cooldown={}s".format(
            self.enabled, self.no_transmit_threshold_sec, self.reboot_cooldown_sec
        ))

    def check_once(self):
        """
        Execute one watchdog cycle.  Safe to call repeatedly — never raises,
        so the caller loop can't die.
        """
        if not self.enabled:
            return

        try:
            # 1. WiFi guard.  If WiFi is down, the WiFi manager owns recovery
            #    (see run_bridge_mode reconnect loop in main.py).  Rebooting
            #    while offline would only prolong the outage and could
            #    boot-loop through extended AP outages.
            try:
                wifi_up = bool(self._get_wifi_connected())
            except Exception:
                wifi_up = False
            if not wifi_up:
                return

            # 2. Activity threshold.
            try:
                last_activity = float(self._get_last_activity() or 0)
            except Exception:
                return  # Can't read timestamp — better to err on the side of not rebooting

            elapsed = time.time() - last_activity
            if elapsed < self.no_transmit_threshold_sec:
                return  # Healthy

            # 3. Reboot cooldown — persisted across reboots.  If we JUST
            #    rebooted from the watchdog and are already stale again,
            #    something upstream is broken (server down, LAN dead, etc.)
            #    and hammering the reset button won't help.  Wait it out.
            last_reboot = self._read_cooldown_ts()
            if last_reboot is not None:
                since_last_reboot = time.time() - last_reboot
                if since_last_reboot < self.reboot_cooldown_sec:
                    return

            # 4. Fire.
            print("[Watchdog] No successful transmit for {:.0f}s (threshold {}s). Rebooting.".format(
                elapsed, self.no_transmit_threshold_sec
            ))
            self._write_cooldown_ts()

            # Small delay so the log_buffer flush and any pending prints
            # reach the operator via /api/status?logs before the reset.
            time.sleep(2)

            import machine
            machine.reset()

        except Exception as e:
            # Never let the watchdog itself crash the poll loop.
            print("[Watchdog] check_once error:", e)

    # =========================================================================
    # Cooldown persistence
    # =========================================================================

    def _read_cooldown_ts(self):
        """Return unix timestamp of last watchdog-triggered reboot, or None."""
        try:
            with open(self.COOLDOWN_FILE) as f:
                return float(f.read().strip())
        except Exception:
            return None

    def _write_cooldown_ts(self):
        """Persist current unix timestamp so cooldown survives the reboot."""
        try:
            with open(self.COOLDOWN_FILE, "w") as f:
                f.write(str(time.time()))
        except Exception as e:
            # Non-fatal — the reboot will still happen, we'll just lose the
            # cooldown guard for the next boot.  Prefer to reboot than to
            # skip because we can't write a file.
            print("[Watchdog] Failed to write cooldown file:", e)
