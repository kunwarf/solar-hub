"""
Pydantic schemas for dashboard endpoints.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class EnergyDataPoint(BaseModel):
    """Single energy data point."""
    timestamp: datetime
    value: float
    unit: str = "kWh"


class PowerDataPoint(BaseModel):
    """Single power data point."""
    timestamp: datetime
    value: float
    unit: str = "kW"


class DailyEnergyStats(BaseModel):
    """Daily energy statistics."""
    date: date
    energy_generated_kwh: float = 0.0
    energy_consumed_kwh: float = 0.0
    energy_exported_kwh: float = 0.0
    energy_imported_kwh: float = 0.0
    peak_power_kw: float = 0.0
    peak_power_time: Optional[datetime] = None
    sunshine_hours: float = 0.0


class MonthlyEnergyStats(BaseModel):
    """Monthly energy statistics."""
    year: int
    month: int
    energy_generated_kwh: float = 0.0
    energy_consumed_kwh: float = 0.0
    energy_exported_kwh: float = 0.0
    energy_imported_kwh: float = 0.0
    avg_daily_generation_kwh: float = 0.0
    peak_power_kw: float = 0.0
    days_with_data: int = 0


class SiteOverviewResponse(BaseModel):
    """Site overview for dashboard."""
    site_id: UUID
    site_name: str
    status: str

    # Current readings
    current_power_kw: float = 0.0
    current_grid_power_kw: float = 0.0
    current_battery_soc_percent: Optional[float] = None

    # Today's stats
    energy_today_kwh: float = 0.0
    energy_exported_today_kwh: float = 0.0
    energy_imported_today_kwh: float = 0.0
    peak_power_today_kw: float = 0.0

    # This month
    energy_this_month_kwh: float = 0.0

    # Lifetime
    energy_lifetime_kwh: float = 0.0

    # Device status
    total_devices: int = 0
    online_devices: int = 0
    devices_with_errors: int = 0

    # Alerts
    active_alerts: int = 0
    critical_alerts: int = 0

    # System info
    system_capacity_kw: float = 0.0
    capacity_factor_percent: float = 0.0

    last_updated: Optional[datetime] = None


class OrganizationOverviewResponse(BaseModel):
    """Organization-wide overview."""
    organization_id: UUID
    organization_name: str

    # Aggregate stats
    total_sites: int = 0
    active_sites: int = 0
    total_devices: int = 0
    online_devices: int = 0

    # Current readings (sum of all sites)
    total_current_power_kw: float = 0.0

    # Today's stats
    total_energy_today_kwh: float = 0.0

    # This month
    total_energy_this_month_kwh: float = 0.0

    # Total capacity
    total_capacity_kw: float = 0.0

    # Alerts
    total_active_alerts: int = 0
    total_critical_alerts: int = 0

    # Top performing sites
    top_sites: List[Dict[str, Any]] = []

    last_updated: Optional[datetime] = None


class EnergyChartData(BaseModel):
    """Energy chart data for visualization."""
    labels: List[str]
    datasets: List[Dict[str, Any]]


class PowerChartData(BaseModel):
    """Real-time power chart data."""
    timestamps: List[datetime]
    power_values: List[float]
    grid_values: Optional[List[float]] = None
    battery_values: Optional[List[float]] = None


class SiteComparisonItem(BaseModel):
    """Single site in comparison."""
    site_id: UUID
    site_name: str
    energy_generated_kwh: float
    capacity_kw: float
    performance_ratio: float
    specific_yield: float  # kWh/kWp


class SiteComparisonResponse(BaseModel):
    """Site comparison data."""
    period_start: date
    period_end: date
    sites: List[SiteComparisonItem]


class EnvironmentalImpactResponse(BaseModel):
    """Environmental impact metrics."""
    site_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    period_start: date
    period_end: date

    # Energy
    total_solar_energy_kwh: float = 0.0

    # Environmental
    co2_avoided_kg: float = 0.0
    trees_equivalent: float = 0.0
    coal_avoided_kg: float = 0.0

    # Financial (estimated)
    estimated_savings_pkr: float = 0.0


class WeatherData(BaseModel):
    """Weather data for site."""
    timestamp: datetime
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    irradiance_w_m2: Optional[float] = None
    wind_speed_m_s: Optional[float] = None
    weather_condition: Optional[str] = None


class DashboardWidgetData(BaseModel):
    """Generic widget data."""
    widget_type: str
    title: str
    data: Dict[str, Any]
    last_updated: Optional[datetime] = None
