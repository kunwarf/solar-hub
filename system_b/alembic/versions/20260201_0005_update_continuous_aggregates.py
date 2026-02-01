"""Update continuous aggregates and retention policies.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-01

Replaces old continuous aggregates with new 4-tier hierarchy:
- Drops old: telemetry_5min, telemetry_hourly, telemetry_daily (from 0002)
- Creates new: telemetry_hourly (1 year), telemetry_daily (3 years),
               telemetry_monthly (5 years), telemetry_yearly (forever)

Also adds compression and retention policies for telemetry_raw.
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Check if TimescaleDB is available
USE_TIMESCALEDB = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"


def upgrade() -> None:
    """Create continuous aggregates and policies."""

    if not USE_TIMESCALEDB:
        print("Skipping continuous aggregates (USE_TIMESCALEDB=false)")
        return

    # =========================================================================
    # 0. Drop old continuous aggregates from migration 0002
    # =========================================================================
    print("Dropping old continuous aggregates...")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_5min CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_daily CASCADE;")

    # =========================================================================
    # 1. Create Hourly Continuous Aggregate
    # =========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            site_id,
            device_id,
            metric_name,

            -- Statistical aggregates
            AVG(metric_value) as avg_value,
            MIN(metric_value) as min_value,
            MAX(metric_value) as max_value,
            STDDEV(metric_value) as stddev_value,

            -- Sample counts for data quality
            COUNT(*) as sample_count,
            COUNT(*) FILTER (WHERE quality = 'good') as good_samples,

            -- For energy metrics (sum cumulative values)
            SUM(metric_value) FILTER (
                WHERE metric_name LIKE '%_energy_%' OR metric_name LIKE '%_kwh'
            ) as total_energy
        FROM telemetry_raw
        GROUP BY bucket, site_id, device_id, metric_name
        WITH NO DATA;
    """)

    # Add refresh policy for hourly (refresh every hour)
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_hourly',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        );
    """)

    # Add retention policy (keep 1 year)
    op.execute("""
        SELECT add_retention_policy('telemetry_hourly', INTERVAL '1 year');
    """)

    # =========================================================================
    # 2. Create Daily Continuous Aggregate
    # =========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', bucket) AS bucket,
            site_id,
            device_id,
            metric_name,

            -- Aggregate the hourly aggregates
            AVG(avg_value) as avg_value,
            MIN(min_value) as min_value,
            MAX(max_value) as max_value,

            -- Energy totals per day
            SUM(total_energy) as daily_energy,

            -- Data quality metrics
            SUM(sample_count) as total_samples,
            SUM(good_samples) as good_samples,

            -- Calculate daily availability percentage
            CASE
                WHEN SUM(sample_count) > 0 THEN
                    (SUM(good_samples)::float / SUM(sample_count)::float * 100)
                ELSE 0
            END as availability_pct
        FROM telemetry_hourly
        GROUP BY bucket, site_id, device_id, metric_name
        WITH NO DATA;
    """)

    # Add refresh policy for daily (refresh daily at 1 AM)
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_daily',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day'
        );
    """)

    # Add retention policy (keep 3 years)
    op.execute("""
        SELECT add_retention_policy('telemetry_daily', INTERVAL '3 years');
    """)

    # =========================================================================
    # 3. Create Monthly Continuous Aggregate
    # =========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_monthly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 month', bucket) AS bucket,
            site_id,
            device_id,
            metric_name,

            -- Monthly statistics
            AVG(avg_value) as avg_value,
            MIN(min_value) as min_value,
            MAX(max_value) as max_value,

            -- Monthly energy totals
            SUM(daily_energy) as monthly_energy,

            -- Monthly availability
            CASE
                WHEN SUM(total_samples) > 0 THEN
                    (SUM(good_samples)::float / SUM(total_samples)::float * 100)
                ELSE 0
            END as availability_pct,

            -- Days with data in this month
            COUNT(DISTINCT bucket::date) as days_with_data
        FROM telemetry_daily
        GROUP BY bucket, site_id, device_id, metric_name
        WITH NO DATA;
    """)

    # Add refresh policy for monthly (refresh daily)
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_monthly',
            start_offset => INTERVAL '3 months',
            end_offset => INTERVAL '1 month',
            schedule_interval => INTERVAL '1 day'
        );
    """)

    # Add retention policy (keep 5 years)
    op.execute("""
        SELECT add_retention_policy('telemetry_monthly', INTERVAL '5 years');
    """)

    # =========================================================================
    # 4. Create Yearly Continuous Aggregate
    # =========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_yearly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 year', bucket) AS bucket,
            site_id,
            device_id,
            metric_name,

            -- Yearly statistics
            AVG(avg_value) as avg_value,
            MIN(min_value) as min_value,
            MAX(max_value) as max_value,

            -- Yearly energy totals
            SUM(monthly_energy) as yearly_energy,

            -- Yearly availability
            CASE
                WHEN SUM(good_samples) > 0 THEN
                    (SUM(good_samples)::float / NULLIF(SUM(total_samples), 0)::float * 100)
                ELSE 0
            END as availability_pct,

            -- Months with data in this year
            COUNT(DISTINCT bucket) as months_with_data
        FROM telemetry_monthly
        GROUP BY bucket, site_id, device_id, metric_name
        WITH NO DATA;
    """)

    # Add refresh policy for yearly (refresh weekly)
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_yearly',
            start_offset => INTERVAL '2 years',
            end_offset => INTERVAL '1 year',
            schedule_interval => INTERVAL '1 week'
        );
    """)

    # No retention policy for yearly - keep forever

    # =========================================================================
    # 5. Add Compression Policy for Raw Data
    # =========================================================================
    # Compress data older than 7 days (before deletion at 90 days)
    op.execute("""
        SELECT add_compression_policy('telemetry_raw', INTERVAL '7 days');
    """)

    # =========================================================================
    # 6. Add Retention Policy for Raw Data
    # =========================================================================
    # Drop raw data older than 90 days
    op.execute("""
        SELECT add_retention_policy('telemetry_raw', INTERVAL '90 days');
    """)

    print("✓ Created continuous aggregates:")
    print("  - telemetry_hourly (1 year retention)")
    print("  - telemetry_daily (3 years retention)")
    print("  - telemetry_monthly (5 years retention)")
    print("  - telemetry_yearly (forever)")
    print("✓ Added compression policy: 7 days")
    print("✓ Added retention policy: 90 days")


def downgrade() -> None:
    """Remove continuous aggregates and policies."""

    if not USE_TIMESCALEDB:
        return

    # Drop continuous aggregates (cascade drops policies)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_yearly CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_monthly CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_daily CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly CASCADE;")

    # Remove policies from telemetry_raw
    op.execute("""
        SELECT remove_compression_policy('telemetry_raw', if_exists => true);
    """)
    op.execute("""
        SELECT remove_retention_policy('telemetry_raw', if_exists => true);
    """)

    print("✓ Dropped all continuous aggregates and policies")
