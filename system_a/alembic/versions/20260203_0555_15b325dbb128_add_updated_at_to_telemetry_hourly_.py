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
    """Add updated_at column to telemetry_hourly_summary table."""
    op.add_column(
        'telemetry_hourly_summary',
        sa.Column('updated_at', TIMESTAMP(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Remove updated_at column from telemetry_hourly_summary table."""
    op.drop_column('telemetry_hourly_summary', 'updated_at')
