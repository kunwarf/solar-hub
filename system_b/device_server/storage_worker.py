"""
StorageWorker — Phase 3 of the multi-process pipeline.

Reads raw telemetry from the 'telemetry:raw' Redis Stream and writes it to
TimescaleDB and the Redis cache, independently of the main Device Server process.

Phase 3 (current): Shadow mode — the main process still performs its own writes.
Both write the same data; TimescaleDB and Redis cache writes are idempotent so
double-writing is safe. Run this alongside the main process to verify correctness.

Phase 4 will disable writes from the main process, leaving this worker as the
sole storage path.

Run as standalone process:
    python -m app.device_server.storage_worker

Or import and use programmatically:
    worker = StorageWorker()
    await worker.start()
    await worker.run_forever()
    await worker.stop()
"""
import asyncio
import logging
import signal
import sys
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
CONSUMER_NAME = "worker-0"   # Change to worker-1, worker-2 etc for multiple instances
BATCH_SIZE = 50
STALE_RECLAIM_IDLE_MS = 60_000   # Reclaim messages idle > 60 s


class StorageWorker:
    """
    Consumes telemetry from the Redis Stream and writes to TimescaleDB + Redis cache.

    Shadow mode (Phase 3): runs in parallel with the main Device Server writes.
    The main process writes are authoritative; this worker verifies identical results.
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

        # Stats
        self._processed = 0
        self._failed = 0
        self._cache_hits = 0

    async def start(self) -> None:
        """Connect to all backends and prepare the consumer group."""
        logger.info("StorageWorker starting (consumer=%s)...", self._consumer_name)

        self._timescale = TimescaleWriter(self.settings)
        self._redis_cache = TelemetryCacheWriter(self.settings)
        self._registry = DeviceRegistryClient(self.settings)

        await self._timescale.connect()
        await self._redis_cache.connect()
        try:
            await self._registry.connect()
        except Exception as exc:
            logger.warning("Registry connection failed: %s — device_id lookups disabled", exc)

        # Create consumer group if not already present.
        # Use "0" so on restart we replay any unacknowledged messages.
        self._consumer = StreamConsumer(
            redis_client=self._redis_cache._client,
            group=CONSUMER_GROUP,
            consumer=self._consumer_name,
        )
        await self._consumer.ensure_group(start_id="0")

        # Reclaim messages that were in-flight when the last worker crashed
        await self._consumer.reclaim_stale(min_idle_ms=STALE_RECLAIM_IDLE_MS)

        self._running = True
        logger.info(
            "StorageWorker started — listening on telemetry:raw (group=%s, consumer=%s)",
            CONSUMER_GROUP,
            self._consumer_name,
        )

    async def stop(self) -> None:
        """Flush pending writes and disconnect."""
        if not self._running:
            return
        self._running = False
        self._shutdown_event.set()
        logger.info(
            "StorageWorker stopping — processed=%d, failed=%d",
            self._processed,
            self._failed,
        )

        if self._timescale:
            await self._timescale.disconnect()
        if self._redis_cache:
            await self._redis_cache.disconnect()
        if self._registry:
            await self._registry.disconnect()

        logger.info("StorageWorker stopped")

    async def run_forever(self) -> None:
        """Main consume loop — runs until stop() is called."""
        while self._running:
            try:
                await self._consume_batch()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("StorageWorker: unexpected error in consume loop")
                await asyncio.sleep(1)

    async def _consume_batch(self) -> None:
        """Read one batch from the stream and process each message."""
        async for msg_id, fields in self._consumer.read_batch(batch_size=BATCH_SIZE):
            await self._handle_message(msg_id, fields)

    async def _handle_message(self, msg_id: str, fields: dict) -> None:
        """Process a single stream message: write to TimescaleDB + Redis, then ack."""
        device_serial: str = fields["device_serial"]
        device_type: str = fields["device_type"]
        payload: dict = fields["payload"]

        try:
            # --- TimescaleDB write ---
            device_id = await self._resolve_device_id(device_serial)
            if device_id and self._timescale:
                await self._timescale.write(device_id, payload.copy())
            elif not device_id:
                logger.debug(
                    "StorageWorker: no device_id for serial %s — skipping TimescaleDB write",
                    device_serial,
                )

            # --- Redis cache write ---
            if self._redis_cache and device_serial:
                await self._redis_cache.write_telemetry(device_serial, payload.copy())

            self._processed += 1

        except Exception:
            self._failed += 1
            logger.exception(
                "StorageWorker: error handling message %s for device %s",
                msg_id,
                device_serial,
            )
            # Ack anyway to avoid poison-pill loop. A real production setup
            # would move to a dead-letter stream instead.

        await self._consumer.ack(msg_id)

    async def _resolve_device_id(self, serial: str) -> Optional[UUID]:
        """
        Return the device_id UUID for a given serial number.

        Caches results in memory (device list is bounded and changes rarely).
        Returns None if registry is unavailable or serial is not found.
        """
        if serial in self._device_id_cache:
            self._cache_hits += 1
            return self._device_id_cache[serial]

        device_id: Optional[UUID] = None
        if self._registry:
            info = await self._registry.get_device_by_serial(serial)
            if info:
                device_id = info["device_id"]

        self._device_id_cache[serial] = device_id
        return device_id

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "consumer": self._consumer_name,
            "processed": self._processed,
            "failed": self._failed,
            "cache_hits": self._cache_hits,
            "device_id_cache_size": len(self._device_id_cache),
        }


def _setup_signals(worker: StorageWorker, loop: asyncio.AbstractEventLoop) -> None:
    def _handle():
        logger.info("Received shutdown signal")
        loop.create_task(worker.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: _handle())


async def main() -> None:
    """Entry point for running as a standalone process."""
    import os
    consumer_name = os.environ.get("STORAGE_WORKER_NAME", CONSUMER_NAME)

    worker = StorageWorker(consumer_name=consumer_name)
    loop = asyncio.get_event_loop()
    _setup_signals(worker, loop)

    try:
        await worker.start()
        await worker.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
