"""
Unit tests for WorkerManager.

Tests worker lifecycle management, health monitoring, and statistics.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from device_server.workers.worker_manager import WorkerManager
from device_server.workers.command_worker import CommandWorker
from device_server.workers.aggregation_worker import AggregationWorker
from device_server.workers.telemetry_worker import TelemetryWorker


@pytest.fixture
def mock_command_worker():
    """Create a mock command worker."""
    worker = MagicMock(spec=CommandWorker)
    worker.start = AsyncMock()
    worker.stop = AsyncMock()
    worker.is_running = True
    worker.get_stats = MagicMock(return_value={
        "running": True,
        "commands_processed": 10,
        "commands_failed": 1,
    })
    return worker


@pytest.fixture
def mock_aggregation_worker():
    """Create a mock aggregation worker."""
    worker = MagicMock(spec=AggregationWorker)
    worker.start = AsyncMock()
    worker.stop = AsyncMock()
    worker.is_running = True
    worker.run_manual_aggregation = AsyncMock(return_value=50)
    worker.get_stats = MagicMock(return_value={
        "running": True,
        "runs_completed": 5,
    })
    return worker


@pytest.fixture
def mock_telemetry_worker():
    """Create a mock telemetry worker."""
    worker = MagicMock(spec=TelemetryWorker)
    worker.start = AsyncMock()
    worker.stop = AsyncMock()
    worker.is_running = True
    worker.submit = AsyncMock(return_value=True)
    worker.queue_depth = 100
    worker.get_stats = MagicMock(return_value={
        "running": True,
        "telemetry_received": 1000,
        "telemetry_processed": 999,
    })
    return worker


@pytest.fixture
def manager(mock_command_worker, mock_aggregation_worker, mock_telemetry_worker):
    """Create a WorkerManager with mock workers."""
    return WorkerManager(
        command_worker=mock_command_worker,
        aggregation_worker=mock_aggregation_worker,
        telemetry_worker=mock_telemetry_worker,
    )


class TestWorkerManagerInit:
    """Test manager initialization."""

    def test_init_with_default_workers(self):
        """Test manager creates default workers."""
        manager = WorkerManager()
        assert isinstance(manager.command_worker, CommandWorker)
        assert isinstance(manager.aggregation_worker, AggregationWorker)
        assert isinstance(manager.telemetry_worker, TelemetryWorker)
        assert manager._running is False

    def test_init_with_custom_workers(
        self, mock_command_worker, mock_aggregation_worker, mock_telemetry_worker
    ):
        """Test manager uses provided workers."""
        manager = WorkerManager(
            command_worker=mock_command_worker,
            aggregation_worker=mock_aggregation_worker,
            telemetry_worker=mock_telemetry_worker,
        )
        assert manager.command_worker == mock_command_worker
        assert manager.aggregation_worker == mock_aggregation_worker
        assert manager.telemetry_worker == mock_telemetry_worker


class TestStartAll:
    """Test starting all workers."""

    @pytest.mark.asyncio
    async def test_start_all_sets_running(self, manager):
        """Test start_all sets running flag."""
        await manager.start_all()

        assert manager._running is True
        assert manager.is_running is True

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_start_all_starts_all_workers(
        self, manager, mock_command_worker, mock_aggregation_worker, mock_telemetry_worker
    ):
        """Test start_all starts all workers."""
        await manager.start_all()

        mock_telemetry_worker.start.assert_called_once()
        mock_command_worker.start.assert_called_once()
        mock_aggregation_worker.start.assert_called_once()

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_start_all_records_start_time(self, manager):
        """Test start_all records start time."""
        before = datetime.now(timezone.utc)
        await manager.start_all()
        after = datetime.now(timezone.utc)

        assert manager._started_at is not None
        assert before <= manager._started_at <= after

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_start_all_when_already_running(self, manager):
        """Test start_all does nothing when already running."""
        await manager.start_all()
        await manager.start_all()  # Should not raise

        assert manager._running is True
        await manager.stop_all()


class TestStopAll:
    """Test stopping all workers."""

    @pytest.mark.asyncio
    async def test_stop_all_clears_running(self, manager):
        """Test stop_all clears running flag."""
        await manager.start_all()
        await manager.stop_all()

        assert manager._running is False
        assert manager.is_running is False

    @pytest.mark.asyncio
    async def test_stop_all_stops_all_workers(
        self, manager, mock_command_worker, mock_aggregation_worker, mock_telemetry_worker
    ):
        """Test stop_all stops all workers in reverse order."""
        await manager.start_all()
        await manager.stop_all()

        mock_aggregation_worker.stop.assert_called_once()
        mock_command_worker.stop.assert_called_once()
        mock_telemetry_worker.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_all_when_not_running(self, manager):
        """Test stop_all does nothing when not running."""
        await manager.stop_all()  # Should not raise
        assert manager._running is False


class TestHealthCheck:
    """Test health checking."""

    @pytest.mark.asyncio
    async def test_update_health_status(self, manager):
        """Test health status is updated."""
        await manager.start_all()
        manager._update_health_status()

        assert manager._health_status["command_worker"] is True
        assert manager._health_status["aggregation_worker"] is True
        assert manager._health_status["telemetry_worker"] is True

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_get_health_all_healthy(self, manager):
        """Test get health when all workers are healthy."""
        await manager.start_all()

        health = manager.get_health()

        assert health["healthy"] is True
        assert health["status"] == "running"
        assert health["started_at"] is not None
        assert health["uptime_seconds"] >= 0
        assert health["workers"]["command_worker"] is True
        assert health["workers"]["aggregation_worker"] is True
        assert health["workers"]["telemetry_worker"] is True

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_get_health_unhealthy_worker(
        self, manager, mock_command_worker
    ):
        """Test get health when a worker is unhealthy."""
        await manager.start_all()

        # Simulate unhealthy worker
        mock_command_worker.is_running = False

        health = manager.get_health()

        assert health["healthy"] is False
        assert health["workers"]["command_worker"] is False

        await manager.stop_all()

    def test_get_health_when_stopped(self, manager):
        """Test get health when manager is stopped."""
        health = manager.get_health()

        assert health["healthy"] is False
        assert health["status"] == "stopped"
        assert health["started_at"] is None
        assert health["uptime_seconds"] == 0


class TestGetStats:
    """Test statistics retrieval."""

    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        """Test get stats returns all worker stats."""
        await manager.start_all()

        stats = manager.get_stats()

        assert "manager" in stats
        assert "command_worker" in stats
        assert "aggregation_worker" in stats
        assert "telemetry_worker" in stats

        assert stats["manager"]["running"] is True
        assert stats["command_worker"]["commands_processed"] == 10
        assert stats["aggregation_worker"]["runs_completed"] == 5
        assert stats["telemetry_worker"]["telemetry_received"] == 1000

        await manager.stop_all()

    def test_get_stats_when_stopped(self, manager):
        """Test get stats when manager is stopped."""
        stats = manager.get_stats()

        assert stats["manager"]["running"] is False
        assert stats["manager"]["started_at"] is None


class TestIsRunning:
    """Test is_running property."""

    def test_is_running_initially_false(self, manager):
        """Test is_running is False initially."""
        assert manager.is_running is False

    @pytest.mark.asyncio
    async def test_is_running_after_start(self, manager):
        """Test is_running after start."""
        await manager.start_all()
        assert manager.is_running is True
        await manager.stop_all()


class TestIsHealthy:
    """Test is_healthy property."""

    @pytest.mark.asyncio
    async def test_is_healthy_when_all_running(self, manager):
        """Test is_healthy when all workers running."""
        await manager.start_all()
        assert manager.is_healthy is True
        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_is_healthy_when_worker_stopped(
        self, manager, mock_command_worker
    ):
        """Test is_healthy when a worker is stopped."""
        await manager.start_all()

        # Simulate stopped worker
        mock_command_worker.is_running = False

        assert manager.is_healthy is False
        await manager.stop_all()


class TestConvenienceMethods:
    """Test convenience methods."""

    @pytest.mark.asyncio
    async def test_submit_telemetry(self, manager, mock_telemetry_worker):
        """Test submit_telemetry delegates to telemetry worker."""
        device_id = uuid4()
        site_id = uuid4()
        metrics = {"battery_soc_pct": 75.0}

        result = await manager.submit_telemetry(device_id, site_id, metrics)

        assert result is True
        mock_telemetry_worker.submit.assert_called_once_with(
            device_id, site_id, metrics
        )

    def test_get_telemetry_queue_depth(self, manager, mock_telemetry_worker):
        """Test get_telemetry_queue_depth delegates to telemetry worker."""
        depth = manager.get_telemetry_queue_depth()

        assert depth == 100

    @pytest.mark.asyncio
    async def test_run_manual_aggregation(self, manager, mock_aggregation_worker):
        """Test run_manual_aggregation delegates to aggregation worker."""
        start_time = datetime.now(timezone.utc) - timedelta(hours=24)
        end_time = datetime.now(timezone.utc)

        result = await manager.run_manual_aggregation(
            start_time=start_time,
            end_time=end_time,
        )

        assert result == 50
        mock_aggregation_worker.run_manual_aggregation.assert_called_once_with(
            start_time=start_time,
            end_time=end_time,
        )


class TestHealthCheckLoop:
    """Test health check loop."""

    @pytest.mark.asyncio
    async def test_health_check_loop_runs(self, manager):
        """Test health check loop runs when started."""
        # Use short interval for testing
        manager._health_check_interval = 0.1

        await manager.start_all()
        await asyncio.sleep(0.15)  # Let one health check run
        await manager.stop_all()

        # Health status should have been updated


class TestWorkerStartOrder:
    """Test worker start/stop order."""

    @pytest.mark.asyncio
    async def test_workers_start_in_correct_order(
        self, manager, mock_command_worker, mock_aggregation_worker, mock_telemetry_worker
    ):
        """Test workers start in telemetry, command, aggregation order."""
        call_order = []

        async def record_telemetry_start():
            call_order.append("telemetry")

        async def record_command_start():
            call_order.append("command")

        async def record_aggregation_start():
            call_order.append("aggregation")

        mock_telemetry_worker.start = AsyncMock(side_effect=record_telemetry_start)
        mock_command_worker.start = AsyncMock(side_effect=record_command_start)
        mock_aggregation_worker.start = AsyncMock(side_effect=record_aggregation_start)

        await manager.start_all()

        assert call_order == ["telemetry", "command", "aggregation"]

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_workers_stop_in_reverse_order(
        self, manager, mock_command_worker, mock_aggregation_worker, mock_telemetry_worker
    ):
        """Test workers stop in aggregation, command, telemetry order."""
        call_order = []

        async def record_telemetry_stop():
            call_order.append("telemetry")

        async def record_command_stop():
            call_order.append("command")

        async def record_aggregation_stop():
            call_order.append("aggregation")

        mock_telemetry_worker.stop = AsyncMock(side_effect=record_telemetry_stop)
        mock_command_worker.stop = AsyncMock(side_effect=record_command_stop)
        mock_aggregation_worker.stop = AsyncMock(side_effect=record_aggregation_stop)

        await manager.start_all()
        await manager.stop_all()

        assert call_order == ["aggregation", "command", "telemetry"]
