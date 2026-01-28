"""Add partial unique indexes for telemetry summary tables.

Revision ID: 009
Revises: 008
Create Date: 2026-01-28

Adds partial unique indexes for rows where device_id IS NULL (site-level summaries).
These are needed for PostgreSQL UPSERT (ON CONFLICT) to work correctly with nullable columns,
since NULL != NULL in standard unique constraints.
"""
from alembic import op


# revision identifiers
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Partial unique index for hourly summary: site-level rows (device_id IS NULL)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_hourly_site_time_no_device
        ON telemetry_hourly_summary (site_id, timestamp_hour)
        WHERE device_id IS NULL
        """
    )

    # Partial unique index for daily summary: site-level rows (device_id IS NULL)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_site_date_no_device
        ON telemetry_daily_summary (site_id, summary_date)
        WHERE device_id IS NULL
        """
    )

    # Partial unique index for monthly summary: site-level rows (device_id IS NULL)
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_monthly_site_period_no_device
        ON telemetry_monthly_summary (site_id, year, month)
        WHERE device_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_hourly_site_time_no_device")
    op.execute("DROP INDEX IF EXISTS uq_daily_site_date_no_device")
    op.execute("DROP INDEX IF EXISTS uq_monthly_site_period_no_device")
