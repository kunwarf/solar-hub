"""
Dashboard API endpoints.
"""
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
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
from ...domain.entities.user import User, UserRole

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])


# Constants for environmental calculations
CO2_PER_KWH_KG = 0.475  # Pakistan grid emission factor (approximate)
TREES_PER_TON_CO2 = 45  # Trees needed to absorb 1 ton CO2 per year
COAL_PER_KWH_KG = 0.4   # Coal needed to generate 1 kWh
PKR_PER_KWH = 25.0      # Average electricity rate in Pakistan


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
):
    """Get organization-wide dashboard overview."""
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

    # Get site counts
    all_sites = await uow.sites.get_by_organization_id(org.id, limit=1000)
    active_sites = [s for s in all_sites if s.status.value == 'active']

    # Get device counts
    total_devices = await uow.devices.count_by_organization_id(org.id)
    devices_with_errors = await uow.devices.get_devices_with_errors(org.id)

    # Calculate total capacity
    total_capacity = sum(s.configuration.system_capacity_kw for s in all_sites)

    # Get online devices across all sites
    online_count = 0
    for site in active_sites:
        online_devices = await uow.devices.get_online_devices(site.id)
        online_count += len(online_devices)

    # TODO: Get actual energy data from telemetry system (System B)
    # For now, return placeholder/calculated values

    # Build top sites list
    top_sites = []
    for site in active_sites[:5]:
        top_sites.append({
            "id": str(site.id),
            "name": site.name,
            "capacity_kw": site.configuration.system_capacity_kw,
            "energy_today_kwh": 0.0,  # TODO: from telemetry
            "status": site.status.value,
        })

    return OrganizationOverviewResponse(
        organization_id=org.id,
        organization_name=org.name,
        total_sites=len(all_sites),
        active_sites=len(active_sites),
        total_devices=total_devices,
        online_devices=online_count,
        total_current_power_kw=0.0,  # TODO: from telemetry
        total_energy_today_kwh=0.0,  # TODO: from telemetry
        total_energy_this_month_kwh=0.0,  # TODO: from telemetry
        total_capacity_kw=total_capacity,
        total_active_alerts=0,  # TODO: from alerts
        total_critical_alerts=0,  # TODO: from alerts
        top_sites=top_sites,
        last_updated=datetime.now(timezone.utc),
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
):
    """Get site dashboard overview."""
    site = await check_site_access(site_id, current_user, uow)

    # Get device stats
    total_devices = await uow.devices.count_by_site_id(site_id)
    online_devices = await uow.devices.get_online_devices(site_id)
    devices_with_errors = await uow.devices.get_devices_with_errors(site.organization_id)
    site_errors = [d for d in devices_with_errors if d.site_id == site_id]

    # TODO: Get actual readings from telemetry system
    # These are placeholder values

    return SiteOverviewResponse(
        site_id=site.id,
        site_name=site.name,
        status=site.status.value,
        current_power_kw=0.0,
        current_grid_power_kw=0.0,
        current_battery_soc_percent=None,
        energy_today_kwh=0.0,
        energy_exported_today_kwh=0.0,
        energy_imported_today_kwh=0.0,
        peak_power_today_kw=0.0,
        energy_this_month_kwh=0.0,
        energy_lifetime_kwh=0.0,
        total_devices=total_devices,
        online_devices=len(online_devices),
        devices_with_errors=len(site_errors),
        active_alerts=0,
        critical_alerts=0,
        system_capacity_kw=site.configuration.system_capacity_kw,
        capacity_factor_percent=0.0,
        last_updated=datetime.now(timezone.utc),
    )


@router.get(
    "/sites/{site_id}/energy/daily",
    response_model=list[DailyEnergyStats],
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_daily_energy_stats(
    site_id: UUID,
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
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

    # TODO: Get actual data from telemetry system
    # Return placeholder data for the date range
    stats = []
    current_date = start_date
    while current_date <= end_date:
        stats.append(DailyEnergyStats(
            date=current_date,
            energy_generated_kwh=0.0,
            energy_consumed_kwh=0.0,
            energy_exported_kwh=0.0,
            energy_imported_kwh=0.0,
            peak_power_kw=0.0,
            peak_power_time=None,
            sunshine_hours=0.0,
        ))
        current_date += timedelta(days=1)

    return stats


@router.get(
    "/sites/{site_id}/energy/monthly",
    response_model=list[MonthlyEnergyStats],
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_monthly_energy_stats(
    site_id: UUID,
    year: int = Query(..., ge=2020, le=2100, description="Year"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get monthly energy statistics for a site."""
    await check_site_access(site_id, current_user, uow)

    # TODO: Get actual data from telemetry system
    # Return placeholder data for each month
    stats = []
    for month in range(1, 13):
        stats.append(MonthlyEnergyStats(
            year=year,
            month=month,
            energy_generated_kwh=0.0,
            energy_consumed_kwh=0.0,
            energy_exported_kwh=0.0,
            energy_imported_kwh=0.0,
            avg_daily_generation_kwh=0.0,
            peak_power_kw=0.0,
            days_with_data=0,
        ))

    return stats


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

    # TODO: Get actual data from telemetry system
    # Return placeholder chart data
    today = date.today()

    if period == "day":
        labels = [f"{h:02d}:00" for h in range(24)]
        values = [0.0] * 24
    elif period == "week":
        labels = [(today - timedelta(days=i)).strftime("%a") for i in range(6, -1, -1)]
        values = [0.0] * 7
    elif period == "month":
        labels = [str(i) for i in range(1, 32)]
        values = [0.0] * 31
    else:  # year
        labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        values = [0.0] * 12

    return EnergyChartData(
        labels=labels,
        datasets=[
            {
                "label": "Generation (kWh)",
                "data": values,
                "backgroundColor": "#22c55e",
            },
            {
                "label": "Consumption (kWh)",
                "data": values,
                "backgroundColor": "#ef4444",
            },
        ],
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
):
    """Get real-time power data for live chart."""
    await check_site_access(site_id, current_user, uow)

    # TODO: Get actual data from telemetry system (via Redis pub/sub)
    # Return placeholder data
    now = datetime.now(timezone.utc)
    timestamps = []
    power_values = []

    for i in range(minutes, 0, -1):
        timestamps.append(now - timedelta(minutes=i))
        power_values.append(0.0)

    return PowerChartData(
        timestamps=timestamps,
        power_values=power_values,
        grid_values=None,
        battery_values=None,
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
):
    """Compare multiple sites' performance."""
    await check_org_access(organization_id, current_user, uow)

    # Get sites to compare
    if site_ids:
        site_id_list = [UUID(sid.strip()) for sid in site_ids.split(",")]
        sites = []
        for sid in site_id_list:
            site = await uow.sites.get_by_id(sid)
            if site and site.organization_id == organization_id:
                sites.append(site)
    else:
        # Compare all sites in organization
        sites = await uow.sites.get_by_organization_id(organization_id, limit=20)

    # TODO: Get actual performance data from telemetry system
    comparison_items = []
    for site in sites:
        capacity = site.configuration.system_capacity_kw
        # Placeholder calculations
        energy = 0.0  # TODO: from telemetry
        specific_yield = energy / capacity if capacity > 0 else 0.0
        performance_ratio = 0.0  # TODO: calculate from actual vs expected

        comparison_items.append(SiteComparisonItem(
            site_id=site.id,
            site_name=site.name,
            energy_generated_kwh=energy,
            capacity_kw=capacity,
            performance_ratio=performance_ratio,
            specific_yield=specific_yield,
        ))

    return SiteComparisonResponse(
        period_start=start_date,
        period_end=end_date,
        sites=comparison_items,
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

    # TODO: Get actual energy data from telemetry system
    total_solar_energy = 0.0  # kWh

    # Calculate environmental metrics
    co2_avoided = total_solar_energy * CO2_PER_KWH_KG
    trees_equivalent = (co2_avoided / 1000) * TREES_PER_TON_CO2  # Convert to tons
    coal_avoided = total_solar_energy * COAL_PER_KWH_KG
    estimated_savings = total_solar_energy * PKR_PER_KWH

    return EnvironmentalImpactResponse(
        site_id=site_id,
        organization_id=organization_id,
        period_start=start_date,
        period_end=end_date,
        total_solar_energy_kwh=total_solar_energy,
        co2_avoided_kg=co2_avoided,
        trees_equivalent=trees_equivalent,
        coal_avoided_kg=coal_avoided,
        estimated_savings_pkr=estimated_savings,
    )
