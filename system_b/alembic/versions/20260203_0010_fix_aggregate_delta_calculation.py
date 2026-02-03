"""Fix aggregate to calculate energy deltas instead of sum.

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-03

Bug fix: The telemetry_hourly_local aggregate was using SUM() for energy metrics,
which sums all cumulative counter values instead of calculating the hourly delta.

This caused incorrect values like:
- Peak export showing 545 kWh instead of ~10 kWh
- Off-peak values being artificially inflated

Fix: Use LAST(value, time) - FIRST(value, time) to calculate hourly delta.
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Check if TimescaleDB is available
USE_TIMESCALEDB = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"


def upgrade() -> None:
    """Fix aggregate to calculate deltas instead of sum."""

    if not USE_TIMESCALEDB:
        print("Skipping aggregate fix (USE_TIMESCALEDB=false)")
        return

    print("Fixing telemetry_hourly_local to calculate energy deltas...")

    # =========================================================================
    # Drop Existing Aggregate
    # =========================================================================
    print("Dropping existing telemetry_hourly_local (with incorrect SUM calculation)...")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly_local CASCADE;")

    # =========================================================================
    # Recreate with Correct Delta Calculation
    # =========================================================================
    print("Creating telemetry_hourly_local with correct DELTA calculation...")
    op.execute("""
        CREATE MATERIALIZED VIEW telemetry_hourly_local
        WITH (timescaledb.continuous) AS
        SELECT
            -- Time bucket in UTC (TimescaleDB requirement - cannot transform time column)
            time_bucket('1 hour', tr.time) AS bucket,

            -- Store the site's timezone for query-time conversion
            s.timezone AS site_timezone,

            -- Identifiers
            tr.site_id,
            tr.device_id,
            tr.metric_name,

            -- Statistical aggregates
            AVG(tr.metric_value) as avg_value,
            MIN(tr.metric_value) as min_value,
            MAX(tr.metric_value) as max_value,
            STDDEV(tr.metric_value) as stddev_value,

            -- Sample counts for data quality
            COUNT(*) as sample_count,
            COUNT(*) FILTER (WHERE tr.quality = 'good') as good_samples,

            -- For energy metrics: Calculate DELTA (LAST - FIRST)
            -- Energy counters are cumulative, so we need the difference
            -- between the end and start of each hour
            CASE
                WHEN tr.metric_name LIKE '%_energy_%' OR tr.metric_name LIKE '%_kwh' THEN
                    LAST(tr.metric_value, tr.time) - FIRST(tr.metric_value, tr.time)
                ELSE
                    NULL
            END as total_energy

        FROM telemetry_raw tr
        INNER JOIN sites_metadata s ON tr.site_id = s.id
        GROUP BY bucket, site_timezone, tr.site_id, tr.device_id, tr.metric_name
        WITH NO DATA;
    """)

    print("✓ Created telemetry_hourly_local with delta calculation")

    # =========================================================================
    # Add Refresh Policy
    # =========================================================================
    print("Adding refresh policy...")
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_hourly_local',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        );
    """)

    print("✓ Added refresh policy (hourly)")

    # =========================================================================
    # Create Indexes for Performance
    # =========================================================================
    print("Creating indexes...")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_local_site_bucket
        ON telemetry_hourly_local (site_id, bucket DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_local_site_device_bucket
        ON telemetry_hourly_local (site_id, device_id, bucket DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_local_site_metric_bucket
        ON telemetry_hourly_local (site_id, metric_name, bucket DESC);
    """)

    print("✓ Created indexes")

    # =========================================================================
    # Refresh Data
    # =========================================================================
    print("Refreshing aggregate data for recent period...")
    op.execute("""
        CALL refresh_continuous_aggregate('telemetry_hourly_local',
            NOW() - INTERVAL '30 days',
            NOW()
        );
    """)

    print("✓ Refreshed last 30 days of data")

    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║ BUG FIX COMPLETE: Energy Delta Calculation Fixed                          ║
╠════════════════════════════════════════════════════════════════════════════╣
║ Changes:                                                                   ║
║   - Changed from SUM(metric_value) to LAST - FIRST for energy metrics    ║
║   - This calculates hourly delta instead of summing cumulative values     ║
║   - Refreshed last 30 days of data with correct calculations             ║
║                                                                            ║
║ Expected Results:                                                          ║
║   - Peak export (6-10 PM): ~0-10 kWh (was showing 545 kWh)              ║
║   - Off-peak export: Correct hourly deltas (was inflated)                ║
║   - TOU classification now uses accurate energy values                    ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)


def downgrade() -> None:
    """Revert to SUM-based calculation (not recommended)."""

    if not USE_TIMESCALEDB:
        return

    print("WARNING: Reverting to incorrect SUM calculation!")
    print("This will restore the bug. Only use this for testing.")

    # Drop the fixed aggregate
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly_local CASCADE;")

    # Recreate with the old (buggy) SUM calculation
    op.execute("""
        CREATE MATERIALIZED VIEW telemetry_hourly_local
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', tr.time) AS bucket,
            s.timezone AS site_timezone,
            tr.site_id,
            tr.device_id,
            tr.metric_name,
            AVG(tr.metric_value) as avg_value,
            MIN(tr.metric_value) as min_value,
            MAX(tr.metric_value) as max_value,
            STDDEV(tr.metric_value) as stddev_value,
            COUNT(*) as sample_count,
            COUNT(*) FILTER (WHERE tr.quality = 'good') as good_samples,
            SUM(tr.metric_value) FILTER (
                WHERE tr.metric_name LIKE '%_energy_%' OR tr.metric_name LIKE '%_kwh'
            ) as total_energy
        FROM telemetry_raw tr
        INNER JOIN sites_metadata s ON tr.site_id = s.id
        GROUP BY bucket, site_timezone, tr.site_id, tr.device_id, tr.metric_name
        WITH NO DATA;
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_hourly_local',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        );
    """)

    print("✓ Reverted to buggy SUM calculation")
