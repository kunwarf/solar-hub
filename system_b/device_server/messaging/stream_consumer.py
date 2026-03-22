"""
Redis Streams consumer helper for StorageWorker processes.

Wraps XGROUP CREATE, XREADGROUP, and XACK into a simple async API so that
StorageWorker (Phase 3) can focus on parsing and storage logic.

Usage (Phase 3 — not yet wired):
    consumer = StreamConsumer(redis_client, group="storage-workers", consumer="worker-0")
    await consumer.ensure_group()
    async for msg_id, fields in consumer.read_batch(batch_size=50):
        process(fields)
        await consumer.ack(msg_id)
"""
import json
import logging
from typing import AsyncIterator, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

STREAM_NAME = "telemetry:raw"
DEFAULT_BLOCK_MS = 2_000   # block up to 2 s waiting for new messages
DEFAULT_BATCH = 50         # messages per XREADGROUP call


class StreamConsumer:
    """
    Consumer-group wrapper around the 'telemetry:raw' Redis Stream.

    Each StorageWorker process creates one StreamConsumer with its own
    unique ``consumer`` name (e.g. "worker-0", "worker-1").  All workers
    share the same ``group`` name so Redis load-balances messages across them.
    """

    def __init__(self, redis_client, group: str, consumer: str) -> None:
        """
        Args:
            redis_client: An active redis.asyncio.Redis instance.
            group:        Consumer-group name (all storage workers share this).
            consumer:     Unique name for this specific worker process.
        """
        self._redis = redis_client
        self._group = group
        self._consumer = consumer

    async def ensure_group(self, start_id: str = "$") -> None:
        """
        Create the consumer group if it does not already exist.

        Args:
            start_id: Stream ID to start consuming from.
                      "$" = only new messages (default for a fresh worker).
                      "0" = replay all unacknowledged messages (useful after crash).
        """
        try:
            await self._redis.xgroup_create(
                STREAM_NAME,
                self._group,
                id=start_id,
                mkstream=True,
            )
            logger.info(
                "StreamConsumer: created consumer group '%s' on stream '%s'",
                self._group,
                STREAM_NAME,
            )
        except Exception as exc:
            # BUSYGROUP means the group already exists — that is fine.
            if "BUSYGROUP" in str(exc):
                logger.debug(
                    "StreamConsumer: consumer group '%s' already exists", self._group
                )
            else:
                raise

    async def read_batch(
        self,
        batch_size: int = DEFAULT_BATCH,
        block_ms: int = DEFAULT_BLOCK_MS,
    ) -> AsyncIterator[Tuple[str, Dict]]:
        """
        Yield (message_id, fields_dict) for each pending message.

        Blocks up to ``block_ms`` milliseconds waiting for new messages.
        Fields dict always contains:
            device_serial  (str)
            device_type    (str)
            payload        (dict — already JSON-decoded)
            ts             (float — Unix timestamp)
            inverter_serial (str | None)

        The caller is responsible for calling ack(msg_id) after processing.
        """
        try:
            results = await self._redis.xreadgroup(
                groupname=self._group,
                consumername=self._consumer,
                streams={STREAM_NAME: ">"},
                count=batch_size,
                block=block_ms,
            )
        except Exception:
            logger.exception("StreamConsumer: xreadgroup failed")
            return

        if not results:
            return

        for _stream, messages in results:
            for msg_id, raw_fields in messages:
                try:
                    fields = {
                        "device_serial": raw_fields.get("device_serial", ""),
                        "device_type": raw_fields.get("device_type", ""),
                        "payload": json.loads(raw_fields.get("payload", "{}")),
                        "ts": float(raw_fields.get("ts", 0)),
                        "inverter_serial": raw_fields.get("inverter_serial"),
                    }
                    yield msg_id, fields
                except Exception:
                    logger.exception(
                        "StreamConsumer: failed to decode message %s — acking to skip",
                        msg_id,
                    )
                    await self._ack_silent(msg_id)

    async def ack(self, msg_id: str) -> None:
        """Acknowledge a successfully processed message."""
        try:
            await self._redis.xack(STREAM_NAME, self._group, msg_id)
        except Exception:
            logger.exception("StreamConsumer: xack failed for %s", msg_id)

    async def reclaim_stale(
        self,
        min_idle_ms: int = 60_000,
        batch_size: int = DEFAULT_BATCH,
    ) -> List[str]:
        """
        Reclaim messages that have been pending (unacknowledged) for longer
        than ``min_idle_ms`` milliseconds — typically because a worker crashed.

        Returns the list of reclaimed message IDs (now owned by this consumer).
        Called once at worker startup with start_id "0" in ensure_group() to
        reprocess any messages that were in-flight when the process died.
        """
        try:
            result = await self._redis.xautoclaim(
                STREAM_NAME,
                self._group,
                self._consumer,
                min_idle_time=min_idle_ms,
                start_id="0-0",
                count=batch_size,
            )
            # xautoclaim returns (next_id, messages, deleted_ids) in redis-py >= 4.3
            messages = result[1] if isinstance(result, (list, tuple)) else []
            reclaimed = [msg_id for msg_id, _ in messages]
            if reclaimed:
                logger.info(
                    "StreamConsumer: reclaimed %d stale messages", len(reclaimed)
                )
            return reclaimed
        except Exception:
            logger.exception("StreamConsumer: xautoclaim failed")
            return []

    async def _ack_silent(self, msg_id: str) -> None:
        """Acknowledge without raising — used to skip undecodable messages."""
        try:
            await self._redis.xack(STREAM_NAME, self._group, msg_id)
        except Exception:
            pass
