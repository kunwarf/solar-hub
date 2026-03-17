"""add provider billing schedules

Revision ID: 20260224_pbs01
Revises: 20260223_ai01
Create Date: 2026-02-24 00:01:00.000000+00:00

Adds the provider_billing_schedules table.

Admins define billing rates per provider + tariff category (e.g. LESCO residential).
When a site's disco_provider + tariff_category match an active schedule, the billing
engine uses admin-defined rates instead of per-site billing_config.

  provider_billing_schedules  – admin-managed billing schedule per DISCO + category.
                                Contains TOU prices, peak windows, and defaults.
                                A partial unique index ensures only one active schedule
                                per provider + tariff_category combination.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "20260224_pbs01"
down_revision: Union[str, None] = "20260223_ai01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. New enum for billing schedule status
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "CREATE TYPE billing_schedule_status AS ENUM ('active', 'inactive', 'draft')"
    ))

    # ------------------------------------------------------------------
    # 2. provider_billing_schedules table
    # ------------------------------------------------------------------
    op.create_table(
        "provider_billing_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "provider_id",
            UUID(as_uuid=True),
            sa.ForeignKey("electricity_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tariff_category", sa.String(50), nullable=False),

        # Prices
        sa.Column("price_offpeak_import", sa.Numeric(10, 4), nullable=False),
        sa.Column("price_peak_import", sa.Numeric(10, 4), nullable=False),
        sa.Column("price_offpeak_settlement", sa.Numeric(10, 4), nullable=False),
        sa.Column("price_peak_settlement", sa.Numeric(10, 4), nullable=False),
        sa.Column("fixed_charge", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),

        # TOU config (same structure as billing_config tou_config)
        # Use \\: to escape colons — sa.text() treats bare :word as bind parameters
        sa.Column(
            "tou_windows",
            JSONB,
            nullable=False,
            server_default=sa.text(
                r"""'{"peak_windows":[{"start_hour"\:17,"end_hour"\:22}],"timezone"\:"Asia/Karachi"}'"""
            ),
        ),

        # Defaults
        sa.Column("default_anchor_day", sa.Integer, nullable=False, server_default=sa.text("15")),
        sa.Column("currency", sa.String(10), nullable=False, server_default=sa.text("'PKR'")),
        sa.Column("net_metering_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),

        # Status & dates
        sa.Column(
            "status",
            sa.Enum("active", "inactive", "draft", name="billing_schedule_status", create_type=False),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("effective_from", sa.Date, nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column("description", sa.Text, nullable=True),

        # Audit
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
    )

    # ------------------------------------------------------------------
    # 3. Indexes
    # ------------------------------------------------------------------
    op.create_index("idx_pbs_provider", "provider_billing_schedules", ["provider_id"])
    op.create_index("idx_pbs_status", "provider_billing_schedules", ["status"])
    # Partial unique index: only one active schedule per provider + category
    op.execute(sa.text("""
        CREATE UNIQUE INDEX idx_pbs_active_unique
            ON provider_billing_schedules(provider_id, tariff_category)
            WHERE status = 'active'
    """))


def downgrade() -> None:
    op.drop_index("idx_pbs_active_unique", table_name="provider_billing_schedules")
    op.drop_index("idx_pbs_status", table_name="provider_billing_schedules")
    op.drop_index("idx_pbs_provider", table_name="provider_billing_schedules")
    op.drop_table("provider_billing_schedules")
    op.execute(sa.text("DROP TYPE billing_schedule_status"))
