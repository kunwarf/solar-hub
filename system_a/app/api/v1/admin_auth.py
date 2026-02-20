"""
Admin portal authentication endpoints.

Reuses the existing JWT auth infrastructure — admin users authenticate
with the same mechanism as regular users but must hold a portal-admin role.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import (
    get_auth_service,
    get_unit_of_work,
    require_portal_admin,
)
from ..schemas.admin_schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminPermissions,
    AdminUserResponse,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...application.services.auth_service import AuthService, LoginRequest as ServiceLoginRequest
from ...domain.entities.user import User, UserRole, UserStatus

router = APIRouter(prefix="/admin/auth", tags=["Admin Auth"])

# Roles that are allowed to access the admin portal
_PORTAL_ADMIN_ROLES = {
    UserRole.SUPER_ADMIN,
    UserRole.OPS_ADMIN,
    UserRole.BILLING_ADMIN,
    UserRole.DEVICE_ADMIN,
    UserRole.FIRMWARE_ADMIN,
}


def _build_user_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        email=str(user.email),
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        status=user.status,
        permissions=AdminPermissions.for_role(user.role),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.post("/login", response_model=AdminLoginResponse)
async def admin_login(
    payload: AdminLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> AdminLoginResponse:
    """
    Authenticate as a portal admin user.

    Validates credentials then confirms the user holds a portal-admin role.
    Returns a standard JWT access token that can be used on all admin endpoints.
    """
    service_request = ServiceLoginRequest(
        email=str(payload.email),
        password=payload.password,
    )
    result = await auth_service.login(service_request, uow)

    if not result.success:
        error = result.error or "Invalid email or password"
        if "locked" in error.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
        if "suspended" in error.lower() or "deactivated" in error.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = result.user
    if user.role not in _PORTAL_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: insufficient admin privileges",
        )

    return AdminLoginResponse(
        access_token=result.access_token,
        user=_build_user_response(user),
    )


@router.get("/me", response_model=AdminUserResponse)
async def admin_me(
    current_user: User = Depends(require_portal_admin),
) -> AdminUserResponse:
    """Return the currently authenticated admin user's profile and permissions."""
    return _build_user_response(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def admin_logout(
    current_user: User = Depends(require_portal_admin),
) -> None:
    """
    Log out from the admin portal.

    Since we use stateless JWTs, logout is handled client-side by discarding
    the token. This endpoint is a no-op that exists for API consistency.
    """
    return None
