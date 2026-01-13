"""
Authentication API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import (
    get_auth_service,
    get_current_user,
    get_jwt_handler,
    get_unit_of_work,
)
from ..schemas.auth_schemas import (
    AuthResponse,
    ChangePasswordRequest,
    ErrorResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from ...application.services.auth_service import (
    AuthService,
    LoginRequest as ServiceLoginRequest,
    RegisterRequest as ServiceRegisterRequest,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User
from ...infrastructure.security import JWTHandler

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Email already exists"},
    },
)
async def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Register a new user account.

    Returns the created user profile. Email verification will be required
    before full access is granted.
    """
    service_request = ServiceRegisterRequest(
        email=request.email,
        password=request.password,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
    )

    result = await auth_service.register(service_request, uow)

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

    return UserResponse(
        id=result.user.id,
        email=result.user.email,
        first_name=result.user.first_name,
        last_name=result.user.last_name,
        phone=result.user.phone,
        role=result.user.role.value,
        status=result.user.status.value,
        is_verified=result.user.is_verified,
        created_at=result.user.created_at,
        updated_at=result.user.updated_at,
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
            email=result.user.email,
            first_name=result.user.first_name,
            last_name=result.user.last_name,
            phone=result.user.phone,
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
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
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
):
    """
    Request password reset email.

    If the email exists in the system, a password reset link will be sent.
    For security, this endpoint always returns success even if the email
    doesn't exist.
    """
    # TODO: Implement password reset email sending
    # For now, we just acknowledge the request
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
)
async def verify_email(
    token: str,
):
    """
    Verify user's email address using verification token.

    The token is sent to the user's email during registration.
    """
    # TODO: Implement email verification token handling
    return MessageResponse(
        message="Email verification pending implementation",
        success=False,
    )
