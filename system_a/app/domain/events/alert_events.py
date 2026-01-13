"""
Alert-related domain events.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from .base import DomainEvent


@dataclass
class AlertRuleCreated(DomainEvent):
    """Event raised when an alert rule is created."""
    rule_id: UUID
    organization_id: UUID
    site_id: Optional[UUID]
    name: str
    severity: str
    metric: str


@dataclass
class AlertRuleUpdated(DomainEvent):
    """Event raised when an alert rule is updated."""
    rule_id: UUID
    name: str
    changes: dict = field(default_factory=dict)


@dataclass
class AlertRuleActivated(DomainEvent):
    """Event raised when an alert rule is activated."""
    rule_id: UUID
    organization_id: UUID


@dataclass
class AlertRuleDeactivated(DomainEvent):
    """Event raised when an alert rule is deactivated."""
    rule_id: UUID
    organization_id: UUID


@dataclass
class AlertTriggered(DomainEvent):
    """Event raised when an alert is triggered."""
    alert_id: UUID
    rule_id: UUID
    organization_id: UUID
    site_id: UUID
    device_id: Optional[UUID]
    severity: str
    title: str
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None


@dataclass
class AlertAcknowledged(DomainEvent):
    """Event raised when an alert is acknowledged."""
    alert_id: UUID
    organization_id: UUID
    acknowledged_by: UUID
    acknowledged_at: datetime


@dataclass
class AlertResolved(DomainEvent):
    """Event raised when an alert is resolved."""
    alert_id: UUID
    organization_id: UUID
    resolved_by: Optional[UUID]
    resolved_at: datetime
    auto_resolved: bool = False
    duration_seconds: int = 0


@dataclass
class AlertEscalated(DomainEvent):
    """Event raised when an alert is escalated."""
    alert_id: UUID
    organization_id: UUID
    escalated_at: datetime
    reason: str = "Not acknowledged within escalation window"


@dataclass
class AlertNotificationSent(DomainEvent):
    """Event raised when an alert notification is sent."""
    alert_id: UUID
    notification_id: UUID
    channel: str
    recipient: str
    success: bool = True
    error: Optional[str] = None
