"""
Telemetry aggregation worker.

Periodically aggregates raw telemetry data into time buckets
for efficient querying and historical analysis.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class AggregationWorker:
    """
    Background worker for telemetry aggregation.

    Creates time-bucketed aggregates from raw telemetry data:
    - 5-minute aggregates (kept 7 days)
    - 1-hour aggregates (kept 90 days)
    - 1-day aggregates (kept forever)
    """

    def __init__(
        self,
        run_interval_minutes: int = 5,
        aggregation_delay_minutes: int = 2,
    ):
        """
        Initialize the aggregation worker.

        Args:
            run_interval_minutes: How often to run aggregation.
            aggregation_delay_minutes: Delay before aggregating recent data.
        """
        self.run_interval = timedelta(minutes=run_interval_minutes)
        self.aggregation_delay = timedelta(minutes=aggregation_delay_minutes)

        # Database callbacks
        self._aggregate_5min: Optional[Callable] = None
        self._aggregate_1hour: Optional[Callable] = None
        self._aggregate_1day: Optional[Callable] = None
        self._cleanup_old_aggregates: Optional[Callable] = None
        self._get_devices_with_telemetry: Optional[Callable] = None

        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Stats
        self._runs_completed = 0
        self._last_run_time: Optional[datetime] = None
        self._last_run_duration: Optional[float] = None

    def set_aggregate_5min(self, callback: Callable) -> None:
        """Set callback for 5-minute aggregation."""
        self._aggregate_5min = callback

    def set_aggregate_1hour(self, callback: Callable) -> None:
        """Set callback for 1-hour aggregation."""
        self._aggregate_1hour = callback

    def set_aggregate_1day(self, callback: Callable) -> None:
        """Set callback for 1-day aggregation."""
        self._aggregate_1day = callback

    def set_cleanup_old_aggregates(self, callback: Callable) -> None:
        """Set callback for cleaning old aggregates."""
        self._cleanup_old_aggregates = callback

    def set_get_devices_with_telemetry(self, callback: Callable) -> None:
        """Set callback to get devices with recent telemetry."""
        self._get_devices_with_telemetry = callback

    async def start(self) -> None:
        """Start the aggregation worker."""
        if self._running:
            logger.warning("Aggregation worker already running")
            return

        logger.info("Starting aggregation worker")
        self._running = True
        self._shutdown_event.clear()

        self._task = asyncio.create_task(
            self._run_loop(),
            name="aggregation_worker",
        )

    async def stop(self) -> None:
        """Stop the aggregation worker."""
        if not self._running:
            return

        logger.info("Stopping aggregation worker")
        self._running = False
        self._shutdown_event.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info(f"Aggregation worker stopped. Runs completed: {self._runs_completed}")

    async def _run_loop(self) -> None:
        """Main aggregation loop."""
        logger.debug("Aggregation worker loop started")

        while self._running:
            try:
                start_time = datetime.now(timezone.utc)
                self._last_run_time = start_time

                # Run aggregations
                await self._run_aggregation_cycle()

                # Calculate duration
                self._last_run_duration = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds()

                self._runs_completed += 1

                logger.debug(
                    f"Aggregation cycle completed in {self._last_run_duration:.2f}s"
                )

                # Wait for next cycle
                remaining = self.run_interval.total_seconds() - self._last_run_duration
                if remaining > 0:
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=remaining,
                        )
                        break  # Shutdown requested
                    except asyncio.TimeoutError:
                        pass  # Normal timeout

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aggregation worker loop: {e}")
                await asyncio.sleep(60)  # Longer pause on error

        logger.debug("Aggregation worker loop ended")

    async def _run_aggregation_cycle(self) -> None:
        """Run a complete aggregation cycle."""
        now = datetime.now(timezone.utc)

        # Calculate time ranges (with delay to allow data to settle)
        end_time = now - self.aggregation_delay

        # 5-minute aggregation (last hour)
        if self._aggregate_5min:
            await self._run_5min_aggregation(end_time)

        # 1-hour aggregation (once per hour, on the hour)
        if self._aggregate_1hour and now.minute < 10:
            await self._run_1hour_aggregation(end_time)

        # 1-day aggregation (once per day, after midnight)
        if self._aggregate_1day and now.hour == 1 and now.minute < 10:
            await self._run_1day_aggregation(end_time)

        # Cleanup old aggregates (once per day)
        if self._cleanup_old_aggregates and now.hour == 2 and now.minute < 10:
            await self._run_cleanup()

    async def _run_5min_aggregation(self, end_time: datetime) -> None:
        """Run 5-minute aggregation."""
        try:
            start_time = end_time - timedelta(hours=1)

            logger.debug(f"Running 5-minute aggregation: {start_time} to {end_time}")

            count = await self._aggregate_5min(
                start_time=start_time,
                end_time=end_time,
                bucket_interval="5 minutes",
            )

            logger.debug(f"Created {count} 5-minute aggregates")

        except Exception as e:
            logger.error(f"Error in 5-minute aggregation: {e}")

    async def _run_1hour_aggregation(self, end_time: datetime) -> None:
        """Run 1-hour aggregation."""
        try:
            # Aggregate the previous 2 hours
            start_time = end_time - timedelta(hours=2)

            logger.debug(f"Running 1-hour aggregation: {start_time} to {end_time}")

            count = await self._aggregate_1hour(
                start_time=start_time,
                end_time=end_time,
                bucket_interval="1 hour",
            )

            logger.debug(f"Created {count} 1-hour aggregates")

        except Exception as e:
            logger.error(f"Error in 1-hour aggregation: {e}")

    async def _run_1day_aggregation(self, end_time: datetime) -> None:
        """Run 1-day aggregation."""
        try:
            # Aggregate the previous 2 days
            start_time = end_time - timedelta(days=2)

            logger.debug(f"Running 1-day aggregation: {start_time} to {end_time}")

            count = await self._aggregate_1day(
                start_time=start_time,
                end_time=end_time,
                bucket_interval="1 day",
            )

            logger.debug(f"Created {count} 1-day aggregates")

        except Exception as e:
            logger.error(f"Error in 1-day aggregation: {e}")

    async def _run_cleanup(self) -> None:
        """Run cleanup of old aggregates."""
        try:
            logger.debug("Running aggregate cleanup")

            deleted = await self._cleanup_old_aggregates()

            logger.info(f"Cleaned up {deleted} old aggregate records")

        except Exception as e:
            logger.error(f"Error in aggregate cleanup: {e}")

    async def run_manual_aggregation(
        self,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "1 hour",
    ) -> int:
        """
        Run manual aggregation for a time range.

        Args:
            start_time: Start of range.
            end_time: End of range.
            bucket_interval: Aggregation bucket interval.

        Returns:
            Number of aggregates created.
        """
        if not self._aggregate_1hour:
            return 0

        try:
            count = await self._aggregate_1hour(
                start_time=start_time,
                end_time=end_time,
                bucket_interval=bucket_interval,
            )

            logger.info(
                f"Manual aggregation: created {count} aggregates "
                f"for {start_time} to {end_time}"
            )

            return count

        except Exception as e:
            logger.error(f"Error in manual aggregation: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "running": self._running,
            "runs_completed": self._runs_completed,
            "last_run_time": self._last_run_time.isoformat() if self._last_run_time else None,
            "last_run_duration_seconds": self._last_run_duration,
            "run_interval_minutes": self.run_interval.total_seconds() / 60,
        }

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
