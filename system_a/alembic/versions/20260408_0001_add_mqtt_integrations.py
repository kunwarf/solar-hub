"""add mqtt_integrations and mqtt_integration_devices tables

Revision ID: 20260408_mqtt01
Revises: 20260224_pbs02
Create Date: 2026-04-08 00:01:00.000000+00:00

Adds per-user MQTT integration records (one per user) and the device
enrollment pivot table.  Used by the Home Assistant MQTT integration
feature — System A manages broker credentials, System B publishes
telemetry for enrolled devices.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260408_mqtt01"
down_revision: Union[str, None] = "20260224_pbs02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # mqtt_integrations — one row per user
    op.create_table(
        "mqtt_integrations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("ha_username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("publish_interval_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_mqtt_integrations_user_id", "mqtt_integrations", ["user_id"])
    op.create_index("ix_mqtt_integrations_ha_username", "mqtt_integrations", ["ha_username"])

    # mqtt_integration_devices — enrolled devices per integration
    op.create_table(
        "mqtt_integration_devices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "integration_id",
            UUID(as_uuid=True),
            sa.ForeignKey("mqtt_integrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            UUID(as_uuid=True),
            sa.ForeignKey("devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("integration_id", "device_id", name="uq_mqtt_integration_device"),
    )
    op.create_index(
        "ix_mqtt_integration_devices_integration_id",
        "mqtt_integration_devices",
        ["integration_id"],
    )
    op.create_index(
        "ix_mqtt_integration_devices_device_id",
        "mqtt_integration_devices",
        ["device_id"],
    )


def downgrade() -> None:
    op.drop_table("mqtt_integration_devices")
    op.drop_table("mqtt_integrations")
