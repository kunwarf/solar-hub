"""
Alert domain entities.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from uuid import UUID, uuid4

from .base import AggregateRoot, Entity


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class ComparisonOperator(str, Enum):
    """Comparison operators for alert conditions."""
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    EQUAL = "eq"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN_OR_EQUAL = "lte"
    NOT_EQUAL = "neq"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


@dataclass
class AlertCondition:
    """
    Alert triggering condition.

    Defines when an alert should be triggered based on metric values.
    """
    metric: str  # e.g., "power_output", "battery_soc", "temperature"
    operator: ComparisonOperator
    threshold: float
    duration_seconds: int = 0  # Condition must persist for this duration
    device_type: Optional[str] = None  # Optional filter by device type

    def evaluate(self, value: float) -> bool:
        """Evaluate if the value triggers the condition."""
        if self.operator == ComparisonOperator.GREATER_THAN:
            return value > self.threshold
        elif self.operator == ComparisonOperator.LESS_THAN:
            return value < self.threshold
        elif self.operator == ComparisonOperator.EQUAL:
            return value == self.threshold
        elif self.operator == ComparisonOperator.GREATER_THAN_OR_EQUAL:
            return value >= self.threshold
        elif self.operator == ComparisonOperator.LESS_THAN_OR_EQUAL:
            return value <= self.threshold
        elif self.operator == ComparisonOperator.NOT_EQUAL:
            return value != self.threshold
        return False


@dataclass(kw_only=True)
class AlertRule(AggregateRoot):
    """
    Alert rule definition.

    Defines conditions under which alerts should be generated.
    """
    organization_id: UUID
    site_id: Optional[UUID]  # None means applies to all sites in org
    name: str
    description: Optional[str] = None
    condition: AlertCondition = field(default_factory=lambda: AlertCondition(
        metric="power_output",
        operator=ComparisonOperator.LESS_THAN,
        threshold=0.0,
    ))
    severity: AlertSeverity = AlertSeverity.WARNING
    notification_channels: List[NotificationChannel] = field(default_factory=lambda: [NotificationChannel.IN_APP])
    is_active: bool = True
    cooldown_minutes: int = 15  # Minimum time between repeated alerts
    auto_resolve: bool = True  # Auto-resolve when condition clears

    # Notification settings
    notify_on_trigger: bool = True
    notify_on_resolve: bool = True
    escalation_minutes: Optional[int] = None  # Escalate if not acknowledged

    last_triggered_at: Optional[datetime] = None

    def can_trigger(self) -> bool:
        """Check if rule can trigger (respecting cooldown)."""
        if not self.is_active:
            return False
        if self.last_triggered_at is None:
            return True
        cooldown_end = self.last_triggered_at.replace(
            tzinfo=timezone.utc
        ) + timedelta(minutes=self.cooldown_minutes)
        return datetime.now(timezone.utc) >= cooldown_end

    def record_trigger(self) -> None:
        """Record that the rule was triggered."""
        self.last_triggered_at = datetime.now(timezone.utc)
        self.mark_updated()

    def activate(self) -> None:
        """Activate the rule."""
        self.is_active = True
        self.mark_updated()

    def deactivate(self) -> None:
        """Deactivate the rule."""
        self.is_active = False
        self.mark_updated()


@dataclass(kw_only=True)
class Alert(AggregateRoot):
    """
    Alert instance.

    Represents an actual alert that was triggered.
    """
    rule_id: UUID
    organization_id: UUID
    site_id: UUID
    device_id: Optional[UUID] = None

    severity: AlertSeverity = AlertSeverity.WARNING
    status: AlertStatus = AlertStatus.ACTIVE

    title: str = ""
    message: str = ""
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None

    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None

    # Notification tracking
    notifications_sent: List[str] = field(default_factory=list)
    escalated: bool = False
    escalated_at: Optional[datetime] = None

    @property
    def is_active(self) -> bool:
        """Check if alert is still active."""
        return self.status == AlertStatus.ACTIVE

    @property
    def duration_seconds(self) -> int:
        """Get duration of alert in seconds."""
        end_time = self.resolved_at or datetime.now(timezone.utc)
        return int((end_time - self.triggered_at).total_seconds())

    def acknowledge(self, user_id: UUID) -> None:
        """Acknowledge the alert."""
        if self.status != AlertStatus.ACTIVE:
            return
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(timezone.utc)
        self.acknowledged_by = user_id
        self.mark_updated()

    def resolve(self, user_id: Optional[UUID] = None, auto: bool = False) -> None:
        """Resolve the alert."""
        if self.status == AlertStatus.RESOLVED:
            return
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(timezone.utc)
        if user_id:
            self.resolved_by = user_id
        self.mark_updated()

    def escalate(self) -> None:
        """Mark alert as escalated."""
        if not self.escalated:
            self.escalated = True
            self.escalated_at = datetime.now(timezone.utc)
            self.mark_updated()

    def record_notification(self, channel: str) -> None:
        """Record that a notification was sent."""
        self.notifications_sent.append(f"{channel}:{datetime.now(timezone.utc).isoformat()}")
        self.mark_updated()


@dataclass(kw_only=True)
class AlertNotification(Entity):
    """
    Alert notification record.

    Tracks notifications sent for an alert.
    """
    alert_id: UUID
    channel: NotificationChannel
    recipient: str  # Email, phone, webhook URL, user ID
    sent_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    delivered: bool = False
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None


# Import timedelta for use in can_trigger
from datetime import timedelta
