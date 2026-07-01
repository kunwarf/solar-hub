"""
Telemetry API endpoints for System B.

Handles telemetry ingestion and retrieval.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db_session, get_telemetry_service
from ..schemas import (
    TelemetryBatchCreate,
    TelemetryIngestRequest,
    TelemetryLatestResponse,
    TelemetryAggregateResponse,
    TelemetryStatsResponse,
    IngestResponse,
    EnergyChartDataPoint,
    EnergyChartResponse,
)
from ...application.services import TelemetryService
from ...domain.entities.telemetry import TelemetryBatch, TelemetryPoint, DataQuality
from ...infrastructure.database.repositories import TelemetryRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest telemetry data",
    description="Ingest telemetry readings from one or more devices.",
)
async def ingest_telemetry(
    request: TelemetryIngestRequest,
    session: AsyncSession = Depends(get_db_session),
) -> IngestResponse:
    """
    Ingest telemetry data from devices.

    Accepts batch telemetry from multiple devices in a single request.
    """
    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    total_inserted = 0
    total_failed = 0

    for batch_data in request.points:
        # Log received telemetry data
        metric_count = len(batch_data.metrics)
        metric_names = list(batch_data.metrics.keys())[:10]  # Log first 10 metric names
        metric_summary = ", ".join(metric_names)
        if metric_count > 10:
            metric_summary += f" ... (+{metric_count - 10} more)"
        
        logger.info(
            f"Received telemetry from device {batch_data.device_id} "
            f"(site: {batch_data.site_id}): "
            f"{metric_count} metrics, timestamp: {batch_data.timestamp or 'now'}, "
            f"source: {batch_data.source}, metrics: [{metric_summary}]"
        )
        
        try:
            count = await service.ingest_telemetry(
                device_id=batch_data.device_id,
                site_id=batch_data.site_id,
                metrics=batch_data.metrics,
                timestamp=batch_data.timestamp,
                source=batch_data.source,
            )
            logger.info(
                f"Successfully ingested {count} telemetry points for device {batch_data.device_id}"
            )
            total_inserted += count
        except Exception as e:
            logger.error(f"Failed to ingest telemetry for device {batch_data.device_id}: {e}")
            total_failed += len(batch_data.metrics)

    return IngestResponse(
        success=total_failed == 0,
        inserted=total_inserted,
        failed=total_failed,
        message=f"Ingested {total_inserted} metrics" if total_failed == 0 else f"Partial success: {total_inserted} ingested, {total_failed} failed",
    )


@router.post(
    "/ingest/{device_id}",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest device telemetry",
    description="Ingest telemetry readings for a specific device.",
)
async def ingest_device_telemetry(
    device_id: UUID,
    site_id: UUID,
    metrics: dict,
    timestamp: Optional[datetime] = None,
    source: str = "device",
    session: AsyncSession = Depends(get_db_session),
) -> IngestResponse:
    """
    Ingest telemetry for a single device.
    """
    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    # Log received telemetry data
    metric_count = len(metrics)
    metric_names = list(metrics.keys())[:10]  # Log first 10 metric names
    metric_summary = ", ".join(metric_names)
    if metric_count > 10:
        metric_summary += f" ... (+{metric_count - 10} more)"
    
    logger.info(
        f"Received telemetry from device {device_id} "
        f"(site: {site_id}): "
        f"{metric_count} metrics, timestamp: {timestamp or 'now'}, "
        f"source: {source}, metrics: [{metric_summary}]"
    )

    try:
        count = await service.ingest_telemetry(
            device_id=device_id,
            site_id=site_id,
            metrics=metrics,
            timestamp=timestamp,
            source=source,
        )
        
        logger.info(
            f"Successfully ingested {count} telemetry points for device {device_id}"
        )

        return IngestResponse(
            success=True,
            inserted=count,
            failed=0,
        )
    except Exception as e:
        logger.error(f"Failed to ingest telemetry for device {device_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.get(
    "/latest/{device_id}",
    response_model=TelemetryLatestResponse,
    summary="Get latest telemetry",
    description="Get the latest telemetry readings for a device.",
)
async def get_latest_telemetry(
    device_id: UUID,
    metric_names: Optional[List[str]] = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> TelemetryLatestResponse:
    """
    Get latest readings for a device.
    """
    logger.info(f"[TELEMETRY_LATEST] Getting latest telemetry for device {device_id}, metrics: {metric_names}")

    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    readings = await service.get_latest_telemetry(device_id, metric_names)

    logger.info(f"[TELEMETRY_LATEST] Retrieved {len(readings)} readings for device {device_id}")

    return TelemetryLatestResponse(
        device_id=device_id,
        readings=readings,
    )


@router.get(
    "/history/{device_id}",
    summary="Get telemetry history",
    description="Get telemetry history for a device within a time range.",
)
async def get_telemetry_history(
    device_id: UUID,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    metric_names: Optional[List[str]] = Query(default=None),
    limit: int = Query(default=10000, le=100000),
    session: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """
    Get telemetry history for a device.
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    return await service.get_device_telemetry(
        device_id=device_id,
        start_time=start_time,
        end_time=end_time,
        metric_names=metric_names,
        limit=limit,
    )


@router.get(
    "/site/{site_id}",
    summary="Get site telemetry",
    description="Get telemetry for all devices at a site.",
)
async def get_site_telemetry(
    site_id: UUID,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    metric_names: Optional[List[str]] = Query(default=None),
    device_ids: Optional[List[UUID]] = Query(default=None),
    limit: int = Query(default=50000, le=100000),
    session: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """
    Get telemetry for a site.
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    return await service.get_site_telemetry(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        metric_names=metric_names,
        device_ids=device_ids,
        limit=limit,
    )


@router.get(
    "/aggregate/{device_id}/{metric_name}",
    response_model=List[TelemetryAggregateResponse],
    summary="Get aggregated telemetry",
    description="Get time-bucketed aggregates for a metric.",
)
async def get_aggregated_telemetry(
    device_id: UUID,
    metric_name: str,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    bucket_interval: str = Query(default="1 hour"),
    session: AsyncSession = Depends(get_db_session),
) -> List[TelemetryAggregateResponse]:
    """
    Get aggregated telemetry data.
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    # TEMP DEBUG: this endpoint has been 500'ing universally; the global
    # exception handler masks the real error in production (debug=False).
    # Catch here and surface the class name + message + one-frame traceback
    # so we can see what's actually breaking. REMOVE after diagnosing.
    import traceback
    try:
        aggregates = await service.get_aggregated_telemetry(
            device_id=device_id,
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            bucket_interval=bucket_interval,
        )
    except Exception as exc:
        tb = traceback.format_exc().splitlines()
        raise HTTPException(
            status_code=500,
            detail={
                "debug_probe": True,
                "exc_type": type(exc).__name__,
                "exc_msg": str(exc),
                "traceback_tail": tb[-8:],
                "params": {
                    "device_id": str(device_id),
                    "metric_name": metric_name,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "bucket_interval": bucket_interval,
                },
            },
        )

    try:
        return [
            TelemetryAggregateResponse(
                bucket=datetime.fromisoformat(a["bucket"]),
                avg=a["avg"],
                min=a["min"],
                max=a["max"],
                first=a["first"],
                last=a["last"],
                delta=a["delta"],
                sample_count=a["sample_count"],
                quality_percent=a["quality_percent"],
            )
            for a in aggregates
        ]
    except Exception as exc:
        tb = traceback.format_exc().splitlines()
        raise HTTPException(
            status_code=500,
            detail={
                "debug_probe": True,
                "stage": "response_build",
                "exc_type": type(exc).__name__,
                "exc_msg": str(exc),
                "traceback_tail": tb[-8:],
                "row_count": len(aggregates),
                "first_row": aggregates[0] if aggregates else None,
            },
        )


@router.get(
    "/power-chart/{site_id}",
    summary="Get power chart data",
    description="Get aggregated power data for chart display.",
)
async def get_power_chart(
    site_id: UUID,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    bucket_interval: str = Query(default="5 minutes"),
    session: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """
    Get power chart data for a site.
    """
    if end_time is None:
        end_time = datetime.now(timezone.utc)

    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    return await service.get_site_power_chart(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        bucket_interval=bucket_interval,
    )


@router.get(
    "/stats/{device_id}",
    response_model=TelemetryStatsResponse,
    summary="Get telemetry statistics",
    description="Get telemetry statistics for a device.",
)
async def get_telemetry_stats(
    device_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> TelemetryStatsResponse:
    """
    Get statistics for a device's telemetry data.
    """
    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    stats = await service.get_device_stats(device_id)

    return TelemetryStatsResponse(
        total_records=stats["total_records"],
        first_reading=stats["first_reading"],
        last_reading=stats["last_reading"],
        distinct_metrics=stats["distinct_metrics"],
    )


@router.get(
    "/energy-chart/{site_id}",
    response_model=EnergyChartResponse,
    summary="Get energy chart data",
    description="Get comprehensive aggregated energy data for a site with calculated metrics.",
)
async def get_energy_chart(
    site_id: UUID,
    period: str = Query(default="day", regex="^(day|week|month|custom)$"),
    start_time: Optional[datetime] = Query(default=None, description="Custom start time (requires period=custom)"),
    end_time: Optional[datetime] = Query(default=None, description="Custom end time (requires period=custom)"),
    bucket_interval: Optional[str] = Query(default=None, description="Custom bucket interval like '1 hour', '1 day' (requires period=custom)"),
    session: AsyncSession = Depends(get_db_session),
) -> EnergyChartResponse:
    """
    Get comprehensive energy chart data for a site.

    Returns time-bucketed aggregated data including:
    - PV generation (kWh)
    - Load consumption (kWh)
    - Grid import/export (kWh)
    - Battery charge/discharge (kWh)
    - Inverter efficiency (%)
    - Self-sufficiency (%)
    - Temperature (°C)

    Period determines the time range and bucket interval:
    - day: Last 24 hours, hourly buckets
    - week: Last 7 days, daily buckets
    - month: Last 30 days, daily buckets
    - custom: Use provided start_time, end_time, and bucket_interval
    """
    # Determine time range and bucket interval
    if period == "custom":
        # Custom period requires start_time, end_time, and bucket_interval
        if not start_time or not end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time and end_time are required for period=custom"
            )
        if not bucket_interval:
            bucket_interval = "auto"  # Let repository choose best table

        # Ensure times are timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
    else:
        # Preset periods
        end_time = datetime.now(timezone.utc)
        if period == "day":
            start_time = end_time - timedelta(hours=24)
            bucket_interval = "auto"  # Let repository choose best table
        elif period == "week":
            start_time = end_time - timedelta(days=7)
            bucket_interval = "auto"  # Let repository choose best table
        else:  # month
            start_time = end_time - timedelta(days=30)
            bucket_interval = "auto"  # Let repository choose best table

    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    data = await service.get_site_energy_chart(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        bucket_interval=bucket_interval,
    )

    return EnergyChartResponse(
        site_id=site_id,
        period=period,
        start_time=start_time,
        end_time=end_time,
        bucket_interval=bucket_interval,
        data=[EnergyChartDataPoint(**point) for point in data],
    )


@router.get(
    "/daily-peaks/{site_id}",
    summary="Get today's peak power metrics for a site",
    description=(
        "Returns the maximum instantaneous power for PV, load, grid-export, and "
        "grid-import within the requested UTC window (pass today's local midnight "
        "→ end-of-day as UTC bounds). Null values are returned when no data exists. "
        "Pass device_id to restrict peaks to a single inverter."
    ),
)
async def get_daily_peaks(
    site_id: UUID,
    start_time: datetime,
    end_time: datetime,
    device_id: Optional[UUID] = Query(None, description="Restrict peaks to a specific device"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Get today's peak instantaneous power metrics for a site (or single device).

    Uses a single SQL pass over telemetry_raw with FILTER clauses so only one
    table scan is needed.  Peak timestamps are obtained via a DISTINCT ON subquery
    on the same table, which TimescaleDB handles efficiently through chunk pruning.
    """
    # Ensure UTC-aware
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    device_filter = "AND device_id = :device_id" if device_id is not None else ""

    query = text(f"""
        WITH base AS (
            -- Normalise metric names so Voltronic (load_power_w / grid_power_w)
            -- and all other families (load_w / grid_w) are treated identically.
            SELECT
                CASE metric_name
                    WHEN 'load_power_w' THEN 'load_w'
                    WHEN 'grid_power_w' THEN 'grid_w'
                    ELSE metric_name
                END AS metric_name,
                metric_value,
                time
            FROM telemetry_raw
            WHERE site_id = :site_id
              {device_filter}
              AND time    >= :start_time
              AND time     < :end_time
              AND metric_name IN ('pv_total_w', 'load_w', 'load_power_w',
                                  'grid_w',    'grid_power_w')
        ),
        peak_values AS (
            SELECT
                MAX(metric_value)  FILTER (WHERE metric_name = 'pv_total_w')              AS max_pv_w,
                MAX(metric_value)  FILTER (WHERE metric_name = 'load_w')                   AS max_load_w,
                MAX(-metric_value) FILTER (WHERE metric_name = 'grid_w'
                                            AND metric_value < 0)                          AS max_export_w,
                MAX(metric_value)  FILTER (WHERE metric_name = 'grid_w'
                                            AND metric_value > 0)                          AS max_import_w
            FROM base
        ),
        pv_time AS (
            SELECT time FROM base
            WHERE metric_name = 'pv_total_w'
            ORDER BY metric_value DESC LIMIT 1
        ),
        load_time AS (
            SELECT time FROM base
            WHERE metric_name = 'load_w'
            ORDER BY metric_value DESC LIMIT 1
        ),
        export_time AS (
            SELECT time FROM base
            WHERE metric_name = 'grid_w' AND metric_value < 0
            ORDER BY metric_value ASC LIMIT 1
        ),
        import_time AS (
            SELECT time FROM base
            WHERE metric_name = 'grid_w' AND metric_value > 0
            ORDER BY metric_value DESC LIMIT 1
        )
        SELECT
            pv.max_pv_w,
            (SELECT time FROM pv_time)     AS max_pv_at,
            pv.max_load_w,
            (SELECT time FROM load_time)   AS max_load_at,
            pv.max_export_w,
            (SELECT time FROM export_time) AS max_export_at,
            pv.max_import_w,
            (SELECT time FROM import_time) AS max_import_at
        FROM peak_values pv
    """)

    logger.info(
        "[daily-peaks] site=%s device=%s window=%s → %s",
        site_id, device_id, start_time.isoformat(), end_time.isoformat(),
    )
    params: dict = {
        "site_id": site_id,
        "start_time": start_time,
        "end_time": end_time,
    }
    if device_id is not None:
        params["device_id"] = device_id
    result = await session.execute(query, params)
    row = result.fetchone()
    logger.info(
        "[daily-peaks] result: pv=%s load=%s export=%s import=%s",
        getattr(row, "max_pv_w", None),
        getattr(row, "max_load_w", None),
        getattr(row, "max_export_w", None),
        getattr(row, "max_import_w", None),
    )

    def _metric(value, occurred_at):
        if value is None:
            return {"value_w": None, "occurred_at": None}
        return {
            "value_w": float(value),
            "occurred_at": occurred_at.isoformat() if occurred_at else None,
        }

    return {
        "site_id": str(site_id),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "peaks": {
            "pv":     _metric(row.max_pv_w,     row.max_pv_at),
            "load":   _metric(row.max_load_w,   row.max_load_at),
            "export": _metric(row.max_export_w, row.max_export_at),
            "import": _metric(row.max_import_w, row.max_import_at),
        },
    }


@router.get(
    "/ingestion-stats",
    summary="Get ingestion statistics",
    description="Get telemetry ingestion statistics for monitoring.",
)
async def get_ingestion_stats(
    hours: int = Query(default=24, ge=1, le=168),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Get ingestion statistics.
    """
    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    return await service.get_ingestion_stats(hours)


@router.get(
    "/gaps/{device_id}/{metric_name}",
    summary="Check for data gaps",
    description="Check for gaps in telemetry data.",
)
async def check_data_gaps(
    device_id: UUID,
    metric_name: str,
    expected_interval_seconds: int = Query(default=60),
    hours: int = Query(default=24, ge=1, le=168),
    session: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """
    Check for gaps in telemetry data.
    """
    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    return await service.check_data_gaps(
        device_id=device_id,
        metric_name=metric_name,
        expected_interval_seconds=expected_interval_seconds,
        hours=hours,
    )


@router.get(
    "/battery-cells/{device_id}/hourly",
    summary="Per-cell hourly aggregates for a battery bank",
    description=(
        "Returns rows from the ``battery_cell_hourly`` continuous aggregate "
        "for a specific battery device. Used by the System A cell-health "
        "time-series detector (fast_full / fast_empty symptoms)."
    ),
)
async def get_battery_cell_hourly(
    device_id: UUID,
    window_hours: int = Query(default=168, ge=1, le=720),
    session: AsyncSession = Depends(get_db_session),
) -> List[dict]:
    """Per-cell hourly aggregates for the last ``window_hours``.

    Rows are ordered by ``(bucket, unit, cell)``. Only rows where all of
    ``first_v`` and ``last_v`` are non-null are returned — those are the
    only ones useful for dV/dt analysis.
    """
    start_ts = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    result = await session.execute(
        text(
            """
            SELECT bucket, unit, cell,
                   first_v, last_v, avg_v, min_v, max_v,
                   avg_current_a, avg_temp, sample_count
            FROM battery_cell_hourly
            WHERE device_id = :device_id
              AND bucket >= :start_ts
              AND first_v IS NOT NULL
              AND last_v  IS NOT NULL
            ORDER BY bucket ASC, unit ASC, cell ASC
            """
        ),
        {"device_id": device_id, "start_ts": start_ts},
    )
    rows = result.mappings().all()
    return [
        {
            "bucket": r["bucket"].isoformat() if r["bucket"] else None,
            "unit": r["unit"],
            "cell": r["cell"],
            "first_v": r["first_v"],
            "last_v": r["last_v"],
            "avg_v": r["avg_v"],
            "min_v": r["min_v"],
            "max_v": r["max_v"],
            "avg_current_a": r["avg_current_a"],
            "avg_temp": r["avg_temp"],
            "sample_count": r["sample_count"],
        }
        for r in rows
    ]
