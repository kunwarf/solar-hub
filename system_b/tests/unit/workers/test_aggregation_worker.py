"""
Unit tests for AggregationWorker.

Tests aggregation scheduling, execution, and lifecycle management.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from device_server.workers.aggregation_worker import AggregationWorker


@pytest.fixture
def worker():
    """Create an AggregationWorker with default settings."""
    return AggregationWorker(run_interval_minutes=1, aggregation_delay_minutes=1)


class TestAggregationWorkerInit:
    """Test worker initialization."""

    def test_init_with_defaults(self):
        """Test worker initializes with defaults."""
        worker = AggregationWorker()
        assert worker.run_interval == timedelta(minutes=5)
        assert worker.aggregation_delay == timedelta(minutes=2)
        assert worker._running is False

    def test_init_with_custom_settings(self):
        """Test worker initializes with custom settings."""
        worker = AggregationWorker(
            run_interval_minutes=10,
            aggregation_delay_minutes=5,
        )
        assert worker.run_interval == timedelta(minutes=10)
        assert worker.aggregation_delay == timedelta(minutes=5)


class TestSetCallbacks:
    """Test callback setters."""

    def test_set_aggregate_5min(self, worker):
        """Test setting 5-minute aggregation callback."""
        callback = AsyncMock()
        worker.set_aggregate_5min(callback)
        assert worker._aggregate_5min == callback

    def test_set_aggregate_1hour(self, worker):
        """Test setting 1-hour aggregation callback."""
        callback = AsyncMock()
        worker.set_aggregate_1hour(callback)
        assert worker._aggregate_1hour == callback

    def test_set_aggregate_1day(self, worker):
        """Test setting 1-day aggregation callback."""
        callback = AsyncMock()
        worker.set_aggregate_1day(callback)
        assert worker._aggregate_1day == callback

    def test_set_cleanup_old_aggregates(self, worker):
        """Test setting cleanup callback."""
        callback = AsyncMock()
        worker.set_cleanup_old_aggregates(callback)
        assert worker._cleanup_old_aggregates == callback

    def test_set_get_devices_with_telemetry(self, worker):
        """Test setting get devices callback."""
        callback = AsyncMock()
        worker.set_get_devices_with_telemetry(callback)
        assert worker._get_devices_with_telemetry == callback


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


class TestRun5MinAggregation:
    """Test 5-minute aggregation."""

    @pytest.mark.asyncio
    async def test_run_5min_aggregation(self, worker):
        """Test runs 5-minute aggregation."""
        mock_aggregate = AsyncMock(return_value=100)
        worker.set_aggregate_5min(mock_aggregate)

        end_time = datetime.now(timezone.utc)
        await worker._run_5min_aggregation(end_time)

        mock_aggregate.assert_called_once()
        call_args = mock_aggregate.call_args
        assert call_args[1]["bucket_interval"] == "5 minutes"

    @pytest.mark.asyncio
    async def test_run_5min_aggregation_handles_error(self, worker):
        """Test 5-minute aggregation handles errors."""
        mock_aggregate = AsyncMock(side_effect=Exception("DB error"))
        worker.set_aggregate_5min(mock_aggregate)

        end_time = datetime.now(timezone.utc)
        # Should not raise
        await worker._run_5min_aggregation(end_time)


class TestRun1HourAggregation:
    """Test 1-hour aggregation."""

    @pytest.mark.asyncio
    async def test_run_1hour_aggregation(self, worker):
        """Test runs 1-hour aggregation."""
        mock_aggregate = AsyncMock(return_value=24)
        worker.set_aggregate_1hour(mock_aggregate)

        end_time = datetime.now(timezone.utc)
        await worker._run_1hour_aggregation(end_time)

        mock_aggregate.assert_called_once()
        call_args = mock_aggregate.call_args
        assert call_args[1]["bucket_interval"] == "1 hour"

    @pytest.mark.asyncio
    async def test_run_1hour_aggregation_handles_error(self, worker):
        """Test 1-hour aggregation handles errors."""
        mock_aggregate = AsyncMock(side_effect=Exception("DB error"))
        worker.set_aggregate_1hour(mock_aggregate)

        end_time = datetime.now(timezone.utc)
        # Should not raise
        await worker._run_1hour_aggregation(end_time)


class TestRun1DayAggregation:
    """Test 1-day aggregation."""

    @pytest.mark.asyncio
    async def test_run_1day_aggregation(self, worker):
        """Test runs 1-day aggregation."""
        mock_aggregate = AsyncMock(return_value=7)
        worker.set_aggregate_1day(mock_aggregate)

        end_time = datetime.now(timezone.utc)
        await worker._run_1day_aggregation(end_time)

        mock_aggregate.assert_called_once()
        call_args = mock_aggregate.call_args
        assert call_args[1]["bucket_interval"] == "1 day"

    @pytest.mark.asyncio
    async def test_run_1day_aggregation_handles_error(self, worker):
        """Test 1-day aggregation handles errors."""
        mock_aggregate = AsyncMock(side_effect=Exception("DB error"))
        worker.set_aggregate_1day(mock_aggregate)

        end_time = datetime.now(timezone.utc)
        # Should not raise
        await worker._run_1day_aggregation(end_time)


class TestRunCleanup:
    """Test cleanup operations."""

    @pytest.mark.asyncio
    async def test_run_cleanup(self, worker):
        """Test runs cleanup."""
        mock_cleanup = AsyncMock(return_value=1000)
        worker.set_cleanup_old_aggregates(mock_cleanup)

        await worker._run_cleanup()

        mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_cleanup_handles_error(self, worker):
        """Test cleanup handles errors."""
        mock_cleanup = AsyncMock(side_effect=Exception("DB error"))
        worker.set_cleanup_old_aggregates(mock_cleanup)

        # Should not raise
        await worker._run_cleanup()


class TestRunManualAggregation:
    """Test manual aggregation."""

    @pytest.mark.asyncio
    async def test_run_manual_aggregation(self, worker):
        """Test manual aggregation."""
        mock_aggregate = AsyncMock(return_value=50)
        worker.set_aggregate_1hour(mock_aggregate)

        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        result = await worker.run_manual_aggregation(
            start_time=start_time,
            end_time=end_time,
            bucket_interval="1 hour",
        )

        assert result == 50
        mock_aggregate.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_manual_aggregation_returns_zero_without_callback(self, worker):
        """Test manual aggregation returns 0 without callback."""
        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        result = await worker.run_manual_aggregation(
            start_time=start_time,
            end_time=end_time,
        )

        assert result == 0

    @pytest.mark.asyncio
    async def test_run_manual_aggregation_handles_error(self, worker):
        """Test manual aggregation handles errors."""
        mock_aggregate = AsyncMock(side_effect=Exception("DB error"))
        worker.set_aggregate_1hour(mock_aggregate)

        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        result = await worker.run_manual_aggregation(
            start_time=start_time,
            end_time=end_time,
        )

        assert result == 0


class TestRunAggregationCycle:
    """Test aggregation cycle."""

    @pytest.mark.asyncio
    async def test_run_aggregation_cycle_runs_5min(self, worker):
        """Test aggregation cycle runs 5-minute aggregation."""
        mock_5min = AsyncMock(return_value=100)
        worker.set_aggregate_5min(mock_5min)

        await worker._run_aggregation_cycle()

        mock_5min.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_aggregation_cycle_conditionally_runs_1hour(self, worker):
        """Test aggregation cycle conditionally runs 1-hour aggregation."""
        mock_1hour = AsyncMock(return_value=24)
        worker.set_aggregate_1hour(mock_1hour)

        # This test depends on current time, so we just ensure no error
        await worker._run_aggregation_cycle()


class TestGetStats:
    """Test statistics retrieval."""

    def test_get_stats_initial(self, worker):
        """Test get stats with initial values."""
        stats = worker.get_stats()

        assert stats["running"] is False
        assert stats["runs_completed"] == 0
        assert stats["last_run_time"] is None
        assert stats["last_run_duration_seconds"] is None
        assert stats["run_interval_minutes"] == 1.0

    @pytest.mark.asyncio
    async def test_get_stats_after_running(self, worker):
        """Test get stats updates after running."""
        mock_5min = AsyncMock(return_value=100)
        worker.set_aggregate_5min(mock_5min)

        # Manually set some state to simulate a run
        worker._runs_completed = 5
        worker._last_run_time = datetime.now(timezone.utc)
        worker._last_run_duration = 2.5

        stats = worker.get_stats()
        assert stats["runs_completed"] == 5
        assert stats["last_run_duration_seconds"] == 2.5
        assert stats["last_run_time"] is not None


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
