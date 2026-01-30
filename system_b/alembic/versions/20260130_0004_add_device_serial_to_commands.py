"""Add device_serial column to device_commands table

Revision ID: 20260130_0001
Revises: 0002
Create Date: 2026-01-30

Adds device_serial column to store device serial number for direct lookup.
This allows System A to pass the serial directly instead of requiring UUID resolution.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add device_serial column to device_commands table
    op.add_column(
        "device_commands",
        sa.Column("device_serial", sa.String(100), nullable=True)
    )

    # Add index for faster lookups by serial
    op.create_index(
        "idx_device_commands_serial",
        "device_commands",
        ["device_serial"],
        unique=False
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("idx_device_commands_serial", "device_commands")

    # Drop column
    op.drop_column("device_commands", "device_serial")
