"""Add retention policies for hierarchical data management.

Revision ID: 0009
Revises: 0008
Create Date: TBD (run this AFTER backfilling daily/monthly aggregates)

⚠️  WARNING: This migration deletes old data! ⚠️

This migration adds retention policies to automatically delete old data:
- Hourly data older than 90 days will be deleted
- Daily data older than 2 years will be deleted
- Monthly data is kept forever

Make sure you have:
1. Created daily and monthly aggregates (migration 0008)
2. Backfilled all historical data into those aggregates
3. Verified the aggregates contain complete data
4. Tested query router to handle different time ranges

Storage impact:
- Before: All hourly data (~100 GB/year for 100 sites)
- After: Only 90 days hourly + 2 years daily + all monthly (~5 GB)
"""
from typing import Sequence, Union
import os

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Check if TimescaleDB is available
USE_TIMESCALEDB = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"


def upgrade() -> None:
    """Add retention policies to manage storage costs."""

    if not USE_TIMESCALEDB:
        print("Skipping retention policies (USE_TIMESCALEDB=false)")
        return

    print("⚠️  WARNING: Adding retention policies will delete old data!")
    print("Make sure daily and monthly aggregates are backfilled first.")
    print("")

    # =========================================================================
    # Retention Policy for Hourly Data (90 days)
    # =========================================================================
    print("Adding retention policy for hourly data (90 days)...")

    op.execute("""
        SELECT add_retention_policy('telemetry_hourly_local',
            INTERVAL '90 days',
            if_not_exists => true
        );
    """)

    print("✓ Hourly data older than 90 days will be automatically deleted")

    # =========================================================================
    # Retention Policy for Daily Data (2 years)
    # =========================================================================
    print("Adding retention policy for daily data (2 years)...")

    op.execute("""
        SELECT add_retention_policy('telemetry_daily_local',
            INTERVAL '730 days',
            if_not_exists => true
        );
    """)

    print("✓ Daily data older than 2 years will be automatically deleted")

    # =========================================================================
    # No Retention for Monthly (keep forever)
    # =========================================================================
    print("Monthly data: No retention policy (kept forever)")

    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║ Retention Policies Enabled                                                ║
╠════════════════════════════════════════════════════════════════════════════╣
║ ✓ Hourly data: Kept for 90 days                                          ║
║ ✓ Daily data: Kept for 2 years (730 days)                                ║
║ ✓ Monthly data: Kept forever                                             ║
║                                                                            ║
║ Automatic Cleanup:                                                         ║
║   TimescaleDB will automatically delete old data in the background.       ║
║   Cleanup runs daily and is non-blocking.                                 ║
║                                                                            ║
║ Query Strategy:                                                            ║
║   - Last 90 days: Query from telemetry_hourly_local                       ║
║   - 90 days - 2 years: Query from telemetry_daily_local                  ║
║   - Older than 2 years: Query from telemetry_monthly_local               ║
║                                                                            ║
║ Storage Savings:                                                           ║
║   Before: ~100 GB/year (all hourly forever)                              ║
║   After: ~5 GB total (hierarchical retention)                            ║
║   Reduction: ~95% storage saved                                           ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)


def downgrade() -> None:
    """Remove retention policies (restore keeping all data)."""

    if not USE_TIMESCALEDB:
        return

    print("Removing retention policies...")

    # Remove retention policies by job ID
    # TimescaleDB removes the policy when we query by hypertable
    op.execute("""
        SELECT remove_retention_policy('telemetry_hourly_local', if_exists => true);
    """)

    op.execute("""
        SELECT remove_retention_policy('telemetry_daily_local', if_exists => true);
    """)

    print("✓ Retention policies removed - data will be kept indefinitely")
    print("⚠️  Note: Previously deleted data cannot be recovered")
