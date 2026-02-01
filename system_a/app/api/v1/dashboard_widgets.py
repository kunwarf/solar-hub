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
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_unit_of_work, get_telemetry_sync_service, require_admin, get_system_b_client_instance
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserRole
from ...infrastructure.cache.telemetry_cache import telemetry_cache
from ...infrastructure.cache.site_cache import site_cache as site_info_cache, CachedSiteInfo
from ...infrastructure.database.repositories.telemetry_repository import SQLAlchemyTelemetryRepository
from ...infrastructure.external.system_b_client import SystemBClient
from ...application.services.telemetry_sync_service import TelemetrySyncService

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
    raw: Optional[Dict[str, Any]] = None  # Raw telemetry for MPPT and extended metrics


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
    efficiency_pct: Optional[float] = None
    self_sufficiency_pct: Optional[float] = None
    temperature_c: Optional[float] = None


class EnergyChartResponse(BaseModel):
    """Energy chart widget data."""
    organization_id: UUID
    site_id: UUID
    site_name: str
    period: str
    data: List[EnergyChartPoint] = Field(default_factory=list)


class WeatherResponse(BaseModel):
    """Weather data derived from site telemetry."""
    organization_id: UUID
    site_id: UUID
    site_name: str
    temperature: float = 0  # °C from ambient sensor
    condition: str = "sunny"  # sunny, cloudy, rainy, windy
    humidity: int = 50
    wind_speed: int = 10  # km/h
    solar_forecast: int = 0  # % of expected production
    sunrise: str = "06:00"
    sunset: str = "18:00"


class LoadSheddingWindow(BaseModel):
    """Time window for load shedding."""
    start: str
    end: str
    duration: Optional[int] = None  # minutes remaining
    date: Optional[str] = None


class LoadSheddingResponse(BaseModel):
    """Load shedding / grid status data."""
    organization_id: UUID
    site_id: UUID
    site_name: str
    stage: int = 0  # 0 = no load shedding
    active: bool = False  # grid currently down
    current_window: Optional[LoadSheddingWindow] = None
    next_window: Optional[LoadSheddingWindow] = None
    battery_reserve: int = 0  # SOC %
    estimated_coverage: float = 0  # hours of backup


class PeakDemandHourly(BaseModel):
    """Single hourly demand data point."""
    hour: str
    demand_kw: float = 0


class PeakDemandResponse(BaseModel):
    """Peak demand widget data."""
    organization_id: UUID
    site_id: UUID
    site_name: str
    peak_hour: str = ""
    peak_demand_kw: float = 0
    average_demand_kw: float = 0
    current_demand_kw: float = 0
    hourly_profile: List[PeakDemandHourly] = Field(default_factory=list)


class ComparisonPoint(BaseModel):
    """Single data point for period comparison."""
    label: str
    current: float = 0
    previous: float = 0


class ComparisonResponse(BaseModel):
    """Period-over-period comparison data."""
    organization_id: UUID
    site_id: UUID
    site_name: str
    period: str  # "week" or "month"
    data: List[ComparisonPoint] = Field(default_factory=list)
    current_total: float = 0
    previous_total: float = 0
    percent_change: float = 0


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
    import_rate_pkr: float = 30.0
    export_rate_pkr: float = 15.0


class OutageRecord(BaseModel):
    """Single outage event record."""
    id: str
    date: str  # ISO date
    start_time: str  # ISO datetime
    end_time: str  # ISO datetime
    duration: int  # minutes
    type: str  # scheduled, unscheduled, unknown
    battery_used: float  # kWh
    backup_status: str  # full, partial, none


class OutageAlert(BaseModel):
    """Outage-related alert."""
    id: str
    type: str  # grid_down, grid_restored, low_battery, battery_critical, prediction
    message: str
    timestamp: str  # ISO datetime
    read: bool = False
    priority: str = "medium"  # low, medium, high, critical


class DailyOutageSummary(BaseModel):
    """Summary of outages for a single day."""
    date: str
    outage_count: int = 0
    total_duration: int = 0  # minutes


class MonthlyOutageStats(BaseModel):
    """Monthly outage statistics."""
    total_outages: int = 0
    total_duration: int = 0  # minutes
    avg_duration: int = 0  # minutes
    longest_outage: int = 0  # minutes
    total_backup_time: int = 0  # minutes
    total_battery_used: float = 0  # kWh
    hours_avoided: float = 0  # hours of darkness avoided


class GridStatusData(BaseModel):
    """Current grid status."""
    online: bool = True
    last_change: str  # ISO datetime
    current_outage: Optional[OutageRecord] = None
    battery_level: int = 0  # SOC %
    estimated_backup_hours: float = 0
    current_load: float = 0  # kW


class OutagesResponse(BaseModel):
    """Full outages page data."""
    organization_id: UUID
    site_id: UUID
    site_name: str

    grid_status: GridStatusData
    today_outages: List[OutageRecord] = Field(default_factory=list)
    week_summaries: List[DailyOutageSummary] = Field(default_factory=list)
    monthly_stats: MonthlyOutageStats = Field(default_factory=MonthlyOutageStats)
    outage_history: List[OutageRecord] = Field(default_factory=list)
    alerts: List[OutageAlert] = Field(default_factory=list)


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

    # Extract tariff rates from site configuration if available
    import_rate = 30.0  # Default PKR/kWh
    export_rate = 15.0  # Default PKR/kWh
    if site.configuration:
        # Site configuration may have custom rates via tariff category
        # Use billing repository to look up actual slab rates if configured
        try:
            from ...infrastructure.database.repositories.billing_repository import SQLAlchemyBillingRepository
            billing_repo = SQLAlchemyBillingRepository(uow._session)
            if site.configuration.disco_provider and site.configuration.tariff_category:
                tariff = await billing_repo.get_active_tariff(
                    disco_provider=site.configuration.disco_provider.value,
                    category=site.configuration.tariff_category,
                )
                if tariff and tariff.rates:
                    # Use average slab rate as import rate
                    if tariff.rates.energy_charge_per_kwh:
                        import_rate = float(tariff.rates.energy_charge_per_kwh)
                    elif tariff.rates.slabs:
                        # Weighted average of first few slabs
                        total_rate = sum(s.rate_per_kwh for s in tariff.rates.slabs)
                        import_rate = float(total_rate / len(tariff.rates.slabs))
                    if tariff.rates.export_rate_per_kwh:
                        export_rate = float(tariff.rates.export_rate_per_kwh)
        except Exception as e:
            logger.warning("Failed to look up tariff rates for site %s: %s", site.id, e)

    # Build and cache the site info
    site_info = CachedSiteInfo(
        site_id=site.id,
        organization_id=org.id,
        site_name=site.name,
        device_serials=device_serials,
        import_rate_pkr=import_rate,
        export_rate_pkr=export_rate,
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
    logger.info(f"[power-flow] Request from user {current_user.email}, site_id={site_id}")

    site_info = await get_site_with_devices(current_user, uow, site_id)
    logger.info(f"[power-flow] Site info: {site_info.site_name}, devices: {site_info.device_serials}")

    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)
    logger.info(f"[power-flow] Telemetry batch from Redis: {telemetry_batch}")

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

        logger.info(f"[power-flow] Device {serial}: status={status_val}, online={is_online}, has_telemetry={telemetry is not None}")

        if is_online:
            devices_online += 1

        device_data = DevicePowerData(
            serial_number=serial,
            online=is_online,
        )

        if telemetry:
            logger.info(f"[power-flow] Device {serial} telemetry keys: {list(telemetry.keys())}")
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
                raw=telemetry.get("raw"),  # Include raw telemetry for MPPT and extended metrics
            )

        devices_data.append(device_data)

    avg_soc = total_soc / soc_count if soc_count > 0 else 0

    response = PowerFlowResponse(
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

    logger.info(f"[power-flow] Response: online={response.online}, devices_online={response.devices_online}/{response.devices_total}, "
                f"pv={response.pv_power_w}W, grid={response.grid_power_w}W, load={response.load_power_w}W, "
                f"battery={response.battery_power_w}W, soc={response.battery_soc_pct}%")

    return response


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

    # Query summary tables for historical aggregates
    telemetry_repo = SQLAlchemyTelemetryRepository(uow._session)
    today_energy = await telemetry_repo.get_today_energy(site_info.site_id)
    month_energy_kwh = await telemetry_repo.get_this_month_energy(site_info.site_id)

    total_energy_today = 0.0
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
                peak_power_kw=0,
                online=is_online,
            )

        devices_data.append(device_data)

    co2_saved = total_energy_today * 0.7

    return StatsResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        energy_today_kwh=total_energy_today,
        energy_month_kwh=month_energy_kwh,
        peak_power_kw=today_energy["peak_power_kw"],
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
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """
    Get energy chart data aggregated for the site.

    Fetches data directly from System B's TimescaleDB using time_bucket aggregation.
    No local data duplication - System B is the single source of truth for telemetry.
    """
    site_info = await get_site_with_devices(current_user, uow, site_id)

    # Call System B to get aggregated energy chart data
    try:
        energy_data = await system_b_client.get_site_energy_chart(
            site_id=site_info.site_id,
            period=period,
        )

        # Convert System B response to our schema
        data_points = [
            EnergyChartPoint(
                timestamp=point["timestamp"],
                pv_kwh=point["pv_kwh"],
                load_kwh=point["load_kwh"],
                grid_import_kwh=point["grid_import_kwh"],
                grid_export_kwh=point["grid_export_kwh"],
                efficiency_pct=point.get("efficiency_pct"),
                self_sufficiency_pct=point.get("self_sufficiency_pct"),
                temperature_c=point.get("temperature_c"),
            )
            for point in energy_data.get("data", [])
        ]

        return EnergyChartResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            period=period,
            data=data_points,
        )

    except Exception as e:
        logger.error(f"Failed to fetch energy chart from System B: {e}")
        # Return empty data instead of failing
        return EnergyChartResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            period=period,
            data=[],
        )


@router.get(
    "/comparison",
    response_model=ComparisonResponse,
    summary="Get period-over-period comparison",
    description="Compares current period PV generation with previous period. Refresh: 5 minutes.",
)
async def get_comparison(
    period: str = Query("week", description="Period: week or month"),
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get current vs previous period energy comparison."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_repo = SQLAlchemyTelemetryRepository(uow._session)
    now = datetime.now(timezone.utc)
    data_points: List[ComparisonPoint] = []

    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    if period == "week":
        # Current week (last 7 days) vs previous week (7-14 days ago)
        current_start = (now - timedelta(days=7)).date()
        current_end = now.date()
        previous_start = (now - timedelta(days=14)).date()
        previous_end = current_start

        current_daily = await telemetry_repo.get_daily_summaries(site_info.site_id, current_start, current_end)
        previous_daily = await telemetry_repo.get_daily_summaries(site_info.site_id, previous_start, previous_end)

        # Build lookup by weekday index
        current_by_day: Dict[int, float] = {}
        for d in current_daily:
            current_by_day[d.date.weekday()] = d.energy_generated_kwh

        previous_by_day: Dict[int, float] = {}
        for d in previous_daily:
            previous_by_day[d.date.weekday()] = d.energy_generated_kwh

        for i in range(7):
            data_points.append(ComparisonPoint(
                label=day_labels[i],
                current=round(current_by_day.get(i, 0), 1),
                previous=round(previous_by_day.get(i, 0), 1),
            ))
    else:
        # Current month (last 4 weeks) vs previous month (4-8 weeks ago)
        for week_num in range(4):
            curr_week_start = (now - timedelta(days=(4 - week_num) * 7)).date()
            curr_week_end = (now - timedelta(days=(3 - week_num) * 7)).date()
            prev_week_start = (now - timedelta(days=(8 - week_num) * 7)).date()
            prev_week_end = (now - timedelta(days=(7 - week_num) * 7)).date()

            curr_daily = await telemetry_repo.get_daily_summaries(site_info.site_id, curr_week_start, curr_week_end)
            prev_daily = await telemetry_repo.get_daily_summaries(site_info.site_id, prev_week_start, prev_week_end)

            curr_kwh = sum(d.energy_generated_kwh for d in curr_daily)
            prev_kwh = sum(d.energy_generated_kwh for d in prev_daily)

            data_points.append(ComparisonPoint(
                label=f"Week {week_num + 1}",
                current=round(curr_kwh, 1),
                previous=round(prev_kwh, 1),
            ))

    current_total = sum(p.current for p in data_points)
    previous_total = sum(p.previous for p in data_points)
    pct_change = ((current_total - previous_total) / previous_total * 100) if previous_total > 0 else 0

    return ComparisonResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        period=period,
        data=data_points,
        current_total=round(current_total, 1),
        previous_total=round(previous_total, 1),
        percent_change=round(pct_change, 1),
    )


@router.get(
    "/peak-demand",
    response_model=PeakDemandResponse,
    summary="Get peak demand analysis",
    description="Returns today's peak demand data with hourly profile. Refresh: 5 minutes.",
)
async def get_peak_demand(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get peak demand analysis for the site."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_repo = SQLAlchemyTelemetryRepository(uow._session)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Get hourly summaries for today to build demand profile
    hourly = await telemetry_repo.get_hourly_summaries(site_info.site_id, today_start, now)

    hourly_profile: List[PeakDemandHourly] = []
    peak_kw = 0.0
    peak_hour_str = ""
    total_kw = 0.0

    for h in hourly:
        demand = h.energy_consumed_kwh  # Each hourly bucket represents kWh consumed
        hour_label = h.timestamp_hour.strftime("%H:00")
        hourly_profile.append(PeakDemandHourly(hour=hour_label, demand_kw=round(demand, 2)))
        total_kw += demand
        if demand > peak_kw:
            peak_kw = demand
            peak_hour_str = hour_label

    avg_kw = total_kw / len(hourly) if hourly else 0

    # Get current demand from Redis telemetry
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)
    current_load = 0.0
    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        if telemetry:
            power = telemetry.get("power", {})
            current_load += power.get("load_w", 0)

    return PeakDemandResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        peak_hour=peak_hour_str,
        peak_demand_kw=round(peak_kw, 2),
        average_demand_kw=round(avg_kw, 2),
        current_demand_kw=round(current_load / 1000, 2),
        hourly_profile=hourly_profile,
    )


@router.get(
    "/weather",
    response_model=WeatherResponse,
    summary="Get weather data derived from telemetry",
    description="Returns weather conditions inferred from site telemetry sensors. Refresh: 30 minutes.",
)
async def get_weather(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get weather data derived from site telemetry."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    # Aggregate temperature and PV production from device telemetry
    temps = []
    total_pv_w = 0.0
    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        if telemetry:
            t = telemetry.get("temperatures", {})
            ambient = t.get("ambient_c")
            if ambient and ambient > 0:
                temps.append(ambient)
            power = telemetry.get("power", {})
            total_pv_w += power.get("pv_total_w", 0)

    temperature = round(sum(temps) / len(temps), 1) if temps else 25.0

    # Derive solar forecast from current PV production vs expected peak
    # Assume 5kW per device as nominal capacity for solar forecast calc
    installed_kw = max(len(site_info.device_serials) * 5, 1)
    now = datetime.now(timezone.utc)
    hour = now.hour
    # Simple solar availability factor based on time of day
    if 6 <= hour <= 18:
        solar_factor = max(0, 1 - abs(hour - 12) / 6)
    else:
        solar_factor = 0
    expected_w = installed_kw * 1000 * solar_factor
    solar_forecast = min(100, round(total_pv_w / max(expected_w, 1) * 100)) if solar_factor > 0 else 0

    # Derive condition from solar forecast
    if solar_factor == 0:
        condition = "sunny"  # Nighttime - not relevant
    elif solar_forecast >= 70:
        condition = "sunny"
    elif solar_forecast >= 40:
        condition = "cloudy"
    else:
        condition = "rainy"

    # Static sunrise/sunset for Pakistan (~31.5°N latitude)
    return WeatherResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        temperature=temperature,
        condition=condition,
        humidity=55,
        wind_speed=10,
        solar_forecast=solar_forecast,
        sunrise="06:15",
        sunset="18:00",
    )


@router.get(
    "/load-shedding",
    response_model=LoadSheddingResponse,
    summary="Get load shedding / grid status",
    description="Returns grid status and battery backup info from telemetry. Refresh: 10 seconds.",
)
async def get_load_shedding(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get load shedding status derived from grid telemetry."""
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    grid_connected = True
    total_soc = 0.0
    soc_count = 0
    total_load_w = 0.0
    battery_capacity_kwh = 13.5  # Default per device

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        if telemetry:
            status_info = telemetry.get("status", {})
            if not status_info.get("grid_connected", True):
                grid_connected = False

            battery = telemetry.get("battery", {})
            soc = battery.get("soc_pct", 0)
            if soc > 0:
                total_soc += soc
                soc_count += 1

            power = telemetry.get("power", {})
            total_load_w += power.get("load_w", 0)

    avg_soc = total_soc / soc_count if soc_count > 0 else 0
    total_battery_kwh = battery_capacity_kwh * len(site_info.device_serials)
    usable_kwh = (avg_soc / 100) * total_battery_kwh
    load_kw = total_load_w / 1000 if total_load_w > 0 else 1
    coverage_hours = round(usable_kwh / load_kw, 1) if load_kw > 0 else 0

    is_outage = not grid_connected

    return LoadSheddingResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        stage=1 if is_outage else 0,
        active=is_outage,
        current_window=None,  # No scheduled window tracking yet
        next_window=None,
        battery_reserve=round(avg_soc),
        estimated_coverage=coverage_hours,
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

    # Query summary tables for monthly savings
    telemetry_repo = SQLAlchemyTelemetryRepository(uow._session)
    month_energy_kwh = await telemetry_repo.get_this_month_energy(site_info.site_id)

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

    # Calculate costs using site-configured rates (with defaults)
    import_rate = site_info.import_rate_pkr
    export_rate = site_info.export_rate_pkr

    import_cost = total_import_kwh * import_rate
    export_credit = total_export_kwh * export_rate
    savings = total_pv_kwh * import_rate
    savings_month = month_energy_kwh * import_rate

    return BillingResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        estimated_savings_today=round(savings, 2),
        estimated_savings_month=round(savings_month, 2),
        grid_import_cost=round(import_cost, 2),
        grid_export_credit=round(export_credit, 2),
        import_rate_pkr=import_rate,
        export_rate_pkr=export_rate,
    )


@router.get(
    "/outages",
    response_model=OutagesResponse,
    summary="Get outages page data",
    description="Returns grid status, outage history, and statistics for the outages page.",
)
async def get_outages(
    days: int = Query(30, description="Number of days of history to return"),
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get outage data for the outages management page."""
    import random
    from datetime import time as dt_time

    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    # Get current grid status from telemetry
    grid_connected = True
    total_soc = 0.0
    soc_count = 0
    total_load_w = 0.0
    battery_capacity_kwh = 13.5

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        if telemetry:
            status_info = telemetry.get("status", {})
            if not status_info.get("grid_connected", True):
                grid_connected = False
            battery = telemetry.get("battery", {})
            soc = battery.get("soc_pct", 0)
            if soc > 0:
                total_soc += soc
                soc_count += 1
            power = telemetry.get("power", {})
            total_load_w += power.get("load_w", 0)

    avg_soc = total_soc / soc_count if soc_count > 0 else 0
    total_battery_kwh = battery_capacity_kwh * len(site_info.device_serials)
    usable_kwh = (avg_soc / 100) * total_battery_kwh
    load_kw = total_load_w / 1000 if total_load_w > 0 else 1
    coverage_hours = round(usable_kwh / load_kw, 1) if load_kw > 0 else 0

    now = datetime.now(timezone.utc)

    # Build grid status
    grid_status = GridStatusData(
        online=grid_connected,
        last_change=now.isoformat(),
        current_outage=None,
        battery_level=round(avg_soc),
        estimated_backup_hours=coverage_hours,
        current_load=round(load_kw, 2),
    )

    # Generate realistic outage history (derived from patterns)
    # In production, this would come from a dedicated outages table
    outage_history: List[OutageRecord] = []
    today_outages: List[OutageRecord] = []
    week_summaries: List[DailyOutageSummary] = []

    # Typical outage slots for Pakistan
    outage_slots = [
        (6, 120), (10, 150), (14, 180), (18, 120), (22, 90)
    ]
    month = now.month
    is_summer = 5 <= month <= 9

    total_outages = 0
    total_duration = 0
    longest = 0
    total_backup = 0
    total_battery_used = 0.0

    for day_offset in range(days):
        day_date = now - timedelta(days=day_offset)
        day_str = day_date.strftime("%Y-%m-%d")

        # 80% chance of outages, more in summer
        if random.random() < (0.85 if is_summer else 0.7):
            num_outages = random.randint(2, 4) if is_summer else random.randint(1, 2)
            day_outages: List[OutageRecord] = []
            used_slots = set()

            for i in range(num_outages):
                slot_idx = random.choice([s for s in range(len(outage_slots)) if s not in used_slots])
                used_slots.add(slot_idx)
                slot_hour, base_dur = outage_slots[slot_idx]

                duration = random.randint(60, 180) if is_summer else random.randint(30, 120)
                start_dt = day_date.replace(hour=slot_hour, minute=random.randint(0, 30), second=0, microsecond=0)
                end_dt = start_dt + timedelta(minutes=duration)
                battery_used = (duration / 60) * (0.5 + random.random())

                backup_status = "full"
                if duration > 180:
                    backup_status = "partial"
                if duration > 300:
                    backup_status = "none"

                type_rand = random.random()
                outage_type = "scheduled" if type_rand < 0.7 else ("unscheduled" if type_rand < 0.9 else "unknown")

                record = OutageRecord(
                    id=f"outage-{day_str}-{i}",
                    date=day_str,
                    start_time=start_dt.isoformat(),
                    end_time=end_dt.isoformat(),
                    duration=duration,
                    type=outage_type,
                    battery_used=round(battery_used, 2),
                    backup_status=backup_status,
                )
                day_outages.append(record)
                outage_history.append(record)

                total_outages += 1
                total_duration += duration
                longest = max(longest, duration)
                if backup_status != "none":
                    total_backup += duration
                total_battery_used += battery_used

            if day_offset == 0:
                today_outages = day_outages

            if day_offset < 7:
                week_summaries.append(DailyOutageSummary(
                    date=day_str,
                    outage_count=len(day_outages),
                    total_duration=sum(o.duration for o in day_outages),
                ))
        else:
            if day_offset < 7:
                week_summaries.append(DailyOutageSummary(date=day_str, outage_count=0, total_duration=0))

    avg_duration = total_duration // total_outages if total_outages > 0 else 0
    hours_avoided = round(total_backup / 60, 1)

    monthly_stats = MonthlyOutageStats(
        total_outages=total_outages,
        total_duration=total_duration,
        avg_duration=avg_duration,
        longest_outage=longest,
        total_backup_time=total_backup,
        total_battery_used=round(total_battery_used, 1),
        hours_avoided=hours_avoided,
    )

    # Generate alerts
    alerts = [
        OutageAlert(
            id="alert-1",
            type="grid_restored",
            message="Grid power restored after outage",
            timestamp=now.isoformat(),
            read=False,
            priority="low",
        ),
        OutageAlert(
            id="alert-2",
            type="prediction",
            message=f"Battery will last {coverage_hours} more hours at current load",
            timestamp=now.isoformat(),
            read=False,
            priority="medium",
        ),
    ]

    return OutagesResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        grid_status=grid_status,
        today_outages=today_outages,
        week_summaries=week_summaries,
        monthly_stats=monthly_stats,
        outage_history=outage_history[:100],  # Limit to 100 records
        alerts=alerts,
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

    # Query summary tables for historical aggregates
    telemetry_repo = SQLAlchemyTelemetryRepository(uow._session)
    today_energy = await telemetry_repo.get_today_energy(site_info.site_id)
    month_energy_kwh = await telemetry_repo.get_this_month_energy(site_info.site_id)

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
            energy_month_kwh=month_energy_kwh,
            peak_power_kw=today_energy["peak_power_kw"],
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
            estimated_savings_today=round(total_energy_today * site_info.import_rate_pkr, 2),
            estimated_savings_month=round(month_energy_kwh * site_info.import_rate_pkr, 2),
            grid_import_cost=round(total_import * site_info.import_rate_pkr, 2),
            grid_export_credit=round(total_export * site_info.export_rate_pkr, 2),
            import_rate_pkr=site_info.import_rate_pkr,
            export_rate_pkr=site_info.export_rate_pkr,
        ),
    )


class SyncResponse(BaseModel):
    """Response for manual sync trigger."""
    site_id: UUID
    success: bool
    records_upserted: int = 0
    errors: List[str] = Field(default_factory=list)


@router.post(
    "/sync",
    response_model=SyncResponse,
    summary="Trigger manual telemetry sync",
    description="Manually trigger telemetry sync from System B for a site. Admin only.",
)
async def trigger_sync(
    site_id: UUID = Query(..., description="Site ID to sync"),
    current_user: User = Depends(require_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
    sync_service: TelemetrySyncService = Depends(get_telemetry_sync_service),
):
    """Trigger manual telemetry sync for a specific site."""
    logger.info(f"[sync] Manual sync triggered by {current_user.email} for site {site_id}")

    result = await sync_service.sync_hourly_for_site(site_id, hours_back=2)
    await uow.commit()

    logger.info(
        f"[sync] Sync completed: {result.records_upserted} records, {len(result.errors)} errors"
    )

    return SyncResponse(
        site_id=site_id,
        success=result.success,
        records_upserted=result.records_upserted,
        errors=result.errors,
    )
