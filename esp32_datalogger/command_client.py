"""
Datalogger command polling client for MicroPython.

Polls System B for datalogger-scope commands (e.g. reboot_datalogger) that
must be handled by the ESP32 itself rather than forwarded to the inverter.
See system_b/device_server/commands/command_definitions.py::DATALOGGER_COMMANDS.

Why polling instead of piggybacking on the existing TCP session:
- ESP32 datalogger is a transparent Modbus TCP bridge — inverter commands
  arrive as normal Modbus write requests and get forwarded.  There is no
  established channel for datalogger-scoped instructions.
- ESP32 has no static LAN IP, so the server can't reliably initiate an
  HTTP call to the device's /reboot endpoint.
- Polling puts the ESP32 in charge and works from wherever it can already
  reach System B (same path OTA already uses).
"""
import time
import _thread

from http_utils import http_get_json, http_post_json

try:
    from log_buffer import log_print as print
except ImportError:
    pass


class CommandClient:
    """
    Datalogger command poller.

    Usage:
        client = CommandClient(config, get_device_id_fn=bridge.get_device_id)
        # In a background thread:
        while True:
            client.poll_once()
            time.sleep(30)
    """

    def __init__(self, config, get_device_id_fn):
        """
        Args:
            config: Loaded device config dict (needs config['api']['base_url']).
            get_device_id_fn: Callable returning the device UUID string
                assigned by System B at registration, or None if not yet
                registered.  Kept as a callable (not a value) because the
                UUID isn't known until modbus_bridge.register_device()
                succeeds after WiFi comes up.
        """
        self._config = config
        self._get_device_id = get_device_id_fn
        self._base_url = config.get("api", {}).get("base_url", "http://localhost:8001")

        # Handler registry: command_type → callable(command_dict) → (success:bool, result_or_error:str|dict)
        # Populated below.  Adding a new datalogger command means adding a
        # handler here AND a matching entry in the backend's
        # DATALOGGER_COMMANDS dict.
        self._handlers = {
            "reboot_datalogger": self._handle_reboot_datalogger,
        }

    def poll_once(self):
        """
        Execute one poll cycle.  Safe to call repeatedly; catches all
        exceptions so the caller loop never dies.
        """
        try:
            device_id = self._get_device_id()
            if not device_id:
                # Not yet registered with System B.  Silent skip.
                return

            url = "{}/api/v1/commands/pending/{}?scope=datalogger".format(
                self._base_url, device_id
            )
            status, cmd = http_get_json(url, timeout=10)

            if status != 200 or not cmd:
                # 200 with null body = nothing to do; any other status = try later
                return

            command_id = cmd.get("id")
            command_type = cmd.get("command_type")

            if not command_id or not command_type:
                print("[Cmd] Malformed command payload:", cmd)
                return

            print("[Cmd] Claimed {} (id={})".format(command_type, command_id))

            handler = self._handlers.get(command_type)
            if not handler:
                # Unknown datalogger command — report failure so it doesn't
                # sit pending forever.  Should not happen if backend and
                # firmware are kept in sync, but guard against version skew.
                self._report_result(command_id, success=False, error="Unknown datalogger command: " + str(command_type))
                return

            # Ack first so the server sees the device took ownership.  Even
            # if the handler's own report fails afterwards, the ack timestamp
            # lets an operator see the command reached the device.
            self._acknowledge(command_id)

            try:
                success, payload = handler(cmd)
                if success:
                    self._report_result(command_id, success=True, data=payload if isinstance(payload, dict) else {"detail": str(payload)})
                else:
                    self._report_result(command_id, success=False, error=str(payload))
            except Exception as e:
                print("[Cmd] Handler {} raised: {}".format(command_type, e))
                self._report_result(command_id, success=False, error="Handler exception: " + str(e))

        except Exception as e:
            # Any unexpected failure — log and continue.  The poll loop must
            # never die from a transient error.
            print("[Cmd] poll_once error:", e)

    # =========================================================================
    # HTTP wrappers around System B command endpoints
    # =========================================================================

    def _acknowledge(self, command_id):
        """POST /commands/{id}/acknowledge — best-effort, ignore errors."""
        url = "{}/api/v1/commands/{}/acknowledge".format(self._base_url, command_id)
        try:
            http_post_json(url, {}, timeout=10)
        except Exception as e:
            print("[Cmd] ack failed:", e)

    def _report_result(self, command_id, success, data=None, error=None):
        """POST /commands/{id}/result — best-effort, ignore errors."""
        url = "{}/api/v1/commands/{}/result".format(self._base_url, command_id)
        body = {"success": bool(success)}
        if success and data is not None:
            body["data"] = data
        if not success and error:
            body["error_message"] = str(error)
        try:
            http_post_json(url, body, timeout=10)
        except Exception as e:
            print("[Cmd] result report failed:", e)

    # =========================================================================
    # Command handlers
    # =========================================================================

    def _handle_reboot_datalogger(self, command):
        """
        Reboot the ESP32 after briefly deferring so the HTTP result POST has
        time to reach the server before the network stack goes down.

        Result reporting is done by the caller (poll_once) AFTER this handler
        returns success, but the actual reset must happen shortly after.  We
        arm a background timer thread so the ack/result HTTP calls in the
        outer loop can complete first.
        """
        def _delayed_reset():
            import machine
            # 2s gives the poll_once caller time to POST /result before
            # sockets are torn down.  Kept short so a user pressing the
            # button gets fast feedback ("reboot in progress").
            time.sleep(2)
            print("[Cmd] Executing machine.reset() now")
            machine.reset()

        try:
            _thread.start_new_thread(_delayed_reset, ())
            print("[Cmd] Reboot armed (reset in 2s)")
            return True, {"detail": "Reboot scheduled in 2 seconds"}
        except Exception as e:
            return False, "Failed to schedule reset: " + str(e)
