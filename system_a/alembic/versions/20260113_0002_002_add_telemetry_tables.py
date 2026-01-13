"""Add telemetry summary tables

Revision ID: 002
Revises: 001
Create Date: 2026-01-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # TELEMETRY HOURLY SUMMARY
    # =========================================================================
    op.create_table(
        'telemetry_hourly_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('devices.id', ondelete='CASCADE'), nullable=True, index=True),

        # Time bucket
        sa.Column('timestamp_hour', sa.DateTime(timezone=True), nullable=False, index=True),

        # Energy metrics (kWh)
        sa.Column('energy_generated_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_consumed_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_exported_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_imported_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_stored_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_discharged_kwh', sa.Float(), default=0.0, nullable=False),

        # Power metrics (kW)
        sa.Column('peak_power_kw', sa.Float(), default=0.0, nullable=False),
        sa.Column('peak_power_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('average_power_kw', sa.Float(), default=0.0, nullable=False),
        sa.Column('min_power_kw', sa.Float(), default=0.0, nullable=False),

        # Environmental
        sa.Column('avg_irradiance_w_m2', sa.Float(), nullable=True),
        sa.Column('avg_temperature_c', sa.Float(), nullable=True),
        sa.Column('max_temperature_c', sa.Float(), nullable=True),
        sa.Column('min_temperature_c', sa.Float(), nullable=True),

        # Battery
        sa.Column('avg_battery_soc_percent', sa.Float(), nullable=True),
        sa.Column('min_battery_soc_percent', sa.Float(), nullable=True),
        sa.Column('max_battery_soc_percent', sa.Float(), nullable=True),

        # Grid
        sa.Column('avg_grid_voltage_v', sa.Float(), nullable=True),
        sa.Column('avg_grid_frequency_hz', sa.Float(), nullable=True),
        sa.Column('avg_power_factor', sa.Float(), nullable=True),

        # Data quality
        sa.Column('sample_count', sa.Integer(), default=0, nullable=False),
        sa.Column('data_quality_percent', sa.Float(), default=100.0, nullable=False),

        # Calculated
        sa.Column('performance_ratio', sa.Float(), nullable=True),
        sa.Column('capacity_factor', sa.Float(), nullable=True),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Composite indexes for hourly
    op.create_unique_constraint('uq_hourly_site_device_time', 'telemetry_hourly_summary', ['site_id', 'device_id', 'timestamp_hour'])
    op.create_index('idx_hourly_site_time', 'telemetry_hourly_summary', ['site_id', 'timestamp_hour'])
    op.create_index('idx_hourly_device_time', 'telemetry_hourly_summary', ['device_id', 'timestamp_hour'])

    # =========================================================================
    # TELEMETRY DAILY SUMMARY
    # =========================================================================
    op.create_table(
        'telemetry_daily_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('devices.id', ondelete='CASCADE'), nullable=True, index=True),

        # Date
        sa.Column('summary_date', sa.Date(), nullable=False, index=True),

        # Energy metrics (kWh)
        sa.Column('energy_generated_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_consumed_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_exported_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_imported_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_stored_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_discharged_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('net_energy_kwh', sa.Float(), default=0.0, nullable=False),

        # Power metrics (kW)
        sa.Column('peak_power_kw', sa.Float(), default=0.0, nullable=False),
        sa.Column('peak_power_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('average_power_kw', sa.Float(), default=0.0, nullable=False),

        # Time-based metrics
        sa.Column('sunshine_hours', sa.Float(), default=0.0, nullable=False),
        sa.Column('production_hours', sa.Float(), default=0.0, nullable=False),
        sa.Column('grid_outage_minutes', sa.Integer(), default=0, nullable=False),

        # Environmental
        sa.Column('avg_irradiance_w_m2', sa.Float(), nullable=True),
        sa.Column('total_irradiation_kwh_m2', sa.Float(), nullable=True),
        sa.Column('avg_temperature_c', sa.Float(), nullable=True),
        sa.Column('max_temperature_c', sa.Float(), nullable=True),
        sa.Column('min_temperature_c', sa.Float(), nullable=True),
        sa.Column('avg_humidity_percent', sa.Float(), nullable=True),

        # Battery
        sa.Column('battery_cycles', sa.Float(), default=0.0, nullable=False),
        sa.Column('avg_battery_soc_percent', sa.Float(), nullable=True),

        # Grid
        sa.Column('avg_grid_voltage_v', sa.Float(), nullable=True),
        sa.Column('avg_power_factor', sa.Float(), nullable=True),

        # Performance
        sa.Column('performance_ratio', sa.Float(), nullable=True),
        sa.Column('capacity_factor', sa.Float(), nullable=True),
        sa.Column('specific_yield_kwh_kwp', sa.Float(), nullable=True),

        # Environmental impact
        sa.Column('co2_avoided_kg', sa.Float(), default=0.0, nullable=False),

        # Financial (PKR)
        sa.Column('estimated_revenue_pkr', sa.Float(), default=0.0, nullable=False),
        sa.Column('estimated_savings_pkr', sa.Float(), default=0.0, nullable=False),

        # Data quality
        sa.Column('hours_with_data', sa.Integer(), default=0, nullable=False),
        sa.Column('data_completeness_percent', sa.Float(), default=100.0, nullable=False),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Composite indexes for daily
    op.create_unique_constraint('uq_daily_site_device_date', 'telemetry_daily_summary', ['site_id', 'device_id', 'summary_date'])
    op.create_index('idx_daily_site_date', 'telemetry_daily_summary', ['site_id', 'summary_date'])
    op.create_index('idx_daily_device_date', 'telemetry_daily_summary', ['device_id', 'summary_date'])

    # =========================================================================
    # TELEMETRY MONTHLY SUMMARY
    # =========================================================================
    op.create_table(
        'telemetry_monthly_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('devices.id', ondelete='CASCADE'), nullable=True, index=True),

        # Month identifier
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),

        # Energy metrics (kWh)
        sa.Column('energy_generated_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_consumed_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_exported_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_imported_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_stored_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_discharged_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('net_energy_kwh', sa.Float(), default=0.0, nullable=False),

        # Power metrics
        sa.Column('peak_power_kw', sa.Float(), default=0.0, nullable=False),
        sa.Column('peak_power_date', sa.Date(), nullable=True),
        sa.Column('average_daily_generation_kwh', sa.Float(), default=0.0, nullable=False),

        # Time metrics
        sa.Column('total_sunshine_hours', sa.Float(), default=0.0, nullable=False),
        sa.Column('total_production_hours', sa.Float(), default=0.0, nullable=False),
        sa.Column('total_grid_outage_minutes', sa.Integer(), default=0, nullable=False),

        # Environmental
        sa.Column('avg_temperature_c', sa.Float(), nullable=True),
        sa.Column('total_irradiation_kwh_m2', sa.Float(), nullable=True),

        # Performance
        sa.Column('performance_ratio', sa.Float(), nullable=True),
        sa.Column('capacity_factor', sa.Float(), nullable=True),
        sa.Column('specific_yield_kwh_kwp', sa.Float(), nullable=True),

        # Expected vs actual
        sa.Column('expected_generation_kwh', sa.Float(), nullable=True),
        sa.Column('generation_variance_percent', sa.Float(), nullable=True),

        # Environmental impact
        sa.Column('co2_avoided_kg', sa.Float(), default=0.0, nullable=False),
        sa.Column('trees_equivalent', sa.Float(), default=0.0, nullable=False),

        # Financial (PKR)
        sa.Column('estimated_revenue_pkr', sa.Float(), default=0.0, nullable=False),
        sa.Column('estimated_savings_pkr', sa.Float(), default=0.0, nullable=False),

        # Data quality
        sa.Column('days_with_data', sa.Integer(), default=0, nullable=False),
        sa.Column('data_completeness_percent', sa.Float(), default=100.0, nullable=False),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Composite indexes for monthly
    op.create_unique_constraint('uq_monthly_site_device_period', 'telemetry_monthly_summary', ['site_id', 'device_id', 'year', 'month'])
    op.create_index('idx_monthly_site_period', 'telemetry_monthly_summary', ['site_id', 'year', 'month'])
    op.create_index('idx_monthly_device_period', 'telemetry_monthly_summary', ['device_id', 'year', 'month'])

    # =========================================================================
    # DEVICE TELEMETRY SNAPSHOT (Latest readings)
    # =========================================================================
    op.create_table(
        'device_telemetry_snapshot',
        # Device ID is primary key (one snapshot per device)
        sa.Column('device_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('devices.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sites.id', ondelete='CASCADE'), nullable=False, index=True),

        # Timestamp of reading
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),

        # Power readings
        sa.Column('current_power_kw', sa.Float(), default=0.0, nullable=False),
        sa.Column('power_limit_kw', sa.Float(), nullable=True),

        # Energy totals
        sa.Column('energy_today_kwh', sa.Float(), default=0.0, nullable=False),
        sa.Column('energy_lifetime_kwh', sa.Float(), default=0.0, nullable=False),

        # DC side
        sa.Column('dc_voltage_v', sa.Float(), nullable=True),
        sa.Column('dc_current_a', sa.Float(), nullable=True),
        sa.Column('dc_power_kw', sa.Float(), nullable=True),

        # AC side
        sa.Column('ac_voltage_v', sa.Float(), nullable=True),
        sa.Column('ac_current_a', sa.Float(), nullable=True),
        sa.Column('ac_frequency_hz', sa.Float(), nullable=True),
        sa.Column('power_factor', sa.Float(), nullable=True),

        # 3-phase
        sa.Column('voltage_l1_v', sa.Float(), nullable=True),
        sa.Column('voltage_l2_v', sa.Float(), nullable=True),
        sa.Column('voltage_l3_v', sa.Float(), nullable=True),
        sa.Column('current_l1_a', sa.Float(), nullable=True),
        sa.Column('current_l2_a', sa.Float(), nullable=True),
        sa.Column('current_l3_a', sa.Float(), nullable=True),

        # Temperature
        sa.Column('internal_temperature_c', sa.Float(), nullable=True),
        sa.Column('ambient_temperature_c', sa.Float(), nullable=True),

        # Battery
        sa.Column('battery_soc_percent', sa.Float(), nullable=True),
        sa.Column('battery_voltage_v', sa.Float(), nullable=True),
        sa.Column('battery_current_a', sa.Float(), nullable=True),
        sa.Column('battery_power_kw', sa.Float(), nullable=True),
        sa.Column('battery_temperature_c', sa.Float(), nullable=True),
        sa.Column('charging_state', sa.String(50), nullable=True),

        # Grid/Meter
        sa.Column('grid_import_power_kw', sa.Float(), nullable=True),
        sa.Column('grid_export_power_kw', sa.Float(), nullable=True),

        # Weather station
        sa.Column('irradiance_w_m2', sa.Float(), nullable=True),
        sa.Column('wind_speed_m_s', sa.Float(), nullable=True),
        sa.Column('humidity_percent', sa.Float(), nullable=True),

        # Status
        sa.Column('operating_state', sa.String(100), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('warning_code', sa.String(50), nullable=True),

        # Raw data
        sa.Column('raw_data', postgresql.JSONB(), nullable=True),

        # Audit
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index('idx_snapshot_site', 'device_telemetry_snapshot', ['site_id'])
    op.create_index('idx_snapshot_timestamp', 'device_telemetry_snapshot', ['timestamp'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_snapshot_timestamp', 'device_telemetry_snapshot')
    op.drop_index('idx_snapshot_site', 'device_telemetry_snapshot')
    op.drop_table('device_telemetry_snapshot')

    op.drop_index('idx_monthly_device_period', 'telemetry_monthly_summary')
    op.drop_index('idx_monthly_site_period', 'telemetry_monthly_summary')
    op.drop_constraint('uq_monthly_site_device_period', 'telemetry_monthly_summary')
    op.drop_table('telemetry_monthly_summary')

    op.drop_index('idx_daily_device_date', 'telemetry_daily_summary')
    op.drop_index('idx_daily_site_date', 'telemetry_daily_summary')
    op.drop_constraint('uq_daily_site_device_date', 'telemetry_daily_summary')
    op.drop_table('telemetry_daily_summary')

    op.drop_index('idx_hourly_device_time', 'telemetry_hourly_summary')
    op.drop_index('idx_hourly_site_time', 'telemetry_hourly_summary')
    op.drop_constraint('uq_hourly_site_device_time', 'telemetry_hourly_summary')
    op.drop_table('telemetry_hourly_summary')
