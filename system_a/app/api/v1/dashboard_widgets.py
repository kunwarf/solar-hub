"""
Dashboard Widget API endpoints.

Provides widget-specific endpoints for the frontend dashboard.
Each widget has its own endpoint with appropriate caching and refresh rates.

These endpoints:
- Accept site_id as primary parameter
- Aggregate telemetry from all devices in the site
- Include organization_id and site_id in responses
- Provide both aggregated and per-device breakdown data
- Use Redis cache for site/device relationships (cache-first, DB fallback)
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_unit_of_work
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserRole
from ...infrastructure.cache.telemetry_cache import telemetry_cache
from ...infrastructure.cache.site_cache import site_cache as site_info_cache, CachedSiteInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard Widgets"])


# ============================================================================
# Response Schemas
# ============================================================================

class DevicePowerData(BaseModel):
    """Per-device power data for breakdown."""
    serial_number: str
    pv_power_w: float = 0
    grid_power_w: float = 0
    load_power_w: float = 0
    battery_power_w: float = 0
    battery_soc_pct: float = 0
    is_charging: bool = False
    online: bool = False


class PowerFlowResponse(BaseModel):
    """Real-time power flow data for power flow widget."""
    # Context
    organization_id: UUID
    site_id: UUID
    site_name: str
    timestamp: Optional[str] = None

    # Aggregated power (sum of all devices)
    pv_power_w: float = 0
    grid_power_w: float = 0
    load_power_w: float = 0
    battery_power_w: float = 0
    battery_soc_pct: float = 0  # Average across devices
    is_charging: bool = False
    grid_connected: bool = True

    # Status
    online: bool = False
    stale: bool = True
    devices_online: int = 0
    devices_total: int = 0

    # Per-device breakdown
    devices: List[DevicePowerData] = Field(default_factory=list)


class DeviceStatsData(BaseModel):
    """Per-device stats for breakdown."""
    serial_number: str
    energy_today_kwh: float = 0
    peak_power_kw: float = 0
    online: bool = False


class StatsResponse(BaseModel):
    """Statistics cards data."""
    organization_id: UUID
    site_id: UUID
    site_name: str

    # Aggregated stats (sum of all devices)
    energy_today_kwh: float = 0
    energy_month_kwh: float = 0
    peak_power_kw: float = 0
    co2_saved_kg: float = 0
    online: bool = False
    devices_online: int = 0
    devices_total: int = 0

    # Per-device breakdown
    devices: List[DeviceStatsData] = Field(default_factory=list)


class DeviceBatteryData(BaseModel):
    """Per-device battery data for breakdown."""
    serial_number: str
    soc_pct: float = 0
    power_w: float = 0
    is_charging: bool = False
    online: bool = False


class BatteryStatusResponse(BaseModel):
    """Battery status widget data."""
    organization_id: UUID
    site_id: UUID
    site_name: str

    # Aggregated battery stats
    avg_soc_pct: float = 0
    total_power_w: float = 0
    is_charging: bool = False
    online: bool = False
    devices_online: int = 0
    devices_total: int = 0

    # Per-device breakdown
    devices: List[DeviceBatteryData] = Field(default_factory=list)


class DeviceStatusData(BaseModel):
    """Per-device status for breakdown."""
    serial_number: str
    status: str = "unknown"
    last_seen: Optional[int] = None
    working_mode: Optional[str] = None
    faults: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    online: bool = False


class DeviceStatusResponse(BaseModel):
    """Device status widget data."""
    organization_id: UUID
    site_id: UUID
    site_name: str

    # Site-level status summary
    devices_online: int = 0
    devices_offline: int = 0
    devices_total: int = 0
    total_faults: int = 0
    total_warnings: int = 0
    grid_connected: bool = True

    # Per-device breakdown
    devices: List[DeviceStatusData] = Field(default_factory=list)


class AlertItem(BaseModel):
    """Single alert item."""
    id: str
    serial_number: str
    severity: str
    message: str
    timestamp: str


class AlertsResponse(BaseModel):
    """Alerts widget data."""
    organization_id: UUID
    site_id: UUID
    site_name: str

    # Site-level alerts (aggregated from all devices)
    active_alerts: List[AlertItem] = Field(default_factory=list)
    total_count: int = 0
    critical_count: int = 0


class EnvironmentalResponse(BaseModel):
    """Environmental impact widget data."""
    organization_id: UUID
    site_id: UUID
    site_name: str

    # Site-level environmental impact (sum of all devices)
    co2_avoided_kg: float = 0
    trees_equivalent: float = 0
    coal_avoided_kg: float = 0


class EnergyChartPoint(BaseModel):
    """Single data point for energy chart."""
    timestamp: str
    pv_kwh: float = 0
    load_kwh: float = 0
    grid_import_kwh: float = 0
    grid_export_kwh: float = 0


class EnergyChartResponse(BaseModel):
    """Energy chart widget data."""
    organization_id: UUID
    site_id: UUID
    site_name: str
    period: str
    data: List[EnergyChartPoint] = Field(default_factory=list)


class BillingResponse(BaseModel):
    """Billing summary widget data."""
    organization_id: UUID
    site_id: UUID
    site_name: str

    # Site-level billing (sum of all devices)
    estimated_savings_today: float = 0
    estimated_savings_month: float = 0
    grid_import_cost: float = 0
    grid_export_credit: float = 0


class AllWidgetsResponse(BaseModel):
    """All widget data in a single response."""
    power_flow: PowerFlowResponse
    stats: StatsResponse
    battery: BatteryStatusResponse
    device_status: DeviceStatusResponse
    alerts: AlertsResponse
    environmental: EnvironmentalResponse
    billing: BillingResponse


# ============================================================================
# Helper Functions
# ============================================================================

async def get_site_with_devices(
    user: User,
    uow: UnitOfWork,
    site_id: Optional[UUID] = None,
) -> CachedSiteInfo:
    """
    Get site info with device serial numbers for the current user.

    Uses cache-first approach: tries Redis cache, falls back to DB.
    Validates that the site belongs to user's organization.

    Args:
        user: Current authenticated user.
        uow: Unit of work for DB access.
        site_id: Specific site ID (optional, uses default if not provided).

    Returns:
        CachedSiteInfo with site metadata and device serial numbers.

    Raises:
        HTTPException: If site not found or user doesn't have access.
    """
    # Determine which site to use
    target_site_id = site_id

    if not target_site_id:
        # Try to get user's default site from cache
        target_site_id = await site_info_cache.get_user_default_site(user.id)

        if not target_site_id:
            # Fallback to DB: get first site from first organization
            orgs = await uow.organizations.get_by_member_id(user.id)
            if not orgs:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No organizations found for user",
                )

            sites = await uow.sites.get_by_organization_id(orgs[0].id)
            if not sites:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No sites found in organization",
                )

            target_site_id = sites[0].id
            # Cache the default site
            await site_info_cache.set_user_default_site(user.id, target_site_id)

    # Try to get site info from cache
    cached_info = await site_info_cache.get_site_info(target_site_id)

    if cached_info:
        # Validate user access (check if site's org is accessible to user)
        user_sites = await site_info_cache.get_user_sites(user.id)
        if user_sites and target_site_id in user_sites:
            return cached_info
        # User sites not cached or site not in list - need to verify via DB

    # Cache miss or access validation needed - query DB
    site = await uow.sites.get_by_id(target_site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    org = await uow.organizations.get_by_id(site.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Validate user has access to this organization
    if not org.is_member(user.id) and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this site",
        )

    # Get devices for this site
    devices = await uow.devices.get_by_site_id(site.id)
    device_serials = [d.serial_number for d in devices]

    # Build and cache the site info
    site_info = CachedSiteInfo(
        site_id=site.id,
        organization_id=org.id,
        site_name=site.name,
        device_serials=device_serials,
    )

    await site_info_cache.set_site_info(site_info)

    # Also cache user's accessible sites
    user_orgs = await uow.organizations.get_by_member_id(user.id)
    user_site_ids = []
    for user_org in user_orgs:
        org_sites = await uow.sites.get_by_organization_id(user_org.id)
        user_site_ids.extend([s.id for s in org_sites])
    await site_info_cache.set_user_sites(user.id, user_site_ids)

    return site_info


async def get_all_devices_telemetry(
    device_serials: List[str],
) -> Dict[str, Dict[str, Any]]:
    """
    Get telemetry for all devices using batch read.

    Args:
        device_serials: List of device serial numbers.

    Returns:
        Dictionary mapping serial number to telemetry data.
    """
    if not device_serials:
        return {}

    return await telemetry_cache.get_telemetry_batch(device_serials)


# ============================================================================
# Widget Endpoints
# ============================================================================

@router.get(
    "/power-flow",
    response_model=PowerFlowResponse,
    summary="Get real-time power flow data",
    description="Returns aggregated power flow for all devices in a site. Refresh: 5 seconds.",
)
async def get_power_flow(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get real-time power flow data aggregated for the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    # Aggregate power data
    total_pv = 0.0
    total_grid = 0.0
    total_load = 0.0
    total_battery = 0.0
    total_soc = 0.0
    soc_count = 0
    devices_online = 0
    any_charging = False
    grid_connected = True
    latest_timestamp = None
    any_stale = True
    devices_data = []

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        status_val = await telemetry_cache.get_status(serial)
        is_online = status_val == "online"

        if is_online:
            devices_online += 1

        device_data = DevicePowerData(
            serial_number=serial,
            online=is_online,
        )

        if telemetry:
            power = telemetry.get("power", {})
            battery = telemetry.get("battery", {})
            status_info = telemetry.get("status", {})

            pv_w = power.get("pv_total_w", 0)
            grid_w = power.get("grid_w", 0)
            load_w = power.get("load_w", 0)
            battery_w = power.get("battery_w", 0)
            soc = battery.get("soc_pct", 0)
            charging = battery.get("charging", False)

            total_pv += pv_w
            total_grid += grid_w
            total_load += load_w
            total_battery += battery_w

            if soc > 0:
                total_soc += soc
                soc_count += 1

            if charging:
                any_charging = True

            if not status_info.get("grid_connected", True):
                grid_connected = False

            ts = telemetry.get("timestamp")
            if ts and (not latest_timestamp or ts > latest_timestamp):
                latest_timestamp = ts

            if not telemetry.get("_stale", True):
                any_stale = False

            device_data = DevicePowerData(
                serial_number=serial,
                pv_power_w=pv_w,
                grid_power_w=grid_w,
                load_power_w=load_w,
                battery_power_w=battery_w,
                battery_soc_pct=soc,
                is_charging=charging,
                online=is_online,
            )

        devices_data.append(device_data)

    avg_soc = total_soc / soc_count if soc_count > 0 else 0

    return PowerFlowResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        timestamp=latest_timestamp,
        pv_power_w=total_pv,
        grid_power_w=total_grid,
        load_power_w=total_load,
        battery_power_w=total_battery,
        battery_soc_pct=avg_soc,
        is_charging=any_charging,
        grid_connected=grid_connected,
        online=devices_online > 0,
        stale=any_stale,
        devices_online=devices_online,
        devices_total=len(site_info.device_serials),
        devices=devices_data,
    )


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get statistics cards data",
    description="Returns aggregated energy statistics for the site. Refresh: 30 seconds.",
)
async def get_stats(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get statistics data aggregated for the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    total_energy_today = 0.0
    total_peak_power = 0.0
    devices_online = 0
    devices_data = []

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        status_val = await telemetry_cache.get_status(serial)
        is_online = status_val == "online"

        if is_online:
            devices_online += 1

        device_data = DeviceStatsData(
            serial_number=serial,
            online=is_online,
        )

        if telemetry:
            energy = telemetry.get("energy_today", {})
            pv_kwh = energy.get("pv_kwh", 0)

            total_energy_today += pv_kwh

            device_data = DeviceStatsData(
                serial_number=serial,
                energy_today_kwh=pv_kwh,
                peak_power_kw=0,  # TODO: Get from historical data
                online=is_online,
            )

        devices_data.append(device_data)

    co2_saved = total_energy_today * 0.7

    return StatsResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        energy_today_kwh=total_energy_today,
        energy_month_kwh=0,  # TODO: Get from historical data
        peak_power_kw=total_peak_power,
        co2_saved_kg=co2_saved,
        online=devices_online > 0,
        devices_online=devices_online,
        devices_total=len(site_info.device_serials),
        devices=devices_data,
    )


@router.get(
    "/battery",
    response_model=BatteryStatusResponse,
    summary="Get battery status",
    description="Returns aggregated battery status for the site. Refresh: 10 seconds.",
)
async def get_battery_status(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get battery status aggregated for the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    total_power = 0.0
    total_soc = 0.0
    soc_count = 0
    any_charging = False
    devices_online = 0
    devices_data = []

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        status_val = await telemetry_cache.get_status(serial)
        is_online = status_val == "online"

        if is_online:
            devices_online += 1

        device_data = DeviceBatteryData(
            serial_number=serial,
            online=is_online,
        )

        if telemetry:
            battery = telemetry.get("battery", {})
            power = telemetry.get("power", {})

            soc = battery.get("soc_pct", 0)
            battery_w = power.get("battery_w", 0)
            charging = battery.get("charging", False)

            total_power += battery_w
            if soc > 0:
                total_soc += soc
                soc_count += 1
            if charging:
                any_charging = True

            device_data = DeviceBatteryData(
                serial_number=serial,
                soc_pct=soc,
                power_w=battery_w,
                is_charging=charging,
                online=is_online,
            )

        devices_data.append(device_data)

    avg_soc = total_soc / soc_count if soc_count > 0 else 0

    return BatteryStatusResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        avg_soc_pct=avg_soc,
        total_power_w=total_power,
        is_charging=any_charging,
        online=devices_online > 0,
        devices_online=devices_online,
        devices_total=len(site_info.device_serials),
        devices=devices_data,
    )


@router.get(
    "/device-status",
    response_model=DeviceStatusResponse,
    summary="Get device status",
    description="Returns status of all devices in the site. Refresh: 30 seconds.",
)
async def get_device_status(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get status of all devices in the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    devices_online = 0
    devices_offline = 0
    total_faults = 0
    total_warnings = 0
    grid_connected = True
    devices_data = []

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        status_val = await telemetry_cache.get_status(serial)
        last_seen = await telemetry_cache.get_last_seen(serial)
        is_online = status_val == "online"

        if is_online:
            devices_online += 1
        else:
            devices_offline += 1

        faults = []
        warnings = []
        working_mode = None

        if telemetry:
            status_info = telemetry.get("status", {})
            faults = status_info.get("faults", [])
            warnings = status_info.get("warnings", [])
            working_mode = status_info.get("working_mode_name")

            if not status_info.get("grid_connected", True):
                grid_connected = False

        total_faults += len(faults)
        total_warnings += len(warnings)

        devices_data.append(DeviceStatusData(
            serial_number=serial,
            status=status_val or "unknown",
            last_seen=last_seen,
            working_mode=working_mode,
            faults=faults,
            warnings=warnings,
            online=is_online,
        ))

    return DeviceStatusResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        devices_online=devices_online,
        devices_offline=devices_offline,
        devices_total=len(site_info.device_serials),
        total_faults=total_faults,
        total_warnings=total_warnings,
        grid_connected=grid_connected,
        devices=devices_data,
    )


@router.get(
    "/alerts",
    response_model=AlertsResponse,
    summary="Get active alerts",
    description="Returns alerts from all devices in the site. Refresh: 60 seconds.",
)
async def get_alerts(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get active alerts aggregated from all devices in the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    all_alerts = []
    critical_count = 0

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)

        if telemetry:
            status_info = telemetry.get("status", {})
            timestamp = telemetry.get("timestamp", datetime.now(timezone.utc).isoformat())

            # Convert faults to alerts
            for i, fault in enumerate(status_info.get("faults", [])):
                all_alerts.append(AlertItem(
                    id=f"{serial}_fault_{i}",
                    serial_number=serial,
                    severity="critical",
                    message=fault,
                    timestamp=timestamp,
                ))
                critical_count += 1

            # Convert warnings to alerts
            for i, warning in enumerate(status_info.get("warnings", [])):
                all_alerts.append(AlertItem(
                    id=f"{serial}_warning_{i}",
                    serial_number=serial,
                    severity="warning",
                    message=warning,
                    timestamp=timestamp,
                ))

    return AlertsResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        active_alerts=all_alerts,
        total_count=len(all_alerts),
        critical_count=critical_count,
    )


@router.get(
    "/environmental",
    response_model=EnvironmentalResponse,
    summary="Get environmental impact",
    description="Returns aggregated environmental metrics for the site. Refresh: 1 hour.",
)
async def get_environmental_impact(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get environmental impact aggregated for the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    total_pv_kwh = 0.0

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        if telemetry:
            energy = telemetry.get("energy_today", {})
            total_pv_kwh += energy.get("pv_kwh", 0)

    # Environmental calculations
    co2_avoided = total_pv_kwh * 0.7
    trees_equivalent = co2_avoided / 0.058 if co2_avoided > 0 else 0
    coal_avoided = total_pv_kwh * 0.4

    return EnvironmentalResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        co2_avoided_kg=round(co2_avoided, 2),
        trees_equivalent=round(trees_equivalent, 2),
        coal_avoided_kg=round(coal_avoided, 2),
    )


@router.get(
    "/energy-chart",
    response_model=EnergyChartResponse,
    summary="Get energy chart data",
    description="Returns aggregated energy data for charts. Refresh: 5 minutes.",
)
async def get_energy_chart(
    period: str = Query("day", description="Period: day, week, month"),
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get energy chart data aggregated for the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    # TODO: Get historical data from TimescaleDB
    # For now, aggregate current day snapshot from all devices
    total_pv = 0.0
    total_load = 0.0
    total_import = 0.0
    total_export = 0.0
    latest_timestamp = datetime.now(timezone.utc).isoformat()

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        if telemetry:
            energy = telemetry.get("energy_today", {})
            total_pv += energy.get("pv_kwh", 0)
            total_load += energy.get("load_kwh", 0)
            total_import += energy.get("grid_import_kwh", 0)
            total_export += energy.get("grid_export_kwh", 0)

            ts = telemetry.get("timestamp")
            if ts:
                latest_timestamp = ts

    data = [EnergyChartPoint(
        timestamp=latest_timestamp,
        pv_kwh=total_pv,
        load_kwh=total_load,
        grid_import_kwh=total_import,
        grid_export_kwh=total_export,
    )] if total_pv > 0 or total_load > 0 else []

    return EnergyChartResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        period=period,
        data=data,
    )


@router.get(
    "/billing",
    response_model=BillingResponse,
    summary="Get billing summary",
    description="Returns aggregated billing data for the site. Refresh: 1 hour.",
)
async def get_billing_summary(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get billing summary aggregated for the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    total_pv_kwh = 0.0
    total_import_kwh = 0.0
    total_export_kwh = 0.0

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        if telemetry:
            energy = telemetry.get("energy_today", {})
            total_pv_kwh += energy.get("pv_kwh", 0)
            total_import_kwh += energy.get("grid_import_kwh", 0)
            total_export_kwh += energy.get("grid_export_kwh", 0)

    # Calculate costs (using PKR rates as example)
    # TODO: Get actual tariff rates from site configuration
    import_rate = 30  # PKR/kWh
    export_rate = 15  # PKR/kWh

    import_cost = total_import_kwh * import_rate
    export_credit = total_export_kwh * export_rate
    savings = total_pv_kwh * import_rate

    return BillingResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        estimated_savings_today=round(savings, 2),
        estimated_savings_month=0,  # TODO: Get from historical data
        grid_import_cost=round(import_cost, 2),
        grid_export_credit=round(export_credit, 2),
    )


@router.get(
    "/all",
    response_model=AllWidgetsResponse,
    summary="Get all widget data",
    description="Returns aggregated data for all widgets. Use for initial load.",
)
async def get_all_widgets(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get all widget data in a single request for initial dashboard load."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    # Aggregate all data in a single pass
    total_pv = 0.0
    total_grid = 0.0
    total_load = 0.0
    total_battery = 0.0
    total_soc = 0.0
    soc_count = 0
    total_energy_today = 0.0
    total_import = 0.0
    total_export = 0.0
    devices_online = 0
    any_charging = False
    grid_connected = True
    latest_timestamp = None
    any_stale = True
    total_faults = 0
    total_warnings = 0

    power_devices = []
    stats_devices = []
    battery_devices = []
    status_devices = []
    all_alerts = []

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        status_val = await telemetry_cache.get_status(serial)
        last_seen = await telemetry_cache.get_last_seen(serial)
        is_online = status_val == "online"

        if is_online:
            devices_online += 1

        # Initialize defaults
        pv_w = 0.0
        grid_w = 0.0
        load_w = 0.0
        battery_w = 0.0
        soc = 0.0
        charging = False
        pv_kwh = 0.0
        faults = []
        warnings = []
        working_mode = None

        if telemetry:
            power = telemetry.get("power", {})
            battery_data = telemetry.get("battery", {})
            status_info = telemetry.get("status", {})
            energy = telemetry.get("energy_today", {})

            pv_w = power.get("pv_total_w", 0)
            grid_w = power.get("grid_w", 0)
            load_w = power.get("load_w", 0)
            battery_w = power.get("battery_w", 0)
            soc = battery_data.get("soc_pct", 0)
            charging = battery_data.get("charging", False)
            pv_kwh = energy.get("pv_kwh", 0)

            total_pv += pv_w
            total_grid += grid_w
            total_load += load_w
            total_battery += battery_w
            total_energy_today += pv_kwh
            total_import += energy.get("grid_import_kwh", 0)
            total_export += energy.get("grid_export_kwh", 0)

            if soc > 0:
                total_soc += soc
                soc_count += 1

            if charging:
                any_charging = True

            if not status_info.get("grid_connected", True):
                grid_connected = False

            ts = telemetry.get("timestamp")
            if ts and (not latest_timestamp or ts > latest_timestamp):
                latest_timestamp = ts

            if not telemetry.get("_stale", True):
                any_stale = False

            faults = status_info.get("faults", [])
            warnings = status_info.get("warnings", [])
            working_mode = status_info.get("working_mode_name")

            total_faults += len(faults)
            total_warnings += len(warnings)

            # Build alerts
            timestamp = telemetry.get("timestamp", datetime.now(timezone.utc).isoformat())
            for i, fault in enumerate(faults):
                all_alerts.append(AlertItem(
                    id=f"{serial}_fault_{i}",
                    serial_number=serial,
                    severity="critical",
                    message=fault,
                    timestamp=timestamp,
                ))
            for i, warning in enumerate(warnings):
                all_alerts.append(AlertItem(
                    id=f"{serial}_warning_{i}",
                    serial_number=serial,
                    severity="warning",
                    message=warning,
                    timestamp=timestamp,
                ))

        # Build per-device data
        power_devices.append(DevicePowerData(
            serial_number=serial,
            pv_power_w=pv_w,
            grid_power_w=grid_w,
            load_power_w=load_w,
            battery_power_w=battery_w,
            battery_soc_pct=soc,
            is_charging=charging,
            online=is_online,
        ))

        stats_devices.append(DeviceStatsData(
            serial_number=serial,
            energy_today_kwh=pv_kwh,
            peak_power_kw=0,
            online=is_online,
        ))

        battery_devices.append(DeviceBatteryData(
            serial_number=serial,
            soc_pct=soc,
            power_w=battery_w,
            is_charging=charging,
            online=is_online,
        ))

        status_devices.append(DeviceStatusData(
            serial_number=serial,
            status=status_val or "unknown",
            last_seen=last_seen,
            working_mode=working_mode,
            faults=faults,
            warnings=warnings,
            online=is_online,
        ))

    avg_soc = total_soc / soc_count if soc_count > 0 else 0
    co2_avoided = total_energy_today * 0.7
    devices_total = len(site_info.device_serials)
    devices_offline = devices_total - devices_online

    return AllWidgetsResponse(
        power_flow=PowerFlowResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            timestamp=latest_timestamp,
            pv_power_w=total_pv,
            grid_power_w=total_grid,
            load_power_w=total_load,
            battery_power_w=total_battery,
            battery_soc_pct=avg_soc,
            is_charging=any_charging,
            grid_connected=grid_connected,
            online=devices_online > 0,
            stale=any_stale,
            devices_online=devices_online,
            devices_total=devices_total,
            devices=power_devices,
        ),
        stats=StatsResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            energy_today_kwh=total_energy_today,
            energy_month_kwh=0,
            peak_power_kw=0,
            co2_saved_kg=co2_avoided,
            online=devices_online > 0,
            devices_online=devices_online,
            devices_total=devices_total,
            devices=stats_devices,
        ),
        battery=BatteryStatusResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            avg_soc_pct=avg_soc,
            total_power_w=total_battery,
            is_charging=any_charging,
            online=devices_online > 0,
            devices_online=devices_online,
            devices_total=devices_total,
            devices=battery_devices,
        ),
        device_status=DeviceStatusResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            devices_online=devices_online,
            devices_offline=devices_offline,
            devices_total=devices_total,
            total_faults=total_faults,
            total_warnings=total_warnings,
            grid_connected=grid_connected,
            devices=status_devices,
        ),
        alerts=AlertsResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            active_alerts=all_alerts,
            total_count=len(all_alerts),
            critical_count=sum(1 for a in all_alerts if a.severity == "critical"),
        ),
        environmental=EnvironmentalResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            co2_avoided_kg=round(co2_avoided, 2),
            trees_equivalent=round(co2_avoided / 0.058, 2) if co2_avoided > 0 else 0,
            coal_avoided_kg=round(total_energy_today * 0.4, 2),
        ),
        billing=BillingResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            estimated_savings_today=round(total_energy_today * 30, 2),
            estimated_savings_month=0,
            grid_import_cost=round(total_import * 30, 2),
            grid_export_credit=round(total_export * 15, 2),
        ),
    )
