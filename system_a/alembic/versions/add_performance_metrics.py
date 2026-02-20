"""add performance metrics fields

Revision ID: add_performance_metrics
Revises:
Create Date: 2026-02-01

Adds efficiency_pct and self_sufficiency_pct fields to telemetry summary tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_performance_metrics'
down_revision: Union[str, None] = 'dcf3f785fbc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance metrics fields (only if tables exist — they may have been dropped by a parallel branch)."""
    conn = op.get_bind()
    for table in ('telemetry_hourly_summary', 'telemetry_daily_summary', 'telemetry_monthly_summary'):
        exists = conn.execute(sa.text(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :tbl)"
        ), {"tbl": table}).scalar()
        if exists:
            conn.execute(sa.text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS efficiency_pct FLOAT"
            ))
            conn.execute(sa.text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS self_sufficiency_pct FLOAT"
            ))


def downgrade() -> None:
    """Remove performance metrics fields."""
    # Remove from monthly summaries
    op.drop_column('telemetry_monthly_summary', 'self_sufficiency_pct')
    op.drop_column('telemetry_monthly_summary', 'efficiency_pct')

    # Remove from daily summaries
    op.drop_column('telemetry_daily_summary', 'self_sufficiency_pct')
    op.drop_column('telemetry_daily_summary', 'efficiency_pct')

    # Remove from hourly summaries
    op.drop_column('telemetry_hourly_summary', 'self_sufficiency_pct')
    op.drop_column('telemetry_hourly_summary', 'efficiency_pct')
