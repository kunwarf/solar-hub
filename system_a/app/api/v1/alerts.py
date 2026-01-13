"""
Alert API endpoints.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_current_user, get_unit_of_work
from ..schemas.alert_schemas import (
    AlertAcknowledgeRequest,
    AlertConditionSchema,
    AlertListResponse,
    AlertResolveRequest,
    AlertResponse,
    AlertRuleCreate,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleToggleRequest,
    AlertRuleUpdate,
    AlertSummary,
)
from ..schemas.auth_schemas import ErrorResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.alert import (
    Alert,
    AlertCondition,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    ComparisonOperator,
    NotificationChannel,
)
from ...domain.entities.user import User, UserRole

router = APIRouter(prefix="/alerts", tags=["Alerts"])


async def check_org_access(org_id: UUID, user: User, uow: UnitOfWork) -> None:
    """Verify user has access to organization."""
    org = await uow.organizations.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    if not org.is_member(user.id) and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this organization",
        )


async def check_org_admin(org_id: UUID, user: User, uow: UnitOfWork) -> None:
    """Verify user has admin access to organization."""
    org = await uow.organizations.get_by_id(org_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    if user.role == UserRole.SUPER_ADMIN:
        return
    member = org.get_member(user.id)
    if not member or member.role.value not in ['owner', 'admin', 'manager']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You need admin access to manage alert rules",
        )


def alert_rule_to_response(rule: AlertRule) -> AlertRuleResponse:
    """Convert domain entity to response schema."""
    return AlertRuleResponse(
        id=rule.id,
        organization_id=rule.organization_id,
        site_id=rule.site_id,
        name=rule.name,
        description=rule.description,
        condition=AlertConditionSchema(
            metric=rule.condition.metric,
            operator=rule.condition.operator.value,
            threshold=rule.condition.threshold,
            duration_seconds=rule.condition.duration_seconds,
            device_type=rule.condition.device_type,
        ),
        severity=rule.severity.value,
        notification_channels=[c.value for c in rule.notification_channels],
        is_active=rule.is_active,
        cooldown_minutes=rule.cooldown_minutes,
        auto_resolve=rule.auto_resolve,
        notify_on_trigger=rule.notify_on_trigger,
        notify_on_resolve=rule.notify_on_resolve,
        escalation_minutes=rule.escalation_minutes,
        last_triggered_at=rule.last_triggered_at,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def alert_to_response(alert: Alert) -> AlertResponse:
    """Convert domain entity to response schema."""
    return AlertResponse(
        id=alert.id,
        rule_id=alert.rule_id,
        organization_id=alert.organization_id,
        site_id=alert.site_id,
        device_id=alert.device_id,
        severity=alert.severity.value,
        status=alert.status.value,
        title=alert.title,
        message=alert.message,
        metric_name=alert.metric_name,
        metric_value=alert.metric_value,
        threshold_value=alert.threshold_value,
        triggered_at=alert.triggered_at,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=alert.acknowledged_by,
        resolved_at=alert.resolved_at,
        resolved_by=alert.resolved_by,
        escalated=alert.escalated,
        escalated_at=alert.escalated_at,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


# Alert Rule Endpoints

@router.post(
    "/rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def create_alert_rule(
    rule_data: AlertRuleCreate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Create a new alert rule."""
    await check_org_admin(rule_data.organization_id, current_user, uow)

    # Verify site if provided
    if rule_data.site_id:
        site = await uow.sites.get_by_id(rule_data.site_id)
        if not site or site.organization_id != rule_data.organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Site not found in this organization",
            )

    # Create domain entity
    condition = AlertCondition(
        metric=rule_data.condition.metric,
        operator=ComparisonOperator(rule_data.condition.operator),
        threshold=rule_data.condition.threshold,
        duration_seconds=rule_data.condition.duration_seconds,
        device_type=rule_data.condition.device_type,
    )

    channels = [NotificationChannel(c) for c in rule_data.notification_channels]

    rule = AlertRule(
        organization_id=rule_data.organization_id,
        site_id=rule_data.site_id,
        name=rule_data.name,
        description=rule_data.description,
        condition=condition,
        severity=AlertSeverity(rule_data.severity),
        notification_channels=channels,
        cooldown_minutes=rule_data.cooldown_minutes,
        auto_resolve=rule_data.auto_resolve,
        notify_on_trigger=rule_data.notify_on_trigger,
        notify_on_resolve=rule_data.notify_on_resolve,
        escalation_minutes=rule_data.escalation_minutes,
    )

    created_rule = await uow.alert_rules.add(rule)
    await uow.commit()

    return alert_rule_to_response(created_rule)


@router.get(
    "/rules",
    response_model=AlertRuleListResponse,
    responses={403: {"model": ErrorResponse}},
)
async def list_alert_rules(
    organization_id: UUID = Query(..., description="Organization ID"),
    site_id: Optional[UUID] = Query(None, description="Filter by site"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List alert rules for an organization."""
    await check_org_access(organization_id, current_user, uow)

    if site_id:
        rules = await uow.alert_rules.get_by_site_id(site_id, is_active)
        total = len(rules)
        rules = rules[offset:offset + limit]
    else:
        rules = await uow.alert_rules.get_by_organization_id(
            organization_id, limit, offset, is_active
        )
        total = await uow.alert_rules.count_by_organization_id(
            organization_id, is_active
        )

    return AlertRuleListResponse(
        items=[alert_rule_to_response(r) for r in rules],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/rules/{rule_id}",
    response_model=AlertRuleResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_alert_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get alert rule by ID."""
    rule = await uow.alert_rules.get_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found",
        )

    await check_org_access(rule.organization_id, current_user, uow)

    return alert_rule_to_response(rule)


@router.put(
    "/rules/{rule_id}",
    response_model=AlertRuleResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_alert_rule(
    rule_id: UUID,
    rule_data: AlertRuleUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update an alert rule."""
    rule = await uow.alert_rules.get_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found",
        )

    await check_org_admin(rule.organization_id, current_user, uow)

    # Update fields
    if rule_data.name is not None:
        rule.name = rule_data.name
    if rule_data.description is not None:
        rule.description = rule_data.description
    if rule_data.condition is not None:
        rule.condition = AlertCondition(
            metric=rule_data.condition.metric,
            operator=ComparisonOperator(rule_data.condition.operator),
            threshold=rule_data.condition.threshold,
            duration_seconds=rule_data.condition.duration_seconds,
            device_type=rule_data.condition.device_type,
        )
    if rule_data.severity is not None:
        rule.severity = AlertSeverity(rule_data.severity)
    if rule_data.notification_channels is not None:
        rule.notification_channels = [
            NotificationChannel(c) for c in rule_data.notification_channels
        ]
    if rule_data.cooldown_minutes is not None:
        rule.cooldown_minutes = rule_data.cooldown_minutes
    if rule_data.auto_resolve is not None:
        rule.auto_resolve = rule_data.auto_resolve
    if rule_data.notify_on_trigger is not None:
        rule.notify_on_trigger = rule_data.notify_on_trigger
    if rule_data.notify_on_resolve is not None:
        rule.notify_on_resolve = rule_data.notify_on_resolve
    if rule_data.escalation_minutes is not None:
        rule.escalation_minutes = rule_data.escalation_minutes

    rule.mark_updated()
    updated_rule = await uow.alert_rules.update(rule)
    await uow.commit()

    return alert_rule_to_response(updated_rule)


@router.post(
    "/rules/{rule_id}/toggle",
    response_model=AlertRuleResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def toggle_alert_rule(
    rule_id: UUID,
    toggle_data: AlertRuleToggleRequest,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Activate or deactivate an alert rule."""
    rule = await uow.alert_rules.get_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found",
        )

    await check_org_admin(rule.organization_id, current_user, uow)

    if toggle_data.is_active:
        rule.activate()
    else:
        rule.deactivate()

    updated_rule = await uow.alert_rules.update(rule)
    await uow.commit()

    return alert_rule_to_response(updated_rule)


@router.delete(
    "/rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_alert_rule(
    rule_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Delete an alert rule."""
    rule = await uow.alert_rules.get_by_id(rule_id)
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert rule not found",
        )

    await check_org_admin(rule.organization_id, current_user, uow)

    await uow.alert_rules.delete(rule_id)
    await uow.commit()


# Alert Endpoints

@router.get(
    "",
    response_model=AlertListResponse,
    responses={403: {"model": ErrorResponse}},
)
async def list_alerts(
    organization_id: UUID = Query(..., description="Organization ID"),
    site_id: Optional[UUID] = Query(None, description="Filter by site"),
    device_id: Optional[UUID] = Query(None, description="Filter by device"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List alerts for an organization."""
    await check_org_access(organization_id, current_user, uow)

    if device_id:
        alerts = await uow.alerts.get_by_device_id(device_id, limit, status_filter)
        total = len(alerts)
    elif site_id:
        alerts = await uow.alerts.get_by_site_id(
            site_id, limit, offset, status_filter, severity
        )
        total = await uow.alerts.count_by_site_id(site_id, status_filter, severity)
    else:
        alerts = await uow.alerts.get_by_organization_id(
            organization_id, limit, offset, status_filter, severity
        )
        total = await uow.alerts.count_by_organization_id(
            organization_id, status_filter, severity
        )

    return AlertListResponse(
        items=[alert_to_response(a) for a in alerts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/active",
    response_model=list[AlertResponse],
    responses={403: {"model": ErrorResponse}},
)
async def get_active_alerts(
    organization_id: UUID = Query(..., description="Organization ID"),
    site_id: Optional[UUID] = Query(None, description="Filter by site"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get all active (unresolved) alerts."""
    await check_org_access(organization_id, current_user, uow)

    alerts = await uow.alerts.get_active_alerts(organization_id, site_id)

    return [alert_to_response(a) for a in alerts]


@router.get(
    "/critical",
    response_model=list[AlertResponse],
    responses={403: {"model": ErrorResponse}},
)
async def get_critical_alerts(
    organization_id: UUID = Query(..., description="Organization ID"),
    site_id: Optional[UUID] = Query(None, description="Filter by site"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get critical severity active alerts."""
    await check_org_access(organization_id, current_user, uow)

    alerts = await uow.alerts.get_critical_alerts(organization_id, site_id)

    return [alert_to_response(a) for a in alerts]


@router.get(
    "/summary",
    response_model=AlertSummary,
    responses={403: {"model": ErrorResponse}},
)
async def get_alert_summary(
    organization_id: UUID = Query(..., description="Organization ID"),
    site_id: Optional[UUID] = Query(None, description="Filter by site"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get alert summary for dashboard."""
    await check_org_access(organization_id, current_user, uow)

    if site_id:
        active_count = await uow.alerts.count_by_site_id(site_id, "active")
        acknowledged_count = await uow.alerts.count_by_site_id(site_id, "acknowledged")
        critical_count = await uow.alerts.count_by_site_id(site_id, "active", "critical")
        warning_count = await uow.alerts.count_by_site_id(site_id, "active", "warning")
        info_count = await uow.alerts.count_by_site_id(site_id, "active", "info")
        recent = await uow.alerts.get_by_site_id(site_id, limit=5)
    else:
        active_count = await uow.alerts.count_by_organization_id(organization_id, "active")
        acknowledged_count = await uow.alerts.count_by_organization_id(
            organization_id, "acknowledged"
        )
        critical_count = await uow.alerts.count_by_organization_id(
            organization_id, "active", "critical"
        )
        warning_count = await uow.alerts.count_by_organization_id(
            organization_id, "active", "warning"
        )
        info_count = await uow.alerts.count_by_organization_id(
            organization_id, "active", "info"
        )
        recent = await uow.alerts.get_by_organization_id(organization_id, limit=5)

    return AlertSummary(
        total_active=active_count,
        total_acknowledged=acknowledged_count,
        total_critical=critical_count,
        total_warning=warning_count,
        total_info=info_count,
        recent_alerts=[alert_to_response(a) for a in recent],
    )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get alert by ID."""
    alert = await uow.alerts.get_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_org_access(alert.organization_id, current_user, uow)

    return alert_to_response(alert)


@router.post(
    "/{alert_id}/acknowledge",
    response_model=AlertResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def acknowledge_alert(
    alert_id: UUID,
    _: AlertAcknowledgeRequest = None,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Acknowledge an alert."""
    alert = await uow.alerts.get_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_org_access(alert.organization_id, current_user, uow)

    if alert.status != AlertStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only active alerts can be acknowledged",
        )

    alert.acknowledge(current_user.id)
    updated_alert = await uow.alerts.update(alert)
    await uow.commit()

    return alert_to_response(updated_alert)


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def resolve_alert(
    alert_id: UUID,
    resolve_data: AlertResolveRequest = None,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Resolve an alert."""
    alert = await uow.alerts.get_by_id(alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await check_org_access(alert.organization_id, current_user, uow)

    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert is already resolved",
        )

    alert.resolve(current_user.id)
    updated_alert = await uow.alerts.update(alert)
    await uow.commit()

    return alert_to_response(updated_alert)
