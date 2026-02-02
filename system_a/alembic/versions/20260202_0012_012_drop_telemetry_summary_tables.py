"""Drop telemetry summary tables after System B migration

Revision ID: 20260202_0012
Revises: dcf3f785fbc8
Create Date: 2026-02-02

This migration drops the telemetry summary tables from System A after migrating
billing calculations to use System B's TimescaleDB continuous aggregates.

WARNING: This is a BREAKING CHANGE. Ensure the following before running:
1. System B is fully operational and reliable
2. Billing has been running on System B successfully for at least 30 days
3. All dependent modules have been migrated to use System B
4. Full database backup has been created
5. Telemetry sync service has been disabled

BACKUP INSTRUCTIONS:
Before running this migration, create a backup:
    pg_dump -h localhost -U postgres -d solar_hub_a \
      --table=telemetry_hourly_summary \
      --table=telemetry_daily_summary \
      --table=telemetry_monthly_summary \
      --table=device_telemetry_snapshot \
      --file=backup_system_a_summaries_2026-02-02.sql

ROLLBACK:
If you need to rollback, you MUST restore from the backup file:
    psql -h localhost -U postgres -d solar_hub_a < backup_system_a_summaries_2026-02-02.sql
    alembic downgrade -1
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260202_0012'
down_revision = 'dcf3f785fbc8'  # Links to add_device_settings_table migration
branch_labels = None
depends_on = None


def upgrade():
    """
    Drop telemetry summary tables.

    These tables are no longer needed after migrating to System B.
    """
    # Drop tables in reverse dependency order (children first, parents last)

    # Drop device_telemetry_snapshot (no foreign key dependencies)
    op.execute('DROP TABLE IF EXISTS device_telemetry_snapshot CASCADE')

    # Drop telemetry summary tables
    op.execute('DROP TABLE IF EXISTS telemetry_monthly_summary CASCADE')
    op.execute('DROP TABLE IF EXISTS telemetry_daily_summary CASCADE')
    op.execute('DROP TABLE IF EXISTS telemetry_hourly_summary CASCADE')

    # Log migration
    print("\n" + "="*80)
    print("TELEMETRY SUMMARY TABLES DROPPED")
    print("="*80)
    print("The following tables have been permanently removed from System A:")
    print("  - telemetry_hourly_summary")
    print("  - telemetry_daily_summary")
    print("  - telemetry_monthly_summary")
    print("  - device_telemetry_snapshot")
    print("\nBilling module now uses System B (TimescaleDB) for all telemetry queries.")
    print("="*80 + "\n")


def downgrade():
    """
    Recreate telemetry summary tables.

    WARNING: This only recreates the schema, NOT the data.
    You MUST restore data from backup after running this downgrade.
    """
    # Recreate telemetry_hourly_summary
    op.create_table(
        'telemetry_hourly_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('timestamp_hour', sa.DateTime(timezone=True), nullable=False),
        sa.Column('energy_generated_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_consumed_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_exported_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_imported_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_stored_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_discharged_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('peak_power_kw', sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column('average_power_kw', sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column('avg_irradiance_w_m2', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('avg_temperature_c', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('max_temperature_c', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('min_temperature_c', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('avg_battery_soc_percent', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('avg_grid_voltage_v', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('avg_power_factor', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('sample_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Recreate indexes
    op.create_index('idx_telemetry_hourly_site_time', 'telemetry_hourly_summary', ['site_id', 'timestamp_hour'], unique=False)
    op.create_index('idx_telemetry_hourly_device_time', 'telemetry_hourly_summary', ['device_id', 'timestamp_hour'], unique=False)

    # Unique constraint for site-level aggregates
    op.execute("""
        CREATE UNIQUE INDEX uq_hourly_site_time_no_device
        ON telemetry_hourly_summary (site_id, timestamp_hour)
        WHERE device_id IS NULL
    """)

    # Unique constraint for device-level aggregates
    op.create_index('uq_hourly_site_device_time', 'telemetry_hourly_summary', ['site_id', 'device_id', 'timestamp_hour'], unique=True)

    # Recreate telemetry_daily_summary
    op.create_table(
        'telemetry_daily_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('summary_date', sa.Date(), nullable=False),
        sa.Column('energy_generated_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_consumed_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_exported_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_imported_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_stored_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_discharged_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('net_energy_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('peak_power_kw', sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column('peak_power_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('average_power_kw', sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column('sunshine_hours', sa.Numeric(precision=5, scale=2), server_default='0.0', nullable=True),
        sa.Column('production_hours', sa.Numeric(precision=5, scale=2), server_default='0.0', nullable=True),
        sa.Column('performance_ratio', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('capacity_factor', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('grid_outage_minutes', sa.Integer(), server_default='0', nullable=True),
        sa.Column('avg_irradiance_w_m2', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('avg_temperature_c', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('max_temperature_c', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('min_temperature_c', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('co2_avoided_kg', sa.Numeric(precision=10, scale=3), server_default='0.0', nullable=True),
        sa.Column('estimated_savings_pkr', sa.Numeric(precision=12, scale=2), server_default='0.0', nullable=True),
        sa.Column('hours_with_data', sa.Integer(), server_default='0', nullable=True),
        sa.Column('data_completeness_percent', sa.Numeric(precision=5, scale=2), server_default='0.0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Recreate indexes
    op.create_index('idx_telemetry_daily_site_date', 'telemetry_daily_summary', ['site_id', 'summary_date'], unique=False)
    op.create_index('idx_telemetry_daily_device_date', 'telemetry_daily_summary', ['device_id', 'summary_date'], unique=False)

    # Unique constraints
    op.execute("""
        CREATE UNIQUE INDEX uq_daily_site_date_no_device
        ON telemetry_daily_summary (site_id, summary_date)
        WHERE device_id IS NULL
    """)
    op.create_index('uq_daily_site_device_date', 'telemetry_daily_summary', ['site_id', 'device_id', 'summary_date'], unique=True)

    # Recreate telemetry_monthly_summary (simplified)
    op.create_table(
        'telemetry_monthly_summary',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('energy_generated_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_consumed_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('idx_telemetry_monthly_site_period', 'telemetry_monthly_summary', ['site_id', 'year', 'month'], unique=False)

    # Recreate device_telemetry_snapshot (simplified)
    op.create_table(
        'device_telemetry_snapshot',
        sa.Column('device_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('site_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_power_kw', sa.Numeric(precision=10, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_today_kwh', sa.Numeric(precision=10, scale=3), server_default='0.0', nullable=True),
        sa.Column('energy_lifetime_kwh', sa.Numeric(precision=12, scale=3), server_default='0.0', nullable=True),
        sa.PrimaryKeyConstraint('device_id')
    )

    # Log downgrade warning
    print("\n" + "="*80)
    print("WARNING: SCHEMA RECREATED BUT DATA IS EMPTY")
    print("="*80)
    print("Telemetry summary tables have been recreated, but contain NO DATA.")
    print("\nTo restore data, run:")
    print("  psql -h localhost -U postgres -d solar_hub_a < backup_system_a_summaries_2026-02-02.sql")
    print("\nAfter restoring data, you must also:")
    print("  1. Re-enable telemetry sync service")
    print("  2. Set use_system_b_for_billing=False")
    print("  3. Restart all services")
    print("="*80 + "\n")
