"""
Admin portal - Audit log endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ..dependencies import get_unit_of_work, require_portal_admin
from ..schemas.admin_schemas import AuditLogListResponse, AuditLogResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User

router = APIRouter(prefix="/admin/audit-log", tags=["Admin - Audit Log"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_log(
    admin_user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_portal_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> AuditLogListResponse:
    """
    List audit log entries (most recent first).

    All portal admin roles can view audit logs. Entries are immutable —
    no create/update/delete is exposed through this endpoint.
    """
    logs = await uow.admin_audit_logs.list_all(
        admin_user_id=admin_user_id,
        action=action,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )
    total = await uow.admin_audit_logs.count(
        admin_user_id=admin_user_id,
        action=action,
        resource_type=resource_type,
    )
    return AuditLogListResponse(
        items=[
            AuditLogResponse(
                id=log.id,
                admin_user_id=log.admin_user_id,
                admin_email=log.admin_email,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                old_values=log.old_values,
                new_values=log.new_values,
                ip_address=log.ip_address,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        limit=limit,
        offset=offset,
    )
