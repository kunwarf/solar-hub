"""
Dashboard API endpoints.

Provides real-time and historical telemetry data for dashboards.
"""
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
    get_telemetry_service,
)
from ..schemas.dashboard_schemas import (
    DailyEnergyStats,
    EnergyChartData,
    EnvironmentalImpactResponse,
    MonthlyEnergyStats,
    OrganizationOverviewResponse,
    PowerChartData,
    SiteComparisonItem,
    SiteComparisonResponse,
    SiteOverviewResponse,
)
from ..schemas.auth_schemas import ErrorResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...application.services.telemetry_service import TelemetryService
from ...domain.entities.user import User, UserRole

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])


async def check_org_access(org_id: UUID, user: User, uow: UnitOfWork) -> None:
    """Verify user has access to organization."""
    org = await uow.organizations.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    if not org.is_member(user.id) and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this organization",
        )


async def check_site_access(site_id: UUID, user: User, uow: UnitOfWork):
    """Verify user has access to site."""
    site = await uow.sites.get_by_id(site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )
    await check_org_access(site.organization_id, user, uow)
    return site


@router.get(
    "/overview",
    response_model=OrganizationOverviewResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_organization_overview(
    organization_id: Optional[UUID] = Query(None, description="Organization ID (defaults to first org)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """Get organization-wide dashboard overview with real telemetry data."""
    # Get organization
    if organization_id:
        await check_org_access(organization_id, current_user, uow)
        org = await uow.organizations.get_by_id(organization_id)
    else:
        # Get first organization user belongs to
        orgs = await uow.organizations.get_by_member_id(current_user.id)
        if not orgs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No organizations found",
            )
        org = orgs[0]

    # Get organization overview from telemetry service
    overview = await telemetry_service.get_org_overview(org.id, org.name)

    return OrganizationOverviewResponse(
        organization_id=overview.organization_id,
        organization_name=overview.organization_name,
        total_sites=overview.total_sites,
        active_sites=overview.active_sites,
        total_devices=overview.total_devices,
        online_devices=overview.online_devices,
        total_current_power_kw=overview.total_current_power_kw,
        total_energy_today_kwh=overview.total_energy_today_kwh,
        total_energy_this_month_kwh=overview.total_energy_this_month_kwh,
        total_capacity_kw=overview.total_capacity_kw,
        total_active_alerts=overview.total_active_alerts,
        total_critical_alerts=overview.total_critical_alerts,
        top_sites=overview.top_sites,
        last_updated=overview.last_updated,
    )


@router.get(
    "/sites/{site_id}",
    response_model=SiteOverviewResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_site_overview(
    site_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """Get site dashboard overview with real telemetry data."""
    await check_site_access(site_id, current_user, uow)

    # Get site overview from telemetry service
    overview = await telemetry_service.get_site_overview(site_id)

    return SiteOverviewResponse(
        site_id=overview.site_id,
        site_name=overview.site_name,
        status=overview.status,
        current_power_kw=overview.current_power_kw,
        current_grid_power_kw=overview.current_grid_power_kw,
        current_battery_soc_percent=overview.current_battery_soc_percent,
        energy_today_kwh=overview.energy_today_kwh,
        energy_exported_today_kwh=overview.energy_exported_today_kwh,
        energy_imported_today_kwh=overview.energy_imported_today_kwh,
        peak_power_today_kw=overview.peak_power_today_kw,
        energy_this_month_kwh=overview.energy_this_month_kwh,
        energy_lifetime_kwh=overview.energy_lifetime_kwh,
        total_devices=overview.total_devices,
        online_devices=overview.online_devices,
        devices_with_errors=overview.devices_with_errors,
        active_alerts=overview.active_alerts,
        critical_alerts=overview.critical_alerts,
        system_capacity_kw=overview.system_capacity_kw,
        capacity_factor_percent=overview.capacity_factor_percent,
        last_updated=overview.last_updated,
    )


@router.get(
    "/sites/{site_id}/energy/daily",
    response_model=List[DailyEnergyStats],
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_daily_energy_stats(
    site_id: UUID,
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """Get daily energy statistics for a site."""
    await check_site_access(site_id, current_user, uow)

    # Validate date range
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    if (end_date - start_date).days > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 365 days",
        )

    # Get daily stats from telemetry service
    daily_data = await telemetry_service.get_daily_energy_stats(site_id, start_date, end_date)

    return [
        DailyEnergyStats(
            date=d.date,
            energy_generated_kwh=d.energy_generated_kwh,
            energy_consumed_kwh=d.energy_consumed_kwh,
            energy_exported_kwh=d.energy_exported_kwh,
            energy_imported_kwh=d.energy_imported_kwh,
            peak_power_kw=d.peak_power_kw,
            peak_power_time=d.peak_power_time,
            sunshine_hours=d.sunshine_hours,
        )
        for d in daily_data
    ]


@router.get(
    "/sites/{site_id}/energy/monthly",
    response_model=List[MonthlyEnergyStats],
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_monthly_energy_stats(
    site_id: UUID,
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """Get monthly energy statistics for a site."""
    await check_site_access(site_id, current_user, uow)

    # Get monthly stats from telemetry service
    monthly_data = await telemetry_service.get_monthly_energy_stats(site_id, year)

    return [
        MonthlyEnergyStats(
            year=m.year,
            month=m.month,
            energy_generated_kwh=m.energy_generated_kwh,
            energy_consumed_kwh=m.energy_consumed_kwh,
            energy_exported_kwh=m.energy_exported_kwh,
            energy_imported_kwh=m.energy_imported_kwh,
            avg_daily_generation_kwh=m.avg_daily_generation_kwh,
            peak_power_kw=m.peak_power_kw,
            days_with_data=m.days_with_data,
        )
        for m in monthly_data
    ]


@router.get(
    "/sites/{site_id}/energy/chart",
    response_model=EnergyChartData,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_energy_chart_data(
    site_id: UUID,
    period: str = Query("week", description="Period: day, week, month, year"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """Get energy chart data for visualization."""
    await check_site_access(site_id, current_user, uow)

    # Validate period
    valid_periods = ["day", "week", "month", "year"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Period must be one of: {', '.join(valid_periods)}",
        )

    # Get chart data from telemetry service
    chart_data = await telemetry_service.get_energy_chart_data(site_id, period)

    return EnergyChartData(
        labels=chart_data["labels"],
        datasets=chart_data["datasets"],
    )


@router.get(
    "/sites/{site_id}/power/realtime",
    response_model=PowerChartData,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_realtime_power_data(
    site_id: UUID,
    minutes: int = Query(60, ge=5, le=1440, description="Minutes of data to return"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """Get real-time power data for live chart."""
    await check_site_access(site_id, current_user, uow)

    # Get real-time power history from telemetry service
    power_data = await telemetry_service.get_realtime_power_history(site_id, minutes)

    return PowerChartData(
        timestamps=power_data["timestamps"],
        power_values=power_data["power_values"],
        grid_values=None,  # Could be added if needed
        battery_values=None,  # Could be added if needed
    )


@router.get(
    "/comparison",
    response_model=SiteComparisonResponse,
    responses={403: {"model": ErrorResponse}},
)
async def compare_sites(
    organization_id: UUID = Query(..., description="Organization ID"),
    site_ids: Optional[str] = Query(None, description="Comma-separated site IDs to compare"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """Compare multiple sites' performance."""
    await check_org_access(organization_id, current_user, uow)

    # Parse site IDs if provided
    site_id_list = None
    if site_ids:
        site_id_list = [UUID(sid.strip()) for sid in site_ids.split(",")]

    # Get site comparisons from telemetry service
    comparisons = await telemetry_service.compare_sites(
        organization_id=organization_id,
        site_ids=site_id_list,
        start_date=start_date,
        end_date=end_date,
    )

    return SiteComparisonResponse(
        period_start=start_date,
        period_end=end_date,
        sites=[
            SiteComparisonItem(
                site_id=c.site_id,
                site_name=c.site_name,
                energy_generated_kwh=c.energy_generated_kwh,
                capacity_kw=c.capacity_kw,
                performance_ratio=c.performance_ratio,
                specific_yield=c.specific_yield,
            )
            for c in comparisons
        ],
    )


@router.get(
    "/environmental-impact",
    response_model=EnvironmentalImpactResponse,
    responses={403: {"model": ErrorResponse}},
)
async def get_environmental_impact(
    organization_id: Optional[UUID] = Query(None, description="Organization ID"),
    site_id: Optional[UUID] = Query(None, description="Site ID"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    telemetry_service: TelemetryService = Depends(get_telemetry_service),
):
    """Get environmental impact metrics."""
    if not organization_id and not site_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either organization_id or site_id is required",
        )

    if site_id:
        site = await check_site_access(site_id, current_user, uow)
        organization_id = site.organization_id
    else:
        await check_org_access(organization_id, current_user, uow)

    # Get environmental impact from telemetry service
    impact = await telemetry_service.get_environmental_impact(
        organization_id=organization_id,
        start_date=start_date,
        end_date=end_date,
        site_id=site_id,
    )

    return EnvironmentalImpactResponse(
        site_id=impact.site_id,
        organization_id=impact.organization_id,
        period_start=impact.period_start,
        period_end=impact.period_end,
        total_solar_energy_kwh=impact.total_solar_energy_kwh,
        co2_avoided_kg=impact.co2_avoided_kg,
        trees_equivalent=impact.trees_equivalent,
        coal_avoided_kg=impact.coal_avoided_kg,
        estimated_savings_pkr=impact.estimated_savings_pkr,
    )
