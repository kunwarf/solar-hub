"""add fpa and qta to provider_billing_schedules

Revision ID: 20260224_pbs02
Revises: 20260224_pbs01
Create Date: 2026-02-24 00:02:00.000000+00:00

Adds fuel_price_adjustment (FPA) and quarterly_tariff_adjustment (QTA)
columns to provider_billing_schedules.  These NEPRA-mandated surcharges are
set centrally by admins and applied on top of base import/settlement prices.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260224_pbs02"
down_revision: Union[str, None] = "20260224_pbs01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "provider_billing_schedules",
        sa.Column(
            "fuel_price_adjustment",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "provider_billing_schedules",
        sa.Column(
            "quarterly_tariff_adjustment",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("provider_billing_schedules", "quarterly_tariff_adjustment")
    op.drop_column("provider_billing_schedules", "fuel_price_adjustment")
