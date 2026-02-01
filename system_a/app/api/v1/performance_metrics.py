"""
Performance Metrics Management API

Admin endpoints for calculating and managing performance metrics like
efficiency and self-sufficiency.
"""
import logging
from datetime import date as date_type
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_unit_of_work, require_admin
from ...application.interfaces.unit_of_work import UnitOfWork
from ...application.services.performance_metrics_service import PerformanceMetricsService
from ...domain.entities.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance-metrics", tags=["Performance Metrics"])


class CalculationResponse(BaseModel):
    """Response from metrics calculation."""
    success: bool
    message: str
    hourly_records_updated: int = 0
    daily_records_updated: int = 0
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post(
    "/calculate/previous-day",
    response_model=CalculationResponse,
    summary="Calculate metrics for previous day",
    description="Calculate efficiency and self-sufficiency for yesterday's data. Admin only.",
)
async def calculate_previous_day(
    site_id: Optional[UUID] = Query(None, description="Optional site ID filter"),
    current_user: User = Depends(require_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Calculate performance metrics for the previous day.

    This endpoint is meant to be called daily (e.g., via cron job at 1am)
    to calculate yesterday's efficiency and self-sufficiency.

    The metrics are stored in the hourly and daily summary tables.
    """
    service = PerformanceMetricsService(uow._session)

    try:
        result = await service.calculate_previous_day_metrics(site_id=site_id)
        return CalculationResponse(
            success=True,
            message=f"Successfully calculated metrics for {result['date']}",
            hourly_records_updated=result['hourly_records_updated'],
            daily_records_updated=result['daily_records_updated'],
            start_date=result['date'],
            end_date=result['date'],
        )
    except Exception as e:
        logger.error(f"Error calculating previous day metrics: {e}", exc_info=True)
        return CalculationResponse(
            success=False,
            message=f"Error calculating metrics: {str(e)}",
        )


@router.post(
    "/calculate/backfill",
    response_model=CalculationResponse,
    summary="Backfill historical metrics",
    description="Calculate metrics for historical data (last N days). Admin only.",
)
async def backfill_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to backfill"),
    site_id: Optional[UUID] = Query(None, description="Optional site ID filter"),
    current_user: User = Depends(require_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Backfill performance metrics for historical data.

    Useful for calculating metrics on existing data that was created
    before efficiency and self-sufficiency tracking was implemented.
    """
    service = PerformanceMetricsService(uow._session)

    try:
        result = await service.backfill_metrics(days=days, site_id=site_id)
        return CalculationResponse(
            success=True,
            message=f"Successfully backfilled {days} days of metrics",
            hourly_records_updated=result['hourly_records_updated'],
            daily_records_updated=result['daily_records_updated'],
            start_date=result['start_date'],
            end_date=result['end_date'],
        )
    except Exception as e:
        logger.error(f"Error backfilling metrics: {e}", exc_info=True)
        return CalculationResponse(
            success=False,
            message=f"Error backfilling metrics: {str(e)}",
        )


@router.get(
    "/formulas",
    summary="Get calculation formulas",
    description="Returns the formulas used for calculating performance metrics",
)
async def get_formulas(
    current_user: User = Depends(get_current_user),
):
    """
    Get the formulas used for calculating performance metrics.

    This is a documentation endpoint showing how efficiency
    and self-sufficiency are calculated.
    """
    return {
        "efficiency": {
            "name": "Inverter Efficiency",
            "formula": "((Consumed + Exported + Stored) / Generated) × 100",
            "description": "Percentage of DC power (from solar) that is converted to AC power",
            "components": {
                "DC_Input": "Energy generated from PV panels (kWh)",
                "AC_Output": "Energy consumed + exported + stored in battery (kWh)",
            },
            "typical_range": "95-99% for modern inverters",
            "interpretation": {
                "95-99%": "Excellent efficiency",
                "90-95%": "Good efficiency",
                "<90%": "Poor efficiency - investigate inverter health",
            },
        },
        "self_sufficiency": {
            "name": "Energy Independence / Self-Sufficiency",
            "formula": "((Load - Grid Import) / Load) × 100",
            "alternative_formula": "(1 - (Grid Import / Load)) × 100",
            "description": "Percentage of consumed energy that comes from solar/battery vs grid",
            "components": {
                "Load": "Total energy consumed (kWh)",
                "Grid_Import": "Energy imported from grid (kWh)",
            },
            "interpretation": {
                "100%": "Fully self-sufficient - no grid import",
                "80-99%": "High self-sufficiency - mostly solar/battery",
                "50-79%": "Moderate self-sufficiency",
                "0-49%": "Low self-sufficiency - mostly grid dependent",
                "0%": "No self-sufficiency - all energy from grid",
            },
            "example": {
                "scenario": "Load=10kWh, Grid Import=2kWh",
                "calculation": "(1 - 2/10) × 100 = 80%",
                "meaning": "80% from solar/battery, 20% from grid",
            },
        },
    }
