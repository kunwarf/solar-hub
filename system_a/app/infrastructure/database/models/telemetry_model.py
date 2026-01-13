"""
SQLAlchemy ORM models for telemetry summaries.

Raw telemetry data is stored in System B (TimescaleDB).
These models store aggregated summaries for System A dashboard queries.
"""
from datetime import datetime, date, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TelemetryHourlySummaryModel(Base):
    """SQLAlchemy model for hourly telemetry summaries."""

    __tablename__ = "telemetry_hourly_summary"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Time bucket - start of hour
    timestamp_hour: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Energy metrics (kWh)
    energy_generated_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_consumed_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_exported_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_imported_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_stored_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_discharged_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Power metrics (kW)
    peak_power_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    peak_power_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    average_power_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    min_power_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Environmental
    avg_irradiance_w_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Battery
    avg_battery_soc_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_battery_soc_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_battery_soc_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Grid
    avg_grid_voltage_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_grid_frequency_hz: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_power_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Data quality
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_quality_percent: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)

    # Calculated
    performance_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint('site_id', 'device_id', 'timestamp_hour', name='uq_hourly_site_device_time'),
        Index('idx_hourly_site_time', 'site_id', 'timestamp_hour'),
        Index('idx_hourly_device_time', 'device_id', 'timestamp_hour'),
    )


class TelemetryDailySummaryModel(Base):
    """SQLAlchemy model for daily telemetry summaries."""

    __tablename__ = "telemetry_daily_summary"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Date
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Energy metrics (kWh)
    energy_generated_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_consumed_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_exported_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_imported_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_stored_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_discharged_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    net_energy_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Power metrics (kW)
    peak_power_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    peak_power_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    average_power_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Time-based metrics
    sunshine_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    production_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    grid_outage_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Environmental
    avg_irradiance_w_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_irradiation_kwh_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_humidity_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Battery
    battery_cycles: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_battery_soc_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Grid
    avg_grid_voltage_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_power_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Performance
    performance_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    specific_yield_kwh_kwp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Environmental impact
    co2_avoided_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Financial (PKR)
    estimated_revenue_pkr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_savings_pkr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Data quality
    hours_with_data: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_completeness_percent: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('site_id', 'device_id', 'summary_date', name='uq_daily_site_device_date'),
        Index('idx_daily_site_date', 'site_id', 'summary_date'),
        Index('idx_daily_device_date', 'device_id', 'summary_date'),
    )


class TelemetryMonthlySummaryModel(Base):
    """SQLAlchemy model for monthly telemetry summaries."""

    __tablename__ = "telemetry_monthly_summary"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )

    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Month identifier
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Energy metrics (kWh)
    energy_generated_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_consumed_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_exported_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_imported_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_stored_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_discharged_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    net_energy_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Power metrics
    peak_power_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    peak_power_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    average_daily_generation_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Time metrics
    total_sunshine_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_production_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_grid_outage_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Environmental
    avg_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_irradiation_kwh_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Performance
    performance_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    specific_yield_kwh_kwp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Expected vs actual
    expected_generation_kwh: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    generation_variance_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Environmental impact
    co2_avoided_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    trees_equivalent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Financial (PKR)
    estimated_revenue_pkr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_savings_pkr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Data quality
    days_with_data: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_completeness_percent: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('site_id', 'device_id', 'year', 'month', name='uq_monthly_site_device_period'),
        Index('idx_monthly_site_period', 'site_id', 'year', 'month'),
        Index('idx_monthly_device_period', 'device_id', 'year', 'month'),
    )


class DeviceTelemetrySnapshotModel(Base):
    """SQLAlchemy model for latest device telemetry snapshots."""

    __tablename__ = "device_telemetry_snapshot"

    # Use device_id as primary key (one snapshot per device)
    device_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        primary_key=True,
    )
    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timestamp of reading
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Power readings
    current_power_kw: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    power_limit_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Energy totals
    energy_today_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    energy_lifetime_kwh: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # DC side
    dc_voltage_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dc_current_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dc_power_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # AC side
    ac_voltage_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ac_current_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ac_frequency_hz: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    power_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # 3-phase (L1, L2, L3)
    voltage_l1_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    voltage_l2_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    voltage_l3_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_l1_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_l2_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_l3_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Temperature
    internal_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ambient_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Battery
    battery_soc_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_voltage_v: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_current_a: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_power_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_temperature_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    charging_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Grid/Meter
    grid_import_power_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    grid_export_power_kw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Weather station
    irradiance_w_m2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_speed_m_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status
    operating_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    warning_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Raw data
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_snapshot_site', 'site_id'),
        Index('idx_snapshot_timestamp', 'timestamp'),
    )
