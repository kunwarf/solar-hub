"""
OTA Update Client for ESP8266.

Periodically checks System B for firmware updates and applies them.
machine.reset() works identically on ESP8266 and ESP32.
"""
import time
from http_utils import http_get_json, http_post_json


class OTAClient:
    """OTA Update Client."""

    def __init__(self, config):
        """
        Initialize OTA client.

        Args:
            config: Configuration dict with api settings
        """
        self.config = config
        self.api_config = config.get("api", {})
        self.device_config = config.get("device", {})
        self.base_url = self.api_config.get("base_url", "http://localhost:8001")
        self.check_interval = config.get("ota", {}).get("check_interval", 300)
        self.last_check = 0
        self.updating = False

    def should_check(self):
        """Check if it's time to check for updates."""
        return (time.time() - self.last_check) >= self.check_interval

    def check_for_update(self):
        """
        Check if an update is available.

        Returns:
            Dict with update info if available, None otherwise
        """
        if self.updating:
            print("[OTA] Update already in progress")
            return None

        device_serial = self.device_config.get("serial", "")
        if not device_serial:
            print("[OTA] No device serial configured")
            return None

        current_version = self.device_config.get("firmware_version", "1.0.0")

        device_info = {
            "free_memory": self._get_free_memory(),
            "uptime": time.time()
        }

        url = self.base_url + "/api/v1/firmware/check-update"
        payload = {
            "device_serial": device_serial,
            "current_version": current_version,
            "device_info": device_info
        }

        print("[OTA] Checking for updates...")
        status_code, response = http_post_json(url, payload, timeout=15)

        self.last_check = time.time()

        if status_code == 200 and response:
            if response.get("update_available"):
                print("[OTA] Update available: {}".format(response.get("target_version")))
                return response
            else:
                print("[OTA] No updates available")
        else:
            print("[OTA] Check failed: status={}".format(status_code))

        return None

    def apply_update(self, update_info):
        """
        Download and apply firmware update.

        Args:
            update_info: Update info dict from check_for_update()

        Returns:
            True if successful, False otherwise
        """
        if self.updating:
            print("[OTA] Update already in progress")
            return False

        self.updating = True

        try:
            import hashlib
            import machine
            from file_manager import FileManager

            device_serial = self.device_config.get("serial", "")
            version_id = update_info.get("version_id")
            target_version = update_info.get("target_version")

            print("[OTA] Starting update to version {}".format(target_version))

            self._report_status("downloading", 0)

            files_url = self.base_url + update_info.get("files_url", "")
            status_code, files = http_get_json(files_url, timeout=30)

            if status_code != 200 or not files:
                print("[OTA] Failed to get file list")
                self._report_status("failed", 0, "Failed to get file list")
                return False

            print("[OTA] Found {} files to update".format(len(files)))

            total_files = len(files)
            for i, file_info in enumerate(files):
                filename = file_info.get("filename")
                content = file_info.get("content")
                checksum = file_info.get("checksum")
                is_required = file_info.get("is_required", True)

                print("[OTA] Downloading {}/{}:{}".format(i + 1, total_files, filename))

                actual_checksum = hashlib.sha256(content.encode()).hexdigest()
                if actual_checksum != checksum:
                    print("[OTA] Checksum mismatch for {}".format(filename))
                    if is_required:
                        self._report_status(
                            "failed", 0, "Checksum mismatch: {}".format(filename))
                        return False
                    else:
                        continue

                if not FileManager.save_file(filename, content):
                    print("[OTA] Failed to save {}".format(filename))
                    if is_required:
                        self._report_status(
                            "failed", 0, "Failed to save: {}".format(filename))
                        return False

                progress = int(((i + 1) / total_files) * 90)
                self._report_status("downloading", progress)

            print("[OTA] All files downloaded successfully")

            self._report_status("applying", 95)
            self.config["device"]["firmware_version"] = target_version

            try:
                from config import save_config
                save_config(self.config)
            except Exception as e:
                print("[OTA] Failed to save config:", e)

            self._report_status("success", 100)

            print("[OTA] Update complete! Rebooting in 5 seconds...")
            time.sleep(5)

            machine.reset()

            return True

        except Exception as e:
            print("[OTA] Update failed:", e)
            self._report_status("failed", 0, str(e))
            return False

        finally:
            self.updating = False

    def _report_status(self, status, progress, error_message=None):
        """Report update status to server."""
        device_serial = self.device_config.get("serial", "")
        if not device_serial:
            return

        url = self.base_url + "/api/v1/firmware/update-status"
        payload = {
            "device_serial": device_serial,
            "update_status": status,
            "progress": progress
        }

        if error_message:
            payload["error_message"] = error_message

        status_code, response = http_post_json(url, payload, timeout=10)
        if status_code != 200:
            print("[OTA] Failed to report status")

    def _get_free_memory(self):
        """Get free memory in bytes."""
        try:
            import gc
            gc.collect()
            return gc.mem_free()
        except:
            return 0

    def run_background_check(self):
        """
        Run periodic update checks (call from main loop).

        Returns:
            True if update was applied (device will reboot), False otherwise
        """
        if not self.should_check():
            return False

        update_info = self.check_for_update()
        if update_info:
            return self.apply_update(update_info)

        return False
