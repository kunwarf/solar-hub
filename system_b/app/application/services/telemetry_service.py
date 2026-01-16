"""
Telemetry Service for System B.

Handles telemetry ingestion, validation, and retrieval operations.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4

from ...domain.entities.telemetry import (
    TelemetryPoint,
    TelemetryBatch,
    TelemetryAggregate,
    MetricDefinition,
    DataQuality,
    DeviceType,
)
from ...domain.entities.event import DeviceEvent, EventType, EventSeverity
from ...infrastructure.database.repositories import TelemetryRepository, EventRepository

logger = logging.getLogger(__name__)


class TelemetryService:
    """
    Application service for telemetry operations.

    Coordinates telemetry ingestion, validation, and queries.
    """

    def __init__(
        self,
        telemetry_repo: TelemetryRepository,
        event_repo: Optional[EventRepository] = None,
    ):
        self._telemetry_repo = telemetry_repo
        self._event_repo = event_repo
        self._metric_definitions: Dict[str, MetricDefinition] = {}

    # =========================================================================
    # Ingestion
    # =========================================================================

    async def ingest_telemetry(
        self,
        device_id: UUID,
        site_id: UUID,
        metrics: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        source: str = "device",
        validate: bool = True,
    ) -> int:
        """
        Ingest telemetry data from a device.

        Args:
            device_id: Device UUID.
            site_id: Site UUID.
            metrics: Dict of metric_name: value pairs.
            timestamp: Reading timestamp (defaults to now).
            source: Data source identifier.
            validate: Whether to validate against metric definitions.

        Returns:
            Number of metrics ingested.
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        points: List[TelemetryPoint] = []

        for metric_name, value in metrics.items():
            # Determine quality and value type
            quality = DataQuality.GOOD
            metric_value = None
            metric_value_str = None

            if isinstance(value, (int, float)):
                metric_value = float(value)

                # Validate if enabled
                if validate and metric_name in self._metric_definitions:
                    metric_def = self._metric_definitions[metric_name]
                    if not metric_def.validate_value(metric_value):
                        quality = DataQuality.SUSPECT
                        logger.warning(
                            f"Suspect value for {metric_name}: {metric_value} "
                            f"(expected {metric_def.min_value}-{metric_def.max_value})"
                        )
            elif isinstance(value, str):
                metric_value_str = value
            elif value is None:
                quality = DataQuality.MISSING
                continue
            else:
                # Convert to string for non-standard types
                metric_value_str = str(value)

            # Get unit from metric definition
            unit = None
            if metric_name in self._metric_definitions:
                unit = self._metric_definitions[metric_name].unit

            point = TelemetryPoint(
                time=timestamp,
                device_id=device_id,
                site_id=site_id,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_value_str=metric_value_str,
                quality=quality,
                unit=unit,
                source=source,
            )
            points.append(point)

        if points:
            return await self._telemetry_repo.ingest_points(points)

        return 0

    async def ingest_batch(
        self,
        batch: TelemetryBatch,
        validate: bool = True,
    ) -> Tuple[int, int]:
        """
        Ingest a batch of telemetry points.

        Args:
            batch: TelemetryBatch to ingest.
            validate: Whether to validate against metric definitions.

        Returns:
            Tuple of (inserted_count, failed_count).
        """
        # Assign batch ID if not set
        if not batch.batch_id:
            batch.batch_id = uuid4()

        # Validate points if enabled
        if validate:
            for point in batch.points:
                if point.metric_name in self._metric_definitions:
                    metric_def = self._metric_definitions[point.metric_name]
                    if point.metric_value is not None:
                        if not metric_def.validate_value(point.metric_value):
                            point.quality = DataQuality.SUSPECT

        return await self._telemetry_repo.ingest_batch(batch)

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def get_latest_telemetry(
        self,
        device_id: UUID,
        metric_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get latest telemetry readings for a device.

        Args:
            device_id: Device UUID.
            metric_names: Optional list of specific metrics.

        Returns:
            Dict with metric values and metadata.
        """
        points = await self._telemetry_repo.get_latest_readings(device_id, metric_names)

        result = {}
        for metric_name, point in points.items():
            result[metric_name] = {
                "value": point.metric_value if point.metric_value is not None else point.metric_value_str,
                "time": point.time.isoformat(),
                "quality": point.quality.value,
                "unit": point.unit,
            }

        return result

    async def get_device_telemetry(
        self,
        device_id: UUID,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        limit: int = 10000,
    ) -> List[Dict[str, Any]]:
        """
        Get telemetry history for a device.

        Args:
            device_id: Device UUID.
            start_time: Start of time range.
            end_time: End of time range.
            metric_names: Optional filter for specific metrics.
            limit: Maximum points to return.

        Returns:
            List of telemetry points as dicts.
        """
        points = await self._telemetry_repo.get_time_range(
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            metric_names=metric_names,
            limit=limit,
        )

        return [
            {
                "time": p.time.isoformat(),
                "metric_name": p.metric_name,
                "value": p.metric_value if p.metric_value is not None else p.metric_value_str,
                "quality": p.quality.value,
                "unit": p.unit,
            }
            for p in points
        ]

    async def get_site_telemetry(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        device_ids: Optional[List[UUID]] = None,
        limit: int = 50000,
    ) -> List[Dict[str, Any]]:
        """
        Get telemetry for all devices at a site.

        Args:
            site_id: Site UUID.
            start_time: Start of time range.
            end_time: End of time range.
            metric_names: Optional filter for specific metrics.
            device_ids: Optional filter for specific devices.
            limit: Maximum points to return.

        Returns:
            List of telemetry points as dicts.
        """
        points = await self._telemetry_repo.get_site_time_range(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            metric_names=metric_names,
            device_ids=device_ids,
            limit=limit,
        )

        return [
            {
                "time": p.time.isoformat(),
                "device_id": str(p.device_id),
                "metric_name": p.metric_name,
                "value": p.metric_value if p.metric_value is not None else p.metric_value_str,
                "quality": p.quality.value,
                "unit": p.unit,
            }
            for p in points
        ]

    # =========================================================================
    # Aggregation Operations
    # =========================================================================

    async def get_aggregated_telemetry(
        self,
        device_id: UUID,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "1 hour",
    ) -> List[Dict[str, Any]]:
        """
        Get time-bucketed aggregates for a metric.

        Args:
            device_id: Device UUID.
            metric_name: Metric to aggregate.
            start_time: Start of time range.
            end_time: End of time range.
            bucket_interval: PostgreSQL interval string.

        Returns:
            List of aggregate dicts with stats.
        """
        aggregates = await self._telemetry_repo.get_time_bucket_aggregates(
            device_id=device_id,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            bucket_interval=bucket_interval,
        )

        return [
            {
                "bucket": agg.bucket.isoformat(),
                "avg": agg.avg_value,
                "min": agg.min_value,
                "max": agg.max_value,
                "first": agg.first_value,
                "last": agg.last_value,
                "delta": agg.delta_value,
                "sample_count": agg.sample_count,
                "quality_percent": agg.data_quality_percent,
            }
            for agg in aggregates
        ]

    async def get_site_power_chart(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "5 minutes",
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated power data for chart display.

        Args:
            site_id: Site UUID.
            start_time: Start of time range.
            end_time: End of time range.
            bucket_interval: Chart resolution.

        Returns:
            List of dicts with bucket and power values.
        """
        return await self._telemetry_repo.get_site_power_aggregate(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            bucket_interval=bucket_interval,
        )

    # =========================================================================
    # Metric Definitions
    # =========================================================================

    async def load_metric_definitions(
        self,
        device_type: Optional[DeviceType] = None,
    ) -> None:
        """
        Load metric definitions from database.

        Args:
            device_type: Optional filter by device type.
        """
        definitions = await self._telemetry_repo.get_metric_definitions(device_type)

        for metric_def in definitions:
            self._metric_definitions[metric_def.metric_name] = metric_def

        logger.info(f"Loaded {len(definitions)} metric definitions")

    async def register_metric_definition(
        self,
        metric_def: MetricDefinition,
    ) -> None:
        """
        Register a new metric definition.

        Args:
            metric_def: MetricDefinition to register.
        """
        await self._telemetry_repo.upsert_metric_definition(metric_def)
        self._metric_definitions[metric_def.metric_name] = metric_def

    def get_metric_definition(
        self,
        metric_name: str,
    ) -> Optional[MetricDefinition]:
        """
        Get a metric definition by name.

        Args:
            metric_name: Metric name.

        Returns:
            MetricDefinition if found, None otherwise.
        """
        return self._metric_definitions.get(metric_name)

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_device_stats(self, device_id: UUID) -> Dict[str, Any]:
        """
        Get telemetry statistics for a device.

        Args:
            device_id: Device UUID.

        Returns:
            Dict with device telemetry statistics.
        """
        return await self._telemetry_repo.get_device_stats(device_id)

    async def get_ingestion_stats(
        self,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get ingestion statistics for monitoring.

        Args:
            hours: Lookback period.

        Returns:
            Dict with ingestion statistics.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return await self._telemetry_repo.get_ingestion_stats(since)

    # =========================================================================
    # Data Quality
    # =========================================================================

    async def check_data_gaps(
        self,
        device_id: UUID,
        metric_name: str,
        expected_interval_seconds: int,
        hours: int = 24,
    ) -> List[Dict[str, Any]]:
        """
        Check for gaps in telemetry data.

        Args:
            device_id: Device UUID.
            metric_name: Metric to check.
            expected_interval_seconds: Expected reading interval.
            hours: Lookback period.

        Returns:
            List of detected gaps with start/end times.
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        points = await self._telemetry_repo.get_time_range(
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            metric_names=[metric_name],
            limit=50000,
        )

        if len(points) < 2:
            return []

        gaps = []
        threshold = timedelta(seconds=expected_interval_seconds * 2)

        for i in range(1, len(points)):
            gap = points[i].time - points[i - 1].time
            if gap > threshold:
                gaps.append({
                    "start": points[i - 1].time.isoformat(),
                    "end": points[i].time.isoformat(),
                    "duration_seconds": gap.total_seconds(),
                    "missing_readings": int(gap.total_seconds() / expected_interval_seconds) - 1,
                })

        return gaps

    # =========================================================================
    # Maintenance
    # =========================================================================

    async def cleanup_old_data(
        self,
        retention_days: int = 90,
        device_id: Optional[UUID] = None,
    ) -> int:
        """
        Delete telemetry data older than retention period.

        Args:
            retention_days: Days of data to keep.
            device_id: Optional device filter.

        Returns:
            Number of records deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        return await self._telemetry_repo.delete_old_data(cutoff, device_id)
