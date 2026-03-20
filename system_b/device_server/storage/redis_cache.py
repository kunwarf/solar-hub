"""
Redis cache for real-time telemetry sharing with System A.

This cache provides:
1. Real-time telemetry snapshots keyed by device serial number
2. Device online/offline status
3. Last seen timestamps

System A reads from this cache for dashboard data.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis.asyncio as redis

from ..config import DeviceServerSettings, get_device_server_settings

logger = logging.getLogger(__name__)


class TelemetryCacheWriter:
    """
    Writes telemetry data to Redis cache for System A to read.

    Uses the device serial number as the key to enable
    cross-system data sharing without ID synchronization.
    """

    # Redis key patterns
    KEY_TELEMETRY = "device:{serial}:telemetry"
    KEY_STATUS = "device:{serial}:status"
    KEY_LAST_SEEN = "device:{serial}:last_seen"

    def __init__(
        self,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the cache writer.

        Args:
            settings: Server settings.
        """
        self.settings = settings or get_device_server_settings()
        self._client: Optional[redis.Redis] = None
        self._connected = False

    async def connect(self) -> bool:
        """
        Connect to Redis.

        Returns:
            True if connected successfully.
        """
        try:
            redis_settings = self.settings.redis
            self._client = redis.Redis(
                host=redis_settings.host,
                port=redis_settings.port,
                db=redis_settings.db,
                password=redis_settings.password,
                ssl=redis_settings.ssl,
                decode_responses=True,
            )
            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info(
                f"Redis cache connected: {redis_settings.host}:{redis_settings.port}/{redis_settings.db}"
            )
            return True
        except Exception as e:
            logger.warning(f"Redis cache connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
            self._connected = False
            logger.info("Redis cache disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        return self._connected and self._client is not None

    async def write_telemetry(
        self,
        serial_number: str,
        telemetry: Dict[str, Any],
    ) -> bool:
        """
        Write telemetry data to Redis cache.

        Args:
            serial_number: Device serial number (universal identifier).
            telemetry: Telemetry data dictionary.

        Returns:
            True if write succeeded.
        """
        if not self.is_connected:
            return False

        try:
            redis_settings = self.settings.redis
            now = time.time()

            # Prepare the telemetry data for caching
            # Format it according to the design document structure
            cache_data = self._format_telemetry_for_cache(serial_number, telemetry)

            # Build keys
            key_telemetry = self.KEY_TELEMETRY.format(serial=serial_number)
            key_status = self.KEY_STATUS.format(serial=serial_number)
            key_last_seen = self.KEY_LAST_SEEN.format(serial=serial_number)

            # Use pipeline for atomic writes
            async with self._client.pipeline() as pipe:
                # Write telemetry snapshot
                pipe.setex(
                    key_telemetry,
                    redis_settings.telemetry_ttl,
                    json.dumps(cache_data, default=str),
                )

                # Write status as online
                pipe.setex(
                    key_status,
                    redis_settings.status_ttl,
                    "online",
                )

                # Write last seen timestamp
                pipe.setex(
                    key_last_seen,
                    redis_settings.status_ttl,
                    str(int(now)),
                )

                await pipe.execute()

            logger.debug(f"Cached telemetry for device {serial_number}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache telemetry for {serial_number}: {e}")
            return False

    async def write_status(
        self,
        serial_number: str,
        status: str,
    ) -> bool:
        """
        Write device status to Redis cache.

        Args:
            serial_number: Device serial number.
            status: Status string ("online" or "offline").

        Returns:
            True if write succeeded.
        """
        if not self.is_connected:
            return False

        try:
            key_status = self.KEY_STATUS.format(serial=serial_number)
            await self._client.setex(
                key_status,
                self.settings.redis.status_ttl,
                status,
            )
            logger.debug(f"Cached status for device {serial_number}: {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to cache status for {serial_number}: {e}")
            return False

    def _format_telemetry_for_cache(
        self,
        serial_number: str,
        telemetry: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Format telemetry data for cache storage.

        Transforms the raw telemetry into the structure expected by System A,
        matching the format defined in the telemetry-flow-design.md document.

        Args:
            serial_number: Device serial number.
            telemetry: Raw telemetry from device.

        Returns:
            Formatted telemetry dictionary.
        """
        # Get timestamp from telemetry or use current time
        timestamp = telemetry.get("_timestamp") or datetime.now(timezone.utc).isoformat()

        # Build structured response based on design doc
        cache_data = {
            "serial_number": serial_number,
            "timestamp": timestamp,
        }

        # Extract power metrics
        # Field names from Modbus register maps use _w suffix (e.g., pv1_power_w)
        power_data = {}
        power_mappings = {
            "pv_total_w": ["pv_power_w", "pv_power", "pv_total_power", "solar_power"],
            "pv1_w": ["pv1_power_w", "pv1_power", "pv_power_1"],
            "pv2_w": ["pv2_power_w", "pv2_power", "pv_power_2"],
            "grid_w": ["grid_power_w", "grid_power", "ac_power"],
            "load_w": ["load_power_w", "load_power", "consumption_power"],
            "battery_w": ["battery_power_w", "battery_power", "bat_power", "power"],
        }
        for target_key, source_keys in power_mappings.items():
            for src in source_keys:
                if src in telemetry:
                    power_data[target_key] = telemetry[src]
                    break

        # Calculate pv_total_w if we have pv1 and pv2 but not total
        if "pv_total_w" not in power_data:
            pv1 = power_data.get("pv1_w", 0) or 0
            pv2 = power_data.get("pv2_w", 0) or 0
            if pv1 or pv2:
                power_data["pv_total_w"] = pv1 + pv2

        if power_data:
            cache_data["power"] = power_data

        # Extract battery metrics
        # Field names from Modbus use _pct, _v, _a suffixes
        battery_data = {}
        battery_mappings = {
            "soc_pct": ["battery_soc_pct", "battery_soc", "soc", "state_of_charge"],
            "voltage_v": ["battery_voltage_v", "battery_voltage", "bat_voltage", "pack_voltage"],
            "current_a": ["battery_current_a", "battery_current", "bat_current", "current"],
            "soh_pct": ["battery_soh_pct", "battery_soh", "soh"],
            "cycle_count": ["battery_cycle_count", "cycle_count"],
        }
        for target_key, source_keys in battery_mappings.items():
            for src in source_keys:
                if src in telemetry:
                    battery_data[target_key] = telemetry[src]
                    break
        # Determine if charging — prefer signed current (reliable direction indicator)
        # over battery power which may be U32 (unsigned) on some inverters (e.g. Senergy)
        if "battery_current_a" in telemetry:
            battery_data["charging"] = telemetry["battery_current_a"] > 0
        elif "battery_current" in telemetry:
            battery_data["charging"] = telemetry["battery_current"] > 0
        elif "current" in telemetry:
            battery_data["charging"] = telemetry["current"] > 0
        elif "battery_power_w" in telemetry:
            battery_data["charging"] = telemetry["battery_power_w"] > 0
        elif "battery_power" in telemetry:
            battery_data["charging"] = telemetry["battery_power"] > 0
        if battery_data:
            cache_data["battery"] = battery_data

        # Extract energy today metrics
        # Common Modbus field names for daily energy
        energy_data = {}
        energy_mappings = {
            "pv_kwh": [
                "pv_energy_today_kwh", "pv_energy_today", "solar_energy_today",
                "daily_pv_kwh", "today_pv_kwh", "pv_generation_today_kwh",
            ],
            "load_kwh": [
                "load_energy_today_kwh", "load_energy_today", "consumption_today",
                "daily_load_kwh", "today_load_kwh", "consumption_today_kwh",
            ],
            "grid_import_kwh": [
                "grid_import_today_kwh", "grid_import_today", "import_kwh",
                "grid_buy_today_kwh", "today_import_kwh",
            ],
            "grid_export_kwh": [
                "grid_export_today_kwh", "grid_export_today", "export_kwh",
                "grid_sell_today_kwh", "today_export_kwh",
            ],
            "battery_charge_kwh": [
                "battery_charge_today_kwh", "battery_charge_today", "charge_kwh",
                "today_charge_kwh",
            ],
            "battery_discharge_kwh": [
                "battery_discharge_today_kwh", "battery_discharge_today", "discharge_kwh",
                "today_discharge_kwh",
            ],
        }
        for target_key, source_keys in energy_mappings.items():
            for src in source_keys:
                if src in telemetry:
                    energy_data[target_key] = telemetry[src]
                    break
        if energy_data:
            cache_data["energy_today"] = energy_data

        # Extract temperature metrics
        # Modbus field names use _c suffix for Celsius
        temp_data = {}
        temp_mappings = {
            "inverter_c": [
                "inverter_temp_c", "inverter_temp", "temperature_c",
                "temperature", "inv_temp", "heatsink_temp_c",
            ],
            "battery_c": [
                "battery_temp_c", "battery_temp", "bat_temp_c", "bat_temp",
                "temp1", "mos_temp",
            ],
            "ambient_c": [
                "ambient_temp_c", "ambient_temp", "env_temp_c", "env_temp",
            ],
        }
        for target_key, source_keys in temp_mappings.items():
            for src in source_keys:
                if src in telemetry:
                    temp_data[target_key] = telemetry[src]
                    break
        if temp_data:
            cache_data["temperatures"] = temp_data

        # Extract grid metrics
        # Modbus field names use _v and _hz suffixes
        grid_data = {}
        grid_mappings = {
            "voltage_v": [
                "grid_voltage_v", "grid_voltage", "ac_voltage_v", "ac_voltage",
            ],
            "frequency_hz": [
                "grid_frequency_hz", "grid_frequency", "ac_frequency_hz",
                "ac_frequency", "frequency_hz", "frequency",
            ],
            "l1_voltage_v": [
                "l1_voltage_v", "l1_voltage", "phase1_voltage_v", "phase1_voltage",
                "grid_l1_voltage_v",
            ],
            "l2_voltage_v": [
                "l2_voltage_v", "l2_voltage", "phase2_voltage_v", "phase2_voltage",
                "grid_l2_voltage_v",
            ],
            "l3_voltage_v": [
                "l3_voltage_v", "l3_voltage", "phase3_voltage_v", "phase3_voltage",
                "grid_l3_voltage_v",
            ],
        }
        for target_key, source_keys in grid_mappings.items():
            for src in source_keys:
                if src in telemetry:
                    grid_data[target_key] = telemetry[src]
                    break
        if grid_data:
            cache_data["grid"] = grid_data

        # Extract status info
        status_data = {
            "grid_connected": telemetry.get("grid_connected", True),
            "faults": telemetry.get("faults", []),
            "warnings": telemetry.get("warnings", []),
        }
        if "working_mode" in telemetry:
            status_data["working_mode"] = telemetry["working_mode"]
        if "working_mode_name" in telemetry:
            status_data["working_mode_name"] = telemetry["working_mode_name"]
        cache_data["status"] = status_data

        # Battery bank detail — supports both Pylontech (battery_units/battery_cells)
        # and JK BMS (cell_voltages list) in a unified format.
        battery_units = telemetry.get("battery_units")
        battery_cells = telemetry.get("battery_cells")
        cell_voltages = telemetry.get("cell_voltages")  # JK BMS native field
        if battery_units or battery_cells or cell_voltages:
            bank_data: dict = {}
            if battery_units:
                bank_data["units"] = battery_units
            if battery_cells:
                bank_data["cells"] = battery_cells
            # JK BMS: synthesize a single unit entry and per-cell rows
            if cell_voltages and not battery_units:
                # One logical unit representing the whole pack
                unit_entry: dict = {"unit": 1}
                for field, jk_key in (
                    ("voltage_v", "pack_voltage"),
                    ("current_a", "current"),
                    ("soc_pct", "soc"),
                    ("soh_pct", "soh"),
                    ("temp_c", "temp1"),
                    ("cycle_count", "cycle_count"),
                ):
                    if jk_key in telemetry:
                        unit_entry[field] = telemetry[jk_key]
                bank_data["units"] = [unit_entry]
                bank_data["cells"] = [
                    {"unit": 1, "cell": i + 1, "voltage_v": v}
                    for i, v in enumerate(cell_voltages)
                    if v is not None
                ]
            # Carry over bank-level extras
            for key in ("battery_soh_pct", "battery_cycle_count", "battery_units_count",
                        "battery_has_alarm", "battery_has_fault", "battery_alarms"):
                if key in telemetry:
                    bank_data[key.replace("battery_", "")] = telemetry[key]
            cache_data["battery_bank"] = bank_data

        # Also include raw telemetry values for flexibility
        # (System A can use either structured or raw data)
        cache_data["raw"] = {
            k: v for k, v in telemetry.items()
            if not k.startswith("_")  # Exclude internal metadata
        }

        return cache_data
