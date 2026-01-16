"""
Unit tests for DeviceService.

Tests device registration, connection management, and synchronization.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.application.services.device_service import DeviceService
from app.domain.entities.device import DeviceRegistry, DeviceSession
from app.domain.entities.telemetry import DeviceType, ConnectionStatus


@pytest.fixture
def mock_device_repo():
    """Create a mock device repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_serial_number = AsyncMock(return_value=None)
    repo.get_by_site = AsyncMock(return_value=[])
    repo.get_by_organization = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    repo.upsert = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.update_connection_status = AsyncMock()
    repo.get_connected_devices = AsyncMock(return_value=[])
    repo.get_devices_due_for_polling = AsyncMock(return_value=[])
    repo.update_poll_time = AsyncMock()
    repo.generate_auth_token = AsyncMock(return_value="test_token")
    repo.validate_auth_token = AsyncMock(return_value=True)
    repo.authenticate_by_serial = AsyncMock(return_value=None)
    repo.revoke_auth_token = AsyncMock()
    repo.mark_synced = AsyncMock(return_value=0)
    repo.get_unsynced_devices = AsyncMock(return_value=[])
    repo.get_connection_stats = AsyncMock(return_value={})
    repo.get_device_type_counts = AsyncMock(return_value={})
    return repo


@pytest.fixture
def mock_event_repo():
    """Create a mock event repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def service(mock_device_repo, mock_event_repo):
    """Create a DeviceService with mock repositories."""
    return DeviceService(mock_device_repo, mock_event_repo)


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
        device_id=sample_device_id,
        id=sample_device_id,
        site_id=sample_site_id,
        organization_id=sample_organization_id,
        device_type=DeviceType.INVERTER,
        serial_number="PD12K00001",
        connection_status=ConnectionStatus.DISCONNECTED,
        protocol="modbus_tcp",
        polling_interval_seconds=60,
        created_at=datetime.now(timezone.utc),
    )


class TestDeviceServiceInit:
    """Test service initialization."""

    def test_init_with_repos(self, mock_device_repo, mock_event_repo):
        """Test service initializes with repositories."""
        service = DeviceService(mock_device_repo, mock_event_repo)
        assert service._device_repo == mock_device_repo
        assert service._event_repo == mock_event_repo

    def test_init_without_event_repo(self, mock_device_repo):
        """Test service initializes without event repository."""
        service = DeviceService(mock_device_repo)
        assert service._event_repo is None


class TestRegisterDevice:
    """Test device registration."""

    @pytest.mark.asyncio
    async def test_register_device_creates_device(
        self, service, mock_device_repo, sample_device_id, sample_site_id, sample_organization_id
    ):
        """Test register creates device in repository."""
        mock_device_repo.create = AsyncMock(side_effect=lambda d: d)

        result = await service.register_device(
            device_id=sample_device_id,
            site_id=sample_site_id,
            organization_id=sample_organization_id,
            device_type=DeviceType.INVERTER,
            serial_number="PD12K00001",
        )

        mock_device_repo.create.assert_called_once()
        assert result.device_id == sample_device_id
        assert result.serial_number == "PD12K00001"


class TestSyncDeviceFromSystemA:
    """Test device synchronization from System A."""

    @pytest.mark.asyncio
    async def test_sync_device_upserts(
        self, service, mock_device_repo, sample_device_id, sample_site_id, sample_organization_id
    ):
        """Test sync upserts device."""
        mock_device_repo.upsert = AsyncMock(side_effect=lambda d: d)

        device_data = {
            "id": str(sample_device_id),
            "site_id": str(sample_site_id),
            "organization_id": str(sample_organization_id),
            "device_type": "inverter",
            "serial_number": "PD12K00001",
        }

        result = await service.sync_device_from_system_a(device_data)

        mock_device_repo.upsert.assert_called_once()
        assert result.serial_number == "PD12K00001"


class TestGetDevice:
    """Test getting device."""

    @pytest.mark.asyncio
    async def test_get_device_returns_device(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test returns device when found."""
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        result = await service.get_device(sample_device_id)

        assert result == sample_device

    @pytest.mark.asyncio
    async def test_get_device_returns_none(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test returns None when not found."""
        mock_device_repo.get_by_id = AsyncMock(return_value=None)

        result = await service.get_device(sample_device_id)

        assert result is None


class TestGetDeviceBySerial:
    """Test getting device by serial number."""

    @pytest.mark.asyncio
    async def test_get_device_by_serial_returns_device(
        self, service, mock_device_repo, sample_device
    ):
        """Test returns device when found."""
        mock_device_repo.get_by_serial_number = AsyncMock(return_value=sample_device)

        result = await service.get_device_by_serial("PD12K00001")

        assert result == sample_device


class TestGetSiteDevices:
    """Test getting devices for a site."""

    @pytest.mark.asyncio
    async def test_get_site_devices_returns_list(
        self, service, mock_device_repo, sample_site_id, sample_device
    ):
        """Test returns list of devices."""
        mock_device_repo.get_by_site = AsyncMock(return_value=[sample_device])

        result = await service.get_site_devices(sample_site_id)

        assert len(result) == 1
        assert result[0] == sample_device


class TestUpdateDevice:
    """Test device update."""

    @pytest.mark.asyncio
    async def test_update_device_returns_none_when_not_found(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test returns None when device not found."""
        mock_device_repo.get_by_id = AsyncMock(return_value=None)

        result = await service.update_device(sample_device_id, polling_interval_seconds=120)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_device_applies_updates(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test applies updates to device."""
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)
        mock_device_repo.update = AsyncMock(side_effect=lambda d: d)

        result = await service.update_device(
            sample_device_id,
            polling_interval_seconds=120
        )

        assert result.polling_interval_seconds == 120


class TestDeleteDevice:
    """Test device deletion."""

    @pytest.mark.asyncio
    async def test_delete_device_returns_true(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test delete returns True when successful."""
        mock_device_repo.delete = AsyncMock(return_value=True)

        result = await service.delete_device(sample_device_id)

        assert result is True


class TestHandleDeviceConnect:
    """Test device connection handling."""

    @pytest.mark.asyncio
    async def test_handle_connect_returns_none_for_unknown_device(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test returns None for unknown device."""
        mock_device_repo.get_by_id = AsyncMock(return_value=None)

        result = await service.handle_device_connect(
            device_id=sample_device_id,
            session_id="session_123",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_connect_creates_session(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test creates session for known device."""
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        result = await service.handle_device_connect(
            device_id=sample_device_id,
            session_id="session_123",
            client_address="192.168.1.100",
        )

        assert result is not None
        assert result.device_id == sample_device_id
        assert result.session_id == "session_123"
        mock_device_repo.update_connection_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_connect_logs_event(
        self, service, mock_device_repo, mock_event_repo, sample_device_id, sample_device
    ):
        """Test logs connection event."""
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        await service.handle_device_connect(
            device_id=sample_device_id,
            session_id="session_123",
        )

        mock_event_repo.create.assert_called_once()


class TestHandleDeviceDisconnect:
    """Test device disconnection handling."""

    @pytest.mark.asyncio
    async def test_handle_disconnect_updates_status(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test updates connection status."""
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        await service.handle_device_disconnect(sample_device_id, "Normal disconnect")

        mock_device_repo.update_connection_status.assert_called_once()


class TestHandleDeviceError:
    """Test device error handling."""

    @pytest.mark.asyncio
    async def test_handle_error_updates_status(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test updates status to error."""
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        await service.handle_device_error(
            sample_device_id,
            error_code="E001",
            error_message="Connection timeout"
        )

        mock_device_repo.update_connection_status.assert_called_once()


class TestGetConnectedDevices:
    """Test getting connected devices."""

    @pytest.mark.asyncio
    async def test_get_connected_devices(
        self, service, mock_device_repo, sample_device
    ):
        """Test returns connected devices."""
        mock_device_repo.get_connected_devices = AsyncMock(return_value=[sample_device])

        result = await service.get_connected_devices()

        assert len(result) == 1


class TestGetActiveSession:
    """Test getting active session."""

    def test_get_active_session_returns_none_when_not_connected(
        self, service, sample_device_id
    ):
        """Test returns None when no session."""
        result = service.get_active_session(sample_device_id)
        assert result is None


class TestCleanupStaleSessions:
    """Test stale session cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_sessions(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test cleans up stale sessions."""
        # First connect a device
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)
        await service.handle_device_connect(sample_device_id, "session_123")

        # Make session stale by setting old activity time
        service._active_sessions[sample_device_id].last_activity_at = (
            datetime.now(timezone.utc) - timedelta(minutes=10)
        )

        result = await service.cleanup_stale_sessions(timeout_seconds=300)

        assert result == 1


class TestPollingManagement:
    """Test polling management."""

    @pytest.mark.asyncio
    async def test_get_devices_for_polling(
        self, service, mock_device_repo, sample_device
    ):
        """Test gets devices due for polling."""
        mock_device_repo.get_devices_due_for_polling = AsyncMock(return_value=[sample_device])

        result = await service.get_devices_for_polling()

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_mark_device_polled(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test marks device as polled."""
        await service.mark_device_polled(sample_device_id)

        mock_device_repo.update_poll_time.assert_called_once()


class TestAuthentication:
    """Test device authentication."""

    @pytest.mark.asyncio
    async def test_generate_device_token(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test generates device token."""
        mock_device_repo.generate_auth_token = AsyncMock(return_value="new_token")

        result = await service.generate_device_token(sample_device_id)

        assert result == "new_token"

    @pytest.mark.asyncio
    async def test_validate_device_token(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test validates device token."""
        mock_device_repo.validate_auth_token = AsyncMock(return_value=True)

        result = await service.validate_device_token(sample_device_id, "token")

        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_device(
        self, service, mock_device_repo, sample_device
    ):
        """Test authenticates device by serial."""
        mock_device_repo.authenticate_by_serial = AsyncMock(return_value=sample_device)

        result = await service.authenticate_device("PD12K00001", "token")

        assert result == sample_device

    @pytest.mark.asyncio
    async def test_revoke_device_token(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test revokes device token."""
        await service.revoke_device_token(sample_device_id)

        mock_device_repo.revoke_auth_token.assert_called_once()


class TestSynchronization:
    """Test device synchronization."""

    @pytest.mark.asyncio
    async def test_mark_devices_synced(
        self, service, mock_device_repo
    ):
        """Test marks devices as synced."""
        device_ids = [uuid4(), uuid4()]
        mock_device_repo.mark_synced = AsyncMock(return_value=2)

        result = await service.mark_devices_synced(device_ids)

        assert result == 2

    @pytest.mark.asyncio
    async def test_get_unsynced_devices(
        self, service, mock_device_repo, sample_device
    ):
        """Test gets unsynced devices."""
        mock_device_repo.get_unsynced_devices = AsyncMock(return_value=[sample_device])

        result = await service.get_unsynced_devices()

        assert len(result) == 1


class TestStatistics:
    """Test device statistics."""

    @pytest.mark.asyncio
    async def test_get_connection_stats(
        self, service, mock_device_repo
    ):
        """Test gets connection statistics."""
        mock_device_repo.get_connection_stats = AsyncMock(
            return_value={"connected": 10, "disconnected": 5}
        )
        mock_device_repo.get_device_type_counts = AsyncMock(
            return_value={"inverter": 8, "meter": 7}
        )

        result = await service.get_connection_stats()

        assert result["by_status"]["connected"] == 10
        assert result["by_type"]["inverter"] == 8

    @pytest.mark.asyncio
    async def test_get_device_summary(
        self, service, mock_device_repo, sample_device_id, sample_device
    ):
        """Test gets device summary."""
        mock_device_repo.get_by_id = AsyncMock(return_value=sample_device)

        result = await service.get_device_summary(sample_device_id)

        assert result is not None
        assert result["serial_number"] == "PD12K00001"

    @pytest.mark.asyncio
    async def test_get_device_summary_returns_none(
        self, service, mock_device_repo, sample_device_id
    ):
        """Test returns None when device not found."""
        mock_device_repo.get_by_id = AsyncMock(return_value=None)

        result = await service.get_device_summary(sample_device_id)

        assert result is None
