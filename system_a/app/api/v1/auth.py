"""
Authentication API endpoints.
"""
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger(__name__)

from ..dependencies import (
    get_auth_service,
    get_current_user,
    get_jwt_handler,
    get_registration_service,
    get_unit_of_work,
)
from ..schemas.auth_schemas import (
    AuthResponse,
    ChangePasswordRequest,
    DeviceClaimResponse,
    ErrorResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    SiteResponse,
    TokenResponse,
    UserResponse,
)
from ...application.services.auth_service import (
    AuthService,
    LoginRequest as ServiceLoginRequest,
)
from ...application.services.registration_service import (
    RegistrationService,
    RegistrationRequest as ServiceRegistrationRequest,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User
from ...infrastructure.security import JWTHandler

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Email already exists"},
    },
)
async def register(
    request: RegisterRequest,
    registration_service: RegistrationService = Depends(get_registration_service),
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Register a new user account with organization and site setup.

    Creates:
    - User account
    - Default organization
    - Default site ("My Home")
    - Claims device if device_serial is provided

    Returns the created user profile, site info, and optional device claim info.
    Email verification will be required before full access is granted.
    """
    service_request = ServiceRegistrationRequest(
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        device_serial=request.device_serial,
    )

    result = await registration_service.register(service_request, uow)

    if not result.success:
        if "already registered" in result.error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result.error,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    # Send verification email only if user needs verification
    # (Skip if user is already active - email verification is currently disabled)
    if not result.user.is_verified:
        try:
            await auth_service.send_verification_email(result.user)
        except Exception:
            pass  # Non-blocking, don't fail registration if email fails

    # Build response
    user_response = UserResponse(
        id=result.user.id,
        email=str(result.user.email),
        first_name=result.user.first_name,
        last_name=result.user.last_name,
        phone=str(result.user.phone) if result.user.phone else None,
        role=result.user.role.value,
        status=result.user.status.value,
        is_verified=result.user.is_verified,
        created_at=result.user.created_at,
        updated_at=result.user.updated_at,
    )

    site_response = None
    if result.site:
        site_response = SiteResponse(
            id=result.site.id,
            name=result.site.name,
            is_default=result.site.is_default,
        )

    device_response = None
    if result.device:
        device_response = DeviceClaimResponse(
            id=result.device.id,
            serial_number=result.device.serial_number,
            device_type=result.device.device_type,
            manufacturer=result.device.manufacturer,
            status=result.device.status,
        )

    # Build message
    message = "Registration successful"
    if result.device_error:
        message = f"Registration successful. Note: {result.device_error}"

    return RegisterResponse(
        success=True,
        message=message,
        user=user_response,
        site=site_response,
        device=device_response,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        403: {"model": ErrorResponse, "description": "Account locked or suspended"},
    },
)
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
):
    """
    Authenticate user and return access/refresh tokens.

    Access tokens expire after 15 minutes. Use the refresh endpoint
    to obtain new tokens without re-authenticating.
    """
    service_request = ServiceLoginRequest(
        email=request.email,
        password=request.password,
    )

    result = await auth_service.login(service_request, uow)

    if not result.success:
        if "locked" in result.error.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.error,
            )
        if "suspended" in result.error.lower() or "deactivated" in result.error.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.error,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthResponse(
        user=UserResponse(
            id=result.user.id,
            email=str(result.user.email),
            first_name=result.user.first_name,
            last_name=result.user.last_name,
            phone=str(result.user.phone) if result.user.phone else None,
            role=result.user.role.value,
            status=result.user.status.value,
            is_verified=result.user.is_verified,
            created_at=result.user.created_at,
            updated_at=result.user.updated_at,
        ),
        tokens=TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type="Bearer",
            expires_in=jwt_handler._access_token_expire_minutes * 60,
        ),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    },
)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
):
    """
    Refresh access token using a valid refresh token.

    Returns new access and refresh tokens. The old refresh token
    should be discarded.
    """
    result = await auth_service.refresh_tokens(request.refresh_token)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        token_type="Bearer",
        expires_in=jwt_handler._access_token_expire_minutes * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Get current authenticated user's profile.
    """
    return UserResponse(
        id=current_user.id,
        email=str(current_user.email),
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=str(current_user.phone) if current_user.phone else None,
        role=current_user.role.value,
        status=current_user.status.value,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid current password"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Change current user's password.

    Requires the current password for verification.
    """
    result = await auth_service.change_password(
        user_id=current_user.id,
        current_password=request.current_password,
        new_password=request.new_password,
        uow=uow,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return MessageResponse(
        message="Password changed successfully",
        success=True,
    )


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
)
async def forgot_password(
    request: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Request password reset email.

    If the email exists in the system, a password reset link will be sent.
    For security, this endpoint always returns success even if the email
    doesn't exist.
    """
    await auth_service.request_password_reset(request.email)

    return MessageResponse(
        message="If an account exists with this email, a password reset link has been sent",
        success=True,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
)
async def logout(
    current_user: User = Depends(get_current_user),
):
    """
    Log out current user.

    Note: JWT tokens are stateless, so this endpoint is primarily for
    client-side token cleanup. For enhanced security, implement token
    blacklisting using Redis.
    """
    # TODO: Implement token blacklisting for enhanced security
    return MessageResponse(
        message="Logged out successfully",
        success=True,
    )


@router.post(
    "/verify-email/{token}",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def verify_email(
    token: str,
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Verify user's email address using verification token.

    The token is sent to the user's email during registration.
    """
    result = await auth_service.verify_email_token(token, uow)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return MessageResponse(
        message="Email verified successfully",
        success=True,
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid token or password"},
    },
)
async def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Reset password using the token from password reset email.

    The token expires after 60 minutes for security.
    """
    result = await auth_service.reset_password_with_token(
        token=request.token,
        new_password=request.new_password,
        uow=uow,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return MessageResponse(
        message="Password reset successfully",
        success=True,
    )


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
)
async def resend_verification_email(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Resend email verification link to current user.

    Only available for users who haven't verified their email yet.
    """
    if current_user.is_verified:
        return MessageResponse(
            message="Email is already verified",
            success=True,
        )

    await auth_service.send_verification_email(current_user)

    return MessageResponse(
        message="Verification email sent",
        success=True,
    )


# ============================================================================
# Device Claim Endpoints
# ============================================================================


@router.post(
    "/devices/claim/{serial_number}",
    response_model=DeviceClaimResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Device not found or already claimed"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def claim_device(
    serial_number: str,
    site_id: UUID,
    current_user: User = Depends(get_current_user),
    registration_service: RegistrationService = Depends(get_registration_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Claim an orphan device by serial number.

    The device must be in 'orphan' state (not already claimed).
    Device will be attached to the specified site.
    """
    logger.info("=== DEVICE CLAIM REQUEST ===")
    logger.info("Serial: %s, Site ID: %s, User: %s", serial_number, site_id, current_user.id)

    # Get user's organizations
    orgs = await uow.organizations.get_by_owner_id(current_user.id)
    logger.info("User organizations: %s", [str(o.id) for o in orgs] if orgs else "None")
    if not orgs:
        logger.warning("User has no organization")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization. Please contact support.",
        )

    organization = orgs[0]
    logger.info("Using organization: %s", organization.id)

    # Verify site belongs to user's organization
    site = await uow.sites.get_by_id(site_id)
    logger.info("Site lookup: %s, org_id: %s", site.id if site else "None", site.organization_id if site else "None")
    if not site or site.organization_id != organization.id:
        logger.warning("Site not found or doesn't belong to org")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Site not found or does not belong to your organization.",
        )

    # Claim the device (also creates record in System A)
    logger.info("Calling claim_device_for_user...")
    device, error = await registration_service.claim_device_for_user(
        user_id=current_user.id,
        site_id=site_id,
        organization_id=organization.id,
        device_serial=serial_number,
        uow=uow,  # Pass UoW to create device in System A
    )

    if error:
        logger.warning("Claim failed: %s", error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    logger.info("=== DEVICE CLAIM SUCCESS: %s ===", device.serial_number)
    return DeviceClaimResponse(
        id=device.id,
        serial_number=device.serial_number,
        device_type=device.device_type,
        manufacturer=device.manufacturer,
        status=device.status,
    )


@router.get(
    "/devices/available",
    response_model=List[DeviceClaimResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def get_available_devices(
    current_user: User = Depends(get_current_user),
    registration_service: RegistrationService = Depends(get_registration_service),
):
    """
    Get list of orphan devices available for claiming.

    Returns all devices that are in 'orphan' state and can be claimed.
    """
    logger.info("=== GET AVAILABLE DEVICES REQUEST ===")
    logger.info("User: %s", current_user.id)
    devices = await registration_service.get_orphan_devices()
    logger.info("Found %d orphan devices", len(devices))
    for d in devices:
        logger.info("  Device: %s (%s)", d.serial_number, d.device_type)

    return [
        DeviceClaimResponse(
            id=device.id,
            serial_number=device.serial_number,
            device_type=device.device_type,
            manufacturer=device.manufacturer,
            status=device.status,
        )
        for device in devices
    ]
