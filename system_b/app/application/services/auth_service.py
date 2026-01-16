"""
Device Authentication Service for System B.

Handles device authentication, token management, and session validation.
"""
import hashlib
import hmac
import secrets
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from uuid import UUID

from ...domain.entities.device import DeviceRegistry, DeviceSession
from ...infrastructure.database.repositories import DeviceRegistryRepository

logger = logging.getLogger(__name__)


@dataclass
class AuthToken:
    """Device authentication token."""
    device_id: UUID
    token: str
    expires_at: datetime
    issued_at: datetime = None

    def __post_init__(self):
        if self.issued_at is None:
            self.issued_at = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class AuthResult:
    """Result of authentication attempt."""
    success: bool
    device: Optional[DeviceRegistry] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class DeviceAuthService:
    """
    Service for device authentication.

    Handles:
    - Token generation and validation
    - Device authentication by serial number
    - Session management
    - Rate limiting (basic implementation)
    """

    def __init__(
        self,
        device_repo: DeviceRegistryRepository,
        secret_key: Optional[str] = None,
        token_expiry_days: int = 365,
        max_failed_attempts: int = 5,
        lockout_minutes: int = 30,
    ):
        self._device_repo = device_repo
        self._secret_key = secret_key or secrets.token_hex(32)
        self._token_expiry_days = token_expiry_days
        self._max_failed_attempts = max_failed_attempts
        self._lockout_minutes = lockout_minutes

        # Track failed attempts (in production, use Redis)
        self._failed_attempts: Dict[str, list] = {}

    # =========================================================================
    # Token Generation
    # =========================================================================

    async def generate_token(
        self,
        device_id: UUID,
        expires_in_days: Optional[int] = None,
    ) -> str:
        """
        Generate a new authentication token for a device.

        Args:
            device_id: Device UUID.
            expires_in_days: Token validity period.

        Returns:
            Plain-text token.
        """
        expiry_days = expires_in_days or self._token_expiry_days
        token = await self._device_repo.generate_auth_token(device_id, expiry_days)

        logger.info(f"Generated auth token for device {device_id}")

        return token

    async def regenerate_token(
        self,
        device_id: UUID,
        expires_in_days: Optional[int] = None,
    ) -> str:
        """
        Regenerate token for a device (invalidates old token).

        Args:
            device_id: Device UUID.
            expires_in_days: Token validity period.

        Returns:
            New plain-text token.
        """
        # Generate new token (automatically invalidates old)
        token = await self.generate_token(device_id, expires_in_days)

        logger.info(f"Regenerated auth token for device {device_id}")

        return token

    async def revoke_token(self, device_id: UUID) -> None:
        """
        Revoke a device's authentication token.

        Args:
            device_id: Device UUID.
        """
        await self._device_repo.revoke_auth_token(device_id)

        # Clear failed attempts
        self._clear_failed_attempts(str(device_id))

        logger.info(f"Revoked auth token for device {device_id}")

    # =========================================================================
    # Authentication
    # =========================================================================

    async def authenticate_by_token(
        self,
        device_id: UUID,
        token: str,
    ) -> AuthResult:
        """
        Authenticate device using device ID and token.

        Args:
            device_id: Device UUID.
            token: Authentication token.

        Returns:
            AuthResult with authentication outcome.
        """
        identifier = str(device_id)

        # Check rate limiting
        if self._is_locked_out(identifier):
            logger.warning(f"Device {device_id} is locked out due to failed attempts")
            return AuthResult(
                success=False,
                error_code="LOCKED_OUT",
                error_message="Too many failed authentication attempts",
            )

        # Validate token
        is_valid = await self._device_repo.validate_auth_token(device_id, token)

        if not is_valid:
            self._record_failed_attempt(identifier)
            logger.warning(f"Invalid token for device {device_id}")
            return AuthResult(
                success=False,
                error_code="INVALID_TOKEN",
                error_message="Invalid or expired token",
            )

        # Clear failed attempts on success
        self._clear_failed_attempts(identifier)

        # Get device info
        device = await self._device_repo.get_by_id(device_id)

        logger.info(f"Device {device_id} authenticated successfully")

        return AuthResult(success=True, device=device)

    async def authenticate_by_serial(
        self,
        serial_number: str,
        token: str,
    ) -> AuthResult:
        """
        Authenticate device using serial number and token.

        Args:
            serial_number: Device serial number.
            token: Authentication token.

        Returns:
            AuthResult with authentication outcome.
        """
        identifier = f"serial:{serial_number}"

        # Check rate limiting
        if self._is_locked_out(identifier):
            logger.warning(f"Serial {serial_number} is locked out")
            return AuthResult(
                success=False,
                error_code="LOCKED_OUT",
                error_message="Too many failed authentication attempts",
            )

        # Authenticate
        device = await self._device_repo.authenticate_by_serial(serial_number, token)

        if not device:
            self._record_failed_attempt(identifier)
            logger.warning(f"Authentication failed for serial {serial_number}")
            return AuthResult(
                success=False,
                error_code="INVALID_CREDENTIALS",
                error_message="Invalid serial number or token",
            )

        # Clear failed attempts on success
        self._clear_failed_attempts(identifier)

        logger.info(f"Device {serial_number} authenticated successfully")

        return AuthResult(success=True, device=device)

    async def authenticate_with_challenge(
        self,
        device_id: UUID,
        challenge: str,
        response: str,
    ) -> AuthResult:
        """
        Authenticate using challenge-response (HMAC-based).

        Args:
            device_id: Device UUID.
            challenge: Server-issued challenge.
            response: HMAC response from device.

        Returns:
            AuthResult with authentication outcome.
        """
        device = await self._device_repo.get_by_id(device_id)
        if not device or not device.auth_token_hash:
            return AuthResult(
                success=False,
                error_code="DEVICE_NOT_FOUND",
                error_message="Device not found or no token set",
            )

        # Calculate expected response
        # Note: In production, use the actual token stored securely
        expected = hmac.new(
            device.auth_token_hash.encode(),
            challenge.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, response):
            self._record_failed_attempt(str(device_id))
            return AuthResult(
                success=False,
                error_code="INVALID_RESPONSE",
                error_message="Challenge response mismatch",
            )

        self._clear_failed_attempts(str(device_id))
        return AuthResult(success=True, device=device)

    # =========================================================================
    # Challenge Generation
    # =========================================================================

    def generate_challenge(self) -> str:
        """
        Generate a random challenge for challenge-response auth.

        Returns:
            Random challenge string.
        """
        return secrets.token_hex(32)

    # =========================================================================
    # API Key Management (for HTTP API authentication)
    # =========================================================================

    def generate_api_key(
        self,
        device_id: UUID,
        expires_in_days: int = 365,
    ) -> Tuple[str, str]:
        """
        Generate an API key pair for HTTP API authentication.

        Args:
            device_id: Device UUID.
            expires_in_days: Key validity period.

        Returns:
            Tuple of (key_id, key_secret).
        """
        key_id = f"dev_{secrets.token_hex(8)}"
        key_secret = secrets.token_urlsafe(32)

        # In production, store this mapping in the database
        logger.info(f"Generated API key {key_id} for device {device_id}")

        return key_id, key_secret

    def validate_api_key_signature(
        self,
        key_secret: str,
        timestamp: str,
        signature: str,
        request_body: str = "",
    ) -> bool:
        """
        Validate API request signature.

        Args:
            key_secret: API key secret.
            timestamp: Request timestamp.
            signature: Request signature.
            request_body: Request body for signing.

        Returns:
            True if signature is valid.
        """
        # Construct message to sign
        message = f"{timestamp}:{request_body}"

        # Calculate expected signature
        expected = hmac.new(
            key_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    # =========================================================================
    # Rate Limiting
    # =========================================================================

    def _record_failed_attempt(self, identifier: str) -> None:
        """Record a failed authentication attempt."""
        now = datetime.now(timezone.utc)

        if identifier not in self._failed_attempts:
            self._failed_attempts[identifier] = []

        self._failed_attempts[identifier].append(now)

        # Clean old attempts
        cutoff = now - timedelta(minutes=self._lockout_minutes)
        self._failed_attempts[identifier] = [
            t for t in self._failed_attempts[identifier]
            if t > cutoff
        ]

    def _is_locked_out(self, identifier: str) -> bool:
        """Check if identifier is locked out."""
        if identifier not in self._failed_attempts:
            return False

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self._lockout_minutes)

        # Count recent failed attempts
        recent_attempts = [
            t for t in self._failed_attempts[identifier]
            if t > cutoff
        ]

        return len(recent_attempts) >= self._max_failed_attempts

    def _clear_failed_attempts(self, identifier: str) -> None:
        """Clear failed attempts for identifier."""
        self._failed_attempts.pop(identifier, None)

    def get_lockout_status(self, identifier: str) -> Dict[str, Any]:
        """
        Get lockout status for an identifier.

        Args:
            identifier: Device ID or serial identifier.

        Returns:
            Dict with lockout status information.
        """
        if identifier not in self._failed_attempts:
            return {
                "is_locked": False,
                "failed_attempts": 0,
                "remaining_attempts": self._max_failed_attempts,
            }

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self._lockout_minutes)

        recent_attempts = [
            t for t in self._failed_attempts[identifier]
            if t > cutoff
        ]

        is_locked = len(recent_attempts) >= self._max_failed_attempts
        remaining = max(0, self._max_failed_attempts - len(recent_attempts))

        result = {
            "is_locked": is_locked,
            "failed_attempts": len(recent_attempts),
            "remaining_attempts": remaining,
        }

        if is_locked and recent_attempts:
            oldest = min(recent_attempts)
            unlock_at = oldest + timedelta(minutes=self._lockout_minutes)
            result["unlocks_at"] = unlock_at.isoformat()

        return result

    # =========================================================================
    # Token Validation Helpers
    # =========================================================================

    async def is_token_valid(
        self,
        device_id: UUID,
        token: str,
    ) -> bool:
        """
        Check if a token is valid without recording failed attempts.

        Args:
            device_id: Device UUID.
            token: Token to validate.

        Returns:
            True if valid, False otherwise.
        """
        return await self._device_repo.validate_auth_token(device_id, token)

    async def get_token_status(
        self,
        device_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get token status for a device.

        Args:
            device_id: Device UUID.

        Returns:
            Dict with token status information.
        """
        device = await self._device_repo.get_by_id(device_id)

        if not device:
            return {"has_token": False, "device_found": False}

        has_token = device.auth_token_hash is not None
        is_expired = (
            device.token_expires_at is not None
            and device.token_expires_at < datetime.now(timezone.utc)
        )

        return {
            "device_found": True,
            "has_token": has_token,
            "is_expired": is_expired if has_token else None,
            "expires_at": device.token_expires_at.isoformat() if device.token_expires_at else None,
        }

    # =========================================================================
    # Cleanup
    # =========================================================================

    def cleanup_expired_lockouts(self) -> int:
        """
        Clean up expired lockout entries.

        Returns:
            Number of entries cleaned up.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self._lockout_minutes)

        cleaned = 0
        to_remove = []

        for identifier, attempts in self._failed_attempts.items():
            # Remove old attempts
            self._failed_attempts[identifier] = [t for t in attempts if t > cutoff]

            # Mark for removal if empty
            if not self._failed_attempts[identifier]:
                to_remove.append(identifier)

        for identifier in to_remove:
            del self._failed_attempts[identifier]
            cleaned += 1

        return cleaned
