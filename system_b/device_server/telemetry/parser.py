"""
Base telemetry parser classes.

Defines the interface for parsing device telemetry into normalized metrics.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID


@dataclass
class TelemetryMetric:
    """
    A single normalized telemetry metric.

    Represents one data point to be stored in telemetry_raw table.
    """
    time: datetime
    device_id: UUID
    site_id: UUID
    metric_name: str
    metric_value: float
    metric_value_str: Optional[str] = None
    quality: str = 'good'
    unit: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None

    def to_db_tuple(self) -> tuple:
        """Convert to tuple for database insert."""
        return (
            self.time,
            self.device_id,
            self.metric_name,
            self.site_id,
            self.metric_value,
            self.metric_value_str,
            self.quality,
            self.unit,
            self.source,
            self.tags,
        )


class TelemetryParser(ABC):
    """
    Abstract base class for telemetry parsers.

    Each device type should implement its own parser.
    """

    @abstractmethod
    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime
    ) -> List[TelemetryMetric]:
        """
        Parse device telemetry JSON into normalized metrics.

        Args:
            telemetry_data: Raw telemetry JSON from device.
            device_id: Device UUID.
            site_id: Site UUID.
            timestamp: Timestamp of the telemetry reading.

        Returns:
            List of TelemetryMetric objects ready for database insert.
        """
        pass

    def _safe_extract_float(
        self,
        data: Dict[str, Any],
        *keys: str,
        default: float = 0.0
    ) -> Optional[float]:
        """
        Safely extract a float value from nested dictionary.

        Args:
            data: Dictionary to extract from.
            *keys: Sequence of keys to traverse (e.g., 'power', 'pv_total_w').
            default: Default value if extraction fails.

        Returns:
            Extracted float value or default.
        """
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default

        try:
            return float(current)
        except (ValueError, TypeError):
            return default

    def _safe_extract_str(
        self,
        data: Dict[str, Any],
        *keys: str,
        default: str = ''
    ) -> str:
        """Safely extract a string value from nested dictionary."""
        current = data
        for key in keys:
            if not isinstance(current, dict):
                return default
            current = current.get(key)
            if current is None:
                return default
        return str(current)
