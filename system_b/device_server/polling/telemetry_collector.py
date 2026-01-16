"""
Telemetry collector for polling device data.

Collects telemetry from devices using their adapters and
processes the data for storage.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from ..config import DeviceServerSettings, get_device_server_settings
from ..devices.device_state import DeviceState
from ..devices.device_manager import DeviceManager

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """
    Collects telemetry data from devices.

    Handles the actual polling of devices, error handling,
    and telemetry processing.
    """

    def __init__(
        self,
        device_manager: DeviceManager,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the telemetry collector.

        Args:
            device_manager: Device manager instance.
            settings: Server settings.
        """
        self.device_manager = device_manager
        self.settings = settings or get_device_server_settings()

    async def collect(
        self,
        device_id: UUID,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Collect telemetry from a device.

        Args:
            device_id: Device ID to poll.

        Returns:
            Tuple of (success, data, error_message).
        """
        device_state = self.device_manager.get_device(device_id)
        if not device_state:
            return False, None, "Device not found"

        adapter = self.device_manager.get_adapter(device_id)
        if not adapter:
            return False, None, "No adapter for device"

        connection = self.device_manager.get_connection(device_id)
        if not connection or not connection.is_connected:
            return False, None, "Device not connected"

        start_time = time.monotonic()

        try:
            # Poll the device
            telemetry = await asyncio.wait_for(
                adapter.poll(),
                timeout=self.settings.polling.poll_timeout,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if telemetry:
                # Add metadata
                telemetry = self._enrich_telemetry(
                    device_state, telemetry, duration_ms
                )

                # Record success
                device_state.record_poll(
                    success=True,
                    data=telemetry,
                    duration_ms=duration_ms,
                )

                logger.debug(
                    f"Collected telemetry from {device_id}: "
                    f"{len(telemetry)} values in {duration_ms:.1f}ms"
                )

                return True, telemetry, None
            else:
                device_state.record_poll(
                    success=False,
                    error="Empty response",
                    duration_ms=duration_ms,
                )
                return False, None, "Empty response"

        except asyncio.TimeoutError:
            duration_ms = (time.monotonic() - start_time) * 1000
            error = "Poll timeout"
            device_state.record_poll(
                success=False,
                error=error,
                duration_ms=duration_ms,
            )
            logger.warning(f"Timeout polling device {device_id}")
            return False, None, error

        except asyncio.CancelledError:
            raise

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            error = str(e)
            device_state.record_poll(
                success=False,
                error=error,
                duration_ms=duration_ms,
            )
            logger.error(f"Error polling device {device_id}: {e}")
            return False, None, error

    def _enrich_telemetry(
        self,
        device_state: DeviceState,
        telemetry: Dict[str, Any],
        duration_ms: float,
    ) -> Dict[str, Any]:
        """
        Enrich telemetry with metadata.

        Args:
            device_state: Device state.
            telemetry: Raw telemetry data.
            duration_ms: Poll duration.

        Returns:
            Enriched telemetry dictionary.
        """
        return {
            # Metadata
            "_device_id": str(device_state.device_id),
            "_serial_number": device_state.serial_number,
            "_protocol_id": device_state.protocol_id,
            "_device_type": device_state.device_type,
            "_timestamp": datetime.now(timezone.utc).isoformat(),
            "_poll_duration_ms": round(duration_ms, 2),
            # Actual telemetry values
            **telemetry,
        }

    async def collect_batch(
        self,
        device_ids: list,
    ) -> Dict[UUID, Tuple[bool, Optional[Dict[str, Any]], Optional[str]]]:
        """
        Collect telemetry from multiple devices in parallel.

        Args:
            device_ids: List of device IDs to poll.

        Returns:
            Dictionary mapping device ID to (success, data, error).
        """
        tasks = [
            self.collect(device_id)
            for device_id in device_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for device_id, result in zip(device_ids, results):
            if isinstance(result, Exception):
                output[device_id] = (False, None, str(result))
            else:
                output[device_id] = result

        return output


class TelemetryProcessor:
    """
    Processes telemetry data before storage.

    Handles validation, transformation, and normalization
    of telemetry values.
    """

    def __init__(self):
        """Initialize the telemetry processor."""
        pass

    def process(
        self,
        telemetry: Dict[str, Any],
        device_type: str,
    ) -> Dict[str, Any]:
        """
        Process telemetry data.

        Args:
            telemetry: Raw telemetry data.
            device_type: Type of device.

        Returns:
            Processed telemetry data.
        """
        processed = {}

        for key, value in telemetry.items():
            # Skip metadata fields
            if key.startswith("_"):
                processed[key] = value
                continue

            # Validate and normalize value
            normalized = self._normalize_value(key, value, device_type)
            if normalized is not None:
                processed[key] = normalized

        return processed

    def _normalize_value(
        self,
        key: str,
        value: Any,
        device_type: str,
    ) -> Optional[Any]:
        """
        Normalize a telemetry value.

        Args:
            key: Field name.
            value: Raw value.
            device_type: Device type.

        Returns:
            Normalized value or None if invalid.
        """
        if value is None:
            return None

        # Handle numeric values
        if isinstance(value, (int, float)):
            # Check for common invalid values
            if value == 0xFFFF or value == 0xFFFFFFFF:
                return None  # Common "not available" marker

            # Check for reasonable ranges based on key
            if not self._validate_range(key, value, device_type):
                logger.debug(
                    f"Value {value} for {key} out of range for {device_type}"
                )
                return None

            return value

        # Handle string values
        if isinstance(value, str):
            return value.strip() if value else None

        # Handle other types
        return value

    def _validate_range(
        self,
        key: str,
        value: float,
        device_type: str,
    ) -> bool:
        """
        Validate value is in reasonable range.

        Args:
            key: Field name.
            value: Value to validate.
            device_type: Device type.

        Returns:
            True if valid, False otherwise.
        """
        # Define reasonable ranges for common fields
        ranges = {
            # Voltage (V)
            "voltage": (0, 1000),
            "grid_voltage": (0, 500),
            "battery_voltage": (0, 100),
            "pv_voltage": (0, 1000),

            # Current (A)
            "current": (-1000, 1000),
            "grid_current": (-100, 100),
            "battery_current": (-500, 500),

            # Power (W)
            "power": (-100000, 100000),
            "grid_power": (-50000, 50000),
            "pv_power": (0, 100000),
            "load_power": (0, 100000),

            # Temperature (°C)
            "temperature": (-40, 100),

            # SOC (%)
            "soc": (0, 100),
            "battery_soc": (0, 100),

            # Frequency (Hz)
            "frequency": (40, 70),
            "grid_frequency": (40, 70),
        }

        # Check if key matches any range
        key_lower = key.lower()
        for pattern, (min_val, max_val) in ranges.items():
            if pattern in key_lower:
                return min_val <= value <= max_val

        # No specific range defined, accept value
        return True
