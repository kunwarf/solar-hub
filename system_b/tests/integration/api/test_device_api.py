"""
Integration tests for Device API endpoints.

Tests device registration, status, and management endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import devices
from app.api.v1.devices import router


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


@pytest.fixture
def sample_device_data(sample_device_id, sample_site_id):
    """Create sample device data."""
    return {
        "id": sample_device_id,
        "site_id": sample_site_id,
        "device_type": "inverter",
        "serial_number": "PD12K00001",
        "protocol_id": "powdrive",
        "firmware_version": "1.0.0",
        "hardware_version": "1.0",
        "connection_status": "disconnected",
        "last_seen": None,
        "capabilities": ["modbus_tcp"],
        "device_metadata": {},
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
    }


class TestRegisterDevice:
    """Test device registration endpoint."""

    def test_register_device_success(
        self, client, sample_site_id, sample_device_data
    ):
        """Test successful device registration."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_device = MagicMock(**sample_device_data)
            mock_service = MagicMock()
            mock_service.register_device = AsyncMock(return_value=mock_device)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/devices/register",
                json={
                    "site_id": str(sample_site_id),
                    "device_type": "inverter",
                    "serial_number": "PD12K00001",
                    "protocol_id": "powdrive",
                    "firmware_version": "1.0.0",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["serial_number"] == "PD12K00001"
            assert data["device_type"] == "inverter"

    def test_register_device_validation_error(
        self, client, sample_site_id
    ):
        """Test registration with invalid data."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.register_device = AsyncMock(
                side_effect=ValueError("Serial number already exists")
            )
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/devices/register",
                json={
                    "site_id": str(sample_site_id),
                    "device_type": "inverter",
                    "serial_number": "PD12K00001",
                },
            )

            assert response.status_code == 400


class TestSyncDevice:
    """Test device sync endpoint."""

    def test_sync_device(
        self, client, sample_site_id, sample_device_data
    ):
        """Test device sync."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_device = MagicMock(**sample_device_data)
            mock_service = MagicMock()
            mock_service.sync_device = AsyncMock(return_value=mock_device)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/devices/sync",
                json={
                    "site_id": str(sample_site_id),
                    "device_type": "inverter",
                    "serial_number": "PD12K00001",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["serial_number"] == "PD12K00001"


class TestGetDevice:
    """Test get device endpoint."""

    def test_get_device_found(
        self, client, sample_device_id, sample_device_data
    ):
        """Test getting existing device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_device = MagicMock(**sample_device_data)
            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_device)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/devices/{sample_device_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(sample_device_id)

    def test_get_device_not_found(
        self, client, sample_device_id
    ):
        """Test getting non-existent device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/devices/{sample_device_id}",
            )

            assert response.status_code == 404


class TestUpdateDevice:
    """Test update device endpoint."""

    def test_update_device_success(
        self, client, sample_device_id, sample_device_data
    ):
        """Test updating device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_device = MagicMock(**sample_device_data)
            mock_device.firmware_version = "2.0.0"

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_device)
            mock_repo.update = AsyncMock(return_value=mock_device)
            MockRepo.return_value = mock_repo

            response = client.patch(
                f"/api/v1/devices/{sample_device_id}",
                json={"firmware_version": "2.0.0"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["firmware_version"] == "2.0.0"

    def test_update_device_not_found(
        self, client, sample_device_id
    ):
        """Test updating non-existent device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.patch(
                f"/api/v1/devices/{sample_device_id}",
                json={"firmware_version": "2.0.0"},
            )

            assert response.status_code == 404


class TestGetSiteDevices:
    """Test get site devices endpoint."""

    def test_get_site_devices(
        self, client, sample_site_id, sample_device_data
    ):
        """Test getting devices for a site."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_device = MagicMock(**sample_device_data)

            mock_repo = MagicMock()
            mock_repo.get_by_site = AsyncMock(return_value=[mock_device])
            mock_repo.count_by_site = AsyncMock(return_value=1)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/devices/site/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["devices"]) == 1


class TestDeviceConnect:
    """Test device connect endpoint."""

    def test_device_connect(
        self, client, sample_device_id
    ):
        """Test handling device connection."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.handle_device_connect = AsyncMock(return_value={
                "session_id": "session_123",
                "connected_at": datetime.now(timezone.utc),
            })
            MockService.return_value = mock_service

            response = client.post(
                f"/api/v1/devices/{sample_device_id}/connect",
                params={"ip_address": "192.168.1.100"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["device_id"] == str(sample_device_id)


class TestDeviceDisconnect:
    """Test device disconnect endpoint."""

    def test_device_disconnect(
        self, client, sample_device_id
    ):
        """Test handling device disconnection."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.handle_device_disconnect = AsyncMock()
            MockService.return_value = mock_service

            response = client.post(
                f"/api/v1/devices/{sample_device_id}/disconnect",
                params={"reason": "Normal disconnect"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestDeviceHeartbeat:
    """Test device heartbeat endpoint."""

    def test_device_heartbeat(
        self, client, sample_device_id
    ):
        """Test updating device heartbeat."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.update_last_seen = AsyncMock()
            MockRepo.return_value = mock_repo

            response = client.post(
                f"/api/v1/devices/{sample_device_id}/heartbeat",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True


class TestGetConnectionStats:
    """Test connection stats endpoint."""

    def test_get_connection_stats(self, client):
        """Test getting connection statistics."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.get_connection_stats = AsyncMock(return_value={
                "total": 100,
                "online": 75,
                "offline": 20,
                "error": 5,
            })
            MockRepo.return_value = mock_repo

            response = client.get(
                "/api/v1/devices/stats/connection",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_devices"] == 100
            assert data["online"] == 75


class TestGetDevicesForPolling:
    """Test polling list endpoint."""

    def test_get_devices_for_polling(
        self, client, sample_device_data
    ):
        """Test getting devices for polling."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_device = MagicMock(**sample_device_data)
            mock_service = MagicMock()
            mock_service.get_devices_for_polling = AsyncMock(return_value=[mock_device])
            MockService.return_value = mock_service

            response = client.get(
                "/api/v1/devices/polling/list",
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1


class TestAuthenticateByToken:
    """Test token authentication endpoint."""

    def test_authenticate_by_token_success(
        self, client, sample_device_id
    ):
        """Test successful token authentication."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceAuthService") as MockAuthService:

            mock_service = MagicMock()
            mock_service.authenticate_by_token = AsyncMock(return_value={
                "authenticated": True,
                "session_token": "session_abc123",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            })
            MockAuthService.return_value = mock_service

            response = client.post(
                "/api/v1/devices/auth/token",
                json={
                    "device_id": str(sample_device_id),
                    "token": "valid_token",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True

    def test_authenticate_by_token_failure(
        self, client, sample_device_id
    ):
        """Test failed token authentication."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceAuthService") as MockAuthService:

            mock_service = MagicMock()
            mock_service.authenticate_by_token = AsyncMock(return_value={
                "authenticated": False,
                "reason": "Invalid token",
            })
            MockAuthService.return_value = mock_service

            response = client.post(
                "/api/v1/devices/auth/token",
                json={
                    "device_id": str(sample_device_id),
                    "token": "invalid_token",
                },
            )

            assert response.status_code == 401


class TestGenerateDeviceToken:
    """Test token generation endpoint."""

    def test_generate_device_token(
        self, client, sample_device_id, sample_device_data
    ):
        """Test generating device token."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_device = MagicMock(**sample_device_data)

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_device)
            mock_repo.generate_auth_token = AsyncMock(return_value="new_token_123")
            MockRepo.return_value = mock_repo

            response = client.post(
                f"/api/v1/devices/{sample_device_id}/generate-token",
                params={"expires_in_days": 365},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["token"] == "new_token_123"
            assert data["expires_in_days"] == 365

    def test_generate_device_token_not_found(
        self, client, sample_device_id
    ):
        """Test generating token for non-existent device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.post(
                f"/api/v1/devices/{sample_device_id}/generate-token",
            )

            assert response.status_code == 404


class TestDeviceSelfRegister:
    """Test device self-registration endpoint (ESP flow)."""

    def test_self_register_new_device(self, client):
        """Test new device self-registration."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_device = MagicMock()
            mock_device.device_id = uuid4()
            mock_device.serial_number = "ESP-INV-001"
            mock_device.polling_interval_seconds = 30
            mock_device.reconnect_count = 1
            mock_device.is_claimed = MagicMock(return_value=False)

            mock_service = MagicMock()
            mock_service.register_orphan_device = AsyncMock(return_value=mock_device)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/devices/self-register",
                json={
                    "serial_number": "ESP-INV-001",
                    "device_type": "inverter",
                    "firmware_version": "1.0.0",
                    "manufacturer": "Test Mfg",
                    "protocol": "modbus_tcp",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["device_id"] is not None
            assert data["is_claimed"] is False
            assert data["polling_interval_ms"] == 30000

    def test_self_register_reconnect(self, client):
        """Test device reconnection (already registered)."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_device = MagicMock()
            mock_device.device_id = uuid4()
            mock_device.serial_number = "ESP-INV-001"
            mock_device.polling_interval_seconds = 30
            mock_device.reconnect_count = 5  # Multiple reconnects
            mock_device.is_claimed = MagicMock(return_value=True)

            mock_service = MagicMock()
            mock_service.register_orphan_device = AsyncMock(return_value=mock_device)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/devices/self-register",
                json={
                    "serial_number": "ESP-INV-001",
                    "device_type": "inverter",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "reconnected" in data["message"].lower()
            assert data["is_claimed"] is True

    def test_self_register_invalid_device_type(self, client):
        """Test self-registration with invalid device type."""
        response = client.post(
            "/api/v1/devices/self-register",
            json={
                "serial_number": "ESP-INV-001",
                "device_type": "invalid_type",
            },
        )

        assert response.status_code == 400
        assert "invalid device_type" in response.json()["detail"].lower()


class TestDeviceClaim:
    """Test device claim endpoint."""

    def test_claim_orphan_device_success(self, client, sample_device_id):
        """Test claiming an orphan device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            owner_id = uuid4()
            site_id = uuid4()
            org_id = uuid4()

            mock_device = MagicMock()
            mock_device.device_id = sample_device_id
            mock_device.serial_number = "ESP-INV-001"
            mock_device.device_type = MagicMock(value="inverter")
            mock_device.manufacturer = "Test Mfg"
            mock_device.model = "TEST-001"
            mock_device.firmware_version = "1.0.0"
            mock_device.protocol = "modbus_tcp"
            mock_device.status = "claimed"
            mock_device.owner_id = owner_id
            mock_device.site_id = site_id
            mock_device.organization_id = org_id
            mock_device.connection_status = MagicMock(value="disconnected")
            mock_device.last_connected_at = None
            mock_device.last_telemetry_at = None
            mock_device.capabilities = []
            mock_device.polling_interval_seconds = 30
            mock_device.created_at = datetime.now(timezone.utc)

            mock_service = MagicMock()
            mock_service.claim_device = AsyncMock(return_value=mock_device)
            MockService.return_value = mock_service

            response = client.put(
                f"/api/v1/devices/{sample_device_id}/claim",
                json={
                    "owner_id": str(owner_id),
                    "site_id": str(site_id),
                    "organization_id": str(org_id),
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["device"]["status"] == "claimed"
            assert data["device"]["owner_id"] == str(owner_id)

    def test_claim_already_claimed_device(self, client, sample_device_id):
        """Test claiming an already claimed device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.claim_device = AsyncMock(
                side_effect=ValueError("Device is already claimed")
            )
            MockService.return_value = mock_service

            response = client.put(
                f"/api/v1/devices/{sample_device_id}/claim",
                json={
                    "owner_id": str(uuid4()),
                    "site_id": str(uuid4()),
                    "organization_id": str(uuid4()),
                },
            )

            assert response.status_code == 409

    def test_claim_nonexistent_device(self, client, sample_device_id):
        """Test claiming a non-existent device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.claim_device = AsyncMock(return_value=None)
            MockService.return_value = mock_service

            response = client.put(
                f"/api/v1/devices/{sample_device_id}/claim",
                json={
                    "owner_id": str(uuid4()),
                    "site_id": str(uuid4()),
                    "organization_id": str(uuid4()),
                },
            )

            assert response.status_code == 404


class TestDeviceRelease:
    """Test device release endpoint."""

    def test_release_claimed_device(self, client, sample_device_id):
        """Test releasing a claimed device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_device = MagicMock()
            mock_device.device_id = sample_device_id
            mock_device.serial_number = "ESP-INV-001"
            mock_device.device_type = MagicMock(value="inverter")
            mock_device.manufacturer = "Test Mfg"
            mock_device.model = "TEST-001"
            mock_device.firmware_version = "1.0.0"
            mock_device.protocol = "modbus_tcp"
            mock_device.status = "orphan"
            mock_device.owner_id = None
            mock_device.site_id = None
            mock_device.organization_id = None
            mock_device.connection_status = MagicMock(value="disconnected")
            mock_device.last_connected_at = None
            mock_device.last_telemetry_at = None
            mock_device.capabilities = []
            mock_device.polling_interval_seconds = 30
            mock_device.created_at = datetime.now(timezone.utc)

            mock_service = MagicMock()
            mock_service.release_device = AsyncMock(return_value=mock_device)
            MockService.return_value = mock_service

            response = client.put(
                f"/api/v1/devices/{sample_device_id}/release",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["device"]["status"] == "orphan"
            assert data["device"]["owner_id"] is None

    def test_release_nonexistent_device(self, client, sample_device_id):
        """Test releasing a non-existent device."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.release_device = AsyncMock(return_value=None)
            MockService.return_value = mock_service

            response = client.put(
                f"/api/v1/devices/{sample_device_id}/release",
            )

            assert response.status_code == 404


class TestGetOrphanDevices:
    """Test get orphan devices endpoint."""

    def test_get_orphan_devices(self, client):
        """Test getting all orphan devices."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_device = MagicMock()
            mock_device.device_id = uuid4()
            mock_device.serial_number = "ESP-INV-001"
            mock_device.device_type = MagicMock(value="inverter")
            mock_device.manufacturer = "Test Mfg"
            mock_device.model = "TEST-001"
            mock_device.firmware_version = "1.0.0"
            mock_device.protocol = "modbus_tcp"
            mock_device.status = "orphan"
            mock_device.owner_id = None
            mock_device.site_id = None
            mock_device.organization_id = None
            mock_device.connection_status = MagicMock(value="disconnected")
            mock_device.last_connected_at = None
            mock_device.last_telemetry_at = None
            mock_device.capabilities = []
            mock_device.polling_interval_seconds = 30
            mock_device.created_at = datetime.now(timezone.utc)

            mock_service = MagicMock()
            mock_service.get_orphan_devices = AsyncMock(return_value=[mock_device])
            MockService.return_value = mock_service

            response = client.get("/api/v1/devices/orphan")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["status"] == "orphan"

    def test_get_orphan_devices_empty(self, client):
        """Test getting orphan devices when none exist."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo, \
             patch("app.api.v1.devices.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.get_orphan_devices = AsyncMock(return_value=[])
            MockService.return_value = mock_service

            response = client.get("/api/v1/devices/orphan")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0


class TestGetDeviceBySerial:
    """Test get device by serial number endpoint."""

    def test_get_device_by_serial_found(self, client):
        """Test getting device by serial number."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_device = MagicMock()
            mock_device.device_id = uuid4()
            mock_device.serial_number = "ESP-INV-001"
            mock_device.device_type = MagicMock(value="inverter")
            mock_device.manufacturer = "Test Mfg"
            mock_device.model = "TEST-001"
            mock_device.firmware_version = "1.0.0"
            mock_device.protocol = "modbus_tcp"
            mock_device.status = "orphan"
            mock_device.owner_id = None
            mock_device.site_id = None
            mock_device.organization_id = None
            mock_device.connection_status = MagicMock(value="disconnected")
            mock_device.last_connected_at = None
            mock_device.last_telemetry_at = None
            mock_device.capabilities = []
            mock_device.polling_interval_seconds = 30
            mock_device.created_at = datetime.now(timezone.utc)

            mock_repo = MagicMock()
            mock_repo.get_by_serial_number = AsyncMock(return_value=mock_device)
            MockRepo.return_value = mock_repo

            response = client.get("/api/v1/devices/serial/ESP-INV-001")

            assert response.status_code == 200
            data = response.json()
            assert data["serial_number"] == "ESP-INV-001"

    def test_get_device_by_serial_not_found(self, client):
        """Test getting non-existent device by serial."""
        with patch("app.api.v1.devices.DeviceRegistryRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.get_by_serial_number = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.get("/api/v1/devices/serial/NONEXISTENT")

            assert response.status_code == 404
