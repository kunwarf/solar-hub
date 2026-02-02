"""merge performance metrics and drop telemetry tables

Revision ID: 3c853c02f69f
Revises: add_performance_metrics, 20260202_0012
Create Date: 2026-02-02 07:24:24.620666+00:00

This merge migration resolves a branch conflict between:
1. add_performance_metrics: Added columns to telemetry summary tables
2. 20260202_0012: Dropped those same tables for System B migration

Since the tables are being dropped entirely (20260202_0012), the performance
metrics columns (add_performance_metrics) are no longer needed. This merge
simply unifies both branches without additional operations.

Note: The order of application doesn't matter since the final state is that
the telemetry summary tables are dropped regardless.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c853c02f69f'
down_revision: Union[str, None] = ('add_performance_metrics', '20260202_0012')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
