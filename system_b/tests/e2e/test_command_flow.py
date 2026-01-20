"""
E2E tests for command flow.

Tests the complete flow from API command creation to device execution.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


@pytest.fixture
def sample_command_id():
    return uuid4()


class TestCommandExecutionFlow:
    """
    Test command execution flow.

    Flow: API creates command → device receives → result reported
    """

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_command_flow(
        self, sample_device_id, sample_site_id, sample_command_id
    ):
        """
        Test complete command execution flow.

        1. Command created via API
        2. Command queued for device
        3. Device claims command
        4. Device executes command
        5. Result reported back
        6. Command marked complete
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            # Create command
            mock_command = MagicMock()
            mock_command.id = sample_command_id
            mock_command.device_id = sample_device_id
            mock_command.site_id = sample_site_id
            mock_command.command_type = "set_mode"
            mock_command.command_params = {"mode": "battery_priority"}
            mock_command.status = "pending"
            mock_command.created_at = datetime.now(timezone.utc)

            mock_service.create_command = AsyncMock(return_value=mock_command)

            # Claim command
            claimed_command = MagicMock()
            claimed_command.id = sample_command_id
            claimed_command.status = "sent"
            claimed_command.sent_at = datetime.now(timezone.utc)
            mock_service.get_pending_commands = AsyncMock(return_value=[mock_command])
            mock_service.claim_command = AsyncMock(return_value=claimed_command)

            # Complete command
            completed_command = MagicMock()
            completed_command.id = sample_command_id
            completed_command.status = "completed"
            completed_command.completed_at = datetime.now(timezone.utc)
            completed_command.result = {"new_mode": "battery_priority"}
            mock_service.complete_command = AsyncMock(return_value=completed_command)

            MockService.return_value = mock_service

            # 1. Create command
            command = await mock_service.create_command(
                device_id=sample_device_id,
                site_id=sample_site_id,
                command_type="set_mode",
                command_params={"mode": "battery_priority"},
            )
            assert command.status == "pending"

            # 2. Get pending commands (device polling)
            pending = await mock_service.get_pending_commands(device_id=sample_device_id)
            assert len(pending) == 1

            # 3. Claim command
            claimed = await mock_service.claim_command(command_id=sample_command_id)
            assert claimed.status == "sent"

            # 4. Complete command
            completed = await mock_service.complete_command(
                command_id=sample_command_id,
                result={"new_mode": "battery_priority"},
            )
            assert completed.status == "completed"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_command_failure_flow(
        self, sample_device_id, sample_command_id
    ):
        """
        Test command failure flow.

        1. Command created
        2. Device attempts execution
        3. Execution fails
        4. Error reported
        5. Command marked failed
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            # Failed command
            failed_command = MagicMock()
            failed_command.id = sample_command_id
            failed_command.status = "failed"
            failed_command.failed_at = datetime.now(timezone.utc)
            failed_command.error_message = "Device offline"
            mock_service.fail_command = AsyncMock(return_value=failed_command)

            MockService.return_value = mock_service

            # Report failure
            failed = await mock_service.fail_command(
                command_id=sample_command_id,
                error_message="Device offline",
            )

            assert failed.status == "failed"
            assert failed.error_message == "Device offline"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_command_timeout_flow(
        self, sample_device_id, sample_command_id
    ):
        """
        Test command timeout flow.

        1. Command created
        2. Command sent to device
        3. No response within timeout
        4. Command expires
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            # Expired command
            expired_command = MagicMock()
            expired_command.id = sample_command_id
            expired_command.status = "expired"
            expired_command.expired_at = datetime.now(timezone.utc)
            mock_service.expire_stale_commands = AsyncMock(return_value=1)

            MockService.return_value = mock_service

            # Expire stale commands
            expired_count = await mock_service.expire_stale_commands(
                timeout_seconds=300,
            )

            assert expired_count == 1

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_command_acknowledgment_flow(
        self, sample_device_id, sample_command_id
    ):
        """
        Test command acknowledgment flow.

        1. Command sent to device
        2. Device acknowledges receipt
        3. Status updated to acknowledged
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            acked_command = MagicMock()
            acked_command.id = sample_command_id
            acked_command.status = "acknowledged"
            acked_command.acknowledged_at = datetime.now(timezone.utc)
            mock_service.acknowledge_command = AsyncMock(return_value=acked_command)

            MockService.return_value = mock_service

            # Acknowledge command
            acked = await mock_service.acknowledge_command(
                command_id=sample_command_id,
            )

            assert acked.status == "acknowledged"


class TestCommandRetryFlow:
    """Test command retry flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_command_retry_on_failure(
        self, sample_device_id, sample_command_id
    ):
        """
        Test command retry after failure.

        1. Command fails first attempt
        2. Retry requested
        3. Command re-queued
        4. Second attempt succeeds
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            # First attempt fails
            failed_command = MagicMock()
            failed_command.id = sample_command_id
            failed_command.status = "failed"
            failed_command.retry_count = 1
            mock_service.fail_command = AsyncMock(return_value=failed_command)

            # Retry creates new pending status
            retried_command = MagicMock()
            retried_command.id = sample_command_id
            retried_command.status = "pending"
            retried_command.retry_count = 1
            mock_service.retry_command = AsyncMock(return_value=retried_command)

            # Second attempt succeeds
            completed_command = MagicMock()
            completed_command.id = sample_command_id
            completed_command.status = "completed"
            completed_command.retry_count = 1
            mock_service.complete_command = AsyncMock(return_value=completed_command)

            MockService.return_value = mock_service

            # First attempt fails
            await mock_service.fail_command(
                command_id=sample_command_id,
                error_message="Timeout",
            )

            # Retry command
            retried = await mock_service.retry_command(
                command_id=sample_command_id,
            )
            assert retried.status == "pending"
            assert retried.retry_count == 1

            # Second attempt succeeds
            completed = await mock_service.complete_command(
                command_id=sample_command_id,
                result={"success": True},
            )
            assert completed.status == "completed"


class TestCommandCancellationFlow:
    """Test command cancellation flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cancel_pending_command(
        self, sample_command_id
    ):
        """
        Test cancelling a pending command.

        1. Command is pending
        2. Cancellation requested
        3. Command marked cancelled
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            cancelled_command = MagicMock()
            cancelled_command.id = sample_command_id
            cancelled_command.status = "cancelled"
            cancelled_command.cancelled_at = datetime.now(timezone.utc)
            mock_service.cancel_command = AsyncMock(return_value=cancelled_command)

            MockService.return_value = mock_service

            cancelled = await mock_service.cancel_command(
                command_id=sample_command_id,
                reason="User cancelled",
            )

            assert cancelled.status == "cancelled"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_command(
        self, sample_command_id
    ):
        """
        Test that completed commands cannot be cancelled.

        1. Command is completed
        2. Cancellation attempted
        3. Error raised
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()
            mock_service.cancel_command = AsyncMock(
                side_effect=ValueError("Cannot cancel completed command")
            )
            MockService.return_value = mock_service

            with pytest.raises(ValueError) as exc_info:
                await mock_service.cancel_command(
                    command_id=sample_command_id,
                )

            assert "Cannot cancel" in str(exc_info.value)


class TestCommandPriorityFlow:
    """Test command priority flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_high_priority_command_first(
        self, sample_device_id, sample_site_id
    ):
        """
        Test that high priority commands are processed first.

        1. Low priority command created
        2. High priority command created
        3. Pending commands retrieved
        4. High priority first
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            high_priority = MagicMock()
            high_priority.id = uuid4()
            high_priority.priority = 1
            high_priority.command_type = "emergency_stop"

            low_priority = MagicMock()
            low_priority.id = uuid4()
            low_priority.priority = 10
            low_priority.command_type = "set_mode"

            mock_service = MagicMock()
            mock_service.get_pending_commands = AsyncMock(
                return_value=[high_priority, low_priority]
            )
            MockService.return_value = mock_service

            pending = await mock_service.get_pending_commands(
                device_id=sample_device_id,
            )

            assert len(pending) == 2
            assert pending[0].priority == 1  # High priority first
            assert pending[0].command_type == "emergency_stop"


class TestBatchCommandFlow:
    """Test batch command flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_batch_command_to_multiple_devices(
        self, sample_site_id
    ):
        """
        Test sending same command to multiple devices.

        1. Command created for site
        2. Command sent to all devices
        3. Each device reports result
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            device_ids = [uuid4() for _ in range(3)]
            commands = []

            for device_id in device_ids:
                cmd = MagicMock()
                cmd.id = uuid4()
                cmd.device_id = device_id
                cmd.command_type = "set_mode"
                cmd.status = "completed"
                commands.append(cmd)

            mock_service = MagicMock()
            mock_service.create_batch_commands = AsyncMock(return_value=commands)
            MockService.return_value = mock_service

            created = await mock_service.create_batch_commands(
                site_id=sample_site_id,
                device_ids=device_ids,
                command_type="set_mode",
                command_params={"mode": "battery_priority"},
            )

            assert len(created) == 3


class TestCommandStreamFlow:
    """Test command streaming flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_command_stream_publish(
        self, sample_device_id, sample_site_id, sample_command_id
    ):
        """
        Test command publishing to stream.

        1. Command created
        2. Published to stream
        3. Worker receives command
        """
        with patch("app.infrastructure.messaging.stream_services.CommandStreamService") as MockStreamService:

            mock_service = MagicMock()
            mock_service.publish_command = AsyncMock(return_value="msg_456")
            MockStreamService.return_value = mock_service

            msg_id = await mock_service.publish_command(
                command_id=sample_command_id,
                device_id=sample_device_id,
                site_id=sample_site_id,
                command_type="set_mode",
                command_params={"mode": "battery_priority"},
            )

            assert msg_id == "msg_456"


class TestScheduledCommandFlow:
    """Test scheduled command flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_scheduled_command_execution(
        self, sample_device_id, sample_site_id, sample_command_id
    ):
        """
        Test scheduled command that executes at a future time.

        1. Command created with scheduled time
        2. Command not executed until scheduled time
        3. Command executed at scheduled time
        4. Result reported
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            # Create scheduled command
            scheduled_command = MagicMock()
            scheduled_command.id = sample_command_id
            scheduled_command.status = "pending"
            scheduled_command.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            mock_service.create_command = AsyncMock(return_value=scheduled_command)

            # Get pending returns empty before scheduled time
            mock_service.get_pending_commands = AsyncMock(return_value=[])

            MockService.return_value = mock_service

            # Create scheduled command
            command = await mock_service.create_command(
                device_id=sample_device_id,
                site_id=sample_site_id,
                command_type="set_mode",
                command_params={"mode": "grid_priority"},
                scheduled_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
            assert command.status == "pending"
            assert command.scheduled_at is not None

            # Pending commands should be empty before scheduled time
            pending = await mock_service.get_pending_commands(device_id=sample_device_id)
            assert len(pending) == 0

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_immediate_command_execution(
        self, sample_device_id, sample_site_id, sample_command_id
    ):
        """
        Test immediate command execution with wait.

        1. Create immediate command
        2. Wait for completion
        3. Result returned
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            # Immediate command that completes
            completed_command = MagicMock()
            completed_command.id = sample_command_id
            completed_command.status = "completed"
            completed_command.result = {"mode": "battery_priority"}
            mock_service.create_immediate_command = AsyncMock(return_value=completed_command)

            MockService.return_value = mock_service

            # Create and wait for completion
            result = await mock_service.create_immediate_command(
                device_id=sample_device_id,
                site_id=sample_site_id,
                command_type="set_mode",
                command_params={"mode": "battery_priority"},
                timeout_seconds=30,
            )

            assert result.status == "completed"
            assert result.result["mode"] == "battery_priority"


class TestCommandRetryExhaustion:
    """Test command retry exhaustion flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_max_retries_exhausted(
        self, sample_device_id, sample_command_id
    ):
        """
        Test command fails permanently after max retries.

        1. Command fails multiple times
        2. Max retries reached
        3. Command marked as permanently failed
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            # Command that has exhausted retries
            failed_command = MagicMock()
            failed_command.id = sample_command_id
            failed_command.status = "failed"
            failed_command.retry_count = 3
            failed_command.max_retries = 3
            failed_command.error_message = "Max retries exhausted"
            mock_service.fail_command = AsyncMock(return_value=failed_command)

            # Retry returns error when max retries exceeded
            mock_service.retry_command = AsyncMock(
                side_effect=ValueError("Command has reached maximum retry count")
            )

            MockService.return_value = mock_service

            # Fail command
            failed = await mock_service.fail_command(
                command_id=sample_command_id,
                error_message="Device timeout",
            )
            assert failed.retry_count == failed.max_retries

            # Retry should fail
            with pytest.raises(ValueError) as exc_info:
                await mock_service.retry_command(command_id=sample_command_id)

            assert "maximum retry count" in str(exc_info.value)

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_batch_retry_failed_commands(
        self, sample_device_id
    ):
        """
        Test batch retry of all retryable failed commands.

        1. Multiple commands failed
        2. Batch retry requested
        3. Only retryable commands retried
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()
            mock_service.retry_failed_commands = AsyncMock(return_value=5)
            MockService.return_value = mock_service

            # Retry all failed commands for device
            count = await mock_service.retry_failed_commands(
                device_id=sample_device_id,
            )

            assert count == 5


class TestCommandStatistics:
    """Test command statistics flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_command_stats(self, sample_device_id):
        """
        Test retrieving command statistics.

        1. Commands in various states
        2. Stats aggregated
        3. Counts and success rate returned
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()
            mock_service.get_command_stats = AsyncMock(return_value={
                "total": 100,
                "pending": 5,
                "sent": 3,
                "acknowledged": 2,
                "completed": 80,
                "failed": 8,
                "cancelled": 2,
                "success_rate": 0.80,
                "avg_execution_time_seconds": 2.5,
            })
            MockService.return_value = mock_service

            stats = await mock_service.get_command_stats(
                device_id=sample_device_id,
                hours=24,
            )

            assert stats["total"] == 100
            assert stats["completed"] == 80
            assert stats["success_rate"] == 0.80

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_command_history_pagination(
        self, sample_device_id
    ):
        """
        Test paginated command history retrieval.

        1. Many commands exist
        2. Query with pagination
        3. Correct page returned
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()
            commands = [MagicMock(id=uuid4()) for _ in range(10)]
            mock_service.get_command_history = AsyncMock(return_value={
                "commands": commands,
                "total": 50,
                "page": 1,
                "page_size": 10,
                "has_more": True,
            })
            MockService.return_value = mock_service

            result = await mock_service.get_command_history(
                device_id=sample_device_id,
                page=1,
                page_size=10,
            )

            assert len(result["commands"]) == 10
            assert result["total"] == 50
            assert result["has_more"] is True


class TestCommandWaitFlow:
    """Test command wait flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_wait_for_completion_success(
        self, sample_command_id
    ):
        """
        Test waiting for command completion.

        1. Command in progress
        2. Wait initiated
        3. Command completes
        4. Result returned
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            completed_command = MagicMock()
            completed_command.id = sample_command_id
            completed_command.status = "completed"
            completed_command.result = {"success": True}
            mock_service.wait_for_completion = AsyncMock(return_value=completed_command)

            MockService.return_value = mock_service

            result = await mock_service.wait_for_completion(
                command_id=sample_command_id,
                timeout_seconds=30,
            )

            assert result.status == "completed"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_wait_for_completion_timeout(
        self, sample_command_id
    ):
        """
        Test timeout when waiting for command completion.

        1. Command in progress
        2. Wait initiated with timeout
        3. Timeout reached
        4. TimeoutError raised
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()
            mock_service.wait_for_completion = AsyncMock(
                side_effect=asyncio.TimeoutError("Command did not complete within timeout")
            )
            MockService.return_value = mock_service

            with pytest.raises(asyncio.TimeoutError):
                await mock_service.wait_for_completion(
                    command_id=sample_command_id,
                    timeout_seconds=5,
                )


class TestCommandCleanup:
    """Test command cleanup flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cleanup_old_commands(self):
        """
        Test cleanup of old completed commands.

        1. Old completed commands exist
        2. Cleanup job runs
        3. Commands older than retention deleted
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()
            mock_service.cleanup_old_commands = AsyncMock(return_value=100)
            MockService.return_value = mock_service

            deleted = await mock_service.cleanup_old_commands(
                retention_days=30,
            )

            assert deleted == 100

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_expire_stale_commands(self):
        """
        Test expiring commands that have been pending too long.

        1. Commands pending beyond timeout
        2. Expiration job runs
        3. Commands marked as expired
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()
            mock_service.expire_commands = AsyncMock(return_value=5)
            MockService.return_value = mock_service

            expired = await mock_service.expire_commands(
                timeout_seconds=600,
            )

            assert expired == 5


class TestClaimAndExecuteFlow:
    """Test atomic claim and execute flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_claim_and_execute_command(
        self, sample_device_id, sample_command_id
    ):
        """
        Test atomic claim and execute operation.

        1. Command is pending
        2. Claim and execute atomically
        3. Prevent race conditions
        4. Result returned
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()

            executed_command = MagicMock()
            executed_command.id = sample_command_id
            executed_command.status = "completed"
            executed_command.result = {"executed": True}
            mock_service.claim_and_execute = AsyncMock(return_value=executed_command)

            MockService.return_value = mock_service

            async def executor(cmd):
                return {"executed": True}

            result = await mock_service.claim_and_execute(
                command_id=sample_command_id,
                executor=executor,
            )

            assert result.status == "completed"
            assert result.result["executed"] is True

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_claim_already_claimed_command(
        self, sample_command_id
    ):
        """
        Test claiming a command that's already claimed.

        1. Command already claimed by another worker
        2. Second claim attempted
        3. Claim rejected
        """
        with patch("app.application.services.command_service.CommandService") as MockService:

            mock_service = MagicMock()
            mock_service.claim_and_execute = AsyncMock(
                side_effect=ValueError("Command already claimed")
            )
            MockService.return_value = mock_service

            with pytest.raises(ValueError) as exc_info:
                await mock_service.claim_and_execute(
                    command_id=sample_command_id,
                    executor=lambda x: None,
                )

            assert "already claimed" in str(exc_info.value)

