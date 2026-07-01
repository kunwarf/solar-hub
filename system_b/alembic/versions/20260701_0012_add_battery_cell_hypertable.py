"""Add battery_cell_samples hypertable + battery_cell_hourly continuous aggregate.

Revision ID: 20260701_0012
Revises: 20260216_0011
Create Date: 2026-07-01

Phase 2 of the candidate-faulty-cell detector. The snapshot detector in
System A (Phase 1) works off Redis, which has a 120-second TTL. To detect
"cell charges quickly / discharges quickly" behaviour we need per-cell
history across charge/discharge cycles.

This migration adds a dedicated hypertable for per-cell voltage/current/
temperature samples, plus an hourly continuous aggregate that captures the
FIRST and LAST values per (unit, cell) — enough to compute dV/dt per phase.

The Pylontech and JK BMS parsers already populate ``telemetry["battery_cells"]``.
A new ``CellSamplesWriter`` in ``system_b/device_server/storage/cell_samples_writer.py``
consumes that list and inserts here from the ``_on_telemetry`` callback.

Retention and compression mirror the ``telemetry_raw`` policy:
  - raw samples: 7 days, compressed after 2 days
  - hourly aggregate: 90 days
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260701_0012"
down_revision: Union[str, None] = "20260216_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USE_TIMESCALEDB = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"


def upgrade() -> None:
    # ---- Base table ---------------------------------------------------------
    op.create_table(
        "battery_cell_samples",
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("site_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit", sa.SmallInteger, nullable=False),
        sa.Column("cell", sa.SmallInteger, nullable=False),
        sa.Column("voltage_v", sa.Float, nullable=True),
        sa.Column("current_a", sa.Float, nullable=True),
        sa.Column("temperature", sa.Float, nullable=True),
        sa.Column("soc_pct", sa.SmallInteger, nullable=True),
        sa.PrimaryKeyConstraint("time", "device_id", "unit", "cell"),
    )

    op.create_index(
        "ix_battery_cell_samples_device_time",
        "battery_cell_samples",
        ["device_id", sa.text("time DESC")],
    )
    op.create_index(
        "ix_battery_cell_samples_site_time",
        "battery_cell_samples",
        ["site_id", sa.text("time DESC")],
    )

    if not USE_TIMESCALEDB:
        print("Skipping TimescaleDB hypertable + CAgg (USE_TIMESCALEDB=false)")
        return

    # ---- Hypertable ---------------------------------------------------------
    op.execute(
        """
        SELECT create_hypertable(
            'battery_cell_samples',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
        """
    )

    # ---- Hourly continuous aggregate ----------------------------------------
    # FIRST / LAST per (device, unit, cell) per hour are the essential inputs
    # for dV/dt over a charge/discharge phase.
    op.execute(
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS battery_cell_hourly
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', time) AS bucket,
            device_id,
            site_id,
            unit,
            cell,
            AVG(voltage_v)                    AS avg_v,
            MIN(voltage_v)                    AS min_v,
            MAX(voltage_v)                    AS max_v,
            FIRST(voltage_v, time)            AS first_v,
            LAST(voltage_v, time)             AS last_v,
            AVG(current_a)                    AS avg_current_a,
            AVG(temperature)                  AS avg_temp,
            COUNT(*)                          AS sample_count
        FROM battery_cell_samples
        GROUP BY bucket, device_id, site_id, unit, cell
        WITH NO DATA
        """
    )

    op.execute(
        """
        SELECT add_continuous_aggregate_policy('battery_cell_hourly',
            start_offset      => INTERVAL '3 hours',
            end_offset        => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists     => TRUE
        )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_battery_cell_hourly_device
        ON battery_cell_hourly (device_id, bucket DESC)
        """
    )

    # ---- Retention ----------------------------------------------------------
    op.execute(
        """
        SELECT add_retention_policy('battery_cell_samples',
            INTERVAL '7 days',
            if_not_exists => TRUE
        )
        """
    )
    op.execute(
        """
        SELECT add_retention_policy('battery_cell_hourly',
            INTERVAL '90 days',
            if_not_exists => TRUE
        )
        """
    )

    # ---- Compression --------------------------------------------------------
    op.execute(
        """
        ALTER TABLE battery_cell_samples SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'device_id, unit, cell',
            timescaledb.compress_orderby   = 'time DESC'
        )
        """
    )
    op.execute(
        """
        SELECT add_compression_policy('battery_cell_samples',
            INTERVAL '2 days',
            if_not_exists => TRUE
        )
        """
    )


def downgrade() -> None:
    if USE_TIMESCALEDB:
        # Remove policies before dropping the objects they reference.
        op.execute(
            "SELECT remove_compression_policy('battery_cell_samples', if_exists => TRUE)"
        )
        op.execute(
            "SELECT remove_retention_policy('battery_cell_hourly', if_exists => TRUE)"
        )
        op.execute(
            "SELECT remove_retention_policy('battery_cell_samples', if_exists => TRUE)"
        )
        op.execute(
            "SELECT remove_continuous_aggregate_policy('battery_cell_hourly', if_exists => TRUE)"
        )
        op.execute("DROP MATERIALIZED VIEW IF EXISTS battery_cell_hourly CASCADE")

    op.drop_index("ix_battery_cell_samples_site_time", table_name="battery_cell_samples")
    op.drop_index("ix_battery_cell_samples_device_time", table_name="battery_cell_samples")
    op.drop_table("battery_cell_samples")
