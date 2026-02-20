"""add admin portal tables

Revision ID: a1b2c3d4e5f6
Revises: 15b325dbb128
Create Date: 2026-02-19 00:01:00.000000+00:00

Adds:
- New admin-portal role values to the user_role enum
- electricity_providers table
- electricity_tariffs table
- load_shedding_schedules table
- admin_audit_logs table
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "15b325dbb128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Extend the existing user_role enum with admin-portal roles.
    #    PostgreSQL 12+ supports ALTER TYPE ... ADD VALUE IF NOT EXISTS
    #    within a transaction block — no autocommit required.
    # ------------------------------------------------------------------
    connection = op.get_bind()
    for role_value in ("ops_admin", "billing_admin", "device_admin", "firmware_admin"):
        connection.execute(
            sa.text(f"ALTER TYPE user_role ADD VALUE IF NOT EXISTS '{role_value}'")
        )

    # ------------------------------------------------------------------
    # 2. Create enum types for admin portal entities
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "CREATE TYPE provider_status AS ENUM ('active', 'inactive')"
    ))
    op.execute(sa.text(
        "CREATE TYPE tariff_category AS ENUM "
        "('residential', 'commercial', 'industrial', 'agricultural')"
    ))
    op.execute(sa.text(
        "CREATE TYPE tariff_type AS ENUM ('slab', 'flat', 'tou')"
    ))
    op.execute(sa.text(
        "CREATE TYPE tariff_status AS ENUM ('active', 'inactive', 'draft')"
    ))

    # ------------------------------------------------------------------
    # 3. electricity_providers
    # ------------------------------------------------------------------
    op.create_table(
        "electricity_providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("short_name", sa.String(20), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", name="provider_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("tariff_count", sa.Float, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_electricity_providers_short_name", "electricity_providers", ["short_name"])
    op.create_index("ix_electricity_providers_region", "electricity_providers", ["region"])
    op.create_index("ix_electricity_providers_status", "electricity_providers", ["status"])

    # ------------------------------------------------------------------
    # 4. electricity_tariffs
    # ------------------------------------------------------------------
    op.create_table(
        "electricity_tariffs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "provider_id",
            UUID(as_uuid=True),
            sa.ForeignKey("electricity_providers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "residential", "commercial", "industrial", "agricultural",
                name="tariff_category", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum("slab", "flat", "tou", name="tariff_type", create_type=False),
            nullable=False,
        ),
        sa.Column("rates", JSONB, nullable=False),
        sa.Column("fixed_charges", sa.Float, nullable=False, server_default="0"),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "inactive", "draft", name="tariff_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_electricity_tariffs_provider_id", "electricity_tariffs", ["provider_id"])
    op.create_index("ix_electricity_tariffs_category", "electricity_tariffs", ["category"])
    op.create_index("ix_electricity_tariffs_status", "electricity_tariffs", ["status"])

    # ------------------------------------------------------------------
    # 5. load_shedding_schedules
    # ------------------------------------------------------------------
    op.create_table(
        "load_shedding_schedules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("area_name", sa.String(200), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("feeder_code", sa.String(50), nullable=True),
        sa.Column("schedule", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("effective_from", sa.Date, nullable=True),
        sa.Column("effective_to", sa.Date, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_load_shedding_schedules_region", "load_shedding_schedules", ["region"])
    op.create_index("ix_load_shedding_schedules_feeder_code", "load_shedding_schedules", ["feeder_code"])
    op.create_index("ix_load_shedding_schedules_is_active", "load_shedding_schedules", ["is_active"])

    # ------------------------------------------------------------------
    # 6. admin_audit_logs
    # ------------------------------------------------------------------
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("admin_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("admin_email", sa.String(254), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("old_values", JSONB, nullable=True),
        sa.Column("new_values", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index("ix_admin_audit_logs_admin_user_id", "admin_audit_logs", ["admin_user_id"])
    op.create_index("ix_admin_audit_logs_admin_email", "admin_audit_logs", ["admin_email"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_resource_type", "admin_audit_logs", ["resource_type"])
    op.create_index(
        "ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"],
        postgresql_using="brin",  # BRIN index efficient for append-only time-series
    )


def downgrade() -> None:
    # Drop tables first (reverse order of creation)
    op.drop_table("admin_audit_logs")
    op.drop_table("load_shedding_schedules")
    op.drop_table("electricity_tariffs")
    op.drop_table("electricity_providers")

    # Drop enum types
    op.execute(sa.text("DROP TYPE IF EXISTS tariff_status"))
    op.execute(sa.text("DROP TYPE IF EXISTS tariff_type"))
    op.execute(sa.text("DROP TYPE IF EXISTS tariff_category"))
    op.execute(sa.text("DROP TYPE IF EXISTS provider_status"))

    # Note: PostgreSQL does not support removing values from an existing enum type.
    # The user_role enum additions (ops_admin, billing_admin, device_admin, firmware_admin)
    # cannot be rolled back without dropping and recreating the entire enum and all
    # columns that use it. This is a known PostgreSQL limitation.
    # If a full rollback is needed, run:
    #   1. Drop all columns using user_role
    #   2. DROP TYPE user_role
    #   3. Recreate user_role without the new values
    #   4. Recreate columns
