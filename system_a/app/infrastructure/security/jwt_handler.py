"""
JWT token handling implementation.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt

from ...application.interfaces.services import TokenService

logger = logging.getLogger(__name__)


@dataclass
class TokenPayload:
    """JWT token payload data."""
    sub: str  # Subject (user ID)
    exp: datetime  # Expiration time
    iat: datetime  # Issued at time
    jti: str  # JWT ID (unique identifier)
    type: str  # Token type (access/refresh)
    role: Optional[str] = None
    org_id: Optional[str] = None


@dataclass
class TokenPair:
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    token_type: str = "Bearer"


class JWTHandler(TokenService):
    """JWT token service implementation."""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
    ):
        """
        Initialize JWT handler.

        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT signing algorithm
            access_token_expire_minutes: Access token validity period
            refresh_token_expire_days: Refresh token validity period
            issuer: Token issuer claim
            audience: Token audience claim
        """
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_token_expire_minutes = access_token_expire_minutes
        self._refresh_token_expire_days = refresh_token_expire_days
        self._issuer = issuer
        self._audience = audience

    def create_access_token(
        self,
        user_id: UUID,
        role: Optional[str] = None,
        organization_id: Optional[UUID] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create a new access token.

        Args:
            user_id: User ID to include in token
            role: Optional role claim
            organization_id: Optional organization ID
            expires_delta: Custom expiration time (defaults to access_token_expire_minutes)
        """
        now = datetime.now(timezone.utc)
        if expires_delta:
            expires = now + expires_delta
        else:
            expires = now + timedelta(minutes=self._access_token_expire_minutes)

        payload = {
            "sub": str(user_id),
            "exp": expires,
            "iat": now,
            "jti": self._generate_jti(),
            "type": "access",
        }

        if role:
            payload["role"] = role
        if organization_id:
            payload["org_id"] = str(organization_id)
        if self._issuer:
            payload["iss"] = self._issuer
        if self._audience:
            payload["aud"] = self._audience

        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: UUID) -> str:
        """Create a new refresh token."""
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self._refresh_token_expire_days)

        payload = {
            "sub": str(user_id),
            "exp": expires,
            "iat": now,
            "jti": self._generate_jti(),
            "type": "refresh",
        }

        if self._issuer:
            payload["iss"] = self._issuer
        if self._audience:
            payload["aud"] = self._audience

        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def create_token_pair(
        self,
        user_id: UUID,
        role: Optional[str] = None,
        organization_id: Optional[UUID] = None,
    ) -> TokenPair:
        """Create both access and refresh tokens."""
        now = datetime.now(timezone.utc)
        access_expires = now + timedelta(minutes=self._access_token_expire_minutes)
        refresh_expires = now + timedelta(days=self._refresh_token_expire_days)

        access_token = self.create_access_token(user_id, role, organization_id)
        refresh_token = self.create_refresh_token(user_id)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_expires,
            refresh_token_expires_at=refresh_expires,
        )

    def verify_token(self, token: str) -> Optional[TokenPayload]:
        """Verify and decode a token."""
        try:
            options = {}
            if self._audience:
                options["audience"] = self._audience
            if self._issuer:
                options["issuer"] = self._issuer

            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                **options
            )

            return TokenPayload(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                jti=payload["jti"],
                type=payload["type"],
                role=payload.get("role"),
                org_id=payload.get("org_id"),
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def decode_token_unsafe(self, token: str) -> Optional[dict]:
        """
        Decode token without verification.
        Useful for getting user ID from expired tokens during refresh.
        """
        try:
            return jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
        except jwt.InvalidTokenError:
            return None

    def is_token_expired(self, token: str) -> bool:
        """Check if token is expired."""
        try:
            jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"verify_exp": True}
            )
            return False
        except jwt.ExpiredSignatureError:
            return True
        except jwt.InvalidTokenError:
            return True

    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """Get expiration time from token."""
        payload = self.decode_token_unsafe(token)
        if payload and "exp" in payload:
            return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        return None

    def decode_token(self, token: str) -> dict:
        """
        Decode and validate a token.

        Required by TokenService interface.
        Returns the payload as a dictionary.
        Raises jwt.InvalidTokenError if token is invalid.
        """
        options = {}
        if self._audience:
            options["audience"] = self._audience
        if self._issuer:
            options["issuer"] = self._issuer

        payload = jwt.decode(
            token,
            self._secret_key,
            algorithms=[self._algorithm],
            **options
        )
        return payload

    def revoke_token(self, token: str) -> None:
        """
        Revoke a token by storing its JTI in the Redis blacklist.

        The blacklist entry TTL matches the token's remaining lifetime so
        the entry is automatically cleaned up once the token would have
        expired anyway.
        """
        import asyncio
        try:
            payload = self.decode_token_unsafe(token)
            if not payload:
                return
            jti = payload.get("jti")
            if not jti:
                return
            exp = payload.get("exp")
            ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 1) if exp else (
                self._access_token_expire_minutes * 60
            )
            asyncio.get_event_loop().run_until_complete(self._blacklist_jti(jti, ttl))
        except Exception as e:
            logger.warning("Failed to revoke token: %s", e)

    async def revoke_token_async(self, token: str) -> None:
        """Async version of revoke_token for use inside async route handlers."""
        try:
            payload = self.decode_token_unsafe(token)
            if not payload:
                return
            jti = payload.get("jti")
            if not jti:
                return
            exp = payload.get("exp")
            ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 1) if exp else (
                self._access_token_expire_minutes * 60
            )
            await self._blacklist_jti(jti, ttl)
        except Exception as e:
            logger.warning("Failed to revoke token: %s", e)

    async def is_token_revoked(self, token: str) -> bool:
        """Return True if the token's JTI is in the Redis blacklist."""
        try:
            payload = self.decode_token_unsafe(token)
            if not payload:
                return False
            jti = payload.get("jti")
            if not jti:
                return False
            return await self._is_jti_blacklisted(jti)
        except Exception:
            return False

    @staticmethod
    async def _blacklist_jti(jti: str, ttl_seconds: int) -> None:
        from ..cache.redis_cache import RedisManager
        client = await RedisManager.get_client()
        await client.setex(f"token:blacklist:{jti}", ttl_seconds, "1")

    @staticmethod
    async def _is_jti_blacklisted(jti: str) -> bool:
        from ..cache.redis_cache import RedisManager
        client = await RedisManager.get_client()
        return bool(await client.exists(f"token:blacklist:{jti}"))

    def _generate_jti(self) -> str:
        """Generate unique JWT ID."""
        import uuid
        return str(uuid.uuid4())
