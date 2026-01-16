"""
Repository for raw telemetry data in TimescaleDB.

Handles efficient batch inserts and time-series queries optimized for TimescaleDB.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import select, delete, func, and_, text, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.telemetry_model import (
    TelemetryRawModel,
    IngestionBatchesModel,
    MetricDefinitionsModel,
)
from ....domain.entities.telemetry import (
    TelemetryPoint,
    TelemetryBatch,
    TelemetryAggregate,
    MetricDefinition,
    DataQuality,
    DeviceType,
)

logger = logging.getLogger(__name__)


class TelemetryRepository:
    """
    Repository for raw telemetry data.

    Optimized for TimescaleDB hypertables with batch inserts
    and time-range queries.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # Batch Ingestion
    # =========================================================================

    async def ingest_batch(self, batch: TelemetryBatch) -> Tuple[int, int]:
        """
        Ingest a batch of telemetry points.

        Uses PostgreSQL INSERT ... ON CONFLICT for upsert semantics.

        Args:
            batch: TelemetryBatch containing points to ingest.

        Returns:
            Tuple of (inserted_count, failed_count).
        """
        if not batch.points:
            return 0, 0

        # Create batch tracking record
        batch_record = IngestionBatchesModel(
            id=batch.batch_id or UUID(int=0),
            source_type=batch.source_type,
            source_identifier=batch.source_identifier,
            device_count=batch.device_count,
            record_count=batch.record_count,
            status="processing",
        )
        self._session.add(batch_record)
        await self._session.flush()

        inserted = 0
        failed = 0
        start_time = datetime.now(timezone.utc)

        try:
            # Prepare values for bulk insert
            values = []
            for point in batch.points:
                values.append({
                    "time": point.time,
                    "device_id": point.device_id,
                    "site_id": point.site_id,
                    "metric_name": point.metric_name,
                    "metric_value": point.metric_value,
                    "metric_value_str": point.metric_value_str,
                    "quality": point.quality.value if isinstance(point.quality, DataQuality) else point.quality,
                    "unit": point.unit,
                    "source": point.source,
                    "tags": point.tags,
                    "raw_value": point.raw_value,
                    "received_at": point.received_at,
                    "processed": point.processed,
                })

            # Use PostgreSQL upsert for handling duplicates
            stmt = pg_insert(TelemetryRawModel).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["time", "device_id", "metric_name"],
                set_={
                    "metric_value": stmt.excluded.metric_value,
                    "metric_value_str": stmt.excluded.metric_value_str,
                    "quality": stmt.excluded.quality,
                    "received_at": stmt.excluded.received_at,
                }
            )

            await self._session.execute(stmt)
            inserted = len(values)

            # Update batch record
            elapsed_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            batch_record.status = "completed"
            batch_record.completed_at = datetime.now(timezone.utc)
            batch_record.records_inserted = inserted
            batch_record.records_failed = failed
            batch_record.processing_time_ms = elapsed_ms

            await self._session.commit()

            logger.info(
                f"Ingested {inserted} telemetry points in {elapsed_ms}ms "
                f"(batch: {batch_record.id})"
            )

        except Exception as e:
            logger.error(f"Batch ingestion failed: {e}")
            batch_record.status = "failed"
            batch_record.completed_at = datetime.now(timezone.utc)
            batch_record.errors = {"error": str(e)}
            failed = len(batch.points)
            await self._session.commit()
            raise

        return inserted, failed

    async def ingest_points(self, points: List[TelemetryPoint]) -> int:
        """
        Ingest individual telemetry points.

        Args:
            points: List of TelemetryPoint to ingest.

        Returns:
            Number of points ingested.
        """
        if not points:
            return 0

        values = []
        for point in points:
            values.append({
                "time": point.time,
                "device_id": point.device_id,
                "site_id": point.site_id,
                "metric_name": point.metric_name,
                "metric_value": point.metric_value,
                "metric_value_str": point.metric_value_str,
                "quality": point.quality.value if isinstance(point.quality, DataQuality) else point.quality,
                "unit": point.unit,
                "source": point.source,
                "tags": point.tags,
                "raw_value": point.raw_value,
                "received_at": point.received_at,
                "processed": point.processed,
            })

        stmt = pg_insert(TelemetryRawModel).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["time", "device_id", "metric_name"],
            set_={
                "metric_value": stmt.excluded.metric_value,
                "quality": stmt.excluded.quality,
                "received_at": stmt.excluded.received_at,
            }
        )

        await self._session.execute(stmt)
        return len(values)

    # =========================================================================
    # Query Methods
    # =========================================================================

    async def get_latest_readings(
        self,
        device_id: UUID,
        metric_names: Optional[List[str]] = None,
    ) -> Dict[str, TelemetryPoint]:
        """
        Get the latest reading for each metric from a device.

        Args:
            device_id: Device ID.
            metric_names: Optional list of specific metrics to retrieve.

        Returns:
            Dict mapping metric_name to latest TelemetryPoint.
        """
        # Use TimescaleDB last() function for efficiency
        if metric_names:
            conditions = and_(
                TelemetryRawModel.device_id == device_id,
                TelemetryRawModel.metric_name.in_(metric_names)
            )
        else:
            conditions = TelemetryRawModel.device_id == device_id

        # Subquery to get max time per metric
        subq = (
            select(
                TelemetryRawModel.metric_name,
                func.max(TelemetryRawModel.time).label("max_time")
            )
            .where(conditions)
            .group_by(TelemetryRawModel.metric_name)
            .subquery()
        )

        query = (
            select(TelemetryRawModel)
            .join(
                subq,
                and_(
                    TelemetryRawModel.metric_name == subq.c.metric_name,
                    TelemetryRawModel.time == subq.c.max_time,
                    TelemetryRawModel.device_id == device_id
                )
            )
        )

        result = await self._session.execute(query)
        rows = result.scalars().all()

        return {
            row.metric_name: self._model_to_point(row)
            for row in rows
        }

    async def get_time_range(
        self,
        device_id: UUID,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        limit: int = 10000,
    ) -> List[TelemetryPoint]:
        """
        Get telemetry points for a device within a time range.

        Args:
            device_id: Device ID.
            start_time: Start of time range.
            end_time: End of time range.
            metric_names: Optional filter for specific metrics.
            limit: Maximum number of points to return.

        Returns:
            List of TelemetryPoint ordered by time.
        """
        conditions = [
            TelemetryRawModel.device_id == device_id,
            TelemetryRawModel.time >= start_time,
            TelemetryRawModel.time < end_time,
        ]

        if metric_names:
            conditions.append(TelemetryRawModel.metric_name.in_(metric_names))

        query = (
            select(TelemetryRawModel)
            .where(and_(*conditions))
            .order_by(TelemetryRawModel.time)
            .limit(limit)
        )

        result = await self._session.execute(query)
        rows = result.scalars().all()

        return [self._model_to_point(row) for row in rows]

    async def get_site_time_range(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        device_ids: Optional[List[UUID]] = None,
        limit: int = 50000,
    ) -> List[TelemetryPoint]:
        """
        Get telemetry points for all devices at a site within a time range.

        Args:
            site_id: Site ID.
            start_time: Start of time range.
            end_time: End of time range.
            metric_names: Optional filter for specific metrics.
            device_ids: Optional filter for specific devices.
            limit: Maximum number of points to return.

        Returns:
            List of TelemetryPoint ordered by time.
        """
        conditions = [
            TelemetryRawModel.site_id == site_id,
            TelemetryRawModel.time >= start_time,
            TelemetryRawModel.time < end_time,
        ]

        if metric_names:
            conditions.append(TelemetryRawModel.metric_name.in_(metric_names))

        if device_ids:
            conditions.append(TelemetryRawModel.device_id.in_(device_ids))

        query = (
            select(TelemetryRawModel)
            .where(and_(*conditions))
            .order_by(TelemetryRawModel.time)
            .limit(limit)
        )

        result = await self._session.execute(query)
        rows = result.scalars().all()

        return [self._model_to_point(row) for row in rows]

    # =========================================================================
    # Aggregation Methods (using TimescaleDB functions)
    # =========================================================================

    async def get_time_bucket_aggregates(
        self,
        device_id: UUID,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "1 hour",
    ) -> List[TelemetryAggregate]:
        """
        Get time-bucketed aggregates for a metric.

        Uses TimescaleDB time_bucket function for efficient aggregation.

        Args:
            device_id: Device ID.
            metric_name: Metric to aggregate.
            start_time: Start of time range.
            end_time: End of time range.
            bucket_interval: PostgreSQL interval string (e.g., '1 hour', '5 minutes').

        Returns:
            List of TelemetryAggregate for each bucket.
        """
        # Get site_id for the device (needed for aggregate)
        device_query = select(TelemetryRawModel.site_id).where(
            TelemetryRawModel.device_id == device_id
        ).limit(1)
        device_result = await self._session.execute(device_query)
        site_id = device_result.scalar()

        if not site_id:
            return []

        # Use TimescaleDB time_bucket for aggregation
        query = text("""
            SELECT
                time_bucket(:interval, time) AS bucket,
                AVG(metric_value) AS avg_value,
                MIN(metric_value) AS min_value,
                MAX(metric_value) AS max_value,
                first(metric_value, time) AS first_value,
                last(metric_value, time) AS last_value,
                COUNT(*) AS sample_count,
                COUNT(*) FILTER (WHERE quality = 'good') AS good_count
            FROM telemetry_raw
            WHERE device_id = :device_id
              AND metric_name = :metric_name
              AND time >= :start_time
              AND time < :end_time
            GROUP BY bucket
            ORDER BY bucket
        """)

        result = await self._session.execute(
            query,
            {
                "interval": bucket_interval,
                "device_id": str(device_id),
                "metric_name": metric_name,
                "start_time": start_time,
                "end_time": end_time,
            }
        )

        aggregates = []
        for row in result:
            aggregates.append(TelemetryAggregate(
                bucket=row.bucket,
                device_id=device_id,
                site_id=site_id,
                metric_name=metric_name,
                avg_value=row.avg_value,
                min_value=row.min_value,
                max_value=row.max_value,
                first_value=row.first_value,
                last_value=row.last_value,
                delta_value=(row.last_value - row.first_value) if row.first_value and row.last_value else None,
                sample_count=row.sample_count,
                good_count=row.good_count,
            ))

        return aggregates

    async def get_site_power_aggregate(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "5 minutes",
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated power readings for a site.

        Args:
            site_id: Site ID.
            start_time: Start of time range.
            end_time: End of time range.
            bucket_interval: PostgreSQL interval string.

        Returns:
            List of dicts with bucket and aggregated power values.
        """
        query = text("""
            SELECT
                time_bucket(:interval, time) AS bucket,
                SUM(metric_value) AS total_power,
                COUNT(DISTINCT device_id) AS device_count
            FROM telemetry_raw
            WHERE site_id = :site_id
              AND metric_name = 'power_ac'
              AND time >= :start_time
              AND time < :end_time
            GROUP BY bucket
            ORDER BY bucket
        """)

        result = await self._session.execute(
            query,
            {
                "interval": bucket_interval,
                "site_id": str(site_id),
                "start_time": start_time,
                "end_time": end_time,
            }
        )

        return [
            {
                "bucket": row.bucket,
                "total_power_kw": row.total_power / 1000 if row.total_power else 0,
                "device_count": row.device_count,
            }
            for row in result
        ]

    # =========================================================================
    # Data Management
    # =========================================================================

    async def delete_old_data(
        self,
        older_than: datetime,
        device_id: Optional[UUID] = None,
    ) -> int:
        """
        Delete telemetry data older than a specified time.

        Args:
            older_than: Delete data before this time.
            device_id: Optional device to limit deletion to.

        Returns:
            Number of rows deleted.
        """
        conditions = [TelemetryRawModel.time < older_than]

        if device_id:
            conditions.append(TelemetryRawModel.device_id == device_id)

        stmt = delete(TelemetryRawModel).where(and_(*conditions))
        result = await self._session.execute(stmt)

        deleted = result.rowcount
        logger.info(f"Deleted {deleted} telemetry records older than {older_than}")

        return deleted

    async def mark_as_processed(
        self,
        device_id: UUID,
        before_time: datetime,
    ) -> int:
        """
        Mark telemetry records as processed (for aggregation tracking).

        Args:
            device_id: Device ID.
            before_time: Mark records before this time.

        Returns:
            Number of records updated.
        """
        query = text("""
            UPDATE telemetry_raw
            SET processed = TRUE
            WHERE device_id = :device_id
              AND time < :before_time
              AND processed = FALSE
        """)

        result = await self._session.execute(
            query,
            {"device_id": str(device_id), "before_time": before_time}
        )

        return result.rowcount

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_device_stats(self, device_id: UUID) -> Dict[str, Any]:
        """
        Get statistics for a device's telemetry data.

        Args:
            device_id: Device ID.

        Returns:
            Dict with statistics (count, time range, metrics).
        """
        query = select(
            func.count().label("total_count"),
            func.min(TelemetryRawModel.time).label("first_time"),
            func.max(TelemetryRawModel.time).label("last_time"),
            func.count(func.distinct(TelemetryRawModel.metric_name)).label("metric_count"),
        ).where(TelemetryRawModel.device_id == device_id)

        result = await self._session.execute(query)
        row = result.one()

        return {
            "total_records": row.total_count,
            "first_reading": row.first_time,
            "last_reading": row.last_time,
            "distinct_metrics": row.metric_count,
        }

    async def get_ingestion_stats(
        self,
        since: datetime,
    ) -> Dict[str, Any]:
        """
        Get ingestion statistics for monitoring.

        Args:
            since: Get stats since this time.

        Returns:
            Dict with ingestion statistics.
        """
        query = select(
            func.count().label("batch_count"),
            func.sum(IngestionBatchesModel.records_inserted).label("total_inserted"),
            func.sum(IngestionBatchesModel.records_failed).label("total_failed"),
            func.avg(IngestionBatchesModel.processing_time_ms).label("avg_time_ms"),
        ).where(
            and_(
                IngestionBatchesModel.started_at >= since,
                IngestionBatchesModel.status == "completed",
            )
        )

        result = await self._session.execute(query)
        row = result.one()

        return {
            "batch_count": row.batch_count or 0,
            "total_inserted": row.total_inserted or 0,
            "total_failed": row.total_failed or 0,
            "avg_processing_time_ms": float(row.avg_time_ms) if row.avg_time_ms else 0,
        }

    # =========================================================================
    # Metric Definitions
    # =========================================================================

    async def get_metric_definitions(
        self,
        device_type: Optional[DeviceType] = None,
    ) -> List[MetricDefinition]:
        """
        Get metric definitions, optionally filtered by device type.

        Args:
            device_type: Optional device type to filter by.

        Returns:
            List of MetricDefinition.
        """
        query = select(MetricDefinitionsModel)

        if device_type:
            query = query.where(
                MetricDefinitionsModel.device_types.contains([device_type.value])
            )

        result = await self._session.execute(query)
        rows = result.scalars().all()

        return [self._model_to_metric_def(row) for row in rows]

    async def upsert_metric_definition(
        self,
        metric_def: MetricDefinition,
    ) -> None:
        """
        Insert or update a metric definition.

        Args:
            metric_def: MetricDefinition to upsert.
        """
        stmt = pg_insert(MetricDefinitionsModel).values(
            metric_name=metric_def.metric_name,
            display_name=metric_def.display_name,
            description=metric_def.description,
            unit=metric_def.unit,
            data_type=metric_def.data_type,
            device_types=[dt.value for dt in metric_def.device_types],
            min_value=metric_def.min_value,
            max_value=metric_def.max_value,
            aggregation_method=metric_def.aggregation_method,
            is_cumulative=metric_def.is_cumulative,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["metric_name"],
            set_={
                "display_name": stmt.excluded.display_name,
                "description": stmt.excluded.description,
                "unit": stmt.excluded.unit,
                "data_type": stmt.excluded.data_type,
                "device_types": stmt.excluded.device_types,
                "min_value": stmt.excluded.min_value,
                "max_value": stmt.excluded.max_value,
                "aggregation_method": stmt.excluded.aggregation_method,
                "is_cumulative": stmt.excluded.is_cumulative,
            }
        )

        await self._session.execute(stmt)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _model_to_point(self, model: TelemetryRawModel) -> TelemetryPoint:
        """Convert SQLAlchemy model to domain entity."""
        return TelemetryPoint(
            time=model.time,
            device_id=model.device_id,
            site_id=model.site_id,
            metric_name=model.metric_name,
            metric_value=model.metric_value,
            metric_value_str=model.metric_value_str,
            quality=DataQuality(model.quality) if model.quality else DataQuality.GOOD,
            unit=model.unit,
            source=model.source,
            tags=model.tags,
            raw_value=model.raw_value,
            received_at=model.received_at,
            processed=model.processed,
        )

    def _model_to_metric_def(self, model: MetricDefinitionsModel) -> MetricDefinition:
        """Convert metric definition model to domain entity."""
        return MetricDefinition(
            metric_name=model.metric_name,
            display_name=model.display_name,
            unit=model.unit,
            data_type=model.data_type,
            device_types=[DeviceType(dt) for dt in model.device_types],
            description=model.description,
            min_value=model.min_value,
            max_value=model.max_value,
            aggregation_method=model.aggregation_method,
            is_cumulative=model.is_cumulative,
        )
