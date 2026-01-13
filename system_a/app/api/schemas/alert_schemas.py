"""
Pydantic schemas for alert endpoints.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AlertConditionSchema(BaseModel):
    """Alert condition configuration."""
    metric: str = Field(..., min_length=1, max_length=100, description="Metric to monitor")
    operator: str = Field(..., description="Comparison operator: gt, lt, eq, gte, lte, neq")
    threshold: float = Field(..., description="Threshold value")
    duration_seconds: int = Field(default=0, ge=0, description="Duration condition must persist")
    device_type: Optional[str] = Field(None, max_length=50, description="Filter by device type")

    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v: str) -> str:
        valid = ['gt', 'lt', 'eq', 'gte', 'lte', 'neq']
        if v not in valid:
            raise ValueError(f"Operator must be one of: {', '.join(valid)}")
        return v


class AlertRuleCreate(BaseModel):
    """Schema for creating an alert rule."""
    organization_id: UUID
    site_id: Optional[UUID] = Field(None, description="Specific site or None for all sites")
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    condition: AlertConditionSchema
    severity: str = Field(default="warning", description="Severity: info, warning, critical")
    notification_channels: List[str] = Field(default=["in_app"], description="Channels: email, sms, push, webhook, in_app")
    cooldown_minutes: int = Field(default=15, ge=1, le=1440)
    auto_resolve: bool = Field(default=True)
    notify_on_trigger: bool = Field(default=True)
    notify_on_resolve: bool = Field(default=True)
    escalation_minutes: Optional[int] = Field(None, ge=1, le=1440)

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str) -> str:
        valid = ['info', 'warning', 'critical']
        if v not in valid:
            raise ValueError(f"Severity must be one of: {', '.join(valid)}")
        return v

    @field_validator('notification_channels')
    @classmethod
    def validate_channels(cls, v: List[str]) -> List[str]:
        valid = ['email', 'sms', 'push', 'webhook', 'in_app']
        for channel in v:
            if channel not in valid:
                raise ValueError(f"Channel must be one of: {', '.join(valid)}")
        return v


class AlertRuleUpdate(BaseModel):
    """Schema for updating an alert rule."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    condition: Optional[AlertConditionSchema] = None
    severity: Optional[str] = None
    notification_channels: Optional[List[str]] = None
    cooldown_minutes: Optional[int] = Field(None, ge=1, le=1440)
    auto_resolve: Optional[bool] = None
    notify_on_trigger: Optional[bool] = None
    notify_on_resolve: Optional[bool] = None
    escalation_minutes: Optional[int] = Field(None, ge=1, le=1440)

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        valid = ['info', 'warning', 'critical']
        if v not in valid:
            raise ValueError(f"Severity must be one of: {', '.join(valid)}")
        return v

    @field_validator('notification_channels')
    @classmethod
    def validate_channels(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        valid = ['email', 'sms', 'push', 'webhook', 'in_app']
        for channel in v:
            if channel not in valid:
                raise ValueError(f"Channel must be one of: {', '.join(valid)}")
        return v


class AlertRuleResponse(BaseModel):
    """Alert rule response."""
    id: UUID
    organization_id: UUID
    site_id: Optional[UUID]
    name: str
    description: Optional[str]
    condition: AlertConditionSchema
    severity: str
    notification_channels: List[str]
    is_active: bool
    cooldown_minutes: int
    auto_resolve: bool
    notify_on_trigger: bool
    notify_on_resolve: bool
    escalation_minutes: Optional[int]
    last_triggered_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    """Alert response."""
    id: UUID
    rule_id: UUID
    organization_id: UUID
    site_id: UUID
    device_id: Optional[UUID]
    severity: str
    status: str
    title: str
    message: str
    metric_name: Optional[str]
    metric_value: Optional[float]
    threshold_value: Optional[float]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]
    acknowledged_by: Optional[UUID]
    resolved_at: Optional[datetime]
    resolved_by: Optional[UUID]
    escalated: bool
    escalated_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AlertAcknowledgeRequest(BaseModel):
    """Request to acknowledge an alert."""
    pass  # User ID comes from auth


class AlertResolveRequest(BaseModel):
    """Request to resolve an alert."""
    notes: Optional[str] = Field(None, max_length=1000)


class AlertListResponse(BaseModel):
    """Paginated alert list response."""
    items: List[AlertResponse]
    total: int
    limit: int
    offset: int


class AlertRuleListResponse(BaseModel):
    """Paginated alert rule list response."""
    items: List[AlertRuleResponse]
    total: int
    limit: int
    offset: int


class AlertSummary(BaseModel):
    """Alert summary for dashboard."""
    total_active: int = 0
    total_acknowledged: int = 0
    total_critical: int = 0
    total_warning: int = 0
    total_info: int = 0
    recent_alerts: List[AlertResponse] = []


class AlertRuleToggleRequest(BaseModel):
    """Request to toggle alert rule active state."""
    is_active: bool
