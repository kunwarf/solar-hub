"""
User domain entity and related value objects.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from .base import AggregateRoot, utc_now
from ..value_objects.email import Email
from ..value_objects.phone import PhoneNumber
from ..exceptions import ValidationException, BusinessRuleViolationException


class UserRole(str, Enum):
    """User roles within the system."""
    SUPER_ADMIN = "super_admin"  # Platform administrator
    OWNER = "owner"              # Organization owner
    ADMIN = "admin"              # Organization admin
    MANAGER = "manager"          # Site manager
    VIEWER = "viewer"            # Read-only access
    INSTALLER = "installer"      # Device installation access


class UserStatus(str, Enum):
    """User account status."""
    PENDING = "pending"          # Awaiting email verification
    ACTIVE = "active"            # Fully active account
    SUSPENDED = "suspended"      # Temporarily suspended
    DEACTIVATED = "deactivated"  # Permanently deactivated


@dataclass(frozen=True)
class UserPreferences:
    """User preference settings (value object)."""
    language: str = "en"
    timezone: str = "Asia/Karachi"
    date_format: str = "DD/MM/YYYY"
    time_format: str = "24h"
    currency: str = "PKR"
    notifications_enabled: bool = True
    email_notifications: bool = True
    sms_notifications: bool = True
    dashboard_refresh_interval: int = 30  # seconds

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'language': self.language,
            'timezone': self.timezone,
            'date_format': self.date_format,
            'time_format': self.time_format,
            'currency': self.currency,
            'notifications_enabled': self.notifications_enabled,
            'email_notifications': self.email_notifications,
            'sms_notifications': self.sms_notifications,
            'dashboard_refresh_interval': self.dashboard_refresh_interval
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserPreferences':
        """Create from dictionary."""
        return cls(
            language=data.get('language', 'en'),
            timezone=data.get('timezone', 'Asia/Karachi'),
            date_format=data.get('date_format', 'DD/MM/YYYY'),
            time_format=data.get('time_format', '24h'),
            currency=data.get('currency', 'PKR'),
            notifications_enabled=data.get('notifications_enabled', True),
            email_notifications=data.get('email_notifications', True),
            sms_notifications=data.get('sms_notifications', True),
            dashboard_refresh_interval=data.get('dashboard_refresh_interval', 30)
        )


@dataclass
class User(AggregateRoot):
    """
    User aggregate root.

    Represents a user in the system with authentication credentials,
    profile information, and preferences.
    """
    email: Email
    password_hash: str
    first_name: str
    last_name: str
    phone: Optional[PhoneNumber] = None
    status: UserStatus = UserStatus.PENDING
    role: UserRole = UserRole.VIEWER
    preferences: UserPreferences = field(default_factory=UserPreferences)
    email_verified_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None

    # Constants
    MAX_FAILED_ATTEMPTS = 5
    LOCK_DURATION_MINUTES = 30

    def __post_init__(self) -> None:
        """Validate user data on construction."""
        self._validate()

    def _validate(self) -> None:
        """Validate user data."""
        errors = {}

        if not self.first_name or len(self.first_name.strip()) < 1:
            errors['first_name'] = ['First name is required']

        if len(self.first_name) > 100:
            errors['first_name'] = ['First name cannot exceed 100 characters']

        if not self.last_name or len(self.last_name.strip()) < 1:
            errors['last_name'] = ['Last name is required']

        if len(self.last_name) > 100:
            errors['last_name'] = ['Last name cannot exceed 100 characters']

        if errors:
            raise ValidationException(
                message="Invalid user data",
                errors=errors
            )

    @property
    def full_name(self) -> str:
        """Return user's full name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active(self) -> bool:
        """Check if user account is active."""
        return self.status == UserStatus.ACTIVE

    @property
    def is_verified(self) -> bool:
        """Check if user email is verified."""
        return self.email_verified_at is not None

    @property
    def is_locked(self) -> bool:
        """Check if account is locked due to failed login attempts."""
        if self.locked_until is None:
            return False
        return utc_now() < self.locked_until

    @property
    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role in (UserRole.SUPER_ADMIN, UserRole.OWNER, UserRole.ADMIN)

    def verify_email(self) -> None:
        """Mark email as verified and activate account."""
        if self.is_verified:
            raise BusinessRuleViolationException(
                message="Email already verified",
                rule="email_verification"
            )

        self.email_verified_at = utc_now()
        if self.status == UserStatus.PENDING:
            self.status = UserStatus.ACTIVE
        self.mark_updated()

        # Add domain event
        from ..events.user_events import UserEmailVerified
        self.add_domain_event(UserEmailVerified(user_id=self.id, email=str(self.email)))

    def record_login_success(self) -> None:
        """Record successful login."""
        self.last_login_at = utc_now()
        self.failed_login_attempts = 0
        self.locked_until = None
        self.mark_updated()

        from ..events.user_events import UserLoggedIn
        self.add_domain_event(UserLoggedIn(user_id=self.id))

    def record_login_failure(self) -> None:
        """Record failed login attempt."""
        self.failed_login_attempts += 1

        if self.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            from datetime import timedelta
            self.locked_until = utc_now() + timedelta(minutes=self.LOCK_DURATION_MINUTES)

            from ..events.user_events import UserAccountLocked
            self.add_domain_event(UserAccountLocked(
                user_id=self.id,
                locked_until=self.locked_until
            ))

        self.mark_updated()

    def change_password(self, new_password_hash: str) -> None:
        """Change user password."""
        self.password_hash = new_password_hash
        self.mark_updated()

        from ..events.user_events import UserPasswordChanged
        self.add_domain_event(UserPasswordChanged(user_id=self.id))

    def update_profile(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[PhoneNumber] = None
    ) -> None:
        """Update user profile information."""
        if first_name is not None:
            self.first_name = first_name
        if last_name is not None:
            self.last_name = last_name
        if phone is not None:
            self.phone = phone

        self._validate()
        self.mark_updated()

        from ..events.user_events import UserProfileUpdated
        self.add_domain_event(UserProfileUpdated(user_id=self.id))

    def update_preferences(self, preferences: UserPreferences) -> None:
        """Update user preferences."""
        self.preferences = preferences
        self.mark_updated()

    def change_role(self, new_role: UserRole, changed_by: UUID) -> None:
        """Change user role (requires authorization)."""
        old_role = self.role
        self.role = new_role
        self.mark_updated()

        from ..events.user_events import UserRoleChanged
        self.add_domain_event(UserRoleChanged(
            user_id=self.id,
            old_role=old_role.value,
            new_role=new_role.value,
            changed_by=changed_by
        ))

    def suspend(self, reason: str, suspended_by: UUID) -> None:
        """Suspend user account."""
        if self.status == UserStatus.SUSPENDED:
            raise BusinessRuleViolationException(
                message="User is already suspended",
                rule="user_suspension"
            )

        self.status = UserStatus.SUSPENDED
        self.mark_updated()

        from ..events.user_events import UserSuspended
        self.add_domain_event(UserSuspended(
            user_id=self.id,
            reason=reason,
            suspended_by=suspended_by
        ))

    def reactivate(self, reactivated_by: UUID) -> None:
        """Reactivate suspended user account."""
        if self.status != UserStatus.SUSPENDED:
            raise BusinessRuleViolationException(
                message="User is not suspended",
                rule="user_reactivation"
            )

        self.status = UserStatus.ACTIVE
        self.mark_updated()

        from ..events.user_events import UserReactivated
        self.add_domain_event(UserReactivated(
            user_id=self.id,
            reactivated_by=reactivated_by
        ))

    def deactivate(self) -> None:
        """Permanently deactivate user account."""
        self.status = UserStatus.DEACTIVATED
        self.mark_updated()

        from ..events.user_events import UserDeactivated
        self.add_domain_event(UserDeactivated(user_id=self.id))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize user to dictionary."""
        return {
            'id': str(self.id),
            'email': str(self.email),
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': str(self.phone) if self.phone else None,
            'status': self.status.value,
            'role': self.role.value,
            'is_verified': self.is_verified,
            'preferences': self.preferences.to_dict(),
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def create(
        cls,
        email: str,
        password_hash: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        role: UserRole = UserRole.VIEWER
    ) -> 'User':
        """
        Factory method to create a new user.

        Args:
            email: User's email address
            password_hash: Hashed password
            first_name: User's first name
            last_name: User's last name
            phone: Optional phone number
            role: User role (defaults to VIEWER)

        Returns:
            New User instance with UserCreated event
        """
        user = cls(
            email=Email(email),
            password_hash=password_hash,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            phone=PhoneNumber.pakistan(phone) if phone else None,
            role=role
        )

        from ..events.user_events import UserCreated
        user.add_domain_event(UserCreated(
            user_id=user.id,
            email=str(user.email),
            role=role.value
        ))

        return user
