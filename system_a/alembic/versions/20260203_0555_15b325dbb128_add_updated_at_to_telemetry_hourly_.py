"""add_updated_at_to_telemetry_hourly_summary

Revision ID: 15b325dbb128
Revises: 3c853c02f69f
Create Date: 2026-02-03 05:55:32.545490+00:00

Add updated_at column to telemetry_hourly_summary table to match other summary tables
and support System B data that includes this audit field.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP


# revision identifiers, used by Alembic.
revision: str = '15b325dbb128'
down_revision: Union[str, None] = '3c853c02f69f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add updated_at column to telemetry_hourly_summary table if it exists."""
    # Check if table exists before attempting to alter it
    # (System A may not have this table if using System B for telemetry)
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'telemetry_hourly_summary' in inspector.get_table_names():
        op.add_column(
            'telemetry_hourly_summary',
            sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=True)
        )
        print("✓ Added updated_at column to telemetry_hourly_summary")
    else:
        print("⊘ Table telemetry_hourly_summary does not exist - skipping migration")
        print("  (This is expected if System A uses System B repository for telemetry)")


def downgrade() -> None:
    """Remove updated_at column from telemetry_hourly_summary table if it exists."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'telemetry_hourly_summary' in inspector.get_table_names():
        op.drop_column('telemetry_hourly_summary', 'updated_at')
        print("✓ Removed updated_at column from telemetry_hourly_summary")
    else:
        print("⊘ Table telemetry_hourly_summary does not exist - skipping rollback")
