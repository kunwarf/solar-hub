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
import asyncio
import logging
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_unit_of_work, get_telemetry_sync_service, require_admin, get_system_b_client_instance
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserRole
from ...domain.services.weather_service import weather_service
from ...infrastructure.cache.telemetry_cache import telemetry_cache
from ...infrastructure.cache.site_cache import site_cache as site_info_cache, CachedSiteInfo
from ...infrastructure.database.repositories.telemetry_repository import SQLAlchemyTelemetryRepository
from ...infrastructure.external.system_b_client import SystemBClient
from ...application.services.telemetry_sync_service import TelemetrySyncService

logger = logging.getLogger(__name__)


def calculate_sunrise_sunset(latitude: float, longitude: float, date_utc: datetime) -> tuple[str, str]:
    """
    Calculate sunrise and sunset times for a given location and date.

    Uses simplified algorithm (accurate to within ~10 minutes for mid-latitudes).
    Returns times in HH:MM format in local solar time.

    Args:
        latitude: Site latitude in degrees
        longitude: Site longitude in degrees
        date_utc: Date for calculation (UTC)

    Returns:
        Tuple of (sunrise_time, sunset_time) as HH:MM strings
    """
    # Day of year
    day_of_year = date_utc.timetuple().tm_yday

    # Solar declination angle (degrees)
    declination = 23.45 * math.sin(math.radians((360 / 365) * (day_of_year + 284)))

    # Hour angle at sunrise/sunset
    lat_rad = math.radians(latitude)
    dec_rad = math.radians(declination)

    try:
        cos_hour_angle = -math.tan(lat_rad) * math.tan(dec_rad)
        # Clamp to valid range to avoid domain errors
        cos_hour_angle = max(-1, min(1, cos_hour_angle))
        hour_angle = math.degrees(math.acos(cos_hour_angle))
    except (ValueError, ZeroDivisionError):
        # Polar regions or edge cases - use defaults
        return ("06:00", "18:00")

    # Solar noon (in decimal hours, UTC)
    solar_noon_utc = 12 - (longitude / 15)

    # Sunrise and sunset (decimal hours, UTC)
    sunrise_utc = solar_noon_utc - (hour_angle / 15)
    sunset_utc = solar_noon_utc + (hour_angle / 15)

    # Convert to HH:MM format
    def decimal_to_time(decimal_hour: float) -> str:
        # Normalize to 0-24 range
        decimal_hour = decimal_hour % 24
        hours = int(decimal_hour)
        minutes = int((decimal_hour - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"

    return (decimal_to_time(sunrise_utc), decimal_to_time(sunset_utc))

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


class MaxMetric(BaseModel):
    """A single peak metric with the value and when it occurred."""
    value_kw: float
    occurred_at: datetime


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

    # Energy flows (from today's aggregate data)
    load_energy_today_kwh: float = 0
    grid_import_today_kwh: float = 0
    grid_export_today_kwh: float = 0
    devices_total: int = 0

    # Today's peak instantaneous metrics
    max_pv_today: Optional[MaxMetric] = None
    max_load_today: Optional[MaxMetric] = None
    max_export_today: Optional[MaxMetric] = None
    max_import_today: Optional[MaxMetric] = None

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
    wind_speed: float = 10.0  # m/s
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
    site_info = await get_site_with_devices(current_user, uow, site_id)

    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)
    logger.info(
        "[power-flow] site=%s user=%s devices=%d with_data=%d",
        site_info.site_name,
        current_user.email,
        len(site_info.device_serials),
        sum(1 for s in site_info.device_serials if telemetry_batch.get(s)),
    )
    logger.debug(f"[power-flow] Telemetry batch from Redis: {telemetry_batch}")

    # Aggregate power data
    total_pv = 0.0
    total_grid = 0.0
    total_load = 0.0
    total_soc = 0.0
    soc_count = 0
    devices_online = 0
    any_charging = False
    grid_connected = True
    latest_timestamp = None
    any_stale = True
    devices_data = []

    # Separate battery_w by device type to avoid double-counting.
    # Inverter devices measure the total power on their DC bus — the same
    # physical power that the individual battery devices (JK BMS, Pylontech)
    # each measure independently.  Summing both gives ~2× the true value.
    # Strategy: prefer battery/BMS device measurements; fall back to inverter
    # only when no dedicated battery device has reported power.
    battery_device_battery_w = 0.0   # from battery/BMS type devices
    inverter_device_battery_w = 0.0  # from inverter type devices
    has_battery_device_power = False  # at least one battery device with non-zero battery_w

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        status_val = await telemetry_cache.get_status(serial)
        is_online = status_val == "online"

        logger.debug(f"[power-flow] Device {serial}: status={status_val}, online={is_online}, has_telemetry={telemetry is not None}")

        if is_online:
            devices_online += 1

        device_data = DevicePowerData(
            serial_number=serial,
            online=is_online,
        )

        if telemetry:
            logger.debug(f"[power-flow] Device {serial} telemetry keys: {list(telemetry.keys())}")
            power = telemetry.get("power", {})
            battery = telemetry.get("battery", {})
            status_info = telemetry.get("status", {})
            device_type = (telemetry.get("device_type") or "").lower()

            pv_w = power.get("pv_total_w", 0)
            grid_w = power.get("grid_w", 0)
            load_w = power.get("load_w", 0)
            battery_w = power.get("battery_w", 0)
            soc = battery.get("soc_pct", 0)
            charging = battery.get("charging", False)

            total_pv += pv_w
            total_grid += grid_w
            total_load += load_w

            # Bucket battery_w by device type — aggregated after the loop
            if "inverter" in device_type or "meter" in device_type:
                inverter_device_battery_w += battery_w
            else:
                # battery, bms, or unknown — treat as direct battery measurement
                battery_device_battery_w += battery_w
                if battery_w != 0:
                    has_battery_device_power = True

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

    # Use battery device measurements when available (direct, no double-counting).
    # Fall back to inverter measurement only when no dedicated battery device reported.
    total_battery = battery_device_battery_w if has_battery_device_power else inverter_device_battery_w
    logger.info(
        f"[power-flow] battery_w: battery_devices={battery_device_battery_w:.0f}W "
        f"inverter_devices={inverter_device_battery_w:.0f}W "
        f"has_battery_device_power={has_battery_device_power} → total={total_battery:.0f}W"
    )

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
        is_charging=total_battery > 0,  # derive from sign, not OR across devices
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
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """
    Get statistics data aggregated for the site.

    Fetches energy totals from System B's TimescaleDB.
    """
    from ...domain.services.timezone_utils import TimezoneUtils

    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    # Resolve site timezone for "today" boundaries
    site_entity = await uow.sites.get_by_id(site_info.site_id)
    site_timezone = "UTC"
    if site_entity and site_entity.timezone:
        site_timezone = site_entity.timezone
    else:
        logger.warning("Site %s has no timezone configured; using UTC for daily peaks", site_info.site_id)

    today_local = TimezoneUtils.get_date_in_timezone(datetime.now(timezone.utc), site_timezone)
    today_start_utc, today_end_utc = TimezoneUtils.get_local_date_range(today_local, site_timezone)

    # Fetch today's and this month's energy from System B
    total_energy_today_kwh = 0.0
    month_energy_kwh = 0.0
    peak_power_kw = 0.0
    load_energy_today_kwh = 0.0
    grid_import_today_kwh = 0.0
    grid_export_today_kwh = 0.0

    # Today's peak metrics (populated below)
    max_pv_today: Optional[MaxMetric] = None
    max_load_today: Optional[MaxMetric] = None
    max_export_today: Optional[MaxMetric] = None
    max_import_today: Optional[MaxMetric] = None

    try:
        # Get today's hourly data
        today_data = await system_b_client.get_site_energy_chart(
            site_id=site_info.site_id,
            period="day",
        )
        for point in today_data.get("data", []):
            pv_kwh = point.get("pv_kwh", 0)
            total_energy_today_kwh += pv_kwh
            # Peak power is the max hourly generation (approximate)
            peak_power_kw = max(peak_power_kw, pv_kwh)
            # Sum up load and grid flows
            load_energy_today_kwh += point.get("load_kwh", 0)
            grid_import_today_kwh += point.get("grid_import_kwh", 0)
            grid_export_today_kwh += point.get("grid_export_kwh", 0)

        # Get this month's daily data
        month_data = await system_b_client.get_site_energy_chart(
            site_id=site_info.site_id,
            period="month",
        )
        for point in month_data.get("data", []):
            month_energy_kwh += point.get("pv_kwh", 0)

        # Get today's peak instantaneous metrics
        peaks_data = await system_b_client.get_site_daily_peaks(
            site_id=site_info.site_id,
            start_time=today_start_utc,
            end_time=today_end_utc,
        )
        peaks = peaks_data.get("peaks", {})

        def _parse_peak(raw: dict) -> Optional[MaxMetric]:
            if not raw or raw.get("value_w") is None:
                return None
            return MaxMetric(
                value_kw=round(raw["value_w"] / 1000, 3),
                occurred_at=datetime.fromisoformat(raw["occurred_at"]),
            )

        max_pv_today = _parse_peak(peaks.get("pv", {}))
        max_load_today = _parse_peak(peaks.get("load", {}))
        max_export_today = _parse_peak(peaks.get("export", {}))
        max_import_today = _parse_peak(peaks.get("import", {}))

    except Exception as e:
        logger.error(f"Failed to fetch stats from System B: {e}")

    devices_online = 0
    devices_data = []
    redis_grid_export_kwh = 0.0

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

            device_data = DeviceStatsData(
                serial_number=serial,
                energy_today_kwh=pv_kwh,
                peak_power_kw=0,
                online=is_online,
            )

            # Accumulate grid export from raw inverter counters as a fallback
            raw = telemetry.get("raw", {})
            redis_grid_export_kwh += float(raw.get("grid_export_energy_today_kwh", 0) or 0)

        devices_data.append(device_data)

    # System B often returns 0 for grid_export; use Redis raw counters when that happens
    if grid_export_today_kwh == 0 and redis_grid_export_kwh > 0:
        grid_export_today_kwh = redis_grid_export_kwh

    co2_saved = total_energy_today_kwh * 0.7

    return StatsResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        energy_today_kwh=total_energy_today_kwh,
        energy_month_kwh=month_energy_kwh,
        peak_power_kw=peak_power_kw,
        co2_saved_kg=co2_saved,
        online=devices_online > 0,
        devices_online=devices_online,
        devices_total=len(site_info.device_serials),
        devices=devices_data,
        load_energy_today_kwh=load_energy_today_kwh,
        grid_import_today_kwh=grid_import_today_kwh,
        grid_export_today_kwh=grid_export_today_kwh,
        max_pv_today=max_pv_today,
        max_load_today=max_load_today,
        max_export_today=max_export_today,
        max_import_today=max_import_today,
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
        is_charging=total_power > 0,  # derive from sign, not OR across devices
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

    Note on Historical Data Quality:
    - Data before 2026-02-03 may contain negative energy values due to midnight
      counter resets in the aggregate calculation (fixed in migration 20260203_1300)
    - To refresh historical data with the fix applied, run:
      CALL refresh_continuous_aggregate('telemetry_hourly_local',
        NOW() - INTERVAL '60 days', NOW());
    - New data automatically uses the corrected calculation (GREATEST(0, LAST - FIRST))
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
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """
    Get current vs previous period energy comparison.

    Fetches daily aggregated data from System B for period-over-period analysis.
    """
    site_info = await get_site_with_devices(current_user, uow, site_id)
    data_points: List[ComparisonPoint] = []
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    try:
        now = datetime.now(timezone.utc)
        if period == "week":
            # Fetch current 7 days and previous 7 days using separate custom-range calls
            current_week_end = now
            current_week_start = now - timedelta(days=7)
            prev_week_end = current_week_start
            prev_week_start = now - timedelta(days=14)

            current_data, prev_data = await asyncio.gather(
                system_b_client.get_site_energy_chart(
                    site_id=site_info.site_id,
                    period="custom",
                    start_time=current_week_start,
                    end_time=current_week_end,
                    bucket_interval="1 day",
                ),
                system_b_client.get_site_energy_chart(
                    site_id=site_info.site_id,
                    period="custom",
                    start_time=prev_week_start,
                    end_time=prev_week_end,
                    bucket_interval="1 day",
                ),
            )

            current_by_day: Dict[int, float] = {}
            previous_by_day: Dict[int, float] = {}

            for point in current_data.get("data", []):
                timestamp = datetime.fromisoformat(point["timestamp"])
                weekday = timestamp.weekday()
                current_by_day[weekday] = current_by_day.get(weekday, 0) + (point.get("pv_kwh") or 0)

            for point in prev_data.get("data", []):
                timestamp = datetime.fromisoformat(point["timestamp"])
                weekday = timestamp.weekday()
                previous_by_day[weekday] = previous_by_day.get(weekday, 0) + (point.get("pv_kwh") or 0)

            for i in range(7):
                data_points.append(ComparisonPoint(
                    label=day_labels[i],
                    current=round(current_by_day.get(i, 0), 1),
                    previous=round(previous_by_day.get(i, 0), 1),
                ))
        else:
            # Month period - compare last 4 weeks with previous 4 weeks using two custom calls
            current_month_end = now
            current_month_start = now - timedelta(days=28)
            prev_month_end = current_month_start
            prev_month_start = now - timedelta(days=56)

            current_data, prev_data = await asyncio.gather(
                system_b_client.get_site_energy_chart(
                    site_id=site_info.site_id,
                    period="custom",
                    start_time=current_month_start,
                    end_time=current_month_end,
                    bucket_interval="1 day",
                ),
                system_b_client.get_site_energy_chart(
                    site_id=site_info.site_id,
                    period="custom",
                    start_time=prev_month_start,
                    end_time=prev_month_end,
                    bucket_interval="1 day",
                ),
            )

            current_week_totals = [0.0] * 4
            prev_week_totals = [0.0] * 4

            for point in current_data.get("data", []):
                timestamp = datetime.fromisoformat(point["timestamp"])
                days_ago = (now - timestamp).days
                week_idx = min(days_ago // 7, 3)
                current_week_totals[week_idx] += point.get("pv_kwh") or 0

            for point in prev_data.get("data", []):
                timestamp = datetime.fromisoformat(point["timestamp"])
                days_ago = (now - timestamp).days - 28
                week_idx = min(days_ago // 7, 3)
                if 0 <= week_idx < 4:
                    prev_week_totals[week_idx] += point.get("pv_kwh") or 0

            # Week 1 = most recent
            for week_num in range(4):
                data_points.append(ComparisonPoint(
                    label=f"Week {week_num + 1}",
                    current=round(current_week_totals[week_num], 1),
                    previous=round(prev_week_totals[week_num], 1),
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
    except Exception as e:
        logger.error(f"Failed to fetch comparison data from System B: {e}")
        # Return empty comparison
        return ComparisonResponse(
            organization_id=site_info.organization_id,
            site_id=site_info.site_id,
            site_name=site_info.site_name,
            period=period,
            data=[],
            current_total=0.0,
            previous_total=0.0,
            percent_change=0.0,
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
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """
    Get peak demand analysis for the site.

    Fetches today's hourly demand data from System B.
    """
    site_info = await get_site_with_devices(current_user, uow, site_id)

    hourly_profile: List[PeakDemandHourly] = []
    peak_kw = 0.0
    peak_hour_str = ""
    total_kw = 0.0

    try:
        # Get today's fine-grained data from System B (~5-min buckets for "day" period)
        energy_data = await system_b_client.get_site_energy_chart(
            site_id=site_info.site_id,
            period="day",
        )

        # Aggregate fine-grained buckets into hourly groups.
        # Sum load_kwh per hour → kWh/hour = average kW for that hour.
        hourly_load: dict[str, float] = {}
        for point in energy_data.get("data", []):
            load_kwh = point.get("load_kwh", 0)
            timestamp = datetime.fromisoformat(point["timestamp"])
            hour_label = timestamp.strftime("%H:00")
            hourly_load[hour_label] = hourly_load.get(hour_label, 0.0) + load_kwh

        for hour_label, hour_kwh in sorted(hourly_load.items()):
            # kWh summed over one hour = average kW for that hour
            demand_kw = round(hour_kwh, 2)
            hourly_profile.append(PeakDemandHourly(hour=hour_label, demand_kw=demand_kw))
            total_kw += demand_kw

            if demand_kw > peak_kw:
                peak_kw = demand_kw
                peak_hour_str = hour_label

        avg_kw = total_kw / len(hourly_profile) if hourly_profile else 0

    except Exception as e:
        logger.error(f"Failed to fetch peak demand from System B: {e}")
        avg_kw = 0

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
    summary="Get real-time weather data",
    description="Returns weather from external API (OpenWeatherMap) with telemetry fallback. Refresh: 30 minutes.",
)
async def get_weather(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Get real-time weather data for site location.

    Integrates with OpenWeatherMap API for accurate weather data.
    Falls back to telemetry-derived data if API unavailable.
    """
    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    # Get site location and timezone
    site_entity = await uow.sites.get_by_id(site_info.site_id)
    site_timezone = site_entity.timezone if site_entity else "Asia/Karachi"

    # Determine location
    if site_entity and site_entity.address and site_entity.address.geo_location:
        lat = site_entity.address.geo_location.latitude
        lon = site_entity.address.geo_location.longitude
    else:
        # Default to Lahore, Pakistan
        lat, lon = 31.5, 74.3
        logger.warning(f"Site {site_info.site_id} has no geo_location, using default (Lahore)")

    # Get temperature from telemetry (for fallback and solar forecast)
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

    telemetry_temp = round(sum(temps) / len(temps), 1) if temps else None

    # Fetch weather from API (with telemetry fallback)
    try:
        weather_data = await weather_service.get_weather(lat, lon, telemetry_temp, site_timezone)
    except Exception as e:
        logger.error(f"Failed to get weather data: {e}")
        # Use service fallback
        weather_data = weather_service._get_fallback_weather(lat, lon, telemetry_temp, site_timezone)

    # Calculate solar forecast from PV production (not from API)
    installed_kw = max(len(site_info.device_serials) * 5, 1)
    now = datetime.now(timezone.utc)

    # Get hour in site timezone for solar factor calculation
    from ...domain.services.timezone_utils import TimezoneUtils
    site_hour = TimezoneUtils.get_hour_in_timezone(now, site_timezone)

    # Solar availability factor based on time of day
    if 6 <= site_hour <= 18:
        solar_factor = max(0, 1 - abs(site_hour - 12) / 6)
    else:
        solar_factor = 0
    expected_w = installed_kw * 1000 * solar_factor
    solar_forecast = min(100, round(total_pv_w / max(expected_w, 1) * 100)) if solar_factor > 0 else 0

    # Override weather condition with PV-based forecast if more accurate
    if solar_forecast > 0:
        if solar_forecast >= 70:
            weather_data.condition = "sunny"
        elif solar_forecast >= 40:
            weather_data.condition = "cloudy"
        else:
            weather_data.condition = "rainy"

    weather_data.solar_forecast = solar_forecast

    return WeatherResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        temperature=weather_data.temperature,
        condition=weather_data.condition,
        humidity=weather_data.humidity,
        wind_speed=weather_data.wind_speed,
        solar_forecast=weather_data.solar_forecast,
        sunrise=weather_data.sunrise,
        sunset=weather_data.sunset,
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
    total_battery_kwh = 0.0
    shutdown_soc = 10  # minimum SOC threshold (%)

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

            # Derive battery capacity from raw telemetry
            raw = telemetry.get("raw", {})
            capacity_ah = float(raw.get("battery_capacity_ah", 0) or 0)
            if capacity_ah > 0:
                # Assume 48 V nominal bus (common for residential hybrid inverters)
                total_battery_kwh += capacity_ah * 48 / 1000
            else:
                total_battery_kwh += 13.5  # fallback default kWh
            # Honour inverter's configured shutdown SOC if available
            dev_shutdown = int(raw.get("battery_shutdown_capacity_pct", 10) or 10)
            shutdown_soc = max(shutdown_soc, dev_shutdown)

    avg_soc = total_soc / soc_count if soc_count > 0 else 0
    # Only count energy above the shutdown threshold as usable
    usable_kwh = max(0.0, ((avg_soc - shutdown_soc) / 100) * total_battery_kwh)
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
    description="Returns aggregated billing data for the site using net metering calculations. Refresh: 1 hour.",
)
async def get_billing_summary(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Get billing summary using actual net metering calculations.

    This ensures consistency with the billing page by using the same
    data source (billing_daily snapshots) and calculation logic.
    """
    site_info = await get_site_with_devices(current_user, uow, site_id)

    # Use net metering repository to get authoritative billing data
    from ...infrastructure.database.repositories.net_metering_repository import (
        SQLAlchemyNetMeteringRepository,
    )
    from datetime import date, timedelta

    nm_repo = SQLAlchemyNetMeteringRepository(uow._session)

    # Get billing config for pricing info
    config = await nm_repo.get_billing_config_by_site(site_info.site_id)

    # Default rates if no config exists
    import_rate = 30.0
    export_rate = 15.0

    if config:
        # Use weighted average of peak and off-peak rates as "typical" rate
        # This is a simplification for the dashboard widget display
        import_rate = (config.prices.price_peak_import + config.prices.price_offpeak_import) / 2
        export_rate = (config.prices.price_peak_settlement + config.prices.price_offpeak_settlement) / 2

    # Try to get today's running bill data
    today = date.today()
    snapshot = await nm_repo.get_daily_snapshot(site_info.site_id, today)

    # Fall back to yesterday if today not available yet
    if not snapshot:
        yesterday = today - timedelta(days=1)
        snapshot = await nm_repo.get_daily_snapshot(site_info.site_id, yesterday)

    # If we have snapshot data, use it for accurate billing info
    if snapshot:
        # Estimated today's savings = today's solar generation * import rate
        # (Rough estimate - actual savings depends on TOU and self-consumption patterns)
        estimated_savings_today = 0.0  # We don't have per-day solar in snapshot

        # Month savings = solar generation * import rate (simplified)
        estimated_savings_month = snapshot.solar_generation_kwh * import_rate

        # Grid costs (simplified from bill components)
        grid_import_cost = snapshot.bill_off_energy_rs + snapshot.bill_peak_energy_rs

        # Export credit (from net metering balance)
        grid_export_credit = abs(snapshot.bill_credit_balance_rs_to_date) if snapshot.bill_credit_balance_rs_to_date < 0 else 0

    else:
        # No snapshot available - return zeros
        estimated_savings_today = 0.0
        estimated_savings_month = 0.0
        grid_import_cost = 0.0
        grid_export_credit = 0.0

    return BillingResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        estimated_savings_today=round(estimated_savings_today, 2),
        estimated_savings_month=round(estimated_savings_month, 2),
        grid_import_cost=round(grid_import_cost, 2),
        grid_export_credit=round(grid_export_credit, 2),
        import_rate_pkr=round(import_rate, 2),
        export_rate_pkr=round(export_rate, 2),
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
    """Get outage data for the outages management page (real DB data)."""
    from zoneinfo import ZoneInfo

    PKT = ZoneInfo("Asia/Karachi")

    site_info = await get_site_with_devices(current_user, uow, site_id)
    telemetry_batch = await get_all_devices_telemetry(site_info.device_serials)

    # ── Live telemetry: battery SOC + load ──────────────────────────────────
    grid_connected = True
    total_soc = 0.0
    soc_count = 0
    total_load_w = 0.0
    battery_capacity_kwh = 13.5

    for serial in site_info.device_serials:
        telemetry = telemetry_batch.get(serial)
        if telemetry:
            if not telemetry.get("status", {}).get("grid_connected", True):
                grid_connected = False
            soc = telemetry.get("battery", {}).get("soc_pct", 0)
            if soc > 0:
                total_soc += soc
                soc_count += 1
            total_load_w += telemetry.get("power", {}).get("load_w", 0)

    avg_soc = total_soc / soc_count if soc_count > 0 else 0
    usable_kwh = (avg_soc / 100) * battery_capacity_kwh * max(len(site_info.device_serials), 1)
    load_kw = total_load_w / 1000 if total_load_w > 0 else 1.0
    coverage_hours = round(usable_kwh / load_kw, 1) if load_kw > 0 else 0

    now = datetime.now(timezone.utc)

    # ── Real outage history from DB ──────────────────────────────────────────
    raw_outages = await uow.grid_outages.get_recent(
        site_info.site_id, days=days
    )

    def _to_record(o) -> OutageRecord:
        duration = o.duration_minutes or 0
        battery_approx = round((duration / 60) * 0.8, 2)
        backup_status = "full" if duration <= 180 else ("partial" if duration <= 300 else "none")
        outage_type = "scheduled" if o.was_predicted else "unscheduled"
        start_pkt = o.started_at.astimezone(PKT)
        end_pkt = o.ended_at.astimezone(PKT) if o.ended_at else now.astimezone(PKT)
        return OutageRecord(
            id=str(o.id),
            date=start_pkt.strftime("%Y-%m-%d"),
            start_time=o.started_at.isoformat(),
            end_time=o.ended_at.isoformat() if o.ended_at else now.isoformat(),
            duration=duration,
            type=outage_type,
            battery_used=battery_approx,
            backup_status=backup_status,
        )

    outage_history: List[OutageRecord] = [_to_record(o) for o in raw_outages]

    # Today's outages (PKT date)
    today_str = now.astimezone(PKT).strftime("%Y-%m-%d")
    today_outages: List[OutageRecord] = [o for o in outage_history if o.date == today_str]

    # Weekly summaries (past 7 days)
    week_summaries: List[DailyOutageSummary] = []
    for day_offset in range(7):
        day_date = now.astimezone(PKT) - timedelta(days=day_offset)
        day_str = day_date.strftime("%Y-%m-%d")
        day_records = [o for o in outage_history if o.date == day_str]
        week_summaries.append(DailyOutageSummary(
            date=day_str,
            outage_count=len(day_records),
            total_duration=sum(o.duration for o in day_records),
        ))

    # Monthly stats (last 30 days)
    recent_30 = [o for o in outage_history]
    total_outages_count = len(recent_30)
    total_duration = sum(o.duration for o in recent_30)
    avg_duration = total_duration // total_outages_count if total_outages_count > 0 else 0
    longest = max((o.duration for o in recent_30), default=0)
    total_backup = sum(o.duration for o in recent_30 if o.backup_status != "none")
    total_battery_used = sum(o.battery_used for o in recent_30)
    hours_avoided = round(total_backup / 60, 1)

    monthly_stats = MonthlyOutageStats(
        total_outages=total_outages_count,
        total_duration=total_duration,
        avg_duration=avg_duration,
        longest_outage=longest,
        total_backup_time=total_backup,
        total_battery_used=round(total_battery_used, 1),
        hours_avoided=hours_avoided,
    )

    # ── Active outage + last change ──────────────────────────────────────────
    active_outage = await uow.grid_outages.get_active_outage(site_info.site_id)
    last_outage = await uow.grid_outages.get_last_outage(site_info.site_id)

    current_outage_record: Optional[OutageRecord] = None
    if active_outage:
        current_outage_record = _to_record(active_outage)
        grid_connected = False

    last_change = active_outage.started_at if active_outage else (
        last_outage.ended_at if last_outage and last_outage.ended_at else now
    )

    grid_status = GridStatusData(
        online=grid_connected,
        last_change=last_change.isoformat(),
        current_outage=current_outage_record,
        battery_level=round(avg_soc),
        estimated_backup_hours=coverage_hours,
        current_load=round(load_kw, 2),
    )

    # ── Alerts derived from real data ────────────────────────────────────────
    alerts: List[OutageAlert] = []
    if active_outage:
        duration_so_far = int((now - active_outage.started_at).total_seconds() / 60)
        alerts.append(OutageAlert(
            id=f"alert-active-{active_outage.id}",
            type="grid_down",
            message=f"Grid outage in progress — {duration_so_far} min so far",
            timestamp=active_outage.started_at.isoformat(),
            read=False,
            priority="high",
        ))
    elif last_outage and last_outage.ended_at:
        alerts.append(OutageAlert(
            id=f"alert-restored-{last_outage.id}",
            type="grid_restored",
            message=f"Grid restored after {last_outage.duration_minutes or 0} min outage",
            timestamp=last_outage.ended_at.isoformat(),
            read=False,
            priority="low",
        ))
    if coverage_hours > 0:
        alerts.append(OutageAlert(
            id="alert-battery",
            type="prediction",
            message=f"Battery will last ~{coverage_hours} more hours at current load ({round(load_kw, 1)} kW)",
            timestamp=now.isoformat(),
            read=False,
            priority="medium" if avg_soc < 30 else "low",
        ))

    return OutagesResponse(
        organization_id=site_info.organization_id,
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        grid_status=grid_status,
        today_outages=today_outages,
        week_summaries=week_summaries,
        monthly_stats=monthly_stats,
        outage_history=outage_history[:100],
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
            is_charging=total_battery > 0,  # derive from sign, not OR across devices
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
            is_charging=total_battery > 0,  # derive from sign, not OR across devices
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
