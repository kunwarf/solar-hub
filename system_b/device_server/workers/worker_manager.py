"""
Worker manager for coordinating background workers.

Provides centralized lifecycle management and monitoring
for all background workers.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .command_worker import CommandWorker
from .aggregation_worker import AggregationWorker
from .telemetry_worker import TelemetryWorker

logger = logging.getLogger(__name__)


class WorkerManager:
    """
    Manages lifecycle of all background workers.

    Provides:
    - Centralized start/stop
    - Health monitoring
    - Statistics aggregation
    """

    def __init__(
        self,
        command_worker: Optional[CommandWorker] = None,
        aggregation_worker: Optional[AggregationWorker] = None,
        telemetry_worker: Optional[TelemetryWorker] = None,
    ):
        """
        Initialize the worker manager.

        Args:
            command_worker: Command execution worker.
            aggregation_worker: Telemetry aggregation worker.
            telemetry_worker: Telemetry processing worker.
        """
        self.command_worker = command_worker or CommandWorker()
        self.aggregation_worker = aggregation_worker or AggregationWorker()
        self.telemetry_worker = telemetry_worker or TelemetryWorker()

        self._running = False
        self._started_at: Optional[datetime] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._health_check_interval = 60  # seconds

        # Health status
        self._health_status: Dict[str, bool] = {
            "command_worker": False,
            "aggregation_worker": False,
            "telemetry_worker": False,
        }

    async def start_all(self) -> None:
        """Start all workers."""
        if self._running:
            logger.warning("Worker manager already running")
            return

        logger.info("Starting all workers")
        self._running = True
        self._started_at = datetime.now(timezone.utc)

        # Start workers in order
        await self.telemetry_worker.start()
        await self.command_worker.start()
        await self.aggregation_worker.start()

        # Start health check
        self._health_check_task = asyncio.create_task(
            self._health_check_loop(),
            name="worker_health_check",
        )

        self._update_health_status()
        logger.info("All workers started")

    async def stop_all(self) -> None:
        """Stop all workers."""
        if not self._running:
            return

        logger.info("Stopping all workers")
        self._running = False

        # Stop health check
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Stop workers in reverse order
        await self.aggregation_worker.stop()
        await self.command_worker.stop()
        await self.telemetry_worker.stop()

        logger.info("All workers stopped")

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                self._update_health_status()

                # Log warnings for unhealthy workers
                for worker_name, is_healthy in self._health_status.items():
                    if not is_healthy:
                        logger.warning(f"Worker unhealthy: {worker_name}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}")

    def _update_health_status(self) -> None:
        """Update health status for all workers."""
        self._health_status = {
            "command_worker": self.command_worker.is_running,
            "aggregation_worker": self.aggregation_worker.is_running,
            "telemetry_worker": self.telemetry_worker.is_running,
        }

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of all workers.

        Returns:
            Health status dictionary.
        """
        self._update_health_status()

        all_healthy = all(self._health_status.values())

        return {
            "healthy": all_healthy,
            "status": "running" if self._running else "stopped",
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self._started_at).total_seconds()
                if self._started_at else 0
            ),
            "workers": self._health_status,
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics from all workers.

        Returns:
            Combined statistics dictionary.
        """
        return {
            "manager": {
                "running": self._running,
                "started_at": self._started_at.isoformat() if self._started_at else None,
            },
            "command_worker": self.command_worker.get_stats(),
            "aggregation_worker": self.aggregation_worker.get_stats(),
            "telemetry_worker": self.telemetry_worker.get_stats(),
        }

    @property
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running

    @property
    def is_healthy(self) -> bool:
        """Check if all workers are healthy."""
        self._update_health_status()
        return all(self._health_status.values())

    # Convenience access to workers

    async def submit_telemetry(self, *args, **kwargs) -> bool:
        """Submit telemetry to the telemetry worker."""
        return await self.telemetry_worker.submit(*args, **kwargs)

    def get_telemetry_queue_depth(self) -> int:
        """Get telemetry queue depth."""
        return self.telemetry_worker.queue_depth

    async def run_manual_aggregation(self, *args, **kwargs) -> int:
        """Run manual aggregation."""
        return await self.aggregation_worker.run_manual_aggregation(*args, **kwargs)
