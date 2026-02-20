"""
FastAPI dependency injection providers.
"""
from typing import AsyncGenerator, Optional, Union
from uuid import UUID

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..application.services.auth_service import AuthService
from ..application.services.telemetry_service import TelemetryService
from ..application.services.telemetry_sync_service import TelemetrySyncService
from ..application.services.registration_service import RegistrationService
from ..application.interfaces.unit_of_work import UnitOfWork
from ..domain.entities.user import User, UserRole, UserStatus
from ..infrastructure.database.connection import (
    DatabaseManager,
    get_unit_of_work as create_unit_of_work,
)
from ..infrastructure.database.repositories import (
    SQLAlchemyUserRepository,
    SQLAlchemyTelemetryRepository,
)
from ..infrastructure.cache.telemetry_cache import TelemetryCacheReader, telemetry_cache
from ..infrastructure.security import BcryptPasswordHasher, JWTHandler
from ..infrastructure.external import SMTPEmailService, MockEmailService, SystemBClient
from ..application.interfaces.services import EmailService
from ..config import get_settings

settings = get_settings()

# Security scheme
bearer_scheme = HTTPBearer(auto_error=False)


# Singleton instances for services
_password_hasher: Optional[BcryptPasswordHasher] = None
_jwt_handler: Optional[JWTHandler] = None
_email_service: Optional[EmailService] = None
_system_b_client: Optional[SystemBClient] = None


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


def get_email_service() -> EmailService:
    """
    Get email service instance.

    Uses MockEmailService if email is disabled in settings,
    otherwise uses SMTPEmailService.
    """
    global _email_service
    if _email_service is None:
        if settings.notifications.email_enabled:
            _email_service = SMTPEmailService(settings.notifications)
        else:
            _email_service = MockEmailService()
    return _email_service


def get_system_b_client_instance() -> SystemBClient:
    """Get System B client singleton instance."""
    global _system_b_client
    if _system_b_client is None:
        _system_b_client = SystemBClient(
            base_url=settings.system_b.url,
            timeout=settings.system_b.timeout,
            api_key=settings.system_b.api_key,
        )
    return _system_b_client


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
    email_service: EmailService = Depends(get_email_service),
) -> AuthService:
    """Get authentication service instance."""
    return AuthService(
        user_repository=uow.users,
        password_hasher=password_hasher,
        token_service=jwt_handler,
        email_service=email_service,
        base_url=settings.frontend_url,
    )


def get_registration_service(
    uow: UnitOfWork = Depends(get_unit_of_work),
    password_hasher: BcryptPasswordHasher = Depends(get_password_hasher),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
) -> RegistrationService:
    """Get registration service instance."""
    return RegistrationService(
        user_repository=uow.users,
        password_hasher=password_hasher,
        token_service=jwt_handler,
        system_b_client=system_b_client,
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


async def verify_service_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> bool:
    """
    Verify service-to-service API key from header.

    Used by System B and other backend services to authenticate.
    Returns True if valid API key provided.

    Raises HTTPException if API key is invalid or missing.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Get expected API key from settings
    expected_api_key = settings.system_b.api_key

    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key authentication not configured",
        )

    if x_api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return True


async def get_current_user_or_service(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> Union[User, str]:
    """
    Authenticate via either JWT token (for users) or API key (for services).

    Returns:
        - User entity if authenticated via JWT
        - "service" string if authenticated via API key

    Raises HTTPException if neither authentication method is valid.
    """
    # Try API key first
    if x_api_key:
        expected_api_key = settings.system_b.api_key
        if expected_api_key and x_api_key == expected_api_key:
            return "service"

    # Try JWT token
    if credentials:
        token = credentials.credentials
        payload = jwt_handler.verify_token(token)

        if payload and payload.type == "access":
            try:
                user_id = UUID(payload.sub)
                user = await uow.users.get_by_id(user_id)

                if user and user.status not in (UserStatus.SUSPENDED, UserStatus.DEACTIVATED):
                    return user
            except ValueError:
                pass

    # Neither authentication method worked
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication",
        headers={"WWW-Authenticate": "Bearer, ApiKey"},
    )


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

# Admin portal role checkers
require_portal_admin = RoleChecker([
    UserRole.SUPER_ADMIN,
    UserRole.OPS_ADMIN, UserRole.BILLING_ADMIN,
    UserRole.DEVICE_ADMIN, UserRole.FIRMWARE_ADMIN,
])
require_ops_admin = RoleChecker([UserRole.SUPER_ADMIN, UserRole.OPS_ADMIN])
require_billing_or_ops_admin = RoleChecker([
    UserRole.SUPER_ADMIN, UserRole.OPS_ADMIN, UserRole.BILLING_ADMIN,
])
require_firmware_admin = RoleChecker([UserRole.SUPER_ADMIN, UserRole.FIRMWARE_ADMIN])
require_device_admin = RoleChecker([UserRole.SUPER_ADMIN, UserRole.DEVICE_ADMIN])


async def get_telemetry_service(
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> TelemetryService:
    """
    Get telemetry service instance.

    Provides access to telemetry data for dashboards.
    """
    telemetry_repo = SQLAlchemyTelemetryRepository(uow._session)
    return TelemetryService(
        telemetry_repository=telemetry_repo,
        site_repository=uow.sites,
        device_repository=uow.devices,
        alert_repository=uow.alerts,
    )


def get_telemetry_cache() -> TelemetryCacheReader:
    """
    Get telemetry cache reader for real-time telemetry from Redis.

    System B writes telemetry to Redis, System A reads from it here.
    """
    return telemetry_cache


def get_telemetry_sync_service(
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
) -> TelemetrySyncService:
    """Get telemetry sync service for on-demand sync operations."""
    telemetry_repo = SQLAlchemyTelemetryRepository(uow._session)
    return TelemetrySyncService(
        system_b_client=system_b_client,
        telemetry_repository=telemetry_repo,
        site_repository=uow.sites,
        device_repository=uow.devices,
    )
