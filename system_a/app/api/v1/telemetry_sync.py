"""
Telemetry Sync Management API

Admin endpoints for manually triggering telemetry data sync from System B to System A.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..dependencies import get_current_user, get_telemetry_sync_service, require_admin
from ...application.services.telemetry_sync_service import TelemetrySyncService
from ...domain.entities.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry-sync", tags=["Telemetry Sync"])


class SyncResponse(BaseModel):
    """Response from telemetry sync operation."""
    success: bool
    message: str
    records_synced: int = 0
    hours_synced: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@router.post(
    "/sync/hourly",
    response_model=SyncResponse,
    summary="Sync hourly telemetry data",
    description="Sync hourly aggregated telemetry from System B to System A. Admin only.",
)
async def sync_hourly_telemetry(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to sync (max 7 days)"),
    site_id: Optional[UUID] = Query(None, description="Optional site ID filter"),
    current_user: User = Depends(require_admin),
    sync_service: TelemetrySyncService = Depends(get_telemetry_sync_service),
):
    """
    Manually trigger hourly telemetry sync from System B.

    This endpoint pulls aggregated hourly data from System B (TimescaleDB)
    and upserts it into System A's hourly summary tables.

    Use this to:
    - Populate historical data for charts
    - Backfill missing hourly summaries
    - Recover from sync failures
    """
    try:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        logger.info(f"Starting hourly sync: {hours} hours, site_id={site_id}")

        result = await sync_service.sync_hourly_summaries(
            start_time=start_time,
            end_time=end_time,
            site_id=site_id,
        )

        if result.success:
            return SyncResponse(
                success=True,
                message=f"Successfully synced {hours} hours of hourly data",
                records_synced=result.records_upserted,
                hours_synced=hours,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
            )
        else:
            return SyncResponse(
                success=False,
                message=f"Sync completed with errors: {', '.join(result.errors)}",
                records_synced=result.records_upserted,
                hours_synced=hours,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
            )

    except Exception as e:
        logger.error(f"Error syncing hourly telemetry: {e}", exc_info=True)
        return SyncResponse(
            success=False,
            message=f"Error syncing data: {str(e)}",
        )


@router.post(
    "/sync/daily",
    response_model=SyncResponse,
    summary="Sync daily telemetry data",
    description="Sync daily aggregated telemetry from System B to System A. Admin only.",
)
async def sync_daily_telemetry(
    days: int = Query(7, ge=1, le=90, description="Number of days to sync (max 90 days)"),
    site_id: Optional[UUID] = Query(None, description="Optional site ID filter"),
    current_user: User = Depends(require_admin),
    sync_service: TelemetrySyncService = Depends(get_telemetry_sync_service),
):
    """
    Manually trigger daily telemetry sync from System B.

    This endpoint pulls aggregated daily data from System B (TimescaleDB)
    and upserts it into System A's daily summary tables.
    """
    try:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        logger.info(f"Starting daily sync: {days} days, site_id={site_id}")

        result = await sync_service.sync_daily_summaries(
            start_date=start_date,
            end_date=end_date,
            site_id=site_id,
        )

        if result.success:
            return SyncResponse(
                success=True,
                message=f"Successfully synced {days} days of daily data",
                records_synced=result.records_upserted,
                hours_synced=days * 24,
                start_time=start_date.isoformat(),
                end_time=end_date.isoformat(),
            )
        else:
            return SyncResponse(
                success=False,
                message=f"Sync completed with errors: {', '.join(result.errors)}",
                records_synced=result.records_upserted,
                start_time=start_date.isoformat(),
                end_time=end_date.isoformat(),
            )

    except Exception as e:
        logger.error(f"Error syncing daily telemetry: {e}", exc_info=True)
        return SyncResponse(
            success=False,
            message=f"Error syncing data: {str(e)}",
        )


@router.get(
    "/status",
    summary="Get sync status",
    description="Check the status of telemetry sync",
)
async def get_sync_status(
    current_user: User = Depends(get_current_user),
    sync_service: TelemetrySyncService = Depends(get_telemetry_sync_service),
):
    """
    Get information about the telemetry sync status.

    Returns information about when data was last synced and
    whether the sync service is functioning properly.
    """
    # For now, return basic status
    # In production, this could query the summary tables to see latest data
    return {
        "service": "TelemetrySyncService",
        "status": "available",
        "message": "Use POST /sync/hourly or /sync/daily to manually trigger sync",
        "recommended_schedule": {
            "hourly": "Every hour at :05 (to allow System B aggregation to complete)",
            "daily": "Once per day at 1:00 AM",
        },
    }
