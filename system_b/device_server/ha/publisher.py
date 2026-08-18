"""
Home Assistant Telemetry Publisher.

Reads enrolled devices from System A, polls Redis for current telemetry,
and publishes to the dedicated HA MQTT broker so that Home Assistant
can auto-discover and display all Solar Hub devices.

Lifecycle:
  start()         — connect to HA broker
  serve_forever() — async loop: refresh enrollments → publish → wait
  stop()          — signal shutdown event, disconnect
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from .discovery import (
    build_availability_topic,
    build_discovery_payload,
    build_discovery_topic,
    build_state_topic,
    get_metrics_for_device_type,
    get_stale_metric_keys,
)
from .energy_calculator import BatteryEnergyCalculator, InverterEnergyCalculator
from .spike_guard import EnergySpikeGuard

logger = logging.getLogger(__name__)

# Redis key for device telemetry (written by redis_cache.py)
_REDIS_KEY = "device:{serial}:telemetry"


class HATelemetryPublisher:
    """
    Publishes Solar Hub telemetry to a dedicated HA MQTT broker.

    One instance per System B process.  Runs as a background asyncio task.
    """

    def __init__(
        self,
        ha_mqtt_settings,
        redis_client,
        system_a_url: str,
        system_a_api_key: Optional[str],
        db_url: Optional[str] = None,
    ) -> None:
        self._settings = ha_mqtt_settings
        self._redis = redis_client
        self._system_a_url = system_a_url.rstrip("/")
        self._system_a_api_key = system_a_api_key

        self._mqtt_client = None
        self._enrollments: List[Dict[str, Any]] = []
        self._last_enrollment_refresh: float = 0.0
        # Maps discovery_key → device_type string for which discovery was published.
        # If device_type changes we re-publish discovery with the correct metric set.
        self._discovery_published: Dict[str, str] = {}
        self._shutdown_event = asyncio.Event()

        # Energy calculators  (Redis accumulator + TimescaleDB for totals)
        self._energy_calc     = BatteryEnergyCalculator(redis_client, db_url=db_url)
        self._inv_energy_calc = InverterEnergyCalculator(redis_client, db_url=db_url)

        # Sanity guard for energy sensors — rejects implausible spikes before
        # they poison Home Assistant's long-term statistics.
        self._spike_guard = EnergySpikeGuard(redis_client)

        # Tracks last-publish wall-clock time per device for interval calculation
        self._last_publish_ts: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to the HA MQTT broker."""
        try:
            import aiomqtt  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "aiomqtt is required for HA publisher. "
                "Install with: pip install aiomqtt"
            )

        logger.info(
            "HA publisher connecting to %s:%d",
            self._settings.broker_host,
            self._settings.broker_port,
        )
        # Connection happens inside serve_forever's context manager

    async def stop(self) -> None:
        """Signal the publisher loop to exit."""
        self._shutdown_event.set()
        await self._energy_calc.close()
        await self._inv_energy_calc.close()

    async def serve_forever(self) -> None:
        """
        Main publisher loop.  Runs until stop() is called.

        Uses asyncio-mqtt's Client as a context manager for the full loop
        so the broker connection persists across publish cycles.
        """
        import aiomqtt

        will_topic = f"solarhub/ha/_publisher/availability"

        try:
            async with aiomqtt.Client(
                hostname=self._settings.broker_host,
                port=self._settings.broker_port,
                username=self._settings.publisher_username,
                password=self._settings.publisher_password,
                will=aiomqtt.Will(topic=will_topic, payload=b"offline", retain=True),
            ) as client:
                self._mqtt_client = client
                logger.info("HA publisher connected to broker")

                # Announce publisher is online
                await client.publish(will_topic, payload=b"online", retain=True)

                while not self._shutdown_event.is_set():
                    await self._maybe_refresh_enrollments()
                    await self._publish_cycle(client)
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self._settings.publish_interval,
                        )
                    except asyncio.TimeoutError:
                        pass  # normal — time for next cycle

                # Graceful shutdown: mark all devices offline
                await self._publish_all_offline(client)
                await client.publish(will_topic, payload=b"offline", retain=True)

        except Exception as exc:
            logger.error("HA publisher error: %s", exc, exc_info=True)
        finally:
            self._mqtt_client = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _maybe_refresh_enrollments(self) -> None:
        """Fetch enrollment list from System A if cache is stale."""
        now = time.monotonic()
        if now - self._last_enrollment_refresh < self._settings.enrollment_refresh_interval:
            return

        try:
            headers = {}
            if self._system_a_api_key:
                headers["X-API-Key"] = self._system_a_api_key

            async with aiohttp.ClientSession() as session:
                url = f"{self._system_a_url}/api/v1/integrations/mqtt/enrolled-devices"
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        self._enrollments = await resp.json()
                        self._last_enrollment_refresh = now
                        logger.debug(
                            "Refreshed HA enrollments: %d devices", len(self._enrollments)
                        )
                    else:
                        logger.warning(
                            "Failed to refresh HA enrollments: HTTP %d", resp.status
                        )
        except Exception as exc:
            logger.warning("Error refreshing HA enrollments: %s", exc)

    async def _publish_cycle(self, client) -> None:
        """Publish state + availability for all enrolled devices."""
        for enrollment in self._enrollments:
            try:
                await self._publish_device(client, enrollment)
            except Exception as exc:
                logger.warning(
                    "Error publishing HA state for %s: %s",
                    enrollment.get("device_serial"),
                    exc,
                )

    async def _publish_device(self, client, enrollment: Dict[str, Any]) -> None:
        ha_username = enrollment["ha_username"]
        serial = enrollment["device_serial"]
        device_name = enrollment.get("device_name", serial)
        manufacturer = enrollment.get("manufacturer") or "Solar Hub"
        model = enrollment.get("model") or "Inverter"

        # Read telemetry from Redis first — we need device_type for discovery
        redis_key = _REDIS_KEY.format(serial=serial)
        raw = await self._redis.get(redis_key)

        avail_topic = build_availability_topic(ha_username, serial)

        if raw is None:
            # No recent data — mark device unavailable, skip discovery for now.
            # Advance _last_publish_ts so that when the device reconnects we
            # don't integrate an enormous offline gap into today's energy
            # (that would produce a false ~kWh burst in HA).
            self._last_publish_ts[serial] = time.monotonic()
            await client.publish(avail_topic, payload=b"offline", retain=False)
            return

        try:
            telemetry = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupt telemetry JSON for %s", serial)
            self._last_publish_ts[serial] = time.monotonic()
            await client.publish(avail_topic, payload=b"offline", retain=False)
            return

        # Staleness guard: if the telemetry timestamp is older than 5 minutes,
        # treat the device as offline even if the Redis key hasn't expired yet.
        # This prevents the publisher from accumulating energy from frozen readings
        # (e.g. JK BMS devices that disconnect without clearing their Redis key).
        ts_str = telemetry.get("timestamp")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
                if age_seconds > 300:  # 5 minutes
                    logger.debug(
                        "Stale telemetry for %s (age=%.0fs) — marking offline", serial, age_seconds
                    )
                    self._last_publish_ts[serial] = time.monotonic()
                    await client.publish(avail_topic, payload=b"offline", retain=False)
                    return
            except (ValueError, TypeError):
                pass  # malformed timestamp — let it through

        device_type = (telemetry.get("device_type") or "").lower()

        # Publish discovery when first seen or when device_type changes
        discovery_key = f"{ha_username}:{serial}"
        if self._discovery_published.get(discovery_key) != device_type:
            await self._publish_discovery(
                client, ha_username, serial, device_name, manufacturer, model,
                device_type=device_type,
            )
            self._discovery_published[discovery_key] = device_type

        state = self._build_state_payload(telemetry)

        # Track per-device publish interval for energy accumulation
        now = time.monotonic()
        last_ts = self._last_publish_ts.get(serial)
        interval_sec = (now - last_ts) if last_ts else 0.0
        self._last_publish_ts[serial] = now

        # For battery devices inject calculated energy (no hardware registers)
        if device_type == "battery":
            power_w = state.get("battery_power_w")
            (
                state["battery_charge_today_kwh"],
                state["battery_discharge_today_kwh"],
                state["battery_charge_total_kwh"],
                state["battery_discharge_total_kwh"],
            ) = await self._energy_calc.get_energy(serial, power_w, interval_sec)

        # For inverter devices fill any None energy fields via calculated values
        # (covers Voltronic — no energy registers at all — and Deye — no total registers)
        elif device_type == "inverter":
            await self._inv_energy_calc.fill_missing_energy(serial, state, interval_sec)

        # Final sanity pass: reject implausible energy readings so a single
        # bad Modbus poll can't corrupt HA's long-term statistics.  Rejected
        # values are replaced with the last-good value from Redis (or None if
        # this is the first reading we've ever seen for the metric).
        await self._spike_guard.sanitize(serial, state)

        state_topic = build_state_topic(ha_username, serial)

        await client.publish(
            state_topic,
            payload=json.dumps(state).encode(),
            retain=False,
        )
        await client.publish(avail_topic, payload=b"online", retain=False)

    async def _publish_discovery(
        self,
        client,
        ha_username: str,
        serial: str,
        device_name: str,
        manufacturer: str,
        model: str,
        device_type: str = "",
    ) -> None:
        """Publish retained HA Discovery config for all metrics of a device."""
        metrics = get_metrics_for_device_type(device_type)
        for metric in metrics:
            topic = build_discovery_topic(ha_username, serial, metric["key"])
            payload = build_discovery_payload(
                ha_username=ha_username,
                device_serial=serial,
                device_name=device_name,
                manufacturer=manufacturer,
                model=model,
                metric=metric,
            )
            await client.publish(
                topic,
                payload=json.dumps(payload).encode(),
                retain=True,  # retained so HA sees it on reconnect
            )
        # Tombstone any sensors that existed in the previous (broader) discovery
        # set but are not valid for this device type.  An empty retained payload
        # tells HA to remove the entity.
        for stale_key in get_stale_metric_keys(device_type):
            stale_topic = build_discovery_topic(ha_username, serial, stale_key)
            await client.publish(stale_topic, payload=b"", retain=True)

        logger.debug(
            "Published HA discovery for %s / %s (type=%s, sensors=%d)",
            ha_username, serial, device_type or "unknown", len(metrics),
        )

    def _build_state_payload(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten Redis telemetry JSON into the flat dict HA reads via value_template.

        Redis cache structure (from redis_cache.py):
          power.pv_total_w, power.grid_w, power.load_w, power.battery_w
          battery.soc_pct, battery.voltage_v, battery.current_a,
                  battery.soh_pct, battery.cycle_count
          energy_today.pv_kwh, energy_today.grid_import_kwh,
                  energy_today.grid_export_kwh, energy_today.load_kwh,
                  energy_today.battery_charge_kwh, energy_today.battery_discharge_kwh
          energy_total.pv_kwh, energy_total.grid_import_kwh,
                  energy_total.grid_export_kwh, energy_total.load_kwh,
                  energy_total.battery_charge_kwh, energy_total.battery_discharge_kwh
          temperatures.inverter_c, temperatures.battery_c
          grid.frequency_hz, grid.voltage_v
          raw.* (fallback for any field not in normalised sections)
        """
        power = telemetry.get("power") or {}
        battery = telemetry.get("battery") or {}
        energy = telemetry.get("energy_today") or {}
        energy_total = telemetry.get("energy_total") or {}
        temps = telemetry.get("temperatures") or {}
        grid = telemetry.get("grid") or {}
        raw = telemetry.get("raw") or {}

        def _f(value) -> Optional[float]:
            try:
                return round(float(value), 2) if value is not None else None
            except (TypeError, ValueError):
                return None

        def _i(value) -> Optional[int]:
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        return {
            # Epoch anchor for lifetime-total sensors (state_class: total).
            # A fixed last_reset tells HA to always delta from the previous
            # known value instead of from 0, preventing reconnect spikes.
            "last_reset_epoch": "1970-01-01T00:00:00+00:00",
            # ── Live power ──────────────────────────────────────────────────
            "pv_power_w":      _f(power.get("pv_total_w")),
            "grid_power_w":    _f(power.get("grid_w")),
            "load_power_w":    _f(power.get("load_w")),
            "battery_power_w": _f(power.get("battery_w")),
            # ── Battery state ───────────────────────────────────────────────
            "battery_soc_percent": _f(battery.get("soc_pct")),
            "battery_voltage_v":   _f(battery.get("voltage_v") or raw.get("battery_voltage_v")),
            "battery_current_a":   _f(battery.get("current_a")),
            "battery_soh_percent": _f(battery.get("soh_pct")),
            "battery_cycle_count": _i(battery.get("cycle_count")),
            # ── Grid ────────────────────────────────────────────────────────
            "grid_voltage_v":    _f(grid.get("voltage_v")),
            "grid_frequency_hz": _f(grid.get("frequency_hz")),
            # ── Temperatures ────────────────────────────────────────────────
            "inverter_temp_c": _f(temps.get("inverter_c")),
            "battery_temp_c":  _f(temps.get("battery_c") or raw.get("battery_temp_c")),
            # ── Energy today ────────────────────────────────────────────────
            "pv_energy_today_kwh":         _f(energy.get("pv_kwh")),
            "grid_import_today_kwh":       _f(energy.get("grid_import_kwh")),
            "grid_export_today_kwh":       _f(energy.get("grid_export_kwh")),
            "load_energy_today_kwh":       _f(energy.get("load_kwh")),
            "battery_charge_today_kwh":    _f(energy.get("battery_charge_kwh")),
            "battery_discharge_today_kwh": _f(energy.get("battery_discharge_kwh")),
            # ── Energy total (lifetime) ──────────────────────────────────────
            "pv_energy_total_kwh":         _f(energy_total.get("pv_kwh")),
            "grid_import_total_kwh":       _f(energy_total.get("grid_import_kwh")),
            "grid_export_total_kwh":       _f(energy_total.get("grid_export_kwh")),
            "load_energy_total_kwh":       _f(energy_total.get("load_kwh")),
            "battery_charge_total_kwh":    _f(energy_total.get("battery_charge_kwh")),
            "battery_discharge_total_kwh": _f(energy_total.get("battery_discharge_kwh")),
        }

    async def _publish_all_offline(self, client) -> None:
        """Mark all enrolled devices offline on graceful shutdown."""
        for enrollment in self._enrollments:
            try:
                topic = build_availability_topic(
                    enrollment["ha_username"], enrollment["device_serial"]
                )
                await client.publish(topic, payload=b"offline", retain=False)
            except Exception:
                pass
