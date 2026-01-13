"""
SQLAlchemy ORM models for alerts.
"""
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel
from ....domain.entities.alert import (
    Alert,
    AlertCondition,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    ComparisonOperator,
    NotificationChannel,
)


class AlertRuleModel(BaseModel):
    """SQLAlchemy model for alert rules."""

    __tablename__ = "alert_rules"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    site_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Condition stored as JSON
    condition: Mapped[dict] = mapped_column(JSONB, nullable=False)

    severity: Mapped[AlertSeverity] = mapped_column(
        SQLEnum(AlertSeverity, name="alert_severity"),
        default=AlertSeverity.WARNING,
        nullable=False,
    )

    notification_channels: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=[],
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    auto_resolve: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    notify_on_trigger: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_on_resolve: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    escalation_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    alerts: Mapped[List["AlertModel"]] = relationship(
        "AlertModel",
        back_populates="rule",
        cascade="all, delete-orphan",
    )

    def to_domain(self) -> AlertRule:
        """Convert to domain entity."""
        condition_data = self.condition
        condition = AlertCondition(
            metric=condition_data.get("metric", ""),
            operator=ComparisonOperator(condition_data.get("operator", "gt")),
            threshold=condition_data.get("threshold", 0.0),
            duration_seconds=condition_data.get("duration_seconds", 0),
            device_type=condition_data.get("device_type"),
        )

        channels = [
            NotificationChannel(c) for c in self.notification_channels
            if c in [e.value for e in NotificationChannel]
        ]

        return AlertRule(
            id=self.id,
            organization_id=self.organization_id,
            site_id=self.site_id,
            name=self.name,
            description=self.description,
            condition=condition,
            severity=self.severity,
            notification_channels=channels,
            is_active=self.is_active,
            cooldown_minutes=self.cooldown_minutes,
            auto_resolve=self.auto_resolve,
            notify_on_trigger=self.notify_on_trigger,
            notify_on_resolve=self.notify_on_resolve,
            escalation_minutes=self.escalation_minutes,
            last_triggered_at=self.last_triggered_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
        )

    @classmethod
    def from_domain(cls, entity: AlertRule) -> "AlertRuleModel":
        """Create from domain entity."""
        condition_dict = {
            "metric": entity.condition.metric,
            "operator": entity.condition.operator.value,
            "threshold": entity.condition.threshold,
            "duration_seconds": entity.condition.duration_seconds,
            "device_type": entity.condition.device_type,
        }

        return cls(
            id=entity.id,
            organization_id=entity.organization_id,
            site_id=entity.site_id,
            name=entity.name,
            description=entity.description,
            condition=condition_dict,
            severity=entity.severity,
            notification_channels=[c.value for c in entity.notification_channels],
            is_active=entity.is_active,
            cooldown_minutes=entity.cooldown_minutes,
            auto_resolve=entity.auto_resolve,
            notify_on_trigger=entity.notify_on_trigger,
            notify_on_resolve=entity.notify_on_resolve,
            escalation_minutes=entity.escalation_minutes,
            last_triggered_at=entity.last_triggered_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )

    def update_from_domain(self, entity: AlertRule) -> None:
        """Update model from domain entity."""
        self.name = entity.name
        self.description = entity.description
        self.condition = {
            "metric": entity.condition.metric,
            "operator": entity.condition.operator.value,
            "threshold": entity.condition.threshold,
            "duration_seconds": entity.condition.duration_seconds,
            "device_type": entity.condition.device_type,
        }
        self.severity = entity.severity
        self.notification_channels = [c.value for c in entity.notification_channels]
        self.is_active = entity.is_active
        self.cooldown_minutes = entity.cooldown_minutes
        self.auto_resolve = entity.auto_resolve
        self.notify_on_trigger = entity.notify_on_trigger
        self.notify_on_resolve = entity.notify_on_resolve
        self.escalation_minutes = entity.escalation_minutes
        self.last_triggered_at = entity.last_triggered_at
        self.updated_at = entity.updated_at
        self.version = entity.version


class AlertModel(BaseModel):
    """SQLAlchemy model for alerts."""

    __tablename__ = "alerts"

    rule_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    site_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    severity: Mapped[AlertSeverity] = mapped_column(
        SQLEnum(AlertSeverity, name="alert_severity", create_type=False),
        default=AlertSeverity.WARNING,
        nullable=False,
    )
    status: Mapped[AlertStatus] = mapped_column(
        SQLEnum(AlertStatus, name="alert_status"),
        default=AlertStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    metric_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    notifications_sent: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=[],
        nullable=False,
    )
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    rule: Mapped["AlertRuleModel"] = relationship(
        "AlertRuleModel",
        back_populates="alerts",
    )

    def to_domain(self) -> Alert:
        """Convert to domain entity."""
        return Alert(
            id=self.id,
            rule_id=self.rule_id,
            organization_id=self.organization_id,
            site_id=self.site_id,
            device_id=self.device_id,
            severity=self.severity,
            status=self.status,
            title=self.title,
            message=self.message,
            metric_name=self.metric_name,
            metric_value=self.metric_value,
            threshold_value=self.threshold_value,
            triggered_at=self.triggered_at,
            acknowledged_at=self.acknowledged_at,
            acknowledged_by=self.acknowledged_by,
            resolved_at=self.resolved_at,
            resolved_by=self.resolved_by,
            notifications_sent=list(self.notifications_sent) if self.notifications_sent else [],
            escalated=self.escalated,
            escalated_at=self.escalated_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version,
        )

    @classmethod
    def from_domain(cls, entity: Alert) -> "AlertModel":
        """Create from domain entity."""
        return cls(
            id=entity.id,
            rule_id=entity.rule_id,
            organization_id=entity.organization_id,
            site_id=entity.site_id,
            device_id=entity.device_id,
            severity=entity.severity,
            status=entity.status,
            title=entity.title,
            message=entity.message,
            metric_name=entity.metric_name,
            metric_value=entity.metric_value,
            threshold_value=entity.threshold_value,
            triggered_at=entity.triggered_at,
            acknowledged_at=entity.acknowledged_at,
            acknowledged_by=entity.acknowledged_by,
            resolved_at=entity.resolved_at,
            resolved_by=entity.resolved_by,
            notifications_sent=entity.notifications_sent,
            escalated=entity.escalated,
            escalated_at=entity.escalated_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version,
        )

    def update_from_domain(self, entity: Alert) -> None:
        """Update model from domain entity."""
        self.status = entity.status
        self.acknowledged_at = entity.acknowledged_at
        self.acknowledged_by = entity.acknowledged_by
        self.resolved_at = entity.resolved_at
        self.resolved_by = entity.resolved_by
        self.notifications_sent = entity.notifications_sent
        self.escalated = entity.escalated
        self.escalated_at = entity.escalated_at
        self.updated_at = entity.updated_at
        self.version = entity.version
