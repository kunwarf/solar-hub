"""
User management API endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
    require_admin,
    require_super_admin,
)
from ..schemas.user_schemas import (
    UserDetailResponse,
    UserListResponse,
    UserPreferencesSchema,
    UserPreferencesUpdate,
    UserProfileUpdate,
    UserResponse,
    UserRoleUpdate,
    UserStatusUpdate,
)
from ..schemas.auth_schemas import MessageResponse, ErrorResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserRole, UserStatus, UserPreferences

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserDetailResponse,
    responses={401: {"model": ErrorResponse}},
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user's full profile with preferences."""
    return UserDetailResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        role=current_user.role.value,
        status=current_user.status.value,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        preferences=UserPreferencesSchema(
            timezone=current_user.preferences.timezone,
            language=current_user.preferences.language,
            currency=current_user.preferences.currency,
            date_format=current_user.preferences.date_format,
            notifications_enabled=current_user.preferences.notifications_enabled,
            email_notifications=current_user.preferences.email_notifications,
            sms_notifications=current_user.preferences.sms_notifications,
            dashboard_refresh_interval=current_user.preferences.dashboard_refresh_interval,
        ),
        last_login_at=current_user.last_login_at,
        failed_login_attempts=current_user.failed_login_attempts,
    )


@router.put(
    "/me",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}},
)
async def update_current_user_profile(
    request: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update current user's profile."""
    if request.first_name is not None:
        current_user.first_name = request.first_name
    if request.last_name is not None:
        current_user.last_name = request.last_name
    if request.phone is not None:
        current_user.phone = request.phone

    current_user.mark_updated()
    updated_user = await uow.users.update(current_user)
    await uow.commit()

    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        first_name=updated_user.first_name,
        last_name=updated_user.last_name,
        phone=updated_user.phone,
        role=updated_user.role.value,
        status=updated_user.status.value,
        is_verified=updated_user.is_verified,
        created_at=updated_user.created_at,
        updated_at=updated_user.updated_at,
    )


@router.put(
    "/me/preferences",
    response_model=UserPreferencesSchema,
    responses={401: {"model": ErrorResponse}},
)
async def update_current_user_preferences(
    request: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update current user's preferences."""
    prefs = current_user.preferences

    if request.timezone is not None:
        prefs.timezone = request.timezone
    if request.language is not None:
        prefs.language = request.language
    if request.currency is not None:
        prefs.currency = request.currency
    if request.date_format is not None:
        prefs.date_format = request.date_format
    if request.notifications_enabled is not None:
        prefs.notifications_enabled = request.notifications_enabled
    if request.email_notifications is not None:
        prefs.email_notifications = request.email_notifications
    if request.sms_notifications is not None:
        prefs.sms_notifications = request.sms_notifications
    if request.dashboard_refresh_interval is not None:
        prefs.dashboard_refresh_interval = request.dashboard_refresh_interval

    current_user.preferences = prefs
    current_user.mark_updated()
    await uow.users.update(current_user)
    await uow.commit()

    return UserPreferencesSchema(
        timezone=prefs.timezone,
        language=prefs.language,
        currency=prefs.currency,
        date_format=prefs.date_format,
        notifications_enabled=prefs.notifications_enabled,
        email_notifications=prefs.email_notifications,
        sms_notifications=prefs.sms_notifications,
        dashboard_refresh_interval=prefs.dashboard_refresh_interval,
    )


# Admin endpoints

@router.get(
    "",
    response_model=UserListResponse,
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    admin_user: User = Depends(require_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List all users (admin only)."""
    offset = (page - 1) * page_size

    users = await uow.users.list_all(
        limit=page_size,
        offset=offset,
        status=status_filter,
    )
    total = await uow.users.count(status=status_filter)
    pages = (total + page_size - 1) // page_size

    return UserListResponse(
        items=[
            UserResponse(
                id=u.id,
                email=u.email,
                first_name=u.first_name,
                last_name=u.last_name,
                phone=u.phone,
                role=u.role.value,
                status=u.status.value,
                is_verified=u.is_verified,
                created_at=u.created_at,
                updated_at=u.updated_at,
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_user(
    user_id: UUID,
    admin_user: User = Depends(require_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get user by ID (admin only)."""
    user = await uow.users.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserDetailResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        role=user.role.value,
        status=user.status.value,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        preferences=UserPreferencesSchema(
            timezone=user.preferences.timezone,
            language=user.preferences.language,
            currency=user.preferences.currency,
            date_format=user.preferences.date_format,
            notifications_enabled=user.preferences.notifications_enabled,
            email_notifications=user.preferences.email_notifications,
            sms_notifications=user.preferences.sms_notifications,
            dashboard_refresh_interval=user.preferences.dashboard_refresh_interval,
        ),
        last_login_at=user.last_login_at,
        failed_login_attempts=user.failed_login_attempts,
    )


@router.put(
    "/{user_id}/role",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_user_role(
    user_id: UUID,
    request: UserRoleUpdate,
    admin_user: User = Depends(require_super_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update user's role (super admin only)."""
    user = await uow.users.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent changing own role
    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    # Map string to enum
    role_map = {
        'viewer': UserRole.VIEWER,
        'installer': UserRole.INSTALLER,
        'manager': UserRole.MANAGER,
        'admin': UserRole.ADMIN,
    }
    new_role = role_map.get(request.role)

    if not new_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    user.role = new_role
    user.mark_updated()
    await uow.users.update(user)
    await uow.commit()

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        role=user.role.value,
        status=user.status.value,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.put(
    "/{user_id}/status",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def update_user_status(
    user_id: UUID,
    request: UserStatusUpdate,
    admin_user: User = Depends(require_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update user's status (admin only). Can suspend or reactivate users."""
    user = await uow.users.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent changing own status
    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own status",
        )

    # Apply status change
    if request.status == 'suspended':
        user.suspend(request.reason or "Suspended by administrator")
    elif request.status == 'active':
        user.reactivate()
    elif request.status == 'deactivated':
        user.status = UserStatus.DEACTIVATED
        user.mark_updated()

    await uow.users.update(user)
    await uow.commit()

    return UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone=user.phone,
        role=user.role.value,
        status=user.status.value,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def delete_user(
    user_id: UUID,
    admin_user: User = Depends(require_super_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Delete a user (super admin only)."""
    user = await uow.users.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent self-deletion
    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    deleted = await uow.users.delete(user_id)
    await uow.commit()

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        )

    return MessageResponse(
        message="User deleted successfully",
        success=True,
    )
