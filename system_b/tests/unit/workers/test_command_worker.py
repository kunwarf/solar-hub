"""
Unit tests for CommandWorker.

Tests command processing, execution, and lifecycle management.
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from device_server.workers.command_worker import CommandWorker


@pytest.fixture
def worker():
    """Create a CommandWorker with default settings."""
    return CommandWorker(poll_interval=0.1, batch_size=5)


@pytest.fixture
def sample_command():
    """Create a sample command dictionary."""
    return {
        "id": uuid4(),
        "device_id": uuid4(),
        "command_type": "set_power_mode",
        "command_params": {"mode": "self_consumption"},
    }


class TestCommandWorkerInit:
    """Test worker initialization."""

    def test_init_with_defaults(self):
        """Test worker initializes with defaults."""
        worker = CommandWorker()
        assert worker.poll_interval == 1.0
        assert worker.batch_size == 10
        assert worker._running is False

    def test_init_with_custom_settings(self):
        """Test worker initializes with custom settings."""
        worker = CommandWorker(poll_interval=0.5, batch_size=20)
        assert worker.poll_interval == 0.5
        assert worker.batch_size == 20


class TestSetCallbacks:
    """Test callback setters."""

    def test_set_executor(self, worker):
        """Test setting executor."""
        executor = MagicMock()
        worker.set_executor(executor)
        assert worker._executor == executor

    def test_set_fetch_pending(self, worker):
        """Test setting fetch pending callback."""
        callback = AsyncMock()
        worker.set_fetch_pending(callback)
        assert worker._fetch_pending == callback

    def test_set_mark_sent(self, worker):
        """Test setting mark sent callback."""
        callback = AsyncMock()
        worker.set_mark_sent(callback)
        assert worker._mark_sent == callback

    def test_set_mark_completed(self, worker):
        """Test setting mark completed callback."""
        callback = AsyncMock()
        worker.set_mark_completed(callback)
        assert worker._mark_completed == callback

    def test_set_mark_failed(self, worker):
        """Test setting mark failed callback."""
        callback = AsyncMock()
        worker.set_mark_failed(callback)
        assert worker._mark_failed == callback

    def test_set_expire_stale(self, worker):
        """Test setting expire stale callback."""
        callback = AsyncMock()
        worker.set_expire_stale(callback)
        assert worker._expire_stale == callback


class TestStartStop:
    """Test worker lifecycle."""

    @pytest.mark.asyncio
    async def test_start_sets_running(self, worker):
        """Test start sets running flag."""
        await worker.start()
        assert worker._running is True
        assert worker.is_running is True
        await worker.stop()

    @pytest.mark.asyncio
    async def test_start_when_already_running(self, worker):
        """Test start when already running does nothing."""
        await worker.start()
        await worker.start()  # Should not raise
        assert worker._running is True
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self, worker):
        """Test stop clears running flag."""
        await worker.start()
        await worker.stop()
        assert worker._running is False
        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, worker):
        """Test stop when not running does nothing."""
        await worker.stop()  # Should not raise
        assert worker._running is False


class TestProcessPendingCommands:
    """Test command processing."""

    @pytest.mark.asyncio
    async def test_process_returns_early_without_callbacks(self, worker):
        """Test process returns early when no callbacks set."""
        # No fetch_pending or executor set
        await worker._process_pending_commands()
        # Should not raise

    @pytest.mark.asyncio
    async def test_process_fetches_commands(self, worker, sample_command):
        """Test process fetches pending commands."""
        mock_fetch = AsyncMock(return_value=[sample_command])
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"success": True})

        worker.set_fetch_pending(mock_fetch)
        worker.set_executor(mock_executor)
        worker.set_mark_sent(AsyncMock())
        worker.set_mark_completed(AsyncMock())

        await worker._process_pending_commands()

        mock_fetch.assert_called_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_process_executes_commands(self, worker, sample_command):
        """Test process executes each command."""
        mock_fetch = AsyncMock(return_value=[sample_command])
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"success": True})

        worker.set_fetch_pending(mock_fetch)
        worker.set_executor(mock_executor)
        worker.set_mark_sent(AsyncMock())
        worker.set_mark_completed(AsyncMock())

        await worker._process_pending_commands()

        mock_executor.execute.assert_called_once()


class TestExecuteCommand:
    """Test individual command execution."""

    @pytest.mark.asyncio
    async def test_execute_marks_sent(self, worker, sample_command):
        """Test execute marks command as sent."""
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"success": True})
        mock_mark_sent = AsyncMock()

        worker.set_executor(mock_executor)
        worker.set_mark_sent(mock_mark_sent)
        worker.set_mark_completed(AsyncMock())

        await worker._execute_command(sample_command)

        mock_mark_sent.assert_called_once_with(sample_command["id"])

    @pytest.mark.asyncio
    async def test_execute_success_marks_completed(self, worker, sample_command):
        """Test successful execution marks command completed."""
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"value": 100})
        mock_mark_completed = AsyncMock()

        worker.set_executor(mock_executor)
        worker.set_mark_sent(AsyncMock())
        worker.set_mark_completed(mock_mark_completed)

        await worker._execute_command(sample_command)

        mock_mark_completed.assert_called_once()
        assert worker._commands_processed == 1

    @pytest.mark.asyncio
    async def test_execute_failure_marks_failed(self, worker, sample_command):
        """Test failed execution marks command failed."""
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(side_effect=Exception("Device error"))
        mock_mark_failed = AsyncMock()

        worker.set_executor(mock_executor)
        worker.set_mark_sent(AsyncMock())
        worker.set_mark_failed(mock_mark_failed)

        await worker._execute_command(sample_command)

        mock_mark_failed.assert_called_once()
        assert worker._commands_failed == 1

    @pytest.mark.asyncio
    async def test_execute_handles_mark_sent_failure(self, worker, sample_command):
        """Test execute handles mark_sent failure gracefully."""
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"success": True})
        mock_mark_sent = AsyncMock(side_effect=Exception("DB error"))

        worker.set_executor(mock_executor)
        worker.set_mark_sent(mock_mark_sent)
        worker.set_mark_completed(AsyncMock())

        # Should not raise
        await worker._execute_command(sample_command)


class TestExpireStale:
    """Test stale command expiration."""

    @pytest.mark.asyncio
    async def test_expire_stale_returns_early_without_callback(self, worker):
        """Test expire stale returns early when no callback."""
        await worker._run_expire_stale()
        # Should not raise

    @pytest.mark.asyncio
    async def test_expire_stale_calls_callback(self, worker):
        """Test expire stale calls callback."""
        mock_expire = AsyncMock(return_value=5)
        worker.set_expire_stale(mock_expire)

        await worker._run_expire_stale()

        mock_expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_expire_stale_handles_error(self, worker):
        """Test expire stale handles callback error."""
        mock_expire = AsyncMock(side_effect=Exception("DB error"))
        worker.set_expire_stale(mock_expire)

        # Should not raise
        await worker._run_expire_stale()


class TestGetStats:
    """Test statistics retrieval."""

    def test_get_stats_initial(self, worker):
        """Test get stats with initial values."""
        stats = worker.get_stats()

        assert stats["running"] is False
        assert stats["commands_processed"] == 0
        assert stats["commands_failed"] == 0
        assert stats["last_check_time"] is None
        assert stats["poll_interval"] == 0.1
        assert stats["batch_size"] == 5

    @pytest.mark.asyncio
    async def test_get_stats_after_processing(self, worker, sample_command):
        """Test get stats after processing commands."""
        mock_executor = AsyncMock()
        mock_executor.execute = AsyncMock(return_value={"success": True})

        worker.set_executor(mock_executor)
        worker.set_mark_sent(AsyncMock())
        worker.set_mark_completed(AsyncMock())

        await worker._execute_command(sample_command)

        stats = worker.get_stats()
        assert stats["commands_processed"] == 1


class TestIsRunning:
    """Test is_running property."""

    def test_is_running_initially_false(self, worker):
        """Test is_running is False initially."""
        assert worker.is_running is False

    @pytest.mark.asyncio
    async def test_is_running_after_start(self, worker):
        """Test is_running after start."""
        await worker.start()
        assert worker.is_running is True
        await worker.stop()
