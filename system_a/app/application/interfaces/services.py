"""
External service interfaces (ports).

These interfaces define contracts for external services
that the application depends on.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID


class PasswordHasher(ABC):
    """Interface for password hashing service."""

    @abstractmethod
    def hash(self, password: str) -> str:
        """Hash a plain text password."""
        pass

    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        pass


class TokenService(ABC):
    """Interface for JWT token service."""

    @abstractmethod
    def create_access_token(self, user_id: UUID, extra_claims: Optional[Dict[str, Any]] = None) -> str:
        """Create a new access token."""
        pass

    @abstractmethod
    def create_refresh_token(self, user_id: UUID) -> str:
        """Create a new refresh token."""
        pass

    @abstractmethod
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a token."""
        pass

    @abstractmethod
    def revoke_token(self, token: str) -> None:
        """Revoke a token."""
        pass


class EmailService(ABC):
    """Interface for email service."""

    @abstractmethod
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """Send an email."""
        pass

    @abstractmethod
    async def send_verification_email(self, to: str, verification_url: str) -> bool:
        """Send email verification email."""
        pass

    @abstractmethod
    async def send_password_reset_email(self, to: str, reset_url: str) -> bool:
        """Send password reset email."""
        pass

    @abstractmethod
    async def send_alert_notification(
        self,
        to: str,
        alert_type: str,
        site_name: str,
        message: str
    ) -> bool:
        """Send alert notification email."""
        pass


class SMSService(ABC):
    """Interface for SMS service."""

    @abstractmethod
    async def send_sms(self, to: str, message: str) -> bool:
        """Send an SMS message."""
        pass

    @abstractmethod
    async def send_verification_code(self, to: str, code: str) -> bool:
        """Send verification code via SMS."""
        pass

    @abstractmethod
    async def send_alert_notification(
        self,
        to: str,
        site_name: str,
        message: str
    ) -> bool:
        """Send alert notification via SMS."""
        pass


class CacheService(ABC):
    """Interface for caching service."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache."""
        pass


class EventPublisher(ABC):
    """Interface for publishing domain events."""

    @abstractmethod
    async def publish(self, event: Any) -> None:
        """Publish a single domain event."""
        pass

    @abstractmethod
    async def publish_many(self, events: List[Any]) -> None:
        """Publish multiple domain events."""
        pass


class NotificationService(ABC):
    """Interface for sending notifications through multiple channels."""

    @abstractmethod
    async def send_notification(
        self,
        user_id: UUID,
        title: str,
        message: str,
        notification_type: str,
        channels: Optional[List[str]] = None,  # email, sms, push
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Send notification through specified or default channels."""
        pass

    @abstractmethod
    async def send_alert(
        self,
        user_ids: List[UUID],
        alert_id: UUID,
        site_name: str,
        alert_type: str,
        message: str,
        severity: str
    ) -> bool:
        """Send alert notification to multiple users."""
        pass
