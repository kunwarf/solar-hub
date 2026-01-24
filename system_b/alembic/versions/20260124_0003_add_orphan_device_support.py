"""Add orphan device support for self-registration.

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-24

Adds support for device self-registration with orphan state:
- Make site_id and organization_id nullable (for orphan devices)
- Add manufacturer, model, firmware_version fields
- Add status field (orphan/claimed)
- Add owner_id field (user who claimed the device)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create device_status enum type
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE device_status AS ENUM ('orphan', 'claimed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Make site_id nullable (for orphan devices)
    op.alter_column(
        "device_registry",
        "site_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
    )

    # Make organization_id nullable (for orphan devices)
    op.alter_column(
        "device_registry",
        "organization_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
    )

    # Add new columns for device self-registration
    op.add_column(
        "device_registry",
        sa.Column("manufacturer", sa.String(100), nullable=True),
    )

    op.add_column(
        "device_registry",
        sa.Column("model", sa.String(100), nullable=True),
    )

    op.add_column(
        "device_registry",
        sa.Column("firmware_version", sa.String(50), nullable=True),
    )

    op.add_column(
        "device_registry",
        sa.Column(
            "status",
            sa.Enum("orphan", "claimed", name="device_status", create_type=False),
            nullable=False,
            server_default="orphan",
        ),
    )

    op.add_column(
        "device_registry",
        sa.Column("owner_id", UUID(as_uuid=True), nullable=True),
    )

    op.add_column(
        "device_registry",
        sa.Column("capabilities", sa.dialects.postgresql.JSONB, nullable=True),
    )

    op.add_column(
        "device_registry",
        sa.Column("last_telemetry_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add index for status lookups
    op.create_index(
        "idx_device_registry_device_status",
        "device_registry",
        ["status"],
    )

    # Add index for owner_id lookups
    op.create_index(
        "idx_device_registry_owner",
        "device_registry",
        ["owner_id"],
        postgresql_where=sa.text("owner_id IS NOT NULL"),
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("idx_device_registry_owner", "device_registry")
    op.drop_index("idx_device_registry_device_status", "device_registry")

    # Drop new columns
    op.drop_column("device_registry", "last_telemetry_at")
    op.drop_column("device_registry", "capabilities")
    op.drop_column("device_registry", "owner_id")
    op.drop_column("device_registry", "status")
    op.drop_column("device_registry", "firmware_version")
    op.drop_column("device_registry", "model")
    op.drop_column("device_registry", "manufacturer")

    # Make site_id NOT NULL again
    op.alter_column(
        "device_registry",
        "site_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )

    # Make organization_id NOT NULL again
    op.alter_column(
        "device_registry",
        "organization_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS device_status")
