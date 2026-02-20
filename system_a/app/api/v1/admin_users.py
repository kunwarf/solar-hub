"""
Admin portal - User management endpoints.

Provides super_admin with cross-organization visibility and the ability
to change any user's role or status.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..dependencies import (
    get_unit_of_work,
    require_portal_admin,
    require_super_admin,
)
from ..schemas.admin_schemas import (
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserUpdate,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.admin import AdminAuditLog
from ...domain.entities.user import User, UserRole, UserStatus

router = APIRouter(prefix="/admin/users", tags=["Admin - Users"])


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    role: Optional[UserRole] = Query(None),
    status_filter: Optional[UserStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_portal_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> AdminUserListResponse:
    """
    List all platform users.

    super_admin and ops_admin (view_users permission) can call this.
    """
    users = await uow.users.list_all(
        role=role.value if role else None,
        status=status_filter.value if status_filter else None,
        limit=limit,
        offset=offset,
    )
    total = await uow.users.count(
        role=role.value if role else None,
        status=status_filter.value if status_filter else None,
    )

    return AdminUserListResponse(
        items=[
            AdminUserListItem(
                id=u.id,
                email=str(u.email),
                first_name=u.first_name,
                last_name=u.last_name,
                role=u.role,
                status=u.status,
                last_login_at=u.last_login_at,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put("/{user_id}", response_model=AdminUserListItem)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    request: Request,
    current_user: User = Depends(require_super_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> AdminUserListItem:
    """
    Update a user's role or status. Requires super_admin.

    Used to promote/demote admin roles or suspend/reactivate accounts.
    """
    user = await uow.users.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account through this endpoint",
        )

    old_values: dict = {"role": user.role.value, "status": user.status.value}

    if payload.role is not None:
        user.change_role(new_role=payload.role, changed_by=current_user.id)

    if payload.status is not None:
        if payload.status == UserStatus.SUSPENDED and user.status != UserStatus.SUSPENDED:
            user.suspend(reason="Admin action", suspended_by=current_user.id)
        elif payload.status == UserStatus.ACTIVE and user.status == UserStatus.SUSPENDED:
            user.reactivate(reactivated_by=current_user.id)
        elif payload.status == UserStatus.DEACTIVATED:
            user.deactivate()

    updated = await uow.users.update(user)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="update",
        resource_type="user",
        resource_id=str(user_id),
        old_values=old_values,
        new_values={"role": updated.role.value, "status": updated.status.value},
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()

    return AdminUserListItem(
        id=updated.id,
        email=str(updated.email),
        first_name=updated.first_name,
        last_name=updated.last_name,
        role=updated.role,
        status=updated.status,
        last_login_at=updated.last_login_at,
        created_at=updated.created_at,
    )
