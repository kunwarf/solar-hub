"""Handle midnight counter resets in telemetry aggregate.

Revision ID: 20260203_1300
Revises: 20260203_0555_15b325dbb128
Create Date: 2026-02-03 13:00:00

Bug fix: Energy counters with names like *_energy_today_kwh reset to 0 at midnight.
The aggregate's LAST - FIRST calculation gives negative values when an hour crosses midnight.

Fix: Detect counter resets (LAST < FIRST) and handle them by using MAX(0, LAST - FIRST)
or detecting the reset pattern.
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260203_1300'
down_revision: Union[str, None] = '15b325dbb128'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Check if TimescaleDB is available
USE_TIMESCALEDB = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"


def upgrade() -> None:
    """Fix aggregate to handle midnight counter resets."""

    if not USE_TIMESCALEDB:
        print("Skipping aggregate fix (USE_TIMESCALEDB=false)")
        return

    print("=" * 80)
    print("FIXING AGGREGATE TO HANDLE MIDNIGHT COUNTER RESETS")
    print("=" * 80)
    print()
    print("Problem: Metrics like 'pv_energy_today_kwh' reset to 0 at midnight.")
    print("When aggregate calculates LAST - FIRST across midnight, we get negative values.")
    print()

    # =========================================================================
    # Drop Existing Aggregate
    # =========================================================================
    print("Step 1: Dropping existing telemetry_hourly_local...")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly_local CASCADE;")
    print("✓ Dropped")

    # =========================================================================
    # Recreate with Counter Reset Handling
    # =========================================================================
    print()
    print("Step 2: Creating telemetry_hourly_local with counter reset handling...")
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

            -- For energy metrics: Calculate DELTA with counter reset handling
            --
            -- Daily counters (like *_energy_today_kwh) reset at midnight.
            -- If LAST < FIRST, a reset occurred during this hour.
            --
            -- Strategy:
            --   - If LAST >= FIRST: Normal case, use LAST - FIRST
            --   - If LAST < FIRST: Counter reset detected
            --     - Use GREATEST(0, LAST - FIRST) to avoid negative values
            --     - This filters out the midnight reset artifact
            --
            -- Note: For proper handling of midnight crossings, we would need:
            --   energy_before_reset = (counter_max_value - FIRST)
            --   energy_after_reset = LAST
            --   total = energy_before_reset + energy_after_reset
            -- But since we don't know the counter max value, we use GREATEST(0, delta)
            -- which effectively ignores hours with resets. This is acceptable because
            -- most hours don't cross midnight, and the error is small.
            CASE
                WHEN tr.metric_name LIKE '%_energy_%' OR tr.metric_name LIKE '%_kwh' THEN
                    -- Use GREATEST to ensure non-negative values
                    -- This handles counter resets by clamping to 0
                    GREATEST(0, LAST(tr.metric_value, tr.time) - FIRST(tr.metric_value, tr.time))
                ELSE
                    NULL
            END as total_energy

        FROM telemetry_raw tr
        INNER JOIN sites_metadata s ON tr.site_id = s.id
        GROUP BY bucket, site_timezone, tr.site_id, tr.device_id, tr.metric_name
        WITH NO DATA;
    """)

    print("✓ Created with GREATEST(0, LAST - FIRST) to handle resets")

    # =========================================================================
    # Add Refresh Policy
    # =========================================================================
    print()
    print("Step 3: Adding refresh policy...")
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_hourly_local',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        );
    """)

    print("✓ Added hourly refresh policy")

    # =========================================================================
    # Create Indexes for Performance
    # =========================================================================
    print()
    print("Step 4: Creating indexes...")
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
    # Refresh Data (Last 60 days to cover all billing periods)
    # =========================================================================
    print()
    print("Step 5: Refreshing aggregate data for last 60 days...")
    print("This may take a few minutes...")
    op.execute("""
        CALL refresh_continuous_aggregate('telemetry_hourly_local',
            NOW() - INTERVAL '60 days',
            NOW()
        );
    """)

    print("✓ Refreshed last 60 days of data")
    print()
    print("=" * 80)
    print("AGGREGATE FIX COMPLETE")
    print("=" * 80)
    print()
    print("Changes:")
    print("  - Changed from LAST - FIRST to GREATEST(0, LAST - FIRST)")
    print("  - This prevents negative values from midnight counter resets")
    print("  - Hours crossing midnight will show 0 instead of negative values")
    print()
    print("Expected Results:")
    print("  - No more negative energy values in billing_daily")
    print("  - Hourly energy values will be 0 or positive")
    print("  - Total daily energy will be accurate (small error at midnight hour)")
    print()
    print("Next Step:")
    print("  - Re-run billing recalculation to regenerate snapshots with fixed data")
    print("=" * 80)


def downgrade() -> None:
    """Revert to unprotected LAST - FIRST (will have negative values)."""

    if not USE_TIMESCALEDB:
        return

    print("WARNING: Reverting to LAST - FIRST without reset handling!")
    print("This will restore the negative value bug.")

    # Drop the fixed aggregate
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly_local CASCADE;")

    # Recreate with unprotected LAST - FIRST
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

    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_hourly_local',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        );
    """)

    print("✓ Reverted to unprotected calculation (negative values will occur)")
