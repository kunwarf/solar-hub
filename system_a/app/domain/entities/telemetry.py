"""
Telemetry summary domain entities.

Raw telemetry is stored in System B (TimescaleDB).
These entities represent aggregated summaries stored in System A for dashboard queries.
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID

from .base import Entity


class AggregationPeriod(str, Enum):
    """Time period for aggregation."""
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


class MetricType(str, Enum):
    """Types of metrics tracked."""
    ENERGY_GENERATED = "energy_generated"      # kWh
    ENERGY_CONSUMED = "energy_consumed"        # kWh
    ENERGY_EXPORTED = "energy_exported"        # kWh (to grid)
    ENERGY_IMPORTED = "energy_imported"        # kWh (from grid)
    ENERGY_STORED = "energy_stored"            # kWh (to battery)
    ENERGY_DISCHARGED = "energy_discharged"    # kWh (from battery)
    PEAK_POWER = "peak_power"                  # kW
    AVERAGE_POWER = "average_power"            # kW
    IRRADIANCE = "irradiance"                  # W/m²
    TEMPERATURE = "temperature"                # °C
    BATTERY_SOC = "battery_soc"                # %
    GRID_FREQUENCY = "grid_frequency"          # Hz
    GRID_VOLTAGE = "grid_voltage"              # V
    POWER_FACTOR = "power_factor"              # ratio
    CO2_AVOIDED = "co2_avoided"                # kg
    PERFORMANCE_RATIO = "performance_ratio"    # %


@dataclass(kw_only=True)
class TelemetryHourlySummary(Entity):
    """
    Hourly aggregated telemetry data.

    Stores hourly summaries for each site/device for quick dashboard queries.
    """
    site_id: UUID
    device_id: Optional[UUID] = None  # None = site-level aggregation

    # Time bucket
    timestamp_hour: datetime = field(default_factory=datetime.utcnow)  # Start of hour

    # Energy metrics (kWh)
    energy_generated_kwh: float = 0.0
    energy_consumed_kwh: float = 0.0
    energy_exported_kwh: float = 0.0
    energy_imported_kwh: float = 0.0
    energy_stored_kwh: float = 0.0
    energy_discharged_kwh: float = 0.0

    # Power metrics (kW)
    peak_power_kw: float = 0.0
    peak_power_time: Optional[datetime] = None
    average_power_kw: float = 0.0
    min_power_kw: float = 0.0

    # Environmental
    avg_irradiance_w_m2: Optional[float] = None
    avg_temperature_c: Optional[float] = None
    max_temperature_c: Optional[float] = None
    min_temperature_c: Optional[float] = None

    # Battery (if applicable)
    avg_battery_soc_percent: Optional[float] = None
    min_battery_soc_percent: Optional[float] = None
    max_battery_soc_percent: Optional[float] = None

    # Grid metrics
    avg_grid_voltage_v: Optional[float] = None
    avg_grid_frequency_hz: Optional[float] = None
    avg_power_factor: Optional[float] = None

    # Data quality
    sample_count: int = 0
    data_quality_percent: float = 100.0  # % of expected samples received

    # Calculated metrics
    performance_ratio: Optional[float] = None
    capacity_factor: Optional[float] = None


@dataclass(kw_only=True)
class TelemetryDailySummary(Entity):
    """
    Daily aggregated telemetry data.

    Stores daily summaries for historical analysis and reporting.
    """
    site_id: UUID
    device_id: Optional[UUID] = None

    # Date
    summary_date: date = field(default_factory=date.today)

    # Energy metrics (kWh)
    energy_generated_kwh: float = 0.0
    energy_consumed_kwh: float = 0.0
    energy_exported_kwh: float = 0.0
    energy_imported_kwh: float = 0.0
    energy_stored_kwh: float = 0.0
    energy_discharged_kwh: float = 0.0
    net_energy_kwh: float = 0.0  # generated - consumed

    # Power metrics (kW)
    peak_power_kw: float = 0.0
    peak_power_time: Optional[datetime] = None
    average_power_kw: float = 0.0

    # Time-based metrics
    sunshine_hours: float = 0.0  # Hours with significant generation
    production_hours: float = 0.0  # Hours with any generation
    grid_outage_minutes: int = 0

    # Environmental
    avg_irradiance_w_m2: Optional[float] = None
    total_irradiation_kwh_m2: Optional[float] = None  # Daily solar irradiation
    avg_temperature_c: Optional[float] = None
    max_temperature_c: Optional[float] = None
    min_temperature_c: Optional[float] = None
    avg_humidity_percent: Optional[float] = None

    # Battery metrics
    battery_cycles: float = 0.0
    avg_battery_soc_percent: Optional[float] = None

    # Grid metrics
    avg_grid_voltage_v: Optional[float] = None
    avg_power_factor: Optional[float] = None

    # Performance
    performance_ratio: Optional[float] = None
    capacity_factor: Optional[float] = None
    specific_yield_kwh_kwp: Optional[float] = None  # kWh per kWp installed

    # Environmental impact
    co2_avoided_kg: float = 0.0

    # Financial (estimated)
    estimated_revenue_pkr: float = 0.0
    estimated_savings_pkr: float = 0.0

    # Data quality
    hours_with_data: int = 0
    data_completeness_percent: float = 100.0


@dataclass(kw_only=True)
class TelemetryMonthlySummary(Entity):
    """
    Monthly aggregated telemetry data.

    Stores monthly summaries for long-term analysis and billing.
    """
    site_id: UUID
    device_id: Optional[UUID] = None

    # Month
    year: int = 2024
    month: int = 1

    # Energy metrics (kWh)
    energy_generated_kwh: float = 0.0
    energy_consumed_kwh: float = 0.0
    energy_exported_kwh: float = 0.0
    energy_imported_kwh: float = 0.0
    energy_stored_kwh: float = 0.0
    energy_discharged_kwh: float = 0.0
    net_energy_kwh: float = 0.0

    # Power metrics (kW)
    peak_power_kw: float = 0.0
    peak_power_date: Optional[date] = None
    average_daily_generation_kwh: float = 0.0

    # Time metrics
    total_sunshine_hours: float = 0.0
    total_production_hours: float = 0.0
    total_grid_outage_minutes: int = 0

    # Environmental
    avg_temperature_c: Optional[float] = None
    total_irradiation_kwh_m2: Optional[float] = None

    # Performance
    performance_ratio: Optional[float] = None
    capacity_factor: Optional[float] = None
    specific_yield_kwh_kwp: Optional[float] = None

    # Comparison to expected
    expected_generation_kwh: Optional[float] = None
    generation_variance_percent: Optional[float] = None

    # Environmental impact
    co2_avoided_kg: float = 0.0
    trees_equivalent: float = 0.0

    # Financial
    estimated_revenue_pkr: float = 0.0
    estimated_savings_pkr: float = 0.0

    # Data quality
    days_with_data: int = 0
    data_completeness_percent: float = 100.0


@dataclass(kw_only=True)
class DeviceTelemetrySnapshot(Entity):
    """
    Latest telemetry snapshot for a device.

    Stores the most recent readings for real-time dashboard display.
    Updated frequently (every few seconds to minutes).
    """
    device_id: UUID
    site_id: UUID

    # Timestamp
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Power readings
    current_power_kw: float = 0.0
    power_limit_kw: Optional[float] = None

    # Energy (today's totals)
    energy_today_kwh: float = 0.0
    energy_lifetime_kwh: float = 0.0

    # DC side (for inverters)
    dc_voltage_v: Optional[float] = None
    dc_current_a: Optional[float] = None
    dc_power_kw: Optional[float] = None

    # AC side
    ac_voltage_v: Optional[float] = None
    ac_current_a: Optional[float] = None
    ac_frequency_hz: Optional[float] = None
    power_factor: Optional[float] = None

    # For 3-phase systems
    voltage_l1_v: Optional[float] = None
    voltage_l2_v: Optional[float] = None
    voltage_l3_v: Optional[float] = None
    current_l1_a: Optional[float] = None
    current_l2_a: Optional[float] = None
    current_l3_a: Optional[float] = None

    # Temperature
    internal_temperature_c: Optional[float] = None
    ambient_temperature_c: Optional[float] = None

    # Battery specific
    battery_soc_percent: Optional[float] = None
    battery_voltage_v: Optional[float] = None
    battery_current_a: Optional[float] = None
    battery_power_kw: Optional[float] = None
    battery_temperature_c: Optional[float] = None
    charging_state: Optional[str] = None  # charging, discharging, idle

    # Grid specific (for meters)
    grid_import_power_kw: Optional[float] = None
    grid_export_power_kw: Optional[float] = None

    # Weather station specific
    irradiance_w_m2: Optional[float] = None
    wind_speed_m_s: Optional[float] = None
    humidity_percent: Optional[float] = None

    # Status
    operating_state: Optional[str] = None
    error_code: Optional[str] = None
    warning_code: Optional[str] = None

    # Raw data for debugging
    raw_data: Optional[Dict[str, Any]] = None
