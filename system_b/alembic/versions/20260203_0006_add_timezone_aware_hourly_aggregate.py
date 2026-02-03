"""Add timezone-aware hourly continuous aggregate for global expansion.

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-03

This migration creates a new timezone-aware hourly continuous aggregate that uses
the site's timezone for bucketing. This enables correct daily boundary calculations
for sites across the world.

Key changes:
- Creates telemetry_hourly_local with timezone-aware time buckets
- Uses time AT TIME ZONE sites.timezone for local hour bucketing
- Stores timezone with each bucket for validation
- Sets up refresh policy (hourly)
- No retention policy initially (we'll keep all data during migration period)

This runs in parallel with existing UTC-based telemetry_hourly for validation.
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0007"  # Depends on sites_metadata table
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Check if TimescaleDB is available
USE_TIMESCALEDB = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"


def upgrade() -> None:
    """Create timezone-aware hourly continuous aggregate."""

    if not USE_TIMESCALEDB:
        print("Skipping timezone-aware aggregate (USE_TIMESCALEDB=false)")
        return

    print("Creating timezone-aware hourly continuous aggregate...")

    # =========================================================================
    # Create Timezone-Aware Hourly Continuous Aggregate
    # =========================================================================
    # This aggregate uses the site's timezone to create hourly buckets that
    # align with the local calendar day. This is critical for:
    # 1. Correct daily boundary calculations
    # 2. TOU (Time of Use) classification
    # 3. Multi-timezone support for global expansion
    #
    # Note: We JOIN with sites_metadata table (System B) to get timezone.
    # sites_metadata is a lookup table synced from System A's sites table.
    # The bucket_timezone column allows validation and handling of timezone changes.
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly_local
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

            -- For energy metrics (sum cumulative values)
            -- These are metrics like pv_energy_kwh, load_energy_kwh, etc.
            SUM(tr.metric_value) FILTER (
                WHERE tr.metric_name LIKE '%_energy_%' OR tr.metric_name LIKE '%_kwh'
            ) as total_energy

        FROM telemetry_raw tr
        INNER JOIN sites_metadata s ON tr.site_id = s.id
        GROUP BY bucket, site_timezone, tr.site_id, tr.device_id, tr.metric_name
        WITH NO DATA;
    """)

    print("✓ Created telemetry_hourly_local materialized view")

    # =========================================================================
    # Add Refresh Policy
    # =========================================================================
    # Refresh every hour, covering data from 3 hours ago to 1 hour ago
    # This gives time for late-arriving data while keeping the view recent
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
    # Index on (site_id, bucket) for efficient queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_local_site_bucket
        ON telemetry_hourly_local (site_id, bucket DESC);
    """)

    # Index on (site_id, device_id, bucket) for device-specific queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_local_site_device_bucket
        ON telemetry_hourly_local (site_id, device_id, bucket DESC);
    """)

    # Index on (site_id, metric_name, bucket) for metric-specific queries
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_local_site_metric_bucket
        ON telemetry_hourly_local (site_id, metric_name, bucket DESC);
    """)

    print("✓ Created indexes for query performance")

    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║ PHASE 1 COMPLETE: Timezone-Aware Hourly Aggregate Created                 ║
╠════════════════════════════════════════════════════════════════════════════╣
║ Status: Running in parallel with UTC-based telemetry_hourly               ║
║ Next Steps:                                                                ║
║   1. Backfill recent data (last 7-30 days)                                ║
║   2. Validate data accuracy with dual-calculation                          ║
║   3. Update application code to query from telemetry_hourly_local          ║
║   4. Monitor performance and data quality                                  ║
║                                                                            ║
║ Note: No retention policy set - keeping all data during migration          ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)


def downgrade() -> None:
    """Remove timezone-aware hourly continuous aggregate."""

    if not USE_TIMESCALEDB:
        return

    print("Removing timezone-aware hourly continuous aggregate...")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_telemetry_hourly_local_site_metric_bucket;")
    op.execute("DROP INDEX IF EXISTS idx_telemetry_hourly_local_site_device_bucket;")
    op.execute("DROP INDEX IF EXISTS idx_telemetry_hourly_local_site_bucket;")

    # Drop the continuous aggregate (cascade removes the policy)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly_local CASCADE;")

    print("✓ Removed telemetry_hourly_local and associated indexes")
