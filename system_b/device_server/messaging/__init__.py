"""
Messaging layer for multi-process telemetry pipeline.

Phase 1: Infrastructure only — no behavior change.
Phase 2: StreamPublisher wired into _on_telemetry() as dual-write.
Phase 3: StorageWorker consumes and writes DB + Redis cache.
"""
from .stream_publisher import StreamPublisher
from .stream_consumer import StreamConsumer

__all__ = ["StreamPublisher", "StreamConsumer"]
