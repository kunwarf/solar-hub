"""
StorageWorker — Phase 4 of the multi-process pipeline.

Reads raw telemetry from the 'telemetry:raw' Redis Stream and writes it to
TimescaleDB and the Redis cache, independently of the main Device Server process.

Phase 4 (current): Main process delegates TimescaleDB writes here.
Set STORAGE_WORKER_ENABLED=true in .env to activate the cutover in the main process.
Redis cache writes remain in the main process as a safety net.

Managed by: solarhub-storage-worker.service
Log file:   /opt/solarhub/logs/storage-worker.log
"""
import asyncio
import logging
import os
import signal
import sys
import time
from typing import Dict, Optional
from uuid import UUID

from .config import DeviceServerSettings, get_device_server_settings
from .messaging.stream_consumer import StreamConsumer
from .storage.timescale_writer import TimescaleWriter
from .storage.redis_cache import TelemetryCacheWriter
from .storage.device_registry_client import DeviceRegistryClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

CONSUMER_GROUP = "storage-workers"
CONSUMER_NAME = os.environ.get("STORAGE_WORKER_NAME", "worker-0")
BATCH_SIZE = 50
STALE_RECLAIM_IDLE_MS = 60_000   # Reclaim messages idle > 60 s
STATS_LOG_INTERVAL = 60          # Log stats every N seconds


class StorageWorker:
    """
    Consumes telemetry from the 'telemetry:raw' Redis Stream and persists it to
    TimescaleDB and the Redis cache.

    Phase 4: STORAGE_WORKER_ENABLED=true in .env causes the main process to skip
    TimescaleDB writes; this worker becomes the sole TimescaleDB writer.
    """

    def __init__(
        self,
        settings: Optional[DeviceServerSettings] = None,
        consumer_name: str = CONSUMER_NAME,
    ) -> None:
        self.settings = settings or get_device_server_settings()
        self._consumer_name = consumer_name

        self._timescale: Optional[TimescaleWriter] = None
        self._redis_cache: Optional[TelemetryCacheWriter] = None
        self._registry: Optional[DeviceRegistryClient] = None
        self._consumer: Optional[StreamConsumer] = None

        # In-process device_id cache: serial → UUID (avoids registry query every poll)
        self._device_id_cache: Dict[str, Optional[UUID]] = {}

        self._running = False
        self._shutdown_event = asyncio.Event()
        self._stats_task: Optional[asyncio.Task] = None

        # Stats counters
        self._processed = 0
        self._failed = 0
        self._db_writes = 0
        self._cache_writes = 0
        self._no_device_id = 0
        self._stats_start = time.monotonic()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to all backends, prepare consumer group, start stats logger."""
        logger.info(
            "[STORAGE_WORKER] Starting (consumer=%s, group=%s)",
            self._consumer_name,
            CONSUMER_GROUP,
        )

        self._timescale = TimescaleWriter(self.settings)
        self._redis_cache = TelemetryCacheWriter(self.settings)
        self._registry = DeviceRegistryClient(self.settings)

        await self._timescale.connect()
        logger.info("[STORAGE_WORKER] TimescaleDB connected")

        await self._redis_cache.connect()
        logger.info("[STORAGE_WORKER] Redis connected")

        try:
            await self._registry.connect()
            logger.info("[STORAGE_WORKER] Device registry connected")
        except Exception as exc:
            logger.warning(
                "[STORAGE_WORKER] Registry connection failed: %s — device_id lookups disabled",
                exc,
            )

        # Create consumer group (start_id="0" replays unacked messages after crash)
        self._consumer = StreamConsumer(
            redis_client=self._redis_cache._client,
            group=CONSUMER_GROUP,
            consumer=self._consumer_name,
        )
        await self._consumer.ensure_group(start_id="0")

        # Reclaim messages that were in-flight when a previous worker instance crashed
        reclaimed = await self._consumer.reclaim_stale(min_idle_ms=STALE_RECLAIM_IDLE_MS)
        if reclaimed:
            logger.info("[STORAGE_WORKER] Reclaimed %d stale messages from previous run", len(reclaimed))

        self._running = True
        self._stats_start = time.monotonic()

        # Background task: log stats every STATS_LOG_INTERVAL seconds
        self._stats_task = asyncio.create_task(self._stats_loop(), name="storage_worker_stats")

        logger.info(
            "[STORAGE_WORKER] Ready — consuming from stream 'telemetry:raw' "
            "(group=%s, consumer=%s, batch=%d)",
            CONSUMER_GROUP,
            self._consumer_name,
            BATCH_SIZE,
        )

    async def stop(self) -> None:
        """Flush pending TimescaleDB writes and disconnect cleanly."""
        if not self._running:
            return
        self._running = False
        self._shutdown_event.set()

        if self._stats_task:
            self._stats_task.cancel()
            try:
                await self._stats_task
            except asyncio.CancelledError:
                pass

        self._log_stats(final=True)

        if self._timescale:
            await self._timescale.disconnect()
        if self._redis_cache:
            await self._redis_cache.disconnect()
        if self._registry:
            await self._registry.disconnect()

        logger.info("[STORAGE_WORKER] Stopped")

    async def run_forever(self) -> None:
        """Main consume loop — runs until stop() is called."""
        while self._running:
            try:
                await self._consume_batch()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("[STORAGE_WORKER] Unexpected error in consume loop — retrying in 1s")
                await asyncio.sleep(1)

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    async def _consume_batch(self) -> None:
        """Read one batch from the stream and process each message."""
        async for msg_id, fields in self._consumer.read_batch(batch_size=BATCH_SIZE):
            await self._handle_message(msg_id, fields)

    async def _handle_message(self, msg_id: str, fields: dict) -> None:
        """Write one telemetry snapshot to TimescaleDB + Redis, then ack."""
        device_serial: str = fields["device_serial"]
        device_type: str = fields["device_type"]
        payload: dict = fields["payload"]

        try:
            # --- TimescaleDB write ---
            device_id = await self._resolve_device_id(device_serial)
            if device_id and self._timescale:
                await self._timescale.write(device_id, payload.copy())
                self._db_writes += 1
                logger.debug(
                    "[STORAGE_WORKER] DB write: device=%s type=%s device_id=%s",
                    device_serial,
                    device_type,
                    device_id,
                )
            elif not device_id:
                self._no_device_id += 1
                logger.warning(
                    "[STORAGE_WORKER] No device_id for serial=%s — TimescaleDB write skipped "
                    "(device not in registry yet?)",
                    device_serial,
                )

            # --- Redis cache write ---
            if self._redis_cache and device_serial:
                await self._redis_cache.write_telemetry(device_serial, payload.copy())
                self._cache_writes += 1

            self._processed += 1

        except Exception:
            self._failed += 1
            logger.exception(
                "[STORAGE_WORKER] Error processing msg_id=%s device=%s — acking to skip",
                msg_id,
                device_serial,
            )
            # Ack to avoid a poison-pill loop blocking all future messages.

        await self._consumer.ack(msg_id)

    # ------------------------------------------------------------------
    # Device ID resolution
    # ------------------------------------------------------------------

    async def _resolve_device_id(self, serial: str) -> Optional[UUID]:
        """
        Return the device_id UUID for a given serial number.

        Results are cached in memory (bounded: one entry per device, typically < 20).
        Returns None if the registry is unavailable or the serial is not registered.
        """
        if serial in self._device_id_cache:
            return self._device_id_cache[serial]

        device_id: Optional[UUID] = None
        if self._registry:
            info = await self._registry.get_device_by_serial(serial)
            if info:
                device_id = info["device_id"]

        self._device_id_cache[serial] = device_id
        if device_id:
            logger.info(
                "[STORAGE_WORKER] Resolved device_id for serial=%s → %s", serial, device_id
            )
        return device_id

    # ------------------------------------------------------------------
    # Periodic stats
    # ------------------------------------------------------------------

    async def _stats_loop(self) -> None:
        """Log a stats summary every STATS_LOG_INTERVAL seconds."""
        while self._running:
            try:
                await asyncio.sleep(STATS_LOG_INTERVAL)
                self._log_stats()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("[STORAGE_WORKER] Error in stats loop")

    def _log_stats(self, final: bool = False) -> None:
        elapsed = time.monotonic() - self._stats_start
        rate = self._processed / elapsed if elapsed > 0 else 0
        label = "FINAL STATS" if final else "Stats"
        logger.info(
            "[STORAGE_WORKER] %s — processed=%d (%.1f/min) | db_writes=%d | "
            "cache_writes=%d | failed=%d | no_device_id=%d | devices_cached=%d",
            label,
            self._processed,
            rate * 60,
            self._db_writes,
            self._cache_writes,
            self._failed,
            self._no_device_id,
            len(self._device_id_cache),
        )

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "consumer": self._consumer_name,
            "processed": self._processed,
            "db_writes": self._db_writes,
            "cache_writes": self._cache_writes,
            "failed": self._failed,
            "no_device_id": self._no_device_id,
            "devices_cached": len(self._device_id_cache),
        }


# ------------------------------------------------------------------
# Signal handling & entry point
# ------------------------------------------------------------------

def _setup_signals(worker: StorageWorker, loop: asyncio.AbstractEventLoop) -> None:
    def _handle():
        logger.info("[STORAGE_WORKER] Received shutdown signal")
        loop.create_task(worker.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: _handle())


async def main() -> None:
    """Entry point for running as a standalone process."""
    worker = StorageWorker()
    loop = asyncio.get_event_loop()
    _setup_signals(worker, loop)

    try:
        await worker.start()
        await worker.run_forever()
    except KeyboardInterrupt:
        logger.info("[STORAGE_WORKER] Interrupted")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
