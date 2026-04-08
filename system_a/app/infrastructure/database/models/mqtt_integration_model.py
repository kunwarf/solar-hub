"""
SQLAlchemy ORM models for MQTT integrations.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from ....domain.entities.mqtt_integration import MqttIntegration, MqttIntegrationDevice


class MqttIntegrationModel(BaseModel):
    """SQLAlchemy model for mqtt_integrations table."""

    __tablename__ = "mqtt_integrations"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    ha_username: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    publish_interval_seconds: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    def to_domain(self) -> MqttIntegration:
        return MqttIntegration(
            id=self.id,
            user_id=self.user_id,
            ha_username=self.ha_username,
            password_hash=self.password_hash,
            enabled=self.enabled,
            publish_interval_seconds=self.publish_interval_seconds,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
        )

    @classmethod
    def from_domain(cls, entity: MqttIntegration) -> "MqttIntegrationModel":
        return cls(
            id=entity.id,
            user_id=entity.user_id,
            ha_username=entity.ha_username,
            password_hash=entity.password_hash,
            enabled=entity.enabled,
            publish_interval_seconds=entity.publish_interval_seconds,
        )

    def update_from_domain(self, entity: MqttIntegration) -> None:
        self.password_hash = entity.password_hash
        self.enabled = entity.enabled
        self.publish_interval_seconds = entity.publish_interval_seconds


class MqttIntegrationDeviceModel(BaseModel):
    """SQLAlchemy model for mqtt_integration_devices table."""

    __tablename__ = "mqtt_integration_devices"
    __table_args__ = (
        UniqueConstraint("integration_id", "device_id", name="uq_mqtt_integration_device"),
    )

    integration_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("mqtt_integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_domain(self) -> MqttIntegrationDevice:
        return MqttIntegrationDevice(
            id=self.id,
            integration_id=self.integration_id,
            device_id=self.device_id,
            enabled=self.enabled,
            enrolled_at=self.enrolled_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, entity: MqttIntegrationDevice) -> "MqttIntegrationDeviceModel":
        return cls(
            id=entity.id,
            integration_id=entity.integration_id,
            device_id=entity.device_id,
            enabled=entity.enabled,
            enrolled_at=entity.enrolled_at,
        )

    def update_from_domain(self, entity: MqttIntegrationDevice) -> None:
        self.enabled = entity.enabled
