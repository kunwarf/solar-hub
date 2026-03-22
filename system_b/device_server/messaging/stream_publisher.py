"""
Redis Streams publisher for raw telemetry data.

Publishes raw telemetry dicts to the 'telemetry:raw' stream so that
independent StorageWorker processes can consume and persist them.

Usage (Phase 2 — not yet wired):
    publisher = StreamPublisher(redis_client)
    await publisher.publish(device_serial, device_type, raw_telemetry)
"""
import json
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

STREAM_NAME = "telemetry:raw"

# Trim stream to ~100k messages to bound memory (~50 MB at ~500 bytes/msg).
# StorageWorker is expected to consume far faster than this.
STREAM_MAXLEN = 100_000


class StreamPublisher:
    """
    Publishes raw telemetry snapshots to the Redis Stream 'telemetry:raw'.

    Each message contains:
        device_serial  — data-logger serial (Redis cache key owner)
        device_type    — protocol type string, e.g. 'senergy', 'jkbms'
        payload        — JSON-encoded raw telemetry dict
        ts             — Unix timestamp (float, seconds) of the poll
    """

    def __init__(self, redis_client) -> None:
        """
        Args:
            redis_client: An active redis.asyncio.Redis instance.
                          Shared with the rest of the Device Server — no extra connections.
        """
        self._redis = redis_client

    async def publish(
        self,
        device_serial: str,
        device_type: str,
        raw_telemetry: Dict[str, Any],
        inverter_serial: Optional[str] = None,
    ) -> Optional[str]:
        """
        Publish one telemetry snapshot to the stream.

        Args:
            device_serial:  Data-logger serial (matches Redis cache key).
            device_type:    Protocol identifier string (e.g. 'senergy', 'powdrive').
            raw_telemetry:  Raw dict of metric_key → value as produced by the adapter.
            inverter_serial: Optional inverter serial for linking (may be None).

        Returns:
            The Redis message ID on success, or None if the publish failed.
        """
        try:
            fields = {
                "device_serial": device_serial,
                "device_type": device_type,
                "payload": json.dumps(raw_telemetry, default=str),
                "ts": str(time.time()),
            }
            if inverter_serial:
                fields["inverter_serial"] = inverter_serial

            msg_id = await self._redis.xadd(
                STREAM_NAME,
                fields,
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
            return msg_id
        except Exception:
            # Never let a publish failure crash the Device Server.
            logger.exception(
                "StreamPublisher: failed to publish telemetry for %s", device_serial
            )
            return None
