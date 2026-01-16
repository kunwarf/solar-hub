"""
Unit tests for DeviceRegistryRepository.

Tests device registration, authentication, and connection state management.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import hashlib

from app.infrastructure.database.repositories.device_registry_repository import DeviceRegistryRepository
from app.domain.entities.device import DeviceRegistry
from app.domain.entities.telemetry import DeviceType, ConnectionStatus


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def repository(mock_session):
    """Create a DeviceRegistryRepository with mock session."""
    return DeviceRegistryRepository(mock_session)


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


@pytest.fixture
def sample_organization_id():
    return uuid4()


@pytest.fixture
def sample_device(sample_device_id, sample_site_id, sample_organization_id):
    """Create a sample device registry entity."""
    return DeviceRegistry(
        id=sample_device_id,
        device_id=sample_device_id,
        site_id=sample_site_id,
        organization_id=sample_organization_id,
        device_type=DeviceType.INVERTER,
        serial_number="PD12K00001",
        connection_status=ConnectionStatus.DISCONNECTED,
        protocol="modbus_tcp",
        connection_config={"host": "192.168.1.100", "port": 502},
        polling_interval_seconds=60,
        created_at=datetime.now(timezone.utc),
    )


class TestDeviceRegistryRepositoryInit:
    """Test repository initialization."""

    def test_init_with_session(self, mock_session):
        """Test repository initializes with session."""
        repo = DeviceRegistryRepository(mock_session)
        assert repo._session == mock_session


class TestGetById:
    """Test getting device by ID."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(
        self, repository, mock_session, sample_device_id
    ):
        """Test returns None when device not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_by_id(sample_device_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_device(
        self, repository, mock_session, sample_device_id, sample_site_id, sample_organization_id
    ):
        """Test returns device when found."""
        mock_model = MagicMock()
        mock_model.device_id = sample_device_id
        mock_model.site_id = sample_site_id
        mock_model.organization_id = sample_organization_id
        mock_model.device_type = "inverter"
        mock_model.serial_number = "TEST001"
        mock_model.auth_token_hash = None
        mock_model.token_expires_at = None
        mock_model.connection_status = "disconnected"
        mock_model.last_connected_at = None
        mock_model.last_disconnected_at = None
        mock_model.reconnect_count = 0
        mock_model.protocol = "modbus_tcp"
        mock_model.connection_config = {}
        mock_model.polling_interval_seconds = 60
        mock_model.last_polled_at = None
        mock_model.next_poll_at = None
        mock_model.metadata_ = {}
        mock_model.created_at = datetime.now(timezone.utc)
        mock_model.updated_at = None
        mock_model.synced_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_by_id(sample_device_id)

        assert result is not None
        assert result.device_id == sample_device_id
        assert result.serial_number == "TEST001"


class TestGetBySerialNumber:
    """Test getting device by serial number."""

    @pytest.mark.asyncio
    async def test_get_by_serial_returns_none_when_not_found(
        self, repository, mock_session
    ):
        """Test returns None when serial not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_by_serial_number("NONEXISTENT")

        assert result is None


class TestGetBySite:
    """Test getting devices by site."""

    @pytest.mark.asyncio
    async def test_get_by_site_returns_empty_list(
        self, repository, mock_session, sample_site_id
    ):
        """Test returns empty list when no devices."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_by_site(sample_site_id)

        assert result == []


class TestCreate:
    """Test device creation."""

    @pytest.mark.asyncio
    async def test_create_adds_model_to_session(
        self, repository, mock_session, sample_device
    ):
        """Test create adds model to session."""
        mock_model = MagicMock()
        mock_model.device_id = sample_device.device_id
        mock_model.site_id = sample_device.site_id
        mock_model.organization_id = sample_device.organization_id
        mock_model.device_type = "inverter"
        mock_model.serial_number = sample_device.serial_number
        mock_model.auth_token_hash = None
        mock_model.token_expires_at = None
        mock_model.connection_status = "disconnected"
        mock_model.last_connected_at = None
        mock_model.last_disconnected_at = None
        mock_model.reconnect_count = 0
        mock_model.protocol = "modbus_tcp"
        mock_model.connection_config = {}
        mock_model.polling_interval_seconds = 60
        mock_model.last_polled_at = None
        mock_model.next_poll_at = None
        mock_model.metadata_ = {}
        mock_model.created_at = datetime.now(timezone.utc)
        mock_model.updated_at = None
        mock_model.synced_at = None

        async def mock_refresh(model):
            pass

        mock_session.refresh = mock_refresh

        result = await repository.create(sample_device)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()


class TestUpdate:
    """Test device update."""

    @pytest.mark.asyncio
    async def test_update_executes_statement(
        self, repository, mock_session, sample_device
    ):
        """Test update executes update statement."""
        mock_session.execute = AsyncMock()

        result = await repository.update(sample_device)

        mock_session.execute.assert_called_once()
        assert result.updated_at is not None


class TestDelete:
    """Test device deletion."""

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(
        self, repository, mock_session, sample_device_id
    ):
        """Test delete returns True when device deleted."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.delete(sample_device_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self, repository, mock_session, sample_device_id
    ):
        """Test delete returns False when device not found."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.delete(sample_device_id)

        assert result is False


class TestUpdateConnectionStatus:
    """Test connection status updates."""

    @pytest.mark.asyncio
    async def test_update_status_to_connected(
        self, repository, mock_session, sample_device_id
    ):
        """Test updating status to connected."""
        mock_session.execute = AsyncMock()

        await repository.update_connection_status(
            sample_device_id,
            ConnectionStatus.CONNECTED
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_to_disconnected(
        self, repository, mock_session, sample_device_id
    ):
        """Test updating status to disconnected."""
        mock_session.execute = AsyncMock()

        await repository.update_connection_status(
            sample_device_id,
            ConnectionStatus.DISCONNECTED
        )

        mock_session.execute.assert_called_once()


class TestGetConnectedDevices:
    """Test getting connected devices."""

    @pytest.mark.asyncio
    async def test_get_connected_returns_empty_list(
        self, repository, mock_session
    ):
        """Test returns empty list when no connected devices."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_connected_devices()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_connected_with_site_filter(
        self, repository, mock_session, sample_site_id
    ):
        """Test get connected with site filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_connected_devices(site_id=sample_site_id)

        mock_session.execute.assert_called_once()


class TestGetDevicesDueForPolling:
    """Test getting devices due for polling."""

    @pytest.mark.asyncio
    async def test_get_devices_due_for_polling(
        self, repository, mock_session
    ):
        """Test gets devices due for polling."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_devices_due_for_polling()

        assert result == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_devices_due_respects_limit(
        self, repository, mock_session
    ):
        """Test respects limit parameter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_devices_due_for_polling(limit=50)

        mock_session.execute.assert_called_once()


class TestUpdatePollTime:
    """Test poll time updates."""

    @pytest.mark.asyncio
    async def test_update_poll_time_calculates_next_poll(
        self, repository, mock_session, sample_device_id
    ):
        """Test update poll time calculates next poll."""
        # First call returns polling interval
        mock_result = MagicMock()
        mock_result.scalar.return_value = 60  # 60 second interval
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.update_poll_time(sample_device_id)

        # Called twice: once for interval query, once for update
        assert mock_session.execute.call_count == 2


class TestGenerateAuthToken:
    """Test authentication token generation."""

    @pytest.mark.asyncio
    async def test_generate_auth_token_returns_token(
        self, repository, mock_session, sample_device_id
    ):
        """Test generates and returns token."""
        mock_session.execute = AsyncMock()

        token = await repository.generate_auth_token(sample_device_id)

        assert token is not None
        assert len(token) > 20  # URL-safe token should be reasonably long
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_auth_token_with_custom_expiry(
        self, repository, mock_session, sample_device_id
    ):
        """Test generates token with custom expiry."""
        mock_session.execute = AsyncMock()

        token = await repository.generate_auth_token(
            sample_device_id,
            expires_in_days=30
        )

        assert token is not None


class TestValidateAuthToken:
    """Test authentication token validation."""

    @pytest.mark.asyncio
    async def test_validate_valid_token_returns_true(
        self, repository, mock_session, sample_device_id
    ):
        """Test validates correct token."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # Found
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.validate_auth_token(
            sample_device_id,
            "test_token"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_invalid_token_returns_false(
        self, repository, mock_session, sample_device_id
    ):
        """Test rejects invalid token."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Not found
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.validate_auth_token(
            sample_device_id,
            "wrong_token"
        )

        assert result is False


class TestAuthenticateBySerial:
    """Test authentication by serial number."""

    @pytest.mark.asyncio
    async def test_authenticate_returns_none_for_invalid(
        self, repository, mock_session
    ):
        """Test returns None for invalid credentials."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.authenticate_by_serial(
            "SERIAL001",
            "bad_token"
        )

        assert result is None


class TestRevokeAuthToken:
    """Test token revocation."""

    @pytest.mark.asyncio
    async def test_revoke_auth_token(
        self, repository, mock_session, sample_device_id
    ):
        """Test revokes auth token."""
        mock_session.execute = AsyncMock()

        await repository.revoke_auth_token(sample_device_id)

        mock_session.execute.assert_called_once()


class TestMarkSynced:
    """Test sync marking."""

    @pytest.mark.asyncio
    async def test_mark_synced_returns_count(
        self, repository, mock_session
    ):
        """Test returns update count."""
        device_ids = [uuid4(), uuid4(), uuid4()]
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.mark_synced(device_ids)

        assert result == 3

    @pytest.mark.asyncio
    async def test_mark_synced_empty_list_returns_zero(
        self, repository, mock_session
    ):
        """Test empty list returns 0."""
        result = await repository.mark_synced([])

        assert result == 0
        mock_session.execute.assert_not_called()


class TestGetUnsyncedDevices:
    """Test getting unsynced devices."""

    @pytest.mark.asyncio
    async def test_get_unsynced_devices(
        self, repository, mock_session
    ):
        """Test gets unsynced devices."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_unsynced_devices()

        assert result == []


class TestGetConnectionStats:
    """Test connection statistics."""

    @pytest.mark.asyncio
    async def test_get_connection_stats(
        self, repository, mock_session
    ):
        """Test gets connection stats."""
        mock_rows = [
            MagicMock(connection_status="connected", count=10),
            MagicMock(connection_status="disconnected", count=5),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_connection_stats()

        assert result["connected"] == 10
        assert result["disconnected"] == 5


class TestGetDeviceTypeCounts:
    """Test device type counts."""

    @pytest.mark.asyncio
    async def test_get_device_type_counts(
        self, repository, mock_session
    ):
        """Test gets device type counts."""
        mock_rows = [
            MagicMock(device_type="inverter", count=5),
            MagicMock(device_type="meter", count=3),
            MagicMock(device_type="battery", count=2),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_device_type_counts()

        assert result["inverter"] == 5
        assert result["meter"] == 3
        assert result["battery"] == 2
