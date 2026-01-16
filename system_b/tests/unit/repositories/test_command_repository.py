"""
Unit tests for CommandRepository.

Tests command queueing, status tracking, and lifecycle management.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.infrastructure.database.repositories.command_repository import CommandRepository
from app.domain.entities.command import DeviceCommand, CommandStatus


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
    """Create a CommandRepository with mock session."""
    return CommandRepository(mock_session)


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
    """Create a sample device command entity."""
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


class TestCommandRepositoryInit:
    """Test repository initialization."""

    def test_init_with_session(self, mock_session):
        """Test repository initializes with session."""
        repo = CommandRepository(mock_session)
        assert repo._session == mock_session


class TestGetById:
    """Test getting command by ID."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(
        self, repository, mock_session, sample_command_id
    ):
        """Test returns None when command not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_by_id(sample_command_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_command(
        self, repository, mock_session, sample_command_id, sample_device_id, sample_site_id
    ):
        """Test returns command when found."""
        mock_model = MagicMock()
        mock_model.id = sample_command_id
        mock_model.device_id = sample_device_id
        mock_model.site_id = sample_site_id
        mock_model.command_type = "set_power_mode"
        mock_model.command_params = {"mode": "self_consumption"}
        mock_model.status = "pending"
        mock_model.scheduled_at = None
        mock_model.sent_at = None
        mock_model.acknowledged_at = None
        mock_model.completed_at = None
        mock_model.expires_at = None
        mock_model.result = None
        mock_model.error_message = None
        mock_model.retry_count = 0
        mock_model.max_retries = 3
        mock_model.created_by = None
        mock_model.priority = 1
        mock_model.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_model
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_by_id(sample_command_id)

        assert result is not None
        assert result.id == sample_command_id
        assert result.command_type == "set_power_mode"
        assert result.status == CommandStatus.PENDING


class TestCreate:
    """Test command creation."""

    @pytest.mark.asyncio
    async def test_create_adds_model_to_session(
        self, repository, mock_session, sample_command
    ):
        """Test create adds model to session."""
        result = await repository.create(sample_command)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.id == sample_command.id

    @pytest.mark.asyncio
    async def test_create_generates_id_if_missing(
        self, repository, mock_session, sample_device_id, sample_site_id
    ):
        """Test create generates ID if not provided."""
        command = DeviceCommand(
            device_id=sample_device_id,
            site_id=sample_site_id,
            command_type="test_command",
            command_params={},
            status=CommandStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        result = await repository.create(command)

        assert result.id is not None
        mock_session.add.assert_called_once()


class TestUpdate:
    """Test command update."""

    @pytest.mark.asyncio
    async def test_update_executes_statement(
        self, repository, mock_session, sample_command
    ):
        """Test update executes update statement."""
        mock_session.execute = AsyncMock()

        result = await repository.update(sample_command)

        mock_session.execute.assert_called_once()
        assert result.updated_at is not None


class TestDelete:
    """Test command deletion."""

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(
        self, repository, mock_session, sample_command_id
    ):
        """Test delete returns True when command deleted."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.delete(sample_command_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self, repository, mock_session, sample_command_id
    ):
        """Test delete returns False when command not found."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.delete(sample_command_id)

        assert result is False


class TestGetPendingCommands:
    """Test getting pending commands."""

    @pytest.mark.asyncio
    async def test_get_pending_commands_returns_empty_list(
        self, repository, mock_session
    ):
        """Test returns empty list when no pending commands."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_pending_commands()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_pending_commands_with_device_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test get pending with device filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_pending_commands(device_id=sample_device_id)

        mock_session.execute.assert_called_once()


class TestGetDeviceQueue:
    """Test getting device command queue."""

    @pytest.mark.asyncio
    async def test_get_device_queue_returns_commands(
        self, repository, mock_session, sample_device_id
    ):
        """Test returns device queue."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_device_queue(sample_device_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_device_queue_include_completed(
        self, repository, mock_session, sample_device_id
    ):
        """Test get queue including completed commands."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_device_queue(
            sample_device_id, include_completed=True
        )

        mock_session.execute.assert_called_once()


class TestClaimPendingCommand:
    """Test claiming pending command atomically."""

    @pytest.mark.asyncio
    async def test_claim_pending_returns_none_when_no_commands(
        self, repository, mock_session, sample_device_id
    ):
        """Test returns None when no pending commands."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.claim_pending_command(sample_device_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_claim_pending_updates_status_to_sent(
        self, repository, mock_session, sample_device_id, sample_command_id
    ):
        """Test claiming updates status to SENT."""
        # First call returns command ID
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = sample_command_id

        # Second call returns updated model
        mock_model = MagicMock()
        mock_model.id = sample_command_id
        mock_model.device_id = sample_device_id
        mock_model.site_id = uuid4()
        mock_model.command_type = "test_command"
        mock_model.command_params = {}
        mock_model.status = "sent"
        mock_model.scheduled_at = None
        mock_model.sent_at = datetime.now(timezone.utc)
        mock_model.acknowledged_at = None
        mock_model.completed_at = None
        mock_model.expires_at = None
        mock_model.result = None
        mock_model.error_message = None
        mock_model.retry_count = 0
        mock_model.max_retries = 3
        mock_model.created_by = None
        mock_model.priority = 1
        mock_model.created_at = datetime.now(timezone.utc)

        mock_update_result = MagicMock()
        mock_update_result.scalar_one_or_none.return_value = mock_model

        mock_session.execute = AsyncMock(
            side_effect=[mock_select_result, mock_update_result]
        )

        result = await repository.claim_pending_command(sample_device_id)

        assert result is not None
        assert mock_session.execute.call_count == 2


class TestStatusUpdates:
    """Test command status update methods."""

    @pytest.mark.asyncio
    async def test_mark_sent(
        self, repository, mock_session, sample_command_id
    ):
        """Test marking command as sent."""
        mock_session.execute = AsyncMock()

        await repository.mark_sent(sample_command_id)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_acknowledged(
        self, repository, mock_session, sample_command_id
    ):
        """Test marking command as acknowledged."""
        mock_session.execute = AsyncMock()

        await repository.mark_acknowledged(sample_command_id)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_completed(
        self, repository, mock_session, sample_command_id
    ):
        """Test marking command as completed."""
        mock_session.execute = AsyncMock()

        await repository.mark_completed(
            sample_command_id,
            result={"success": True}
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_failed(
        self, repository, mock_session, sample_command_id
    ):
        """Test marking command as failed."""
        mock_session.execute = AsyncMock()

        await repository.mark_failed(
            sample_command_id,
            error_message="Device unreachable"
        )

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_mark_timeout(
        self, repository, mock_session, sample_command_id
    ):
        """Test marking command as timed out."""
        mock_session.execute = AsyncMock()

        await repository.mark_timeout(sample_command_id)

        mock_session.execute.assert_called_once()


class TestCancelCommand:
    """Test command cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_returns_true_when_cancelled(
        self, repository, mock_session, sample_command_id
    ):
        """Test cancel returns True when command cancelled."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.cancel_command(sample_command_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_returns_false_when_not_cancellable(
        self, repository, mock_session, sample_command_id
    ):
        """Test cancel returns False when command not cancellable."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.cancel_command(sample_command_id)

        assert result is False


class TestRetryCommand:
    """Test command retry functionality."""

    @pytest.mark.asyncio
    async def test_retry_command_returns_none_when_not_found(
        self, repository, mock_session, sample_command_id
    ):
        """Test retry returns None when command not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.retry_command(sample_command_id)

        assert result is None


class TestGetRetryableCommands:
    """Test getting retryable commands."""

    @pytest.mark.asyncio
    async def test_get_retryable_commands(
        self, repository, mock_session
    ):
        """Test gets retryable commands."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_retryable_commands()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_retryable_commands_with_device_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test get retryable with device filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_retryable_commands(device_id=sample_device_id)

        mock_session.execute.assert_called_once()


class TestExpireOldCommands:
    """Test command expiration."""

    @pytest.mark.asyncio
    async def test_expire_old_commands_returns_count(
        self, repository, mock_session
    ):
        """Test expire returns count of expired commands."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.expire_old_commands()

        assert result == 5


class TestGetCommandHistory:
    """Test getting command history."""

    @pytest.mark.asyncio
    async def test_get_command_history(
        self, repository, mock_session, sample_device_id
    ):
        """Test gets command history for device."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_command_history(sample_device_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_command_history_with_filters(
        self, repository, mock_session, sample_device_id
    ):
        """Test command history with filters."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        now = datetime.now(timezone.utc)
        await repository.get_command_history(
            sample_device_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
            command_type="set_power_mode",
            status=CommandStatus.COMPLETED,
        )

        mock_session.execute.assert_called_once()


class TestGetSiteCommands:
    """Test getting site commands."""

    @pytest.mark.asyncio
    async def test_get_site_commands(
        self, repository, mock_session, sample_site_id
    ):
        """Test gets commands for site."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_site_commands(sample_site_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_site_commands_pending_only(
        self, repository, mock_session, sample_site_id
    ):
        """Test get site commands pending only."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_site_commands(sample_site_id, pending_only=True)

        mock_session.execute.assert_called_once()


class TestGetCommandStats:
    """Test command statistics."""

    @pytest.mark.asyncio
    async def test_get_command_stats(
        self, repository, mock_session
    ):
        """Test gets command stats."""
        mock_rows = [
            MagicMock(status="pending", count=10),
            MagicMock(status="completed", count=25),
            MagicMock(status="failed", count=3),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_command_stats()

        assert result["pending"] == 10
        assert result["completed"] == 25
        assert result["failed"] == 3

    @pytest.mark.asyncio
    async def test_get_command_stats_with_filters(
        self, repository, mock_session, sample_device_id, sample_site_id
    ):
        """Test command stats with filters."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_command_stats(
            device_id=sample_device_id,
            site_id=sample_site_id,
            since=datetime.now(timezone.utc) - timedelta(hours=1)
        )

        mock_session.execute.assert_called_once()


class TestGetPendingCount:
    """Test getting pending command count."""

    @pytest.mark.asyncio
    async def test_get_pending_count(
        self, repository, mock_session
    ):
        """Test gets pending count."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 15
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_pending_count()

        assert result == 15

    @pytest.mark.asyncio
    async def test_get_pending_count_handles_none(
        self, repository, mock_session
    ):
        """Test handles None result."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_pending_count()

        assert result == 0


class TestCleanupOldCommands:
    """Test command cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_old_commands(
        self, repository, mock_session
    ):
        """Test cleanup returns deleted count."""
        mock_result = MagicMock()
        mock_result.rowcount = 50
        mock_session.execute = AsyncMock(return_value=mock_result)

        older_than = datetime.now(timezone.utc) - timedelta(days=30)
        result = await repository.cleanup_old_commands(older_than)

        assert result == 50

    @pytest.mark.asyncio
    async def test_cleanup_with_status_filter(
        self, repository, mock_session
    ):
        """Test cleanup with status filter."""
        mock_result = MagicMock()
        mock_result.rowcount = 20
        mock_session.execute = AsyncMock(return_value=mock_result)

        older_than = datetime.now(timezone.utc) - timedelta(days=30)
        result = await repository.cleanup_old_commands(
            older_than,
            statuses=[CommandStatus.COMPLETED, CommandStatus.FAILED]
        )

        assert result == 20
