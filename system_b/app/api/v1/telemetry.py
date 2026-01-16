"""
Telemetry API endpoints for System B.

Handles telemetry ingestion and retrieval.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db_session, get_telemetry_service
from ..schemas import (
    TelemetryBatchCreate,
    TelemetryIngestRequest,
    TelemetryLatestResponse,
    TelemetryAggregateResponse,
    TelemetryStatsResponse,
    IngestResponse,
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
        try:
            count = await service.ingest_telemetry(
                device_id=batch_data.device_id,
                site_id=batch_data.site_id,
                metrics=batch_data.metrics,
                timestamp=batch_data.timestamp,
                source=batch_data.source,
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

    try:
        count = await service.ingest_telemetry(
            device_id=device_id,
            site_id=site_id,
            metrics=metrics,
            timestamp=timestamp,
            source=source,
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
    telemetry_repo = TelemetryRepository(session)
    service = TelemetryService(telemetry_repo)

    readings = await service.get_latest_telemetry(device_id, metric_names)

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

    aggregates = await service.get_aggregated_telemetry(
        device_id=device_id,
        metric_name=metric_name,
        start_time=start_time,
        end_time=end_time,
        bucket_interval=bucket_interval,
    )

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
