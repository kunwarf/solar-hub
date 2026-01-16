"""Add TimescaleDB continuous aggregates.

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-15

Creates continuous aggregates for efficient time-series queries:
- telemetry_5min: 5-minute aggregates
- telemetry_hourly: Hourly aggregates
- telemetry_daily: Daily aggregates
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create 5-minute continuous aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_5min
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('5 minutes', time) AS bucket,
            device_id,
            site_id,
            metric_name,
            AVG(metric_value) AS avg_value,
            MIN(metric_value) AS min_value,
            MAX(metric_value) AS max_value,
            FIRST(metric_value, time) AS first_value,
            LAST(metric_value, time) AS last_value,
            COUNT(*) AS sample_count,
            COUNT(CASE WHEN quality = 'good' THEN 1 END)::float / NULLIF(COUNT(*), 0) * 100 AS quality_percent
        FROM telemetry_raw
        GROUP BY bucket, device_id, site_id, metric_name
        WITH NO DATA
    """)

    # Create hourly continuous aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            device_id,
            site_id,
            metric_name,
            AVG(metric_value) AS avg_value,
            MIN(metric_value) AS min_value,
            MAX(metric_value) AS max_value,
            FIRST(metric_value, time) AS first_value,
            LAST(metric_value, time) AS last_value,
            COUNT(*) AS sample_count,
            COUNT(CASE WHEN quality = 'good' THEN 1 END)::float / NULLIF(COUNT(*), 0) * 100 AS quality_percent
        FROM telemetry_raw
        GROUP BY bucket, device_id, site_id, metric_name
        WITH NO DATA
    """)

    # Create daily continuous aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', time) AS bucket,
            device_id,
            site_id,
            metric_name,
            AVG(metric_value) AS avg_value,
            MIN(metric_value) AS min_value,
            MAX(metric_value) AS max_value,
            FIRST(metric_value, time) AS first_value,
            LAST(metric_value, time) AS last_value,
            COUNT(*) AS sample_count,
            COUNT(CASE WHEN quality = 'good' THEN 1 END)::float / NULLIF(COUNT(*), 0) * 100 AS quality_percent
        FROM telemetry_raw
        GROUP BY bucket, device_id, site_id, metric_name
        WITH NO DATA
    """)

    # Add refresh policies for continuous aggregates
    # 5-minute aggregate: refresh every 5 minutes, data from 1 hour ago to 10 minutes ago
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_5min',
            start_offset => INTERVAL '1 hour',
            end_offset => INTERVAL '10 minutes',
            schedule_interval => INTERVAL '5 minutes',
            if_not_exists => TRUE
        )
    """)

    # Hourly aggregate: refresh every hour, data from 3 hours ago to 1 hour ago
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_hourly',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        )
    """)

    # Daily aggregate: refresh daily, data from 3 days ago to 1 day ago
    op.execute("""
        SELECT add_continuous_aggregate_policy('telemetry_daily',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # Create indexes on continuous aggregates
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_5min_device
        ON telemetry_5min (device_id, bucket DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_5min_site
        ON telemetry_5min (site_id, bucket DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_device
        ON telemetry_hourly (device_id, bucket DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_hourly_site
        ON telemetry_hourly (site_id, bucket DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_daily_device
        ON telemetry_daily (device_id, bucket DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_telemetry_daily_site
        ON telemetry_daily (site_id, bucket DESC)
    """)

    # Create event counts continuous aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS event_counts_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            site_id,
            event_type,
            severity,
            COUNT(*) AS event_count,
            COUNT(CASE WHEN acknowledged = false THEN 1 END) AS unacknowledged_count
        FROM device_events
        GROUP BY bucket, site_id, event_type, severity
        WITH NO DATA
    """)

    op.execute("""
        SELECT add_continuous_aggregate_policy('event_counts_hourly',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        )
    """)

    # Add retention policies
    # Keep raw telemetry for 7 days
    op.execute("""
        SELECT add_retention_policy('telemetry_raw',
            INTERVAL '7 days',
            if_not_exists => TRUE
        )
    """)

    # Keep device events for 90 days
    op.execute("""
        SELECT add_retention_policy('device_events',
            INTERVAL '90 days',
            if_not_exists => TRUE
        )
    """)

    # Keep 5-minute aggregates for 30 days
    op.execute("""
        SELECT add_retention_policy('telemetry_5min',
            INTERVAL '30 days',
            if_not_exists => TRUE
        )
    """)

    # Keep hourly aggregates for 1 year
    op.execute("""
        SELECT add_retention_policy('telemetry_hourly',
            INTERVAL '365 days',
            if_not_exists => TRUE
        )
    """)

    # Daily aggregates kept forever (no retention policy)

    # Create compression policy for old raw data
    op.execute("""
        ALTER TABLE telemetry_raw SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'device_id, metric_name'
        )
    """)

    op.execute("""
        SELECT add_compression_policy('telemetry_raw',
            INTERVAL '2 days',
            if_not_exists => TRUE
        )
    """)


def downgrade() -> None:
    # Remove policies first
    op.execute("SELECT remove_compression_policy('telemetry_raw', if_exists => TRUE)")
    op.execute("SELECT remove_retention_policy('telemetry_hourly', if_exists => TRUE)")
    op.execute("SELECT remove_retention_policy('telemetry_5min', if_exists => TRUE)")
    op.execute("SELECT remove_retention_policy('device_events', if_exists => TRUE)")
    op.execute("SELECT remove_retention_policy('telemetry_raw', if_exists => TRUE)")

    op.execute("SELECT remove_continuous_aggregate_policy('event_counts_hourly', if_exists => TRUE)")
    op.execute("SELECT remove_continuous_aggregate_policy('telemetry_daily', if_exists => TRUE)")
    op.execute("SELECT remove_continuous_aggregate_policy('telemetry_hourly', if_exists => TRUE)")
    op.execute("SELECT remove_continuous_aggregate_policy('telemetry_5min', if_exists => TRUE)")

    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS event_counts_hourly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_5min CASCADE")
