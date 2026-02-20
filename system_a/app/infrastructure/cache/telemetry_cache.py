"""
Telemetry cache reader for System A.

Reads real-time telemetry data from Redis cache that was written by System B.
Uses device serial number as the key for cross-system data sharing.
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional

from .redis_cache import RedisManager

logger = logging.getLogger(__name__)


class TelemetryCacheReader:
    """
    Reads telemetry data from Redis cache.

    System B writes telemetry to Redis using device serial number as key.
    System A reads from this cache for dashboard APIs.
    """

    # Redis key patterns (must match System B's TelemetryCacheWriter)
    KEY_TELEMETRY = "device:{serial}:telemetry"
    KEY_STATUS = "device:{serial}:status"
    KEY_LAST_SEEN = "device:{serial}:last_seen"

    # Cache is considered stale after this many seconds
    STALE_THRESHOLD_SECONDS = 300  # 5 minutes

    async def get_telemetry(
        self,
        serial_number: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get real-time telemetry for a device.

        Args:
            serial_number: Device serial number.

        Returns:
            Telemetry data dictionary or None if not found.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_TELEMETRY.format(serial=serial_number)
            value = await client.get(key)

            if value:
                data = json.loads(value)
                # Add staleness indicator
                data["_cached"] = True
                data["_stale"] = await self._is_stale(serial_number)
                return data
            return None

        except Exception as e:
            logger.error(f"Failed to read telemetry for {serial_number}: {e}")
            return None

    async def get_telemetry_batch(
        self,
        serial_numbers: List[str],
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get telemetry for multiple devices.

        Args:
            serial_numbers: List of device serial numbers.

        Returns:
            Dictionary mapping serial number to telemetry data.
        """
        result = {}
        try:
            client = await RedisManager.get_client()
            pipeline = client.pipeline()

            # Queue all telemetry reads
            keys = [self.KEY_TELEMETRY.format(serial=sn) for sn in serial_numbers]
            for key in keys:
                pipeline.get(key)

            # Execute pipeline
            values = await pipeline.execute()

            # Process results
            for serial, value in zip(serial_numbers, values):
                if value:
                    try:
                        data = json.loads(value)
                        data["_cached"] = True
                        data["_stale"] = await self._is_stale(serial)
                        result[serial] = data
                    except json.JSONDecodeError:
                        result[serial] = None
                else:
                    result[serial] = None

        except Exception as e:
            logger.error(f"Failed to read telemetry batch: {e}")
            # Return empty results on error
            for serial in serial_numbers:
                if serial not in result:
                    result[serial] = None

        return result

    async def get_status(
        self,
        serial_number: str,
    ) -> Optional[str]:
        """
        Get device online/offline status.

        Args:
            serial_number: Device serial number.

        Returns:
            Status string ("online" or "offline") or None if not found.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_STATUS.format(serial=serial_number)
            value = await client.get(key)
            return value.decode() if isinstance(value, bytes) else value
        except Exception as e:
            logger.error(f"Failed to read status for {serial_number}: {e}")
            return None

    async def get_last_seen(
        self,
        serial_number: str,
    ) -> Optional[int]:
        """
        Get device last seen timestamp.

        Args:
            serial_number: Device serial number.

        Returns:
            Unix timestamp or None if not found.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_LAST_SEEN.format(serial=serial_number)
            value = await client.get(key)
            return int(value) if value else None
        except Exception as e:
            logger.error(f"Failed to read last_seen for {serial_number}: {e}")
            return None

    async def _is_stale(
        self,
        serial_number: str,
    ) -> bool:
        """
        Check if cached data is stale.

        Data is considered stale if last_seen is older than threshold.
        """
        last_seen = await self.get_last_seen(serial_number)
        if last_seen is None:
            return True

        age = time.time() - last_seen
        return age > self.STALE_THRESHOLD_SECONDS

    async def get_device_summary(
        self,
        serial_number: str,
    ) -> Dict[str, Any]:
        """
        Get a summary of device status and telemetry.

        Args:
            serial_number: Device serial number.

        Returns:
            Dictionary with status, last_seen, and key telemetry metrics.
        """
        telemetry = await self.get_telemetry(serial_number)
        status = await self.get_status(serial_number)
        last_seen = await self.get_last_seen(serial_number)

        summary = {
            "serial_number": serial_number,
            "status": status or "unknown",
            "last_seen": last_seen,
            "online": status == "online",
            "stale": telemetry.get("_stale", True) if telemetry else True,
        }

        if telemetry:
            # Extract key metrics for summary
            if "power" in telemetry:
                summary["power"] = telemetry["power"]
            if "battery" in telemetry:
                summary["battery_soc"] = telemetry["battery"].get("soc_pct")
            if "energy_today" in telemetry:
                summary["energy_today"] = telemetry["energy_today"].get("pv_kwh")

        return summary


# Singleton instance
telemetry_cache = TelemetryCacheReader()
