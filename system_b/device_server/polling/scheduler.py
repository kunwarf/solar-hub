"""
Polling scheduler for device telemetry collection.

Manages polling tasks for all connected devices with
configurable intervals and failure handling.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from ..config import DeviceServerSettings, get_device_server_settings
from ..devices.device_state import DeviceState, DeviceStatus
from ..devices.device_manager import DeviceManager
from .telemetry_collector import TelemetryCollector, TelemetryProcessor

logger = logging.getLogger(__name__)


class PollingScheduler:
    """
    Manages telemetry polling for all devices.

    Features:
    - Configurable per-device intervals
    - Async task management
    - Retry on transient failures
    - Backoff on repeated failures
    """

    def __init__(
        self,
        device_manager: DeviceManager,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the polling scheduler.

        Args:
            device_manager: Device manager instance.
            settings: Server settings.
        """
        self.device_manager = device_manager
        self.settings = settings or get_device_server_settings()

        # Create collector and processor
        self.collector = TelemetryCollector(device_manager, settings)
        self.processor = TelemetryProcessor()

        # Polling tasks per device
        self._poll_tasks: Dict[UUID, asyncio.Task] = {}

        # Callbacks
        self._on_telemetry: Optional[Callable] = None
        self._on_poll_error: Optional[Callable] = None
        self._on_device_offline: Optional[Callable] = None

        # State
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the polling scheduler."""
        logger.info("Starting polling scheduler")
        self._running = True
        self._shutdown_event.clear()

    async def stop(self) -> None:
        """Stop the polling scheduler."""
        logger.info("Stopping polling scheduler")
        self._running = False
        self._shutdown_event.set()

        # Cancel all polling tasks
        for device_id, task in list(self._poll_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._poll_tasks.clear()
        logger.info("Polling scheduler stopped")

    async def schedule_polling(self, device_id: UUID) -> None:
        """
        Start polling for a device.

        Args:
            device_id: Device ID to start polling.
        """
        if not self._running:
            logger.warning("Scheduler not running, cannot schedule polling")
            return

        device_state = self.device_manager.get_device(device_id)
        if not device_state:
            logger.error(f"Device {device_id} not found")
            return

        # Cancel existing task if any
        await self.cancel_polling(device_id)

        # Create new polling task
        task = asyncio.create_task(
            self._poll_loop(device_id),
            name=f"poll_{device_id}",
        )
        self._poll_tasks[device_id] = task

        logger.info(
            f"Scheduled polling for {device_id} "
            f"(interval={device_state.poll_interval}s)"
        )

    async def cancel_polling(self, device_id: UUID) -> None:
        """
        Cancel polling for a device.

        Args:
            device_id: Device ID to stop polling.
        """
        task = self._poll_tasks.pop(device_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.debug(f"Cancelled polling for {device_id}")

    async def _poll_loop(self, device_id: UUID) -> None:
        """
        Continuous polling loop for a device.

        Args:
            device_id: Device to poll.
        """
        logger.debug(f"Starting poll loop for {device_id}")

        while self._running:
            device_state = self.device_manager.get_device(device_id)
            if not device_state:
                logger.info(f"Device {device_id} removed, stopping poll loop")
                break

            try:
                # Collect telemetry
                success, telemetry, error = await self.collector.collect(device_id)

                if success and telemetry:
                    # Process telemetry
                    processed = self.processor.process(
                        telemetry, device_state.device_type
                    )

                    # Trigger callback
                    if self._on_telemetry:
                        try:
                            await self._on_telemetry(device_id, processed)
                        except Exception as e:
                            logger.error(f"Error in telemetry callback: {e}")

                else:
                    # Handle failure
                    if self._on_poll_error:
                        try:
                            await self._on_poll_error(device_id, error)
                        except Exception as e:
                            logger.error(f"Error in poll_error callback: {e}")

                    # Check for too many failures
                    if self._should_mark_offline(device_state):
                        await self._handle_device_offline(device_id, device_state)
                        break

                # Calculate next poll interval (with backoff if needed)
                interval = self._calculate_interval(device_state)

                # Wait for next poll
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=interval,
                    )
                    # Shutdown event was set
                    break
                except asyncio.TimeoutError:
                    # Normal timeout, continue polling
                    pass

            except asyncio.CancelledError:
                logger.debug(f"Poll loop cancelled for {device_id}")
                break
            except Exception as e:
                logger.error(f"Unexpected error in poll loop for {device_id}: {e}")
                await asyncio.sleep(5)  # Brief pause before retry

        logger.debug(f"Poll loop ended for {device_id}")

    def _should_mark_offline(self, device_state: DeviceState) -> bool:
        """
        Check if device should be marked offline.

        Args:
            device_state: Device state.

        Returns:
            True if device should be marked offline.
        """
        return (
            device_state.consecutive_failures >=
            self.settings.polling.max_consecutive_failures
        )

    async def _handle_device_offline(
        self,
        device_id: UUID,
        device_state: DeviceState,
    ) -> None:
        """
        Handle device going offline.

        Args:
            device_id: Device ID.
            device_state: Device state.
        """
        logger.warning(
            f"Device {device_id} marked offline after "
            f"{device_state.consecutive_failures} consecutive failures"
        )

        await self.device_manager.mark_device_offline(
            device_id,
            f"Too many poll failures ({device_state.consecutive_failures})",
        )

        if self._on_device_offline:
            try:
                await self._on_device_offline(device_id, device_state)
            except Exception as e:
                logger.error(f"Error in device_offline callback: {e}")

    def _calculate_interval(self, device_state: DeviceState) -> float:
        """
        Calculate next poll interval.

        Implements exponential backoff on failures.

        Args:
            device_state: Device state.

        Returns:
            Interval in seconds.
        """
        base_interval = device_state.poll_interval

        if not self.settings.polling.failure_backoff:
            return base_interval

        failures = device_state.consecutive_failures

        if failures == 0:
            return base_interval

        # Exponential backoff: interval * 2^failures
        backoff = min(
            base_interval * (2 ** failures),
            self.settings.polling.max_interval,
        )

        return max(backoff, self.settings.polling.min_interval)

    def update_poll_interval(
        self,
        device_id: UUID,
        interval: int,
    ) -> bool:
        """
        Update polling interval for a device.

        Args:
            device_id: Device ID.
            interval: New interval in seconds.

        Returns:
            True if updated successfully.
        """
        device_state = self.device_manager.get_device(device_id)
        if not device_state:
            return False

        # Validate interval
        interval = max(
            self.settings.polling.min_interval,
            min(interval, self.settings.polling.max_interval),
        )

        device_state.poll_interval = interval
        logger.info(f"Updated poll interval for {device_id} to {interval}s")

        return True

    def get_polling_stats(self) -> Dict[str, Any]:
        """
        Get polling statistics.

        Returns:
            Dictionary of polling stats.
        """
        active_tasks = sum(
            1 for task in self._poll_tasks.values()
            if not task.done()
        )

        return {
            "running": self._running,
            "active_tasks": active_tasks,
            "total_tasks": len(self._poll_tasks),
        }

    def set_on_telemetry(self, callback: Callable) -> None:
        """Set callback for telemetry events."""
        self._on_telemetry = callback

    def set_on_poll_error(self, callback: Callable) -> None:
        """Set callback for poll error events."""
        self._on_poll_error = callback

    def set_on_device_offline(self, callback: Callable) -> None:
        """Set callback for device offline events."""
        self._on_device_offline = callback

    def is_polling(self, device_id: UUID) -> bool:
        """
        Check if device is being polled.

        Args:
            device_id: Device ID.

        Returns:
            True if polling is active.
        """
        task = self._poll_tasks.get(device_id)
        return task is not None and not task.done()

    def get_polling_devices(self) -> List[UUID]:
        """
        Get list of devices being polled.

        Returns:
            List of device IDs.
        """
        return [
            device_id
            for device_id, task in self._poll_tasks.items()
            if not task.done()
        ]
