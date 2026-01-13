"""
FastAPI dependency injection providers.
"""
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..application.services.auth_service import AuthService
from ..application.interfaces.unit_of_work import UnitOfWork
from ..domain.entities.user import User, UserRole, UserStatus
from ..infrastructure.database.connection import (
    DatabaseManager,
    get_unit_of_work as create_unit_of_work,
)
from ..infrastructure.database.repositories import SQLAlchemyUserRepository
from ..infrastructure.security import BcryptPasswordHasher, JWTHandler
from ..config import get_settings

settings = get_settings()

# Security scheme
bearer_scheme = HTTPBearer(auto_error=False)


# Singleton instances for services
_password_hasher: Optional[BcryptPasswordHasher] = None
_jwt_handler: Optional[JWTHandler] = None


def get_password_hasher() -> BcryptPasswordHasher:
    """Get password hasher instance."""
    global _password_hasher
    if _password_hasher is None:
        _password_hasher = BcryptPasswordHasher(rounds=12)
    return _password_hasher


def get_jwt_handler() -> JWTHandler:
    """Get JWT handler instance."""
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler(
            secret_key=settings.jwt.secret_key,
            algorithm=settings.jwt.algorithm,
            access_token_expire_minutes=settings.jwt.access_token_expire_minutes,
            refresh_token_expire_days=settings.jwt.refresh_token_expire_days,
            issuer=settings.jwt.issuer,
            audience=settings.jwt.audience,
        )
    return _jwt_handler


async def get_unit_of_work() -> AsyncGenerator[UnitOfWork, None]:
    """
    Provide Unit of Work for request lifecycle.

    Handles transaction management per request.
    """
    uow = create_unit_of_work()
    async with uow:
        yield uow


def get_auth_service(
    uow: UnitOfWork = Depends(get_unit_of_work),
    password_hasher: BcryptPasswordHasher = Depends(get_password_hasher),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> AuthService:
    """Get authentication service instance."""
    return AuthService(
        user_repository=uow.users,
        password_hasher=password_hasher,
        token_service=jwt_handler,
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> Optional[User]:
    """
    Get current user from token if present.

    Returns None if no token provided.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = jwt_handler.verify_token(token)

    if not payload or payload.type != "access":
        return None

    try:
        user_id = UUID(payload.sub)
    except ValueError:
        return None

    user = await uow.users.get_by_id(user_id)

    if user and user.status in (UserStatus.SUSPENDED, UserStatus.DEACTIVATED):
        return None

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> User:
    """
    Get current authenticated user.

    Raises HTTPException if not authenticated.
    """
    token = credentials.credentials
    payload = jwt_handler.verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(payload.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await uow.users.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status == UserStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been suspended",
        )

    if user.status == UserStatus.DEACTIVATED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they are active.

    Raises HTTPException if user is not active.
    """
    if current_user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify email is verified.

    Raises HTTPException if email not verified.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return current_user


class RoleChecker:
    """
    Dependency for checking user roles.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(
            user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))
        ):
            ...
    """

    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user


# Common role checkers
require_admin = RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN])
require_super_admin = RoleChecker([UserRole.SUPER_ADMIN])
require_manager = RoleChecker([UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPER_ADMIN])
