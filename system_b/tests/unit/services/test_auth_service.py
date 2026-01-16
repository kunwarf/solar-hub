"""
Unit tests for DeviceAuthService.

Tests device authentication, token management, and rate limiting.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.application.services.auth_service import DeviceAuthService, AuthResult
from app.domain.entities.device import DeviceRegistry
from app.domain.entities.telemetry import DeviceType, ConnectionStatus


@pytest.fixture
def mock_device_repo():
    """Create a mock device repository."""
    repo = AsyncMock()
    repo.generate_auth_token = AsyncMock(return_value="test_token_123")
    repo.validate_auth_token = AsyncMock(return_value=True)
    repo.authenticate_by_serial = AsyncMock(return_value=None)
    repo.revoke_auth_token = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def service(mock_device_repo):
    """Create a DeviceAuthService with mock repository."""
    return DeviceAuthService(mock_device_repo)


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_device(sample_device_id):
    """Create a sample device registry entity."""
    return DeviceRegistry(
        device_id=sample_device_id,
        id=sample_device_id,
        site_id=uuid4(),
        organization_id=uuid4(),
        device_type=DeviceType.INVERTER,
        serial_number="PD12K00001",
        connection_status=ConnectionStatus.DISCONNECTED,
        auth_token_hash="hashed_token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        created_at=datetime.now(timezone.utc),
    )


class TestDeviceAuthServiceInit:
    """Test service initialization."""

    def test_init_with_defaults(self, mock_device_repo):
        """Test service initializes with default settings."""
        service = DeviceAuthService(mock_device_repo)
        assert service._token_expiry_days == 365
        assert service._max_failed_attempts == 5
        assert service._lockout_minutes == 30

    def test_init_with_custom_settings(self, mock_device_repo):
        """Test service initializes with custom settings."""
        service = DeviceAuthService(
            mock_device_repo,
            token_expiry_days=30,
            max_failed_attempts=3,
            lockout_minutes=15,
        )
        assert service._token_expiry_days == 30
        assert service._max_failed_attempts == 3
        assert service._lockout_minutes == 15


class TestGenerateToken:
    """Test token generation."""

    @pytest.mark.asyncio
    async def test_generate_token_returns_token(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test generates and returns token."""
        mock_device_repo.generate_auth_token = AsyncMock(return_value="new_token_abc")

        result = await service.generate_token(sample_device_id)

        assert result == "new_token_abc"
        mock_device_repo.generate_auth_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_token_with_custom_expiry(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test generates token with custom expiry."""
        await service.generate_token(sample_device_id, expires_in_days=30)

        mock_device_repo.generate_auth_token.assert_called_once_with(
            sample_device_id, 30
        )


class TestRegenerateToken:
    """Test token regeneration."""

    @pytest.mark.asyncio
    async def test_regenerate_token(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test regenerates token."""
        mock_device_repo.generate_auth_token = AsyncMock(return_value="regenerated_token")

        result = await service.regenerate_token(sample_device_id)

        assert result == "regenerated_token"


class TestRevokeToken:
    """Test token revocation."""

    @pytest.mark.asyncio
    async def test_revoke_token(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test revokes token."""
        await service.revoke_token(sample_device_id)

        mock_device_repo.revoke_auth_token.assert_called_once_with(sample_device_id)


class TestAuthenticateByToken:
    """Test authentication by device ID and token."""

    @pytest.mark.asyncio
    async def test_authenticate_success(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test successful authentication."""
        mock_device_repo.validate_auth_token = AsyncMock(return_value=True)
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        result = await service.authenticate_by_token(sample_device_id, "valid_token")

        assert result.success is True
        assert result.device == sample_device

    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test authentication with invalid token."""
        mock_device_repo.validate_auth_token = AsyncMock(return_value=False)

        result = await service.authenticate_by_token(sample_device_id, "invalid_token")

        assert result.success is False
        assert result.error_code == "INVALID_TOKEN"

    @pytest.mark.asyncio
    async def test_authenticate_locked_out(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test authentication when locked out."""
        mock_device_repo.validate_auth_token = AsyncMock(return_value=False)

        # Exceed max failed attempts
        for _ in range(6):
            await service.authenticate_by_token(sample_device_id, "wrong")

        result = await service.authenticate_by_token(sample_device_id, "valid_token")

        assert result.success is False
        assert result.error_code == "LOCKED_OUT"


class TestAuthenticateBySerial:
    """Test authentication by serial number and token."""

    @pytest.mark.asyncio
    async def test_authenticate_by_serial_success(
        self, service, mock_device_repo, sample_device
    ):
        """Test successful serial authentication."""
        mock_device_repo.authenticate_by_serial = AsyncMock(return_value=sample_device)

        result = await service.authenticate_by_serial("PD12K00001", "valid_token")

        assert result.success is True
        assert result.device == sample_device

    @pytest.mark.asyncio
    async def test_authenticate_by_serial_failure(
        self, service, mock_device_repo
    ):
        """Test failed serial authentication."""
        mock_device_repo.authenticate_by_serial = AsyncMock(return_value=None)

        result = await service.authenticate_by_serial("UNKNOWN", "token")

        assert result.success is False
        assert result.error_code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_authenticate_by_serial_locked_out(
        self, service, mock_device_repo
    ):
        """Test serial authentication when locked out."""
        mock_device_repo.authenticate_by_serial = AsyncMock(return_value=None)

        # Exceed max failed attempts
        for _ in range(6):
            await service.authenticate_by_serial("PD12K00001", "wrong")

        result = await service.authenticate_by_serial("PD12K00001", "valid")

        assert result.success is False
        assert result.error_code == "LOCKED_OUT"


class TestAuthenticateWithChallenge:
    """Test challenge-response authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_device_not_found(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test authentication when device not found."""
        mock_device_repo.get_by_id = AsyncMock(return_value=None)

        result = await service.authenticate_with_challenge(
            sample_device_id, "challenge", "response"
        )

        assert result.success is False
        assert result.error_code == "DEVICE_NOT_FOUND"


class TestGenerateChallenge:
    """Test challenge generation."""

    def test_generate_challenge_returns_string(self, service):
        """Test generates challenge string."""
        challenge = service.generate_challenge()

        assert isinstance(challenge, str)
        assert len(challenge) == 64  # 32 bytes in hex

    def test_generate_challenge_unique(self, service):
        """Test generates unique challenges."""
        challenges = [service.generate_challenge() for _ in range(10)]
        assert len(set(challenges)) == 10


class TestGenerateApiKey:
    """Test API key generation."""

    def test_generate_api_key_returns_tuple(self, service, sample_device_id):
        """Test generates key ID and secret."""
        key_id, key_secret = service.generate_api_key(sample_device_id)

        assert key_id.startswith("dev_")
        assert len(key_secret) > 20


class TestValidateApiKeySignature:
    """Test API key signature validation."""

    def test_validate_valid_signature(self, service):
        """Test validates correct signature."""
        import hmac
        import hashlib

        secret = "test_secret"
        timestamp = "1234567890"
        body = '{"data": "test"}'

        # Calculate expected signature
        message = f"{timestamp}:{body}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        result = service.validate_api_key_signature(
            key_secret=secret,
            timestamp=timestamp,
            signature=signature,
            request_body=body,
        )

        assert result is True

    def test_validate_invalid_signature(self, service):
        """Test rejects invalid signature."""
        result = service.validate_api_key_signature(
            key_secret="secret",
            timestamp="1234567890",
            signature="invalid_signature",
            request_body="body",
        )

        assert result is False


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_is_locked_out_initially_false(self, service):
        """Test not locked out initially."""
        assert not service._is_locked_out("test_id")

    def test_record_failed_attempt(self, service):
        """Test records failed attempt."""
        service._record_failed_attempt("test_id")

        assert "test_id" in service._failed_attempts
        assert len(service._failed_attempts["test_id"]) == 1

    def test_lockout_after_max_attempts(self, service):
        """Test lockout after max failed attempts."""
        for _ in range(5):
            service._record_failed_attempt("test_id")

        assert service._is_locked_out("test_id") is True

    def test_clear_failed_attempts(self, service):
        """Test clears failed attempts."""
        service._record_failed_attempt("test_id")
        service._clear_failed_attempts("test_id")

        assert "test_id" not in service._failed_attempts


class TestGetLockoutStatus:
    """Test lockout status retrieval."""

    def test_get_lockout_status_not_locked(self, service):
        """Test status when not locked."""
        status = service.get_lockout_status("test_id")

        assert status["is_locked"] is False
        assert status["failed_attempts"] == 0
        assert status["remaining_attempts"] == 5

    def test_get_lockout_status_partial_attempts(self, service):
        """Test status with some failed attempts."""
        for _ in range(3):
            service._record_failed_attempt("test_id")

        status = service.get_lockout_status("test_id")

        assert status["is_locked"] is False
        assert status["failed_attempts"] == 3
        assert status["remaining_attempts"] == 2

    def test_get_lockout_status_locked(self, service):
        """Test status when locked."""
        for _ in range(5):
            service._record_failed_attempt("test_id")

        status = service.get_lockout_status("test_id")

        assert status["is_locked"] is True
        assert status["failed_attempts"] == 5
        assert status["remaining_attempts"] == 0
        assert "unlocks_at" in status


class TestIsTokenValid:
    """Test token validation helper."""

    @pytest.mark.asyncio
    async def test_is_token_valid_true(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test returns True for valid token."""
        mock_device_repo.validate_auth_token = AsyncMock(return_value=True)

        result = await service.is_token_valid(sample_device_id, "valid_token")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_token_valid_false(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test returns False for invalid token."""
        mock_device_repo.validate_auth_token = AsyncMock(return_value=False)

        result = await service.is_token_valid(sample_device_id, "invalid_token")

        assert result is False


class TestGetTokenStatus:
    """Test token status retrieval."""

    @pytest.mark.asyncio
    async def test_get_token_status_device_not_found(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test status when device not found."""
        mock_device_repo.get_by_id = AsyncMock(return_value=None)

        status = await service.get_token_status(sample_device_id)

        assert status["device_found"] is False
        assert status["has_token"] is False

    @pytest.mark.asyncio
    async def test_get_token_status_with_valid_token(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test status with valid token."""
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        status = await service.get_token_status(sample_device_id)

        assert status["device_found"] is True
        assert status["has_token"] is True
        assert status["is_expired"] is False

    @pytest.mark.asyncio
    async def test_get_token_status_expired(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test status with expired token."""
        sample_device.token_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        status = await service.get_token_status(sample_device_id)

        assert status["is_expired"] is True


class TestCleanupExpiredLockouts:
    """Test lockout cleanup."""

    def test_cleanup_expired_lockouts(self, service):
        """Test cleans up expired lockouts."""
        # Add some old failed attempts
        service._failed_attempts["old_id"] = [
            datetime.now(timezone.utc) - timedelta(hours=1)
        ]

        # Add some recent failed attempts
        service._failed_attempts["recent_id"] = [
            datetime.now(timezone.utc)
        ]

        cleaned = service.cleanup_expired_lockouts()

        assert cleaned == 1
        assert "old_id" not in service._failed_attempts
        assert "recent_id" in service._failed_attempts
