"""
Telemetry processing worker.

Processes incoming telemetry from an async queue, validates data,
generates events for anomalies, and forwards to storage.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID

logger = logging.getLogger(__name__)


class TelemetryWorker:
    """
    Background worker for telemetry processing.

    Features:
    - Async queue processing
    - Data validation
    - Anomaly detection
    - Event generation
    - Batch forwarding to storage
    """

    def __init__(
        self,
        queue_size: int = 10000,
        batch_size: int = 100,
        flush_interval: float = 1.0,
    ):
        """
        Initialize the telemetry worker.

        Args:
            queue_size: Maximum queue size.
            batch_size: Batch size for storage writes.
            flush_interval: Interval for batch flushing in seconds.
        """
        self.queue_size = queue_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Async queue
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)

        # Callbacks
        self._store_telemetry: Optional[Callable] = None
        self._create_event: Optional[Callable] = None
        self._get_metric_definitions: Optional[Callable] = None
        self._get_device_config: Optional[Callable] = None

        # Anomaly detection thresholds (per metric)
        self._anomaly_thresholds: Dict[str, Dict[str, float]] = {}

        # Recent values for anomaly detection (device_id -> metric -> values)
        self._recent_values: Dict[UUID, Dict[str, List[float]]] = {}
        self._recent_window_size = 10

        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._flush_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Batch buffer
        self._batch: List[Dict[str, Any]] = []
        self._batch_lock = asyncio.Lock()

        # Stats
        self._telemetry_received = 0
        self._telemetry_processed = 0
        self._telemetry_dropped = 0
        self._anomalies_detected = 0
        self._last_process_time: Optional[datetime] = None

    def set_store_telemetry(self, callback: Callable) -> None:
        """Set callback to store telemetry batch."""
        self._store_telemetry = callback

    def set_create_event(self, callback: Callable) -> None:
        """Set callback to create device events."""
        self._create_event = callback

    def set_get_metric_definitions(self, callback: Callable) -> None:
        """Set callback to get metric definitions."""
        self._get_metric_definitions = callback

    def set_anomaly_thresholds(self, thresholds: Dict[str, Dict[str, float]]) -> None:
        """
        Set anomaly detection thresholds.

        Args:
            thresholds: Dict mapping metric_name -> {min, max, rate_of_change}.
        """
        self._anomaly_thresholds = thresholds

    async def start(self) -> None:
        """Start the telemetry worker."""
        if self._running:
            logger.warning("Telemetry worker already running")
            return

        logger.info("Starting telemetry worker")
        self._running = True
        self._shutdown_event.clear()

        # Start processing task
        self._task = asyncio.create_task(
            self._process_loop(),
            name="telemetry_worker",
        )

        # Start flush task
        self._flush_task = asyncio.create_task(
            self._flush_loop(),
            name="telemetry_flush",
        )

    async def stop(self) -> None:
        """Stop the telemetry worker."""
        if not self._running:
            return

        logger.info("Stopping telemetry worker")
        self._running = False
        self._shutdown_event.set()

        # Cancel tasks
        for task in [self._task, self._flush_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Final flush
        await self._flush_batch()

        logger.info(
            f"Telemetry worker stopped. "
            f"Received: {self._telemetry_received}, "
            f"Processed: {self._telemetry_processed}, "
            f"Dropped: {self._telemetry_dropped}"
        )

    async def submit(
        self,
        device_id: UUID,
        site_id: UUID,
        metrics: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        source: str = "device",
    ) -> bool:
        """
        Submit telemetry for processing.

        Args:
            device_id: Device ID.
            site_id: Site ID.
            metrics: Dictionary of metric name -> value.
            timestamp: Telemetry timestamp.
            source: Data source identifier.

        Returns:
            True if queued successfully.
        """
        if not self._running:
            return False

        self._telemetry_received += 1

        try:
            self._queue.put_nowait({
                "device_id": device_id,
                "site_id": site_id,
                "metrics": metrics,
                "timestamp": timestamp or datetime.now(timezone.utc),
                "source": source,
            })
            return True

        except asyncio.QueueFull:
            self._telemetry_dropped += 1
            logger.warning(f"Telemetry queue full, dropping data for {device_id}")
            return False

    async def _process_loop(self) -> None:
        """Main processing loop."""
        logger.debug("Telemetry processing loop started")

        while self._running:
            try:
                # Get item from queue with timeout
                try:
                    item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue

                # Process the telemetry
                await self._process_telemetry(item)
                self._last_process_time = datetime.now(timezone.utc)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telemetry processing loop: {e}")

        logger.debug("Telemetry processing loop ended")

    async def _process_telemetry(self, item: Dict[str, Any]) -> None:
        """
        Process a single telemetry item.

        Args:
            item: Telemetry data.
        """
        device_id = item["device_id"]
        site_id = item["site_id"]
        metrics = item["metrics"]
        timestamp = item["timestamp"]
        source = item["source"]

        # Validate metrics
        validated_metrics = await self._validate_metrics(metrics)

        # Check for anomalies
        anomalies = self._detect_anomalies(device_id, validated_metrics)

        # Create events for anomalies
        if anomalies and self._create_event:
            for anomaly in anomalies:
                try:
                    await self._create_event(
                        device_id=device_id,
                        site_id=site_id,
                        event_type="telemetry_anomaly",
                        severity="warning",
                        message=anomaly["message"],
                        details=anomaly,
                    )
                    self._anomalies_detected += 1
                except Exception as e:
                    logger.error(f"Failed to create anomaly event: {e}")

        # Add to batch for storage
        async with self._batch_lock:
            for metric_name, value in validated_metrics.items():
                self._batch.append({
                    "device_id": device_id,
                    "site_id": site_id,
                    "metric_name": metric_name,
                    "value": value,
                    "timestamp": timestamp,
                    "source": source,
                })

            # Flush if batch is large enough
            if len(self._batch) >= self.batch_size:
                await self._flush_batch()

        self._telemetry_processed += 1

    async def _validate_metrics(
        self,
        metrics: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        Validate and convert metrics.

        Args:
            metrics: Raw metrics dictionary.

        Returns:
            Validated metrics with numeric values.
        """
        validated = {}

        for name, value in metrics.items():
            # Skip non-numeric values
            if value is None:
                continue

            try:
                numeric_value = float(value)

                # Skip NaN and Inf
                if numeric_value != numeric_value:  # NaN check
                    continue
                if abs(numeric_value) == float("inf"):
                    continue

                validated[name] = numeric_value

            except (TypeError, ValueError):
                # Skip non-convertible values
                pass

        return validated

    def _detect_anomalies(
        self,
        device_id: UUID,
        metrics: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in telemetry data.

        Args:
            device_id: Device ID.
            metrics: Validated metrics.

        Returns:
            List of anomaly details.
        """
        anomalies = []

        # Initialize device history if needed
        if device_id not in self._recent_values:
            self._recent_values[device_id] = {}

        device_history = self._recent_values[device_id]

        for metric_name, value in metrics.items():
            # Get thresholds for this metric
            thresholds = self._anomaly_thresholds.get(metric_name, {})

            if not thresholds:
                # Update history even without thresholds
                if metric_name not in device_history:
                    device_history[metric_name] = []
                device_history[metric_name].append(value)
                if len(device_history[metric_name]) > self._recent_window_size:
                    device_history[metric_name].pop(0)
                continue

            # Check min/max bounds
            min_val = thresholds.get("min")
            max_val = thresholds.get("max")

            if min_val is not None and value < min_val:
                anomalies.append({
                    "metric_name": metric_name,
                    "value": value,
                    "threshold": min_val,
                    "type": "below_minimum",
                    "message": f"{metric_name} ({value}) below minimum threshold ({min_val})",
                })

            if max_val is not None and value > max_val:
                anomalies.append({
                    "metric_name": metric_name,
                    "value": value,
                    "threshold": max_val,
                    "type": "above_maximum",
                    "message": f"{metric_name} ({value}) above maximum threshold ({max_val})",
                })

            # Check rate of change
            rate_threshold = thresholds.get("rate_of_change")
            if rate_threshold is not None:
                if metric_name in device_history and device_history[metric_name]:
                    prev_value = device_history[metric_name][-1]
                    rate = abs(value - prev_value)

                    if rate > rate_threshold:
                        anomalies.append({
                            "metric_name": metric_name,
                            "value": value,
                            "previous_value": prev_value,
                            "rate": rate,
                            "threshold": rate_threshold,
                            "type": "rapid_change",
                            "message": f"{metric_name} changed rapidly ({prev_value} -> {value})",
                        })

            # Update history
            if metric_name not in device_history:
                device_history[metric_name] = []
            device_history[metric_name].append(value)
            if len(device_history[metric_name]) > self._recent_window_size:
                device_history[metric_name].pop(0)

        return anomalies

    async def _flush_loop(self) -> None:
        """Periodic flush loop."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    async def _flush_batch(self) -> None:
        """Flush current batch to storage."""
        async with self._batch_lock:
            if not self._batch or not self._store_telemetry:
                return

            batch = self._batch
            self._batch = []

        try:
            await self._store_telemetry(batch)
            logger.debug(f"Flushed {len(batch)} telemetry records")
        except Exception as e:
            logger.error(f"Error flushing telemetry batch: {e}")
            # Put back in batch for retry
            async with self._batch_lock:
                self._batch.extend(batch)

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "queue_capacity": self.queue_size,
            "batch_size": len(self._batch),
            "telemetry_received": self._telemetry_received,
            "telemetry_processed": self._telemetry_processed,
            "telemetry_dropped": self._telemetry_dropped,
            "anomalies_detected": self._anomalies_detected,
            "last_process_time": self._last_process_time.isoformat() if self._last_process_time else None,
            "devices_tracked": len(self._recent_values),
        }

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running

    @property
    def queue_depth(self) -> int:
        """Get current queue depth."""
        return self._queue.qsize()
