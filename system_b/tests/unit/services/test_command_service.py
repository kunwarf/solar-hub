"""
Unit tests for CommandService.

Tests command creation, execution, and lifecycle management.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.application.services.command_service import CommandService
from app.domain.entities.command import DeviceCommand, CommandStatus, CommandResult


@pytest.fixture
def mock_command_repo():
    """Create a mock command repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_device_queue = AsyncMock(return_value=[])
    repo.get_site_commands = AsyncMock(return_value=[])
    repo.get_pending_commands = AsyncMock(return_value=[])
    repo.get_command_history = AsyncMock(return_value=[])
    repo.claim_pending_command = AsyncMock(return_value=None)
    repo.mark_sent = AsyncMock()
    repo.mark_acknowledged = AsyncMock()
    repo.mark_completed = AsyncMock()
    repo.mark_failed = AsyncMock()
    repo.mark_timeout = AsyncMock()
    repo.cancel_command = AsyncMock(return_value=True)
    repo.retry_command = AsyncMock(return_value=None)
    repo.get_retryable_commands = AsyncMock(return_value=[])
    repo.expire_old_commands = AsyncMock(return_value=0)
    repo.cleanup_old_commands = AsyncMock(return_value=0)
    repo.get_command_stats = AsyncMock(return_value={})
    repo.get_pending_count = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_event_repo():
    """Create a mock event repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def service(mock_command_repo, mock_event_repo):
    """Create a CommandService with mock repositories."""
    return CommandService(mock_command_repo, mock_event_repo)


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


@pytest.fixture
def sample_command_id():
    return uuid4()


@pytest.fixture
def sample_command(sample_command_id, sample_device_id, sample_site_id):
    """Create a sample device command."""
    return DeviceCommand(
        id=sample_command_id,
        device_id=sample_device_id,
        site_id=sample_site_id,
        command_type="set_power_mode",
        command_params={"mode": "self_consumption"},
        status=CommandStatus.PENDING,
        priority=1,
        max_retries=3,
        created_at=datetime.now(timezone.utc),
    )


class TestCommandServiceInit:
    """Test service initialization."""

    def test_init_with_repos(self, mock_command_repo, mock_event_repo):
        """Test service initializes with repositories."""
        service = CommandService(mock_command_repo, mock_event_repo)
        assert service._command_repo == mock_command_repo
        assert service._event_repo == mock_event_repo

    def test_init_without_event_repo(self, mock_command_repo):
        """Test service initializes without event repository."""
        service = CommandService(mock_command_repo)
        assert service._event_repo is None


class TestCreateCommand:
    """Test command creation."""

    @pytest.mark.asyncio
    async def test_create_command_returns_command(
        self, service, mock_command_repo, sample_device_id, sample_site_id
    ):
        """Test create returns created command."""
        mock_command_repo.create = AsyncMock(side_effect=lambda c: c)

        result = await service.create_command(
            device_id=sample_device_id,
            site_id=sample_site_id,
            command_type="set_power_mode",
            command_params={"mode": "self_consumption"},
        )

        assert result.device_id == sample_device_id
        assert result.command_type == "set_power_mode"
        mock_command_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_command_sets_expiry(
        self, service, mock_command_repo, sample_device_id, sample_site_id
    ):
        """Test create sets expiry time."""
        mock_command_repo.create = AsyncMock(side_effect=lambda c: c)

        result = await service.create_command(
            device_id=sample_device_id,
            site_id=sample_site_id,
            command_type="test",
            expires_in_minutes=30,
        )

        assert result.expires_at is not None
        # Expiry should be approximately 30 minutes from now
        expected = datetime.now(timezone.utc) + timedelta(minutes=30)
        diff = abs((result.expires_at - expected).total_seconds())
        assert diff < 5  # Within 5 seconds


class TestCreateImmediateCommand:
    """Test immediate command creation."""

    @pytest.mark.asyncio
    async def test_create_immediate_without_waiting(
        self, service, mock_command_repo, sample_device_id, sample_site_id
    ):
        """Test create immediate without waiting."""
        mock_command_repo.create = AsyncMock(side_effect=lambda c: c)

        result = await service.create_immediate_command(
            device_id=sample_device_id,
            site_id=sample_site_id,
            command_type="test",
            wait_for_completion=False,
        )

        assert result.priority == 1  # High priority


class TestGetCommand:
    """Test command retrieval."""

    @pytest.mark.asyncio
    async def test_get_command_returns_command(
        self, service, mock_command_repo, sample_command_id, sample_command
    ):
        """Test returns command when found."""
        mock_command_repo.get_by_id = AsyncMock(return_value=sample_command)

        result = await service.get_command(sample_command_id)

        assert result == sample_command

    @pytest.mark.asyncio
    async def test_get_command_returns_none(
        self, service, mock_command_repo, sample_command_id
    ):
        """Test returns None when not found."""
        mock_command_repo.get_by_id = AsyncMock(return_value=None)

        result = await service.get_command(sample_command_id)

        assert result is None


class TestGetDeviceCommands:
    """Test getting device commands."""

    @pytest.mark.asyncio
    async def test_get_device_commands(
        self, service, mock_command_repo, sample_device_id, sample_command
    ):
        """Test returns device commands."""
        mock_command_repo.get_device_queue = AsyncMock(return_value=[sample_command])

        result = await service.get_device_commands(sample_device_id)

        assert len(result) == 1


class TestGetSiteCommands:
    """Test getting site commands."""

    @pytest.mark.asyncio
    async def test_get_site_commands(
        self, service, mock_command_repo, sample_site_id, sample_command
    ):
        """Test returns site commands."""
        mock_command_repo.get_site_commands = AsyncMock(return_value=[sample_command])

        result = await service.get_site_commands(sample_site_id)

        assert len(result) == 1


class TestGetPendingCommands:
    """Test getting pending commands."""

    @pytest.mark.asyncio
    async def test_get_pending_commands(
        self, service, mock_command_repo, sample_command
    ):
        """Test returns pending commands."""
        mock_command_repo.get_pending_commands = AsyncMock(return_value=[sample_command])

        result = await service.get_pending_commands()

        assert len(result) == 1


class TestRegisterExecutor:
    """Test executor registration."""

    def test_register_executor(self, service):
        """Test registers executor."""
        async def test_executor(cmd):
            return CommandResult(
                command_id=cmd.id,
                device_id=cmd.device_id,
                success=True,
            )

        service.register_executor("test_command", test_executor)

        assert "test_command" in service._executors


class TestClaimAndExecute:
    """Test claim and execute."""

    @pytest.mark.asyncio
    async def test_claim_and_execute_returns_none_when_no_commands(
        self, service, mock_command_repo, sample_device_id
    ):
        """Test returns None when no pending commands."""
        mock_command_repo.claim_pending_command = AsyncMock(return_value=None)

        result = await service.claim_and_execute(sample_device_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_claim_and_execute_runs_executor(
        self, service, mock_command_repo, sample_device_id, sample_command
    ):
        """Test runs executor when command claimed."""
        mock_command_repo.claim_pending_command = AsyncMock(return_value=sample_command)

        async def test_executor(cmd):
            return CommandResult(
                command_id=cmd.id,
                device_id=cmd.device_id,
                success=True,
                data={"result": "success"},
            )

        service.register_executor("set_power_mode", test_executor)

        result = await service.claim_and_execute(sample_device_id)

        assert result is not None
        assert result.success is True


class TestExecuteCommand:
    """Test command execution."""

    @pytest.mark.asyncio
    async def test_execute_command_no_executor_fails(
        self, service, mock_command_repo, sample_command
    ):
        """Test fails when no executor registered."""
        # Don't register executor
        result = await service.execute_command(sample_command)

        assert result.success is False
        assert result.error_code == "NO_EXECUTOR"
        mock_command_repo.mark_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_success(
        self, service, mock_command_repo, sample_command
    ):
        """Test successful execution."""
        async def test_executor(cmd):
            return CommandResult(
                command_id=cmd.id,
                device_id=cmd.device_id,
                success=True,
                data={"value": 100},
            )

        service.register_executor("set_power_mode", test_executor)

        result = await service.execute_command(sample_command)

        assert result.success is True
        mock_command_repo.mark_completed.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_failure(
        self, service, mock_command_repo, sample_command
    ):
        """Test failed execution."""
        async def test_executor(cmd):
            return CommandResult(
                command_id=cmd.id,
                device_id=cmd.device_id,
                success=False,
                error_code="DEVICE_ERROR",
                error_message="Device rejected command",
            )

        service.register_executor("set_power_mode", test_executor)

        result = await service.execute_command(sample_command)

        assert result.success is False
        mock_command_repo.mark_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_handles_exception(
        self, service, mock_command_repo, sample_command
    ):
        """Test handles executor exception."""
        async def test_executor(cmd):
            raise Exception("Unexpected error")

        service.register_executor("set_power_mode", test_executor)

        result = await service.execute_command(sample_command)

        assert result.success is False
        assert result.error_code == "EXCEPTION"
        mock_command_repo.mark_failed.assert_called_once()


class TestReportResult:
    """Test result reporting."""

    @pytest.mark.asyncio
    async def test_report_result_success(
        self, service, mock_command_repo, sample_command_id, sample_command
    ):
        """Test reports successful result."""
        mock_command_repo.get_by_id = AsyncMock(return_value=sample_command)

        await service.report_result(
            command_id=sample_command_id,
            success=True,
            data={"value": 100},
        )

        mock_command_repo.mark_completed.assert_called_once()

    @pytest.mark.asyncio
    async def test_report_result_failure(
        self, service, mock_command_repo, sample_command_id, sample_command
    ):
        """Test reports failed result."""
        mock_command_repo.get_by_id = AsyncMock(return_value=sample_command)

        await service.report_result(
            command_id=sample_command_id,
            success=False,
            error_message="Device error",
        )

        mock_command_repo.mark_failed.assert_called_once()


class TestMarkAcknowledged:
    """Test marking command as acknowledged."""

    @pytest.mark.asyncio
    async def test_mark_acknowledged(
        self, service, mock_command_repo, sample_command_id
    ):
        """Test marks command as acknowledged."""
        await service.mark_acknowledged(sample_command_id)

        mock_command_repo.mark_acknowledged.assert_called_once()


class TestCancelCommand:
    """Test command cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_command_returns_true(
        self, service, mock_command_repo, sample_command_id
    ):
        """Test cancel returns True when successful."""
        mock_command_repo.cancel_command = AsyncMock(return_value=True)

        result = await service.cancel_command(sample_command_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_command_returns_false(
        self, service, mock_command_repo, sample_command_id
    ):
        """Test cancel returns False when not cancellable."""
        mock_command_repo.cancel_command = AsyncMock(return_value=False)

        result = await service.cancel_command(sample_command_id)

        assert result is False


class TestCancelDeviceCommands:
    """Test cancelling all device commands."""

    @pytest.mark.asyncio
    async def test_cancel_device_commands(
        self, service, mock_command_repo, sample_device_id, sample_command
    ):
        """Test cancels all device commands."""
        mock_command_repo.get_device_queue = AsyncMock(return_value=[sample_command])
        mock_command_repo.cancel_command = AsyncMock(return_value=True)

        result = await service.cancel_device_commands(sample_device_id)

        assert result == 1


class TestRetryCommand:
    """Test command retry."""

    @pytest.mark.asyncio
    async def test_retry_command(
        self, service, mock_command_repo, sample_command_id, sample_command
    ):
        """Test retries command."""
        mock_command_repo.retry_command = AsyncMock(return_value=sample_command)

        result = await service.retry_command(sample_command_id)

        assert result == sample_command


class TestRetryFailedCommands:
    """Test retrying all failed commands."""

    @pytest.mark.asyncio
    async def test_retry_failed_commands(
        self, service, mock_command_repo, sample_command
    ):
        """Test retries all failed commands."""
        mock_command_repo.get_retryable_commands = AsyncMock(return_value=[sample_command])
        mock_command_repo.retry_command = AsyncMock(return_value=sample_command)

        result = await service.retry_failed_commands()

        assert result == 1


class TestExpireCommands:
    """Test command expiration."""

    @pytest.mark.asyncio
    async def test_expire_commands(
        self, service, mock_command_repo
    ):
        """Test expires old commands."""
        mock_command_repo.expire_old_commands = AsyncMock(return_value=5)

        result = await service.expire_commands()

        assert result == 5


class TestCleanupOldCommands:
    """Test command cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_old_commands(
        self, service, mock_command_repo
    ):
        """Test cleans up old commands."""
        mock_command_repo.cleanup_old_commands = AsyncMock(return_value=50)

        result = await service.cleanup_old_commands(days=30)

        assert result == 50


class TestGetCommandStats:
    """Test command statistics."""

    @pytest.mark.asyncio
    async def test_get_command_stats(
        self, service, mock_command_repo
    ):
        """Test gets command stats."""
        mock_command_repo.get_command_stats = AsyncMock(
            return_value={
                "pending": 5,
                "completed": 100,
                "failed": 10,
            }
        )
        mock_command_repo.get_pending_count = AsyncMock(return_value=5)

        result = await service.get_command_stats()

        assert result["total_commands"] == 115
        assert result["pending_commands"] == 5
        # Success rate should be 100 / 110 * 100 ≈ 90.9
        assert result["success_rate"] > 90
