"""Add daily and monthly continuous aggregates for long-term retention.

Revision ID: 0008
Revises: 0006
Create Date: TBD (run this 3-6 months after 0006)

This migration creates hierarchical continuous aggregates to support
retention policies on hourly data while preserving long-term historical data.

Storage strategy:
- Hourly: Keep 90 days (~2.2M rows for 100 sites)
- Daily: Keep 2 years (~73K rows for 100 sites)
- Monthly: Keep forever (~2.4K rows for 100 sites)

This reduces storage by 95% while maintaining queryability of historical data.
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Check if TimescaleDB is available
USE_TIMESCALEDB = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"


def upgrade() -> None:
    """Create daily and monthly continuous aggregates."""

    if not USE_TIMESCALEDB:
        print("Skipping daily/monthly aggregates (USE_TIMESCALEDB=false)")
        return

    print("Creating daily continuous aggregate...")

    # =========================================================================
    # Daily Continuous Aggregate
    # =========================================================================
    # Aggregate from hourly buckets to daily buckets
    # Each daily bucket contains 24 hourly buckets
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_daily_local
        WITH (timescaledb.continuous) AS
        SELECT
            -- Daily bucket (still in UTC, timezone stored separately)
            time_bucket('1 day', bucket) AS bucket,

            -- Store timezone for query-time conversion
            site_timezone,

            -- Identifiers
            site_id,
            device_id,
            metric_name,

            -- Aggregate the hourly aggregates
            AVG(avg_value) as avg_value,
            MIN(min_value) as min_value,
            MAX(max_value) as max_value,

            -- Sum of hourly counts
            SUM(sample_count) as sample_count,
            SUM(good_samples) as good_samples,

            -- Sum of hourly energy totals
            SUM(total_energy) as total_energy

        FROM telemetry_hourly_local
        GROUP BY bucket, site_timezone, site_id, device_id, metric_name
        WITH NO DATA;
    """)

    print("✓ Created telemetry_daily_local")

    # Add refresh policy - refresh daily at 2 AM
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_daily_local',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day'
        );
    """)

    print("✓ Added daily refresh policy")

    # =========================================================================
    # Monthly Continuous Aggregate
    # =========================================================================
    # Aggregate from daily buckets to monthly buckets
    # Each monthly bucket contains ~30 daily buckets
    print("Creating monthly continuous aggregate...")

    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_monthly_local
        WITH (timescaledb.continuous) AS
        SELECT
            -- Monthly bucket (first day of month)
            time_bucket('1 month', bucket) AS bucket,

            -- Store timezone
            site_timezone,

            -- Identifiers
            site_id,
            device_id,
            metric_name,

            -- Aggregate the daily aggregates
            AVG(avg_value) as avg_value,
            MIN(min_value) as min_value,
            MAX(max_value) as max_value,

            -- Sum of daily counts
            SUM(sample_count) as sample_count,
            SUM(good_samples) as good_samples,

            -- Sum of daily energy totals
            SUM(total_energy) as total_energy

        FROM telemetry_daily_local
        GROUP BY bucket, site_timezone, site_id, device_id, metric_name
        WITH NO DATA;
    """)

    print("✓ Created telemetry_monthly_local")

    # Add refresh policy - refresh monthly on 1st of month
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_monthly_local',
            start_offset => INTERVAL '62 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day'
        );
    """)

    print("✓ Added monthly refresh policy")

    # =========================================================================
    # Create Indexes
    # =========================================================================
    print("Creating indexes...")

    # Daily indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_daily_local_site_bucket
        ON telemetry_daily_local (site_id, bucket DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_daily_local_site_metric_bucket
        ON telemetry_daily_local (site_id, metric_name, bucket DESC);
    """)

    # Monthly indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_monthly_local_site_bucket
        ON telemetry_monthly_local (site_id, bucket DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_monthly_local_site_metric_bucket
        ON telemetry_monthly_local (site_id, metric_name, bucket DESC);
    """)

    print("✓ Created indexes")

    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║ Daily and Monthly Aggregates Created                                      ║
╠════════════════════════════════════════════════════════════════════════════╣
║ Status: Hierarchical aggregation enabled                                  ║
║                                                                            ║
║ Next Steps:                                                                ║
║   1. Backfill daily aggregates from hourly data                           ║
║   2. Backfill monthly aggregates from daily data                          ║
║   3. Add retention policies:                                              ║
║      - telemetry_hourly_local: 90 days                                    ║
║      - telemetry_daily_local: 2 years                                     ║
║      - telemetry_monthly_local: forever                                   ║
║   4. Update application code to use smart query router                    ║
║                                                                            ║
║ Storage Impact:                                                            ║
║   Before: All hourly data forever (~100 GB/year for 100 sites)           ║
║   After: Hourly (90d) + Daily (2y) + Monthly (∞) (~5 GB total)           ║
║   Savings: ~95% storage reduction                                         ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)


def downgrade() -> None:
    """Remove daily and monthly continuous aggregates."""

    if not USE_TIMESCALEDB:
        return

    print("Removing daily and monthly continuous aggregates...")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_telemetry_monthly_local_site_metric_bucket;")
    op.execute("DROP INDEX IF EXISTS idx_telemetry_monthly_local_site_bucket;")
    op.execute("DROP INDEX IF EXISTS idx_telemetry_daily_local_site_metric_bucket;")
    op.execute("DROP INDEX IF EXISTS idx_telemetry_daily_local_site_bucket;")

    # Drop aggregates (cascade removes policies)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_monthly_local CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_daily_local CASCADE;")

    print("✓ Removed daily and monthly aggregates")
