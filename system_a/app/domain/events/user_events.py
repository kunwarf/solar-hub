"""
User domain events.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from .base import DomainEvent


@dataclass
class UserCreated(DomainEvent):
    """Event raised when a new user is created."""
    user_id: UUID
    email: str
    role: str

    @property
    def event_type(self) -> str:
        return "user.created"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id),
            'email': self.email,
            'role': self.role
        }


@dataclass
class UserEmailVerified(DomainEvent):
    """Event raised when user email is verified."""
    user_id: UUID
    email: str

    @property
    def event_type(self) -> str:
        return "user.email_verified"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id),
            'email': self.email
        }


@dataclass
class UserLoggedIn(DomainEvent):
    """Event raised when user logs in successfully."""
    user_id: UUID

    @property
    def event_type(self) -> str:
        return "user.logged_in"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id)
        }


@dataclass
class UserAccountLocked(DomainEvent):
    """Event raised when user account is locked due to failed login attempts."""
    user_id: UUID
    locked_until: datetime

    @property
    def event_type(self) -> str:
        return "user.account_locked"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id),
            'locked_until': self.locked_until.isoformat()
        }


@dataclass
class UserPasswordChanged(DomainEvent):
    """Event raised when user changes their password."""
    user_id: UUID

    @property
    def event_type(self) -> str:
        return "user.password_changed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id)
        }


@dataclass
class UserProfileUpdated(DomainEvent):
    """Event raised when user updates their profile."""
    user_id: UUID

    @property
    def event_type(self) -> str:
        return "user.profile_updated"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id)
        }


@dataclass
class UserRoleChanged(DomainEvent):
    """Event raised when user role is changed."""
    user_id: UUID
    old_role: str
    new_role: str
    changed_by: UUID

    @property
    def event_type(self) -> str:
        return "user.role_changed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id),
            'old_role': self.old_role,
            'new_role': self.new_role,
            'changed_by': str(self.changed_by)
        }


@dataclass
class UserSuspended(DomainEvent):
    """Event raised when user account is suspended."""
    user_id: UUID
    reason: str
    suspended_by: UUID

    @property
    def event_type(self) -> str:
        return "user.suspended"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id),
            'reason': self.reason,
            'suspended_by': str(self.suspended_by)
        }


@dataclass
class UserReactivated(DomainEvent):
    """Event raised when suspended user is reactivated."""
    user_id: UUID
    reactivated_by: UUID

    @property
    def event_type(self) -> str:
        return "user.reactivated"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id),
            'reactivated_by': str(self.reactivated_by)
        }


@dataclass
class UserDeactivated(DomainEvent):
    """Event raised when user account is permanently deactivated."""
    user_id: UUID

    @property
    def event_type(self) -> str:
        return "user.deactivated"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'user_id': str(self.user_id)
        }
