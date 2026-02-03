"""Add sites metadata lookup table for timezone-aware aggregates.

Revision ID: 0007
Revises: 0005
Create Date: 2026-02-03

This migration creates a denormalized sites_metadata table in System B
(TimescaleDB) to support timezone-aware continuous aggregates.

Why this is needed:
- Continuous aggregates cannot JOIN across databases
- telemetry_raw is in System B (solar_hub_telemetry)
- sites table is in System A (solar_hub)
- Need site timezone for local time bucketing

Solution:
- Create sites_metadata table with minimal data (id + timezone)
- Auto-sync from System A via application code
- Small footprint, fast queries, no cross-database JOINs

The table is kept in sync automatically by the SystemBTimezoneSyncService
in System A, which hooks into site create/update/delete operations.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sites_metadata lookup table."""

    print("Creating sites_metadata lookup table...")

    # Create sites_metadata table
    # This table stores only the minimal site information needed for
    # timezone-aware continuous aggregates (id and timezone)
    op.execute("""
        CREATE TABLE IF NOT EXISTS sites_metadata (
            id UUID PRIMARY KEY,
            timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Karachi',
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)

    print("✓ Created sites_metadata table")

    # Create index on timezone for queries that filter by timezone
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sites_metadata_timezone
        ON sites_metadata (timezone);
    """)

    print("✓ Created timezone index")

    # Create index on updated_at for monitoring sync freshness
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sites_metadata_updated_at
        ON sites_metadata (updated_at DESC);
    """)

    print("✓ Created updated_at index")

    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║ Sites Metadata Table Created                                              ║
╠════════════════════════════════════════════════════════════════════════════╣
║ Next Steps:                                                                ║
║   1. Run: python scripts/sync_sites_metadata.py                           ║
║      This will copy existing sites from System A                          ║
║                                                                            ║
║   2. Restart System A to enable auto-sync on new site operations          ║
║                                                                            ║
║ Auto-sync will then keep this table in sync with System A sites table     ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)


def downgrade() -> None:
    """Remove sites_metadata lookup table."""

    print("Removing sites_metadata lookup table...")

    # Drop table (cascade will drop indexes)
    op.execute("DROP TABLE IF EXISTS sites_metadata CASCADE;")

    print("✓ Removed sites_metadata table and indexes")
