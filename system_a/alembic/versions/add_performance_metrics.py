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
down_revision: Union[str, None] = None  # Update this with the actual previous revision
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance metrics fields."""
    # Add to hourly summaries
    op.add_column('telemetry_hourly_summary', sa.Column('efficiency_pct', sa.Float(), nullable=True))
    op.add_column('telemetry_hourly_summary', sa.Column('self_sufficiency_pct', sa.Float(), nullable=True))

    # Add to daily summaries
    op.add_column('telemetry_daily_summary', sa.Column('efficiency_pct', sa.Float(), nullable=True))
    op.add_column('telemetry_daily_summary', sa.Column('self_sufficiency_pct', sa.Float(), nullable=True))

    # Add to monthly summaries
    op.add_column('telemetry_monthly_summary', sa.Column('efficiency_pct', sa.Float(), nullable=True))
    op.add_column('telemetry_monthly_summary', sa.Column('self_sufficiency_pct', sa.Float(), nullable=True))


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
