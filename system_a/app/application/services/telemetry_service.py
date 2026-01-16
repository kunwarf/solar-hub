"""
Telemetry Application Service.

Provides telemetry data access for dashboards and analytics.
Coordinates between telemetry repository and other services.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from ...infrastructure.database.repositories.telemetry_repository import (
    SQLAlchemyTelemetryRepository,
    SiteEnergyTotals,
    DailySummary,
    MonthlySummary,
    DeviceSnapshot,
)
from ...infrastructure.database.repositories.site_repository import SQLAlchemySiteRepository
from ...infrastructure.database.repositories.device_repository import SQLAlchemyDeviceRepository
from ...infrastructure.database.repositories.alert_repository import SQLAlchemyAlertRepository

logger = logging.getLogger(__name__)


# Environmental constants
CO2_PER_KWH_KG = 0.475  # Pakistan grid emission factor
TREES_PER_TON_CO2 = 45  # Trees to absorb 1 ton CO2/year
COAL_PER_KWH_KG = 0.4   # Coal for 1 kWh
PKR_PER_KWH = 25.0      # Average electricity rate


@dataclass
class SiteOverview:
    """Site dashboard overview data."""
    site_id: UUID
    site_name: str
    status: str
    current_power_kw: float
    current_grid_power_kw: float
    current_battery_soc_percent: Optional[float]
    energy_today_kwh: float
    energy_exported_today_kwh: float
    energy_imported_today_kwh: float
    peak_power_today_kw: float
    energy_this_month_kwh: float
    energy_lifetime_kwh: float
    total_devices: int
    online_devices: int
    devices_with_errors: int
    active_alerts: int
    critical_alerts: int
    system_capacity_kw: float
    capacity_factor_percent: float
    last_updated: datetime


@dataclass
class OrgOverview:
    """Organization dashboard overview data."""
    organization_id: UUID
    organization_name: str
    total_sites: int
    active_sites: int
    total_devices: int
    online_devices: int
    total_current_power_kw: float
    total_energy_today_kwh: float
    total_energy_this_month_kwh: float
    total_capacity_kw: float
    total_active_alerts: int
    total_critical_alerts: int
    top_sites: List[Dict[str, Any]]
    last_updated: datetime


@dataclass
class EnvironmentalImpact:
    """Environmental impact metrics."""
    site_id: Optional[UUID]
    organization_id: UUID
    period_start: date
    period_end: date
    total_solar_energy_kwh: float
    co2_avoided_kg: float
    trees_equivalent: float
    coal_avoided_kg: float
    estimated_savings_pkr: float


@dataclass
class SiteComparison:
    """Site comparison data."""
    site_id: UUID
    site_name: str
    energy_generated_kwh: float
    capacity_kw: float
    performance_ratio: Optional[float]
    specific_yield: float


class TelemetryService:
    """
    Application service for telemetry data access.

    Provides aggregated and real-time telemetry data for dashboards.
    """

    def __init__(
        self,
        telemetry_repository: SQLAlchemyTelemetryRepository,
        site_repository: SQLAlchemySiteRepository,
        device_repository: SQLAlchemyDeviceRepository,
        alert_repository: Optional[SQLAlchemyAlertRepository] = None,
    ):
        self._telemetry_repo = telemetry_repository
        self._site_repo = site_repository
        self._device_repo = device_repository
        self._alert_repo = alert_repository

    # =========================================================================
    # Site Overview
    # =========================================================================

    async def get_site_overview(self, site_id: UUID) -> SiteOverview:
        """Get comprehensive site overview for dashboard."""
        site = await self._site_repo.get_by_id(site_id)
        if not site:
            raise ValueError(f"Site {site_id} not found")

        # Get device stats
        total_devices = await self._device_repo.count_by_site_id(site_id)
        online_devices = await self._device_repo.get_online_devices(site_id)
        devices_with_errors = await self._device_repo.get_devices_with_errors(site.organization_id)
        site_errors = [d for d in devices_with_errors if d.site_id == site_id]

        # Get real-time power from device snapshots
        current_power = await self._telemetry_repo.get_site_current_power(site_id)
        snapshots = await self._telemetry_repo.get_device_snapshots(site_id)

        # Calculate grid power and battery SOC from snapshots
        grid_power = 0.0
        battery_soc = None
        for snap in snapshots:
            if snap.grid_import_power_kw is not None:
                grid_power += snap.grid_import_power_kw
            if snap.grid_export_power_kw is not None:
                grid_power -= snap.grid_export_power_kw
            if snap.battery_soc_percent is not None:
                battery_soc = snap.battery_soc_percent  # Use last one found

        # Get today's energy
        today_data = await self._telemetry_repo.get_today_energy(site_id)

        # Get this month's energy
        month_energy = await self._telemetry_repo.get_this_month_energy(site_id)

        # Get lifetime energy
        lifetime_energy = await self._telemetry_repo.get_lifetime_energy(site_id)

        # Get alert counts if repository available
        active_alerts = 0
        critical_alerts = 0
        if self._alert_repo:
            alerts = await self._alert_repo.list_alerts(site_id=site_id, resolved=False)
            active_alerts = len(alerts)
            critical_alerts = len([a for a in alerts if a.severity.value == 'critical'])

        # Calculate capacity factor
        capacity = site.configuration.system_capacity_kw
        capacity_factor = (current_power / capacity * 100) if capacity > 0 else 0.0

        return SiteOverview(
            site_id=site.id,
            site_name=site.name,
            status=site.status.value,
            current_power_kw=current_power,
            current_grid_power_kw=grid_power,
            current_battery_soc_percent=battery_soc,
            energy_today_kwh=today_data["energy_generated_kwh"],
            energy_exported_today_kwh=today_data["energy_exported_kwh"],
            energy_imported_today_kwh=today_data["energy_imported_kwh"],
            peak_power_today_kw=today_data["peak_power_kw"],
            energy_this_month_kwh=month_energy,
            energy_lifetime_kwh=lifetime_energy,
            total_devices=total_devices,
            online_devices=len(online_devices),
            devices_with_errors=len(site_errors),
            active_alerts=active_alerts,
            critical_alerts=critical_alerts,
            system_capacity_kw=capacity,
            capacity_factor_percent=capacity_factor,
            last_updated=datetime.now(timezone.utc),
        )

    # =========================================================================
    # Organization Overview
    # =========================================================================

    async def get_org_overview(
        self,
        organization_id: UUID,
        org_name: str,
    ) -> OrgOverview:
        """Get organization-wide dashboard overview."""
        # Get all sites
        all_sites = await self._site_repo.get_by_organization_id(organization_id, limit=1000)
        active_sites = [s for s in all_sites if s.status.value == 'active']
        site_ids = [s.id for s in active_sites]

        # Get device counts
        total_devices = await self._device_repo.count_by_organization_id(organization_id)

        # Count online devices across all sites
        online_count = 0
        for site in active_sites:
            online_devices = await self._device_repo.get_online_devices(site.id)
            online_count += len(online_devices)

        # Get aggregated energy data
        energy_data = await self._telemetry_repo.aggregate_org_totals(site_ids)

        # Calculate total capacity
        total_capacity = sum(s.configuration.system_capacity_kw for s in all_sites)

        # Get alert counts if repository available
        total_active_alerts = 0
        total_critical_alerts = 0
        if self._alert_repo:
            for site in active_sites:
                alerts = await self._alert_repo.list_alerts(site_id=site.id, resolved=False)
                total_active_alerts += len(alerts)
                total_critical_alerts += len([a for a in alerts if a.severity.value == 'critical'])

        # Build top sites list with energy data
        top_sites = []
        for site in active_sites[:5]:
            site_energy = await self._telemetry_repo.get_today_energy(site.id)
            top_sites.append({
                "id": str(site.id),
                "name": site.name,
                "capacity_kw": site.configuration.system_capacity_kw,
                "energy_today_kwh": site_energy["energy_generated_kwh"],
                "status": site.status.value,
            })

        return OrgOverview(
            organization_id=organization_id,
            organization_name=org_name,
            total_sites=len(all_sites),
            active_sites=len(active_sites),
            total_devices=total_devices,
            online_devices=online_count,
            total_current_power_kw=energy_data["current_power_kw"],
            total_energy_today_kwh=energy_data["energy_today_kwh"],
            total_energy_this_month_kwh=energy_data["energy_month_kwh"],
            total_capacity_kw=total_capacity,
            total_active_alerts=total_active_alerts,
            total_critical_alerts=total_critical_alerts,
            top_sites=top_sites,
            last_updated=datetime.now(timezone.utc),
        )

    # =========================================================================
    # Energy Statistics
    # =========================================================================

    async def get_daily_energy_stats(
        self,
        site_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[DailySummary]:
        """Get daily energy statistics for a site."""
        summaries = await self._telemetry_repo.get_daily_summaries(
            site_id=site_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Fill in missing dates with zero values
        summary_by_date = {s.date: s for s in summaries}
        result = []
        current = start_date
        while current <= end_date:
            if current in summary_by_date:
                result.append(summary_by_date[current])
            else:
                result.append(DailySummary(
                    date=current,
                    energy_generated_kwh=0.0,
                    energy_consumed_kwh=0.0,
                    energy_exported_kwh=0.0,
                    energy_imported_kwh=0.0,
                    peak_power_kw=0.0,
                    peak_power_time=None,
                    sunshine_hours=0.0,
                    performance_ratio=None,
                    co2_avoided_kg=0.0,
                ))
            current += timedelta(days=1)

        return result

    async def get_monthly_energy_stats(
        self,
        site_id: UUID,
        year: int,
    ) -> List[MonthlySummary]:
        """Get monthly energy statistics for a site."""
        summaries = await self._telemetry_repo.get_monthly_summaries(
            site_id=site_id,
            year=year,
        )

        # Fill in missing months with zero values
        summary_by_month = {s.month: s for s in summaries}
        result = []
        for month in range(1, 13):
            if month in summary_by_month:
                result.append(summary_by_month[month])
            else:
                result.append(MonthlySummary(
                    year=year,
                    month=month,
                    energy_generated_kwh=0.0,
                    energy_consumed_kwh=0.0,
                    energy_exported_kwh=0.0,
                    energy_imported_kwh=0.0,
                    avg_daily_generation_kwh=0.0,
                    peak_power_kw=0.0,
                    days_with_data=0,
                    performance_ratio=None,
                    co2_avoided_kg=0.0,
                ))

        return result

    async def get_hourly_power_data(
        self,
        site_id: UUID,
        target_date: date,
    ) -> List[Dict[str, Any]]:
        """Get hourly power data for a specific day."""
        start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=1)

        hourly_data = await self._telemetry_repo.get_hourly_summaries(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Convert to simple dict format for chart
        result = []
        for hour in range(24):
            hour_start = start_time + timedelta(hours=hour)
            matching = [h for h in hourly_data if h.timestamp_hour == hour_start]

            if matching:
                h = matching[0]
                result.append({
                    "hour": hour,
                    "power_kw": h.average_power_kw,
                    "energy_kwh": h.energy_generated_kwh,
                })
            else:
                result.append({
                    "hour": hour,
                    "power_kw": 0.0,
                    "energy_kwh": 0.0,
                })

        return result

    # =========================================================================
    # Real-time Data
    # =========================================================================

    async def get_device_snapshots(self, site_id: UUID) -> List[DeviceSnapshot]:
        """Get latest telemetry snapshots for all devices at a site."""
        return await self._telemetry_repo.get_device_snapshots(site_id)

    async def get_realtime_power_history(
        self,
        site_id: UUID,
        minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        Get recent power readings for live chart.

        Note: In a full implementation, this would query time-series data
        from System B via Redis or direct connection. For now, returns
        data from hourly summaries as approximation.
        """
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(minutes=minutes)

        # Get hourly summaries as approximation
        hourly_data = await self._telemetry_repo.get_hourly_summaries(
            site_id=site_id,
            start_time=start_time,
            end_time=now,
        )

        timestamps = []
        power_values = []

        # For a real implementation, we'd have minute-level data
        # For now, interpolate from hourly data
        for h in hourly_data:
            timestamps.append(h.timestamp_hour)
            power_values.append(h.average_power_kw)

        return {
            "timestamps": timestamps,
            "power_values": power_values,
        }

    # =========================================================================
    # Environmental Impact
    # =========================================================================

    async def get_environmental_impact(
        self,
        organization_id: UUID,
        start_date: date,
        end_date: date,
        site_id: Optional[UUID] = None,
    ) -> EnvironmentalImpact:
        """Calculate environmental impact metrics."""
        if site_id:
            # Single site
            totals = await self._telemetry_repo.aggregate_site_totals(
                site_id=site_id,
                start_date=start_date,
                end_date=end_date,
            )
            total_energy = totals.energy_generated_kwh
        else:
            # All sites in organization
            sites = await self._site_repo.get_by_organization_id(organization_id, limit=1000)
            site_ids = [s.id for s in sites]

            total_energy = 0.0
            for sid in site_ids:
                totals = await self._telemetry_repo.aggregate_site_totals(
                    site_id=sid,
                    start_date=start_date,
                    end_date=end_date,
                )
                total_energy += totals.energy_generated_kwh

        # Calculate environmental metrics
        co2_avoided = total_energy * CO2_PER_KWH_KG
        trees_equivalent = (co2_avoided / 1000) * TREES_PER_TON_CO2
        coal_avoided = total_energy * COAL_PER_KWH_KG
        estimated_savings = total_energy * PKR_PER_KWH

        return EnvironmentalImpact(
            site_id=site_id,
            organization_id=organization_id,
            period_start=start_date,
            period_end=end_date,
            total_solar_energy_kwh=total_energy,
            co2_avoided_kg=co2_avoided,
            trees_equivalent=trees_equivalent,
            coal_avoided_kg=coal_avoided,
            estimated_savings_pkr=estimated_savings,
        )

    # =========================================================================
    # Site Comparison
    # =========================================================================

    async def compare_sites(
        self,
        organization_id: UUID,
        site_ids: Optional[List[UUID]],
        start_date: date,
        end_date: date,
    ) -> List[SiteComparison]:
        """Compare performance across multiple sites."""
        if site_ids:
            sites = []
            for sid in site_ids:
                site = await self._site_repo.get_by_id(sid)
                if site and site.organization_id == organization_id:
                    sites.append(site)
        else:
            sites = await self._site_repo.get_by_organization_id(organization_id, limit=20)

        comparisons = []
        for site in sites:
            totals = await self._telemetry_repo.aggregate_site_totals(
                site_id=site.id,
                start_date=start_date,
                end_date=end_date,
            )

            capacity = site.configuration.system_capacity_kw
            energy = totals.energy_generated_kwh

            # Calculate specific yield (kWh/kWp)
            specific_yield = energy / capacity if capacity > 0 else 0.0

            # Get performance metrics
            metrics = await self._telemetry_repo.get_site_performance_metrics(
                site_id=site.id,
                start_date=start_date,
                end_date=end_date,
            )

            comparisons.append(SiteComparison(
                site_id=site.id,
                site_name=site.name,
                energy_generated_kwh=energy,
                capacity_kw=capacity,
                performance_ratio=metrics.get("avg_performance_ratio"),
                specific_yield=specific_yield,
            ))

        # Sort by energy generated descending
        comparisons.sort(key=lambda x: x.energy_generated_kwh, reverse=True)
        return comparisons

    # =========================================================================
    # Chart Data
    # =========================================================================

    async def get_energy_chart_data(
        self,
        site_id: UUID,
        period: str,
    ) -> Dict[str, Any]:
        """
        Get energy chart data for visualization.

        Args:
            site_id: Site UUID
            period: One of 'day', 'week', 'month', 'year'

        Returns:
            Chart data with labels and datasets
        """
        today = date.today()

        if period == "day":
            # Hourly data for today
            hourly_data = await self.get_hourly_power_data(site_id, today)
            labels = [f"{h['hour']:02d}:00" for h in hourly_data]
            generation = [h["energy_kwh"] for h in hourly_data]
            # Consumption would come from a different query in full implementation
            consumption = [0.0] * 24

        elif period == "week":
            # Daily data for last 7 days
            start_date = today - timedelta(days=6)
            daily_data = await self.get_daily_energy_stats(site_id, start_date, today)
            labels = [d.date.strftime("%a") for d in daily_data]
            generation = [d.energy_generated_kwh for d in daily_data]
            consumption = [d.energy_consumed_kwh for d in daily_data]

        elif period == "month":
            # Daily data for last 30 days
            start_date = today - timedelta(days=29)
            daily_data = await self.get_daily_energy_stats(site_id, start_date, today)
            labels = [str(d.date.day) for d in daily_data]
            generation = [d.energy_generated_kwh for d in daily_data]
            consumption = [d.energy_consumed_kwh for d in daily_data]

        else:  # year
            # Monthly data for current year
            monthly_data = await self.get_monthly_energy_stats(site_id, today.year)
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            labels = month_names
            generation = [m.energy_generated_kwh for m in monthly_data]
            consumption = [m.energy_consumed_kwh for m in monthly_data]

        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "Generation (kWh)",
                    "data": generation,
                    "backgroundColor": "#22c55e",
                },
                {
                    "label": "Consumption (kWh)",
                    "data": consumption,
                    "backgroundColor": "#ef4444",
                },
            ],
        }
