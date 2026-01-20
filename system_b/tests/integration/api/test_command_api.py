"""
Integration tests for Command API endpoints.

Tests command creation, execution, and lifecycle endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import commands
from app.api.v1.commands import router


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
def sample_command_id():
    return uuid4()


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


@pytest.fixture
def sample_command_data(sample_command_id, sample_device_id, sample_site_id):
    """Create sample command data."""
    return {
        "id": sample_command_id,
        "device_id": sample_device_id,
        "site_id": sample_site_id,
        "command_type": "set_power_mode",
        "command_params": {"mode": "self_consumption"},
        "status": "pending",
        "scheduled_at": None,
        "sent_at": None,
        "acknowledged_at": None,
        "completed_at": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "result": None,
        "error_message": None,
        "retry_count": 0,
        "priority": 1,
        "created_at": datetime.now(timezone.utc),
    }


class TestCreateCommand:
    """Test command creation endpoint."""

    def test_create_command_success(
        self, client, sample_device_id, sample_site_id, sample_command_data
    ):
        """Test successful command creation."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo, \
             patch("app.api.v1.commands.EventRepository") as MockEventRepo, \
             patch("app.api.v1.commands.CommandService") as MockService:

            mock_command = MagicMock(**sample_command_data)
            mock_service = MagicMock()
            mock_service.create_command = AsyncMock(return_value=mock_command)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/commands/",
                json={
                    "device_id": str(sample_device_id),
                    "site_id": str(sample_site_id),
                    "command_type": "set_power_mode",
                    "command_params": {"mode": "self_consumption"},
                    "priority": 1,
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["command_type"] == "set_power_mode"
            assert data["status"] == "pending"

    def test_create_command_with_schedule(
        self, client, sample_device_id, sample_site_id, sample_command_data
    ):
        """Test creating scheduled command."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo, \
             patch("app.api.v1.commands.EventRepository") as MockEventRepo, \
             patch("app.api.v1.commands.CommandService") as MockService:

            scheduled_time = datetime.now(timezone.utc) + timedelta(hours=1)
            sample_command_data["scheduled_at"] = scheduled_time
            mock_command = MagicMock(**sample_command_data)

            mock_service = MagicMock()
            mock_service.create_command = AsyncMock(return_value=mock_command)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/commands/",
                json={
                    "device_id": str(sample_device_id),
                    "site_id": str(sample_site_id),
                    "command_type": "set_power_mode",
                    "command_params": {"mode": "self_consumption"},
                    "scheduled_at": scheduled_time.isoformat(),
                },
            )

            assert response.status_code == 201

    def test_create_command_validation_error(
        self, client, sample_device_id, sample_site_id
    ):
        """Test creating command with invalid data."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo, \
             patch("app.api.v1.commands.EventRepository") as MockEventRepo, \
             patch("app.api.v1.commands.CommandService") as MockService:

            mock_service = MagicMock()
            mock_service.create_command = AsyncMock(
                side_effect=ValueError("Invalid command type")
            )
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/commands/",
                json={
                    "device_id": str(sample_device_id),
                    "site_id": str(sample_site_id),
                    "command_type": "invalid_type",
                },
            )

            assert response.status_code == 400


class TestGetCommand:
    """Test get command endpoint."""

    def test_get_command_found(
        self, client, sample_command_id, sample_command_data
    ):
        """Test getting existing command."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            mock_command = MagicMock(**sample_command_data)

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_command)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/commands/{sample_command_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == str(sample_command_id)

    def test_get_command_not_found(
        self, client, sample_command_id
    ):
        """Test getting non-existent command."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/commands/{sample_command_id}",
            )

            assert response.status_code == 404


class TestGetDeviceCommands:
    """Test get device commands endpoint."""

    def test_get_device_commands(
        self, client, sample_device_id, sample_command_data
    ):
        """Test getting commands for a device."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            mock_command = MagicMock(**sample_command_data)

            mock_repo = MagicMock()
            mock_repo.get_by_device = AsyncMock(return_value=[mock_command])
            mock_repo.count_by_device = AsyncMock(return_value=1)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/commands/device/{sample_device_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["commands"]) == 1

    def test_get_device_commands_with_status_filter(
        self, client, sample_device_id
    ):
        """Test filtering commands by status."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.get_by_device = AsyncMock(return_value=[])
            mock_repo.count_by_device = AsyncMock(return_value=0)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/commands/device/{sample_device_id}",
                params={"status": "pending"},
            )

            assert response.status_code == 200


class TestGetSiteCommands:
    """Test get site commands endpoint."""

    def test_get_site_commands(
        self, client, sample_site_id, sample_command_data
    ):
        """Test getting commands for a site."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            mock_command = MagicMock(**sample_command_data)

            mock_repo = MagicMock()
            mock_repo.get_by_site = AsyncMock(return_value=[mock_command])
            mock_repo.count_by_site = AsyncMock(return_value=1)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/commands/site/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1


class TestClaimPendingCommand:
    """Test claim pending command endpoint."""

    def test_claim_pending_command_found(
        self, client, sample_device_id, sample_command_data
    ):
        """Test claiming pending command."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            sample_command_data["status"] = "sent"
            mock_command = MagicMock(**sample_command_data)

            mock_repo = MagicMock()
            mock_repo.claim_pending_command = AsyncMock(return_value=mock_command)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/commands/pending/{sample_device_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "sent"

    def test_claim_pending_command_none(
        self, client, sample_device_id
    ):
        """Test claiming when no pending commands."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.claim_pending_command = AsyncMock(return_value=None)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/commands/pending/{sample_device_id}",
            )

            assert response.status_code == 200
            assert response.json() is None


class TestAcknowledgeCommand:
    """Test acknowledge command endpoint."""

    def test_acknowledge_command(
        self, client, sample_command_id, sample_command_data
    ):
        """Test acknowledging a command."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo, \
             patch("app.api.v1.commands.EventRepository") as MockEventRepo, \
             patch("app.api.v1.commands.CommandService") as MockService:

            sample_command_data["status"] = "acknowledged"
            sample_command_data["acknowledged_at"] = datetime.now(timezone.utc)
            mock_command = MagicMock(**sample_command_data)

            mock_service = MagicMock()
            mock_service.acknowledge_command = AsyncMock(return_value=mock_command)
            MockService.return_value = mock_service

            response = client.post(
                f"/api/v1/commands/{sample_command_id}/acknowledge",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "acknowledged"


class TestReportCommandResult:
    """Test report command result endpoint."""

    def test_report_success_result(
        self, client, sample_command_id, sample_command_data
    ):
        """Test reporting successful result."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo, \
             patch("app.api.v1.commands.EventRepository") as MockEventRepo, \
             patch("app.api.v1.commands.CommandService") as MockService:

            sample_command_data["status"] = "completed"
            sample_command_data["result"] = {"value": 100}
            mock_command = MagicMock(**sample_command_data)

            mock_service = MagicMock()
            mock_service.complete_command = AsyncMock(return_value=mock_command)
            MockService.return_value = mock_service

            response = client.post(
                f"/api/v1/commands/{sample_command_id}/result",
                json={
                    "success": True,
                    "data": {"value": 100},
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"

    def test_report_failure_result(
        self, client, sample_command_id, sample_command_data
    ):
        """Test reporting failed result."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo, \
             patch("app.api.v1.commands.EventRepository") as MockEventRepo, \
             patch("app.api.v1.commands.CommandService") as MockService:

            sample_command_data["status"] = "failed"
            sample_command_data["error_message"] = "Device rejected command"
            mock_command = MagicMock(**sample_command_data)

            mock_service = MagicMock()
            mock_service.fail_command = AsyncMock(return_value=mock_command)
            MockService.return_value = mock_service

            response = client.post(
                f"/api/v1/commands/{sample_command_id}/result",
                json={
                    "success": False,
                    "error_message": "Device rejected command",
                    "error_code": "DEVICE_ERROR",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"


class TestRetryCommand:
    """Test retry command endpoint."""

    def test_retry_command(
        self, client, sample_command_id, sample_command_data
    ):
        """Test retrying a failed command."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            # First call returns failed command
            failed_command = MagicMock(**sample_command_data)
            failed_command.status = "failed"

            # After retry, returns pending command
            sample_command_data["status"] = "pending"
            sample_command_data["retry_count"] = 1
            retried_command = MagicMock(**sample_command_data)

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=failed_command)
            mock_repo.retry_command = AsyncMock(return_value=retried_command)
            MockRepo.return_value = mock_repo

            response = client.post(
                f"/api/v1/commands/{sample_command_id}/retry",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pending"
            assert data["retry_count"] == 1

    def test_retry_command_invalid_status(
        self, client, sample_command_id, sample_command_data
    ):
        """Test retrying command with invalid status."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            sample_command_data["status"] = "completed"
            mock_command = MagicMock(**sample_command_data)

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_command)
            MockRepo.return_value = mock_repo

            response = client.post(
                f"/api/v1/commands/{sample_command_id}/retry",
            )

            assert response.status_code == 400


class TestCancelCommand:
    """Test cancel command endpoint."""

    def test_cancel_command(
        self, client, sample_command_id, sample_command_data
    ):
        """Test cancelling a pending command."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo, \
             patch("app.api.v1.commands.EventRepository") as MockEventRepo, \
             patch("app.api.v1.commands.CommandService") as MockService:

            # First call returns pending command
            pending_command = MagicMock(**sample_command_data)
            pending_command.status = "pending"

            # After cancel, returns cancelled command
            sample_command_data["status"] = "cancelled"
            cancelled_command = MagicMock(**sample_command_data)

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=pending_command)
            MockRepo.return_value = mock_repo

            mock_service = MagicMock()
            mock_service.cancel_command = AsyncMock(return_value=cancelled_command)
            MockService.return_value = mock_service

            response = client.post(
                f"/api/v1/commands/{sample_command_id}/cancel",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cancelled"

    def test_cancel_command_invalid_status(
        self, client, sample_command_id, sample_command_data
    ):
        """Test cancelling command with invalid status."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo, \
             patch("app.api.v1.commands.EventRepository") as MockEventRepo, \
             patch("app.api.v1.commands.CommandService") as MockService:

            sample_command_data["status"] = "completed"
            mock_command = MagicMock(**sample_command_data)

            mock_repo = MagicMock()
            mock_repo.get_by_id = AsyncMock(return_value=mock_command)
            MockRepo.return_value = mock_repo

            response = client.post(
                f"/api/v1/commands/{sample_command_id}/cancel",
            )

            assert response.status_code == 400


class TestGetCommandStats:
    """Test command stats endpoint."""

    def test_get_command_stats(self, client):
        """Test getting command statistics."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.get_stats = AsyncMock(return_value={
                "by_status": {"pending": 5, "completed": 100, "failed": 10},
                "total": 115,
                "pending": 5,
                "success_rate": 90.9,
            })
            MockRepo.return_value = mock_repo

            response = client.get(
                "/api/v1/commands/stats/summary",
                params={"hours": 24},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_commands"] == 115


class TestExpireStaleCommands:
    """Test expire stale commands endpoint."""

    def test_expire_stale_commands(self, client):
        """Test expiring stale commands."""
        with patch("app.api.v1.commands.CommandRepository") as MockRepo:

            mock_repo = MagicMock()
            mock_repo.expire_stale_commands = AsyncMock(return_value=5)
            MockRepo.return_value = mock_repo

            response = client.post(
                "/api/v1/commands/expire-stale",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["expired_count"] == 5
