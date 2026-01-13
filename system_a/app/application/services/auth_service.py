"""
Authentication application service.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from ..interfaces.repositories import UserRepository
from ..interfaces.services import PasswordHasher, TokenService, EventPublisher
from ..interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserStatus, UserRole, UserPreferences
from ...domain.events.user_events import (
    UserCreated,
    UserLoggedIn,
    UserAccountLocked,
    UserPasswordChanged,
    UserEmailVerified,
)


@dataclass
class AuthResult:
    """Result of authentication operations."""
    success: bool
    user: Optional[User] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RegisterRequest:
    """User registration request data."""
    email: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None


@dataclass
class LoginRequest:
    """User login request data."""
    email: str
    password: str


class AuthService:
    """
    Authentication service handling user registration, login, and token management.
    """

    # Account lockout settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        event_publisher: Optional[EventPublisher] = None,
    ):
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._event_publisher = event_publisher

    async def register(
        self,
        request: RegisterRequest,
        uow: UnitOfWork,
    ) -> AuthResult:
        """
        Register a new user.

        Args:
            request: Registration data
            uow: Unit of work for transaction management

        Returns:
            AuthResult with success status and user data
        """
        # Check if email already exists
        existing = await self._user_repository.get_by_email(request.email)
        if existing:
            return AuthResult(
                success=False,
                error="Email address is already registered"
            )

        # Hash password
        password_hash = self._password_hasher.hash(request.password)

        # Create user entity
        user = User(
            email=request.email.lower().strip(),
            phone=request.phone,
            password_hash=password_hash,
            first_name=request.first_name.strip(),
            last_name=request.last_name.strip(),
            status=UserStatus.PENDING_VERIFICATION,
            role=UserRole.VIEWER,  # Default role
            preferences=UserPreferences(),
        )

        # Add domain event
        user.add_domain_event(UserCreated(
            user_id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
        ))

        # Save user
        saved_user = await uow.users.add(user)
        await uow.commit()

        # Publish events
        if self._event_publisher:
            for event in saved_user.clear_domain_events():
                await self._event_publisher.publish(event)

        return AuthResult(
            success=True,
            user=saved_user,
        )

    async def login(
        self,
        request: LoginRequest,
        uow: UnitOfWork,
    ) -> AuthResult:
        """
        Authenticate user and return tokens.

        Args:
            request: Login credentials
            uow: Unit of work for transaction management

        Returns:
            AuthResult with tokens on success
        """
        # Find user by email
        user = await self._user_repository.get_by_email(request.email.lower().strip())

        if not user:
            return AuthResult(
                success=False,
                error="Invalid email or password"
            )

        # Check if account is locked
        if user.is_locked:
            return AuthResult(
                success=False,
                error="Account is temporarily locked due to too many failed login attempts"
            )

        # Check if account is active
        if user.status == UserStatus.SUSPENDED:
            return AuthResult(
                success=False,
                error="Account has been suspended"
            )

        if user.status == UserStatus.DEACTIVATED:
            return AuthResult(
                success=False,
                error="Account has been deactivated"
            )

        # Verify password
        if not self._password_hasher.verify(request.password, user.password_hash):
            # Record failed attempt
            user.record_login_failure()

            if user.is_locked:
                user.add_domain_event(UserAccountLocked(
                    user_id=user.id,
                    email=user.email,
                    failed_attempts=user.failed_login_attempts,
                    locked_until=user.locked_until,
                ))

            await uow.users.update(user)
            await uow.commit()

            # Publish events
            if self._event_publisher:
                for event in user.clear_domain_events():
                    await self._event_publisher.publish(event)

            return AuthResult(
                success=False,
                error="Invalid email or password"
            )

        # Successful login
        user.record_login_success()
        user.add_domain_event(UserLoggedIn(
            user_id=user.id,
            email=user.email,
        ))

        await uow.users.update(user)
        await uow.commit()

        # Generate tokens
        access_token = self._token_service.create_access_token(
            user_id=user.id,
            role=user.role.value,
        )
        refresh_token = self._token_service.create_refresh_token(user.id)

        # Publish events
        if self._event_publisher:
            for event in user.clear_domain_events():
                await self._event_publisher.publish(event)

        return AuthResult(
            success=True,
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_tokens(
        self,
        refresh_token: str,
    ) -> AuthResult:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            AuthResult with new tokens
        """
        # Verify refresh token
        payload = self._token_service.verify_token(refresh_token)

        if not payload:
            return AuthResult(
                success=False,
                error="Invalid or expired refresh token"
            )

        if payload.type != "refresh":
            return AuthResult(
                success=False,
                error="Invalid token type"
            )

        # Get user
        user_id = UUID(payload.sub)
        user = await self._user_repository.get_by_id(user_id)

        if not user:
            return AuthResult(
                success=False,
                error="User not found"
            )

        if user.status in (UserStatus.SUSPENDED, UserStatus.DEACTIVATED):
            return AuthResult(
                success=False,
                error="Account is not active"
            )

        # Generate new tokens
        new_access_token = self._token_service.create_access_token(
            user_id=user.id,
            role=user.role.value,
        )
        new_refresh_token = self._token_service.create_refresh_token(user.id)

        return AuthResult(
            success=True,
            user=user,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

    async def verify_email(
        self,
        user_id: UUID,
        uow: UnitOfWork,
    ) -> AuthResult:
        """
        Mark user's email as verified.

        Args:
            user_id: User to verify
            uow: Unit of work for transaction management

        Returns:
            AuthResult with success status
        """
        user = await self._user_repository.get_by_id(user_id)

        if not user:
            return AuthResult(
                success=False,
                error="User not found"
            )

        if user.is_verified:
            return AuthResult(
                success=True,
                user=user,
            )

        user.verify_email()

        await uow.users.update(user)
        await uow.commit()

        # Publish events
        if self._event_publisher:
            for event in user.clear_domain_events():
                await self._event_publisher.publish(event)

        return AuthResult(
            success=True,
            user=user,
        )

    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
        uow: UnitOfWork,
    ) -> AuthResult:
        """
        Change user's password.

        Args:
            user_id: User ID
            current_password: Current password for verification
            new_password: New password to set
            uow: Unit of work for transaction management

        Returns:
            AuthResult with success status
        """
        user = await self._user_repository.get_by_id(user_id)

        if not user:
            return AuthResult(
                success=False,
                error="User not found"
            )

        # Verify current password
        if not self._password_hasher.verify(current_password, user.password_hash):
            return AuthResult(
                success=False,
                error="Current password is incorrect"
            )

        # Hash and set new password
        new_hash = self._password_hasher.hash(new_password)
        user.change_password(new_hash)

        await uow.users.update(user)
        await uow.commit()

        # Publish events
        if self._event_publisher:
            for event in user.clear_domain_events():
                await self._event_publisher.publish(event)

        return AuthResult(
            success=True,
            user=user,
        )

    async def reset_password(
        self,
        user_id: UUID,
        new_password: str,
        uow: UnitOfWork,
    ) -> AuthResult:
        """
        Reset user's password (admin operation or after password reset request).

        Args:
            user_id: User ID
            new_password: New password to set
            uow: Unit of work for transaction management

        Returns:
            AuthResult with success status
        """
        user = await self._user_repository.get_by_id(user_id)

        if not user:
            return AuthResult(
                success=False,
                error="User not found"
            )

        # Hash and set new password
        new_hash = self._password_hasher.hash(new_password)
        user.change_password(new_hash)

        # Unlock account if it was locked
        user.failed_login_attempts = 0
        user.locked_until = None

        await uow.users.update(user)
        await uow.commit()

        # Publish events
        if self._event_publisher:
            for event in user.clear_domain_events():
                await self._event_publisher.publish(event)

        return AuthResult(
            success=True,
            user=user,
        )

    async def get_current_user(
        self,
        access_token: str,
    ) -> Optional[User]:
        """
        Get current user from access token.

        Args:
            access_token: Valid access token

        Returns:
            User if token is valid, None otherwise
        """
        payload = self._token_service.verify_token(access_token)

        if not payload or payload.type != "access":
            return None

        user_id = UUID(payload.sub)
        return await self._user_repository.get_by_id(user_id)

    def validate_password_strength(self, password: str) -> Tuple[bool, Optional[str]]:
        """
        Validate password meets security requirements.

        Args:
            password: Password to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        if len(password) > 128:
            return False, "Password must not exceed 128 characters"

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)

        if not has_upper:
            return False, "Password must contain at least one uppercase letter"

        if not has_lower:
            return False, "Password must contain at least one lowercase letter"

        if not has_digit:
            return False, "Password must contain at least one number"

        if not has_special:
            return False, "Password must contain at least one special character"

        return True, None
