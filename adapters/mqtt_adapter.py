"""
MQTT Adapter for solar devices that communicate via MQTT protocol.

This adapter supports devices that publish telemetry data to an MQTT broker
and accept commands via MQTT topics.

Topic Structure:
    solar-hub/{device_id}/telemetry     - Device publishes JSON telemetry
    solar-hub/{device_id}/status        - Online/offline status (LWT)
    solar-hub/{device_id}/command       - System publishes commands
    solar-hub/{device_id}/command/response - Device responds to commands
"""
import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    mqtt = None
    PAHO_AVAILABLE = False

from solarhub.adapters.base import InverterAdapter
from solarhub.models import Telemetry
from solarhub.config import InverterConfig

log = logging.getLogger(__name__)


def now_iso() -> str:
    """Get current timestamp in ISO format using configured timezone."""
    try:
        from solarhub.timezone_utils import now_configured_iso
        return now_configured_iso()
    except ImportError:
        return datetime.now(timezone.utc).isoformat()


@dataclass
class MQTTConfig:
    """Configuration for MQTT connection."""
    broker_host: str = "localhost"
    broker_port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    topic_prefix: str = "solar-hub"
    device_id: str = ""
    keepalive: int = 60
    qos: int = 1
    use_tls: bool = False
    ca_cert: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None


class MQTTAdapter(InverterAdapter):
    """
    MQTT-based adapter for solar devices.

    Supports devices that:
    - Push telemetry data to an MQTT topic
    - Accept commands via MQTT command topic
    - Respond to commands via MQTT response topic

    The adapter caches the latest telemetry and returns it on poll().
    For request-response patterns, commands are published and responses
    are awaited with a configurable timeout.
    """

    def __init__(self, inv: InverterConfig):
        super().__init__(inv)

        if not PAHO_AVAILABLE:
            raise ImportError(
                "paho-mqtt is required for MQTT adapter. "
                "Install with: pip install paho-mqtt>=2.0.0"
            )

        # Parse MQTT configuration from adapter config
        adapter = inv.adapter
        self.config = MQTTConfig(
            broker_host=getattr(adapter, 'host', None) or getattr(adapter, 'broker_host', 'localhost'),
            broker_port=getattr(adapter, 'port', None) or getattr(adapter, 'broker_port', 1883),
            username=getattr(adapter, 'username', None),
            password=getattr(adapter, 'password', None),
            client_id=getattr(adapter, 'client_id', None) or f"solarhub-{inv.id}",
            topic_prefix=getattr(adapter, 'topic_prefix', 'solar-hub'),
            device_id=getattr(adapter, 'device_id', None) or str(inv.id),
            keepalive=getattr(adapter, 'keepalive', 60),
            qos=getattr(adapter, 'qos', 1),
            use_tls=getattr(adapter, 'use_tls', False),
            ca_cert=getattr(adapter, 'ca_cert', None),
            client_cert=getattr(adapter, 'client_cert', None),
            client_key=getattr(adapter, 'client_key', None),
        )

        # Build topic paths
        base_topic = f"{self.config.topic_prefix}/{self.config.device_id}"
        self.topic_telemetry = f"{base_topic}/telemetry"
        self.topic_status = f"{base_topic}/status"
        self.topic_command = f"{base_topic}/command"
        self.topic_command_response = f"{base_topic}/command/response"

        # MQTT client (created on connect)
        self.client: Optional[mqtt.Client] = None
        self._mqtt_thread: Optional[threading.Thread] = None
        self._connected = False
        self._connection_error: Optional[str] = None

        # Event loop for async operations
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Cached telemetry data
        self._last_telemetry: Optional[Telemetry] = None
        self._last_telemetry_raw: Dict[str, Any] = {}
        self._telemetry_timestamp: Optional[datetime] = None

        # Command response handling
        self._pending_commands: Dict[str, asyncio.Future] = {}
        self._command_lock = threading.Lock()

        # Register map (optional, for field mapping)
        self._register_map: Dict[str, Dict[str, Any]] = {}
        register_map_file = getattr(adapter, 'register_map_file', None)
        if register_map_file:
            self._load_register_map(register_map_file)

    def _load_register_map(self, file_path: str) -> None:
        """Load optional register/field mapping from JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                regs = json.load(f)
            self._register_map = {r.get('id', r.get('name', '')): r for r in regs if r.get('id') or r.get('name')}
            log.info(f"Loaded MQTT field mapping from {file_path} ({len(self._register_map)} fields)")
        except Exception as e:
            log.warning(f"Could not load register map {file_path}: {e}")

    # ==================== Connection Management ====================

    async def connect(self) -> None:
        """Connect to the MQTT broker."""
        if self._connected:
            log.debug("MQTT adapter already connected")
            return

        # Store the event loop for thread-safe callbacks
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()

        # Create MQTT client
        # paho-mqtt v2.0+ uses CallbackAPIVersion
        try:
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.config.client_id,
            )
        except (TypeError, AttributeError):
            # Fallback for older paho-mqtt versions
            self.client = mqtt.Client(client_id=self.config.client_id)

        # Set credentials if provided
        if self.config.username:
            self.client.username_pw_set(self.config.username, self.config.password)

        # Configure TLS if enabled
        if self.config.use_tls:
            import ssl
            self.client.tls_set(
                ca_certs=self.config.ca_cert,
                certfile=self.config.client_cert,
                keyfile=self.config.client_key,
                cert_reqs=ssl.CERT_REQUIRED if self.config.ca_cert else ssl.CERT_NONE,
            )

        # Set Last Will and Testament (LWT)
        self.client.will_set(
            self.topic_status,
            payload=json.dumps({"status": "offline", "ts": now_iso()}),
            qos=self.config.qos,
            retain=True,
        )

        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Connect asynchronously
        connection_future = asyncio.Future()
        self._connection_future = connection_future

        try:
            log.info(f"Connecting to MQTT broker at {self.config.broker_host}:{self.config.broker_port}")
            self.client.connect_async(
                self.config.broker_host,
                self.config.broker_port,
                keepalive=self.config.keepalive,
            )

            # Start the MQTT network loop in a background thread
            self.client.loop_start()

            # Wait for connection with timeout
            try:
                await asyncio.wait_for(connection_future, timeout=10.0)
            except asyncio.TimeoutError:
                raise RuntimeError(f"MQTT connection timeout to {self.config.broker_host}:{self.config.broker_port}")

            if self._connection_error:
                raise RuntimeError(f"MQTT connection failed: {self._connection_error}")

            log.info(f"MQTT adapter connected to {self.config.broker_host}:{self.config.broker_port}")

        except Exception as e:
            log.error(f"Failed to connect to MQTT broker: {e}")
            await self.close()
            raise

    async def close(self) -> None:
        """Disconnect from the MQTT broker."""
        if self.client:
            try:
                # Publish offline status
                if self._connected:
                    self.client.publish(
                        self.topic_status,
                        payload=json.dumps({"status": "offline", "ts": now_iso()}),
                        qos=self.config.qos,
                        retain=True,
                    )

                # Stop the network loop
                self.client.loop_stop()

                # Disconnect
                self.client.disconnect()

                log.info("MQTT adapter disconnected")

            except Exception as e:
                log.warning(f"Error during MQTT disconnect: {e}")
            finally:
                self.client = None
                self._connected = False

    # ==================== MQTT Callbacks ====================

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        """Callback when connected to MQTT broker."""
        # Handle both v1 and v2 callback signatures
        if isinstance(reason_code, int):
            rc = reason_code
        else:
            rc = reason_code.value if hasattr(reason_code, 'value') else 0

        if rc == 0:
            self._connected = True
            self._connection_error = None
            log.info(f"Connected to MQTT broker, subscribing to topics")

            # Subscribe to telemetry and command response topics
            client.subscribe(self.topic_telemetry, qos=self.config.qos)
            client.subscribe(self.topic_command_response, qos=self.config.qos)
            client.subscribe(self.topic_status, qos=self.config.qos)

            # Publish online status
            client.publish(
                self.topic_status,
                payload=json.dumps({"status": "online", "ts": now_iso()}),
                qos=self.config.qos,
                retain=True,
            )

            # Resolve connection future
            if hasattr(self, '_connection_future') and self._connection_future:
                if self._loop and not self._connection_future.done():
                    self._loop.call_soon_threadsafe(
                        self._connection_future.set_result, True
                    )
        else:
            self._connected = False
            self._connection_error = f"Connection refused with code {rc}"
            log.error(f"MQTT connection failed: {self._connection_error}")

            if hasattr(self, '_connection_future') and self._connection_future:
                if self._loop and not self._connection_future.done():
                    self._loop.call_soon_threadsafe(
                        self._connection_future.set_exception,
                        RuntimeError(self._connection_error)
                    )

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None) -> None:
        """Callback when disconnected from MQTT broker."""
        self._connected = False
        log.warning(f"Disconnected from MQTT broker (reason: {reason_code})")

    def _on_message(self, client, userdata, msg) -> None:
        """Callback when a message is received."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')

            log.debug(f"MQTT message received on {topic}: {payload[:200]}...")

            if topic == self.topic_telemetry:
                self._handle_telemetry_message(payload)
            elif topic == self.topic_command_response:
                self._handle_command_response(payload)
            elif topic == self.topic_status:
                self._handle_status_message(payload)
            else:
                log.debug(f"Received message on unhandled topic: {topic}")

        except Exception as e:
            log.error(f"Error processing MQTT message: {e}")

    def _handle_telemetry_message(self, payload: str) -> None:
        """Process incoming telemetry message."""
        try:
            data = json.loads(payload)
            self._last_telemetry_raw = data
            self._telemetry_timestamp = datetime.now(timezone.utc)

            # Map raw telemetry to Telemetry object
            tel = self._map_telemetry(data)
            self._last_telemetry = tel

            log.debug(f"Telemetry updated: pv={tel.pv_power_w}W, grid={tel.grid_power_w}W, soc={tel.batt_soc_pct}%")

        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in telemetry message: {e}")
        except Exception as e:
            log.error(f"Error processing telemetry: {e}")

    def _handle_command_response(self, payload: str) -> None:
        """Process command response message."""
        try:
            data = json.loads(payload)
            command_id = data.get('command_id') or data.get('id')

            if command_id:
                with self._command_lock:
                    future = self._pending_commands.pop(command_id, None)

                if future and self._loop:
                    self._loop.call_soon_threadsafe(
                        future.set_result, data
                    )
                else:
                    log.debug(f"Received response for unknown command: {command_id}")
            else:
                log.warning("Command response missing command_id")

        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON in command response: {e}")

    def _handle_status_message(self, payload: str) -> None:
        """Process device status message."""
        try:
            data = json.loads(payload)
            status = data.get('status', 'unknown')
            log.info(f"Device status: {status}")
        except json.JSONDecodeError:
            log.debug(f"Status message: {payload}")

    # ==================== Telemetry Mapping ====================

    def _map_telemetry(self, data: Dict[str, Any]) -> Telemetry:
        """Map raw telemetry data to Telemetry object."""
        # Helper to get value with multiple possible keys
        def get_value(*keys, default=None):
            for key in keys:
                if key in data:
                    return data[key]
            return default

        # Extract common fields with various naming conventions
        pv_power = get_value('pv_power_w', 'pv_power', 'solar_power', 'dc_power')
        grid_power = get_value('grid_power_w', 'grid_power', 'ac_power')
        load_power = get_value('load_power_w', 'load_power', 'consumption')
        batt_voltage = get_value('batt_voltage_v', 'battery_voltage', 'batt_voltage')
        batt_current = get_value('batt_current_a', 'battery_current', 'batt_current')
        batt_power = get_value('batt_power_w', 'battery_power', 'batt_power')
        batt_soc = get_value('batt_soc_pct', 'battery_soc', 'soc', 'state_of_charge')
        inverter_temp = get_value('inverter_temp_c', 'temperature', 'temp')

        # Get timestamp from data or use current time
        ts = data.get('ts') or data.get('timestamp') or now_iso()

        # Get array_id from inverter config
        array_id = getattr(self.inv, 'array_id', None)

        # Build extra dict with all raw data
        extra = data.copy()

        return Telemetry(
            ts=ts,
            pv_power_w=pv_power,
            grid_power_w=grid_power,
            load_power_w=load_power,
            batt_voltage_v=batt_voltage,
            batt_current_a=batt_current,
            batt_power_w=self.normalize_battery_power(batt_power),
            batt_soc_pct=batt_soc,
            inverter_temp_c=inverter_temp,
            array_id=array_id,
            extra=extra,
        )

    # ==================== Adapter Interface ====================

    async def poll(self) -> Telemetry:
        """
        Return the latest cached telemetry.

        For push-based MQTT devices, telemetry is received asynchronously
        and cached. This method returns the most recent cached value.

        If no telemetry has been received, returns a Telemetry object
        with null values.
        """
        if not self._connected:
            await self.connect()

        if self._last_telemetry:
            # Check if telemetry is stale (older than 2x expected interval)
            if self._telemetry_timestamp:
                age = (datetime.now(timezone.utc) - self._telemetry_timestamp).total_seconds()
                max_age = getattr(self.inv.adapter, 'polling_interval', 60) * 2
                if age > max_age:
                    log.warning(f"Telemetry data is stale ({age:.0f}s old)")

            return self._last_telemetry

        # No telemetry received yet, return empty Telemetry
        log.debug("No telemetry data available yet")
        return Telemetry(
            ts=now_iso(),
            array_id=getattr(self.inv, 'array_id', None),
            extra={},
        )

    async def handle_command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a command to the device via MQTT and wait for response.

        Supported command actions:
        - write: Write a single value
        - write_many: Write multiple values
        - read: Request current value(s)
        - raw: Send raw command payload

        Args:
            cmd: Command dictionary with 'action' and other parameters

        Returns:
            Response dictionary from the device
        """
        if not self._connected:
            await self.connect()

        action = cmd.get('action', '').lower()
        log.info(f"Executing MQTT command: {action}")

        # Generate unique command ID
        import uuid
        command_id = str(uuid.uuid4())[:8]

        # Build command payload
        command_payload = {
            'command_id': command_id,
            'action': action,
            'ts': now_iso(),
            **{k: v for k, v in cmd.items() if k != 'action'}
        }

        # Create future for response
        response_future: asyncio.Future = asyncio.Future()
        with self._command_lock:
            self._pending_commands[command_id] = response_future

        try:
            # Publish command
            result = self.client.publish(
                self.topic_command,
                payload=json.dumps(command_payload),
                qos=self.config.qos,
            )

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise RuntimeError(f"Failed to publish command: {result.rc}")

            # Wait for response with timeout
            timeout = cmd.get('timeout', 10.0)
            try:
                response = await asyncio.wait_for(response_future, timeout=timeout)
                return response
            except asyncio.TimeoutError:
                log.warning(f"Command {command_id} timed out after {timeout}s")
                return {'ok': False, 'reason': 'timeout', 'command_id': command_id}

        except Exception as e:
            log.error(f"Error executing command: {e}")
            return {'ok': False, 'reason': str(e), 'command_id': command_id}
        finally:
            # Clean up pending command
            with self._command_lock:
                self._pending_commands.pop(command_id, None)

    async def read_serial_number(self) -> Optional[str]:
        """
        Read device serial number.

        For MQTT devices, the serial number may be included in telemetry
        or retrieved via a command.
        """
        # Check if serial number is in cached telemetry
        if self._last_telemetry_raw:
            for key in ('serial_number', 'sn', 'device_serial', 'serial'):
                if key in self._last_telemetry_raw:
                    return str(self._last_telemetry_raw[key])

        # Try to request serial number via command
        try:
            response = await self.handle_command({
                'action': 'read',
                'id': 'serial_number',
                'timeout': 5.0,
            })
            if response.get('ok') and 'value' in response:
                return str(response['value'])
        except Exception as e:
            log.debug(f"Could not read serial number via command: {e}")

        return None

    async def check_connectivity(self) -> bool:
        """Check if device is connected and responding."""
        if not self._connected:
            return False

        # Check if we've received recent telemetry
        if self._telemetry_timestamp:
            age = (datetime.now(timezone.utc) - self._telemetry_timestamp).total_seconds()
            # Consider connected if telemetry received within last 2 minutes
            if age < 120:
                return True

        # Try a ping command
        try:
            response = await self.handle_command({
                'action': 'ping',
                'timeout': 5.0,
            })
            return response.get('ok', False)
        except Exception:
            return False

    def get_tou_window_capability(self) -> Dict[str, Any]:
        """
        Returns the TOU window capability for this adapter.

        MQTT devices may have varying capabilities, so this returns
        a generic default. Device-specific adapters should override.
        """
        return {
            "max_windows": 3,
            "bidirectional": True,
            "separate_charge_discharge": False,
            "max_charge_windows": 3,
            "max_discharge_windows": 3
        }
