"""
TimescaleDB writer for telemetry storage.

Writes telemetry data to TimescaleDB hypertables with
batching and async support.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

try:
    import asyncpg
except ImportError:
    asyncpg = None

from ..config import DeviceServerSettings, get_device_server_settings

logger = logging.getLogger(__name__)


class TimescaleWriter:
    """
    Writes telemetry data to TimescaleDB.

    Features:
    - Async connection pooling
    - Batch inserts for efficiency
    - Hypertable support for time-series data
    """

    def __init__(
        self,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the TimescaleDB writer.

        Args:
            settings: Server settings.
        """
        self.settings = settings or get_device_server_settings()
        self._pool: Optional[asyncpg.Pool] = None

        # Batch buffer
        self._batch: List[Dict[str, Any]] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Connect to TimescaleDB."""
        if asyncpg is None:
            logger.warning(
                "asyncpg not installed, TimescaleDB writes disabled"
            )
            return

        storage = self.settings.storage
        try:
            self._pool = await asyncpg.create_pool(
                host=storage.timescale_host,
                port=storage.timescale_port,
                database=storage.timescale_database,
                user=storage.timescale_user,
                password=storage.timescale_password,
                min_size=2,
                max_size=10,
            )
            logger.info(
                f"Connected to TimescaleDB at "
                f"{storage.timescale_host}:{storage.timescale_port}"
            )

            # Ensure tables exist
            await self._ensure_tables()

            # Start batch flush task
            self._flush_task = asyncio.create_task(self._flush_loop())

        except Exception as e:
            logger.error(f"Failed to connect to TimescaleDB: {e}")
            self._pool = None

    async def disconnect(self) -> None:
        """Disconnect from TimescaleDB."""
        # Stop flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Flush remaining data
        await self.flush()

        # Close pool
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Disconnected from TimescaleDB")

    async def _ensure_tables(self) -> None:
        """Ensure required tables exist."""
        if not self._pool:
            return

        async with self._pool.acquire() as conn:
            # Create telemetry table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS device_telemetry (
                    time TIMESTAMPTZ NOT NULL,
                    device_id UUID NOT NULL,
                    serial_number TEXT NOT NULL,
                    protocol_id TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    data JSONB NOT NULL,
                    poll_duration_ms FLOAT
                );
            """)

            # Check if hypertable exists (TimescaleDB specific)
            try:
                # Try to create hypertable (will fail silently if exists)
                await conn.execute("""
                    SELECT create_hypertable(
                        'device_telemetry',
                        'time',
                        if_not_exists => TRUE
                    );
                """)
                logger.debug("Created hypertable for device_telemetry")
            except Exception as e:
                # Might fail if TimescaleDB extension not installed
                logger.debug(f"Hypertable creation skipped: {e}")

            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
                ON device_telemetry (device_id, time DESC);
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_serial_time
                ON device_telemetry (serial_number, time DESC);
            """)

            logger.debug("Database tables and indexes ensured")

    async def write(
        self,
        device_id: UUID,
        telemetry: Dict[str, Any],
    ) -> bool:
        """
        Write telemetry data.

        Data is buffered and written in batches.

        Args:
            device_id: Device ID.
            telemetry: Telemetry data dictionary.

        Returns:
            True if queued successfully.
        """
        if not self._pool:
            logger.debug("No database connection, skipping write")
            return False

        # Extract metadata
        serial_number = telemetry.pop("_serial_number", "unknown")
        protocol_id = telemetry.pop("_protocol_id", "unknown")
        device_type = telemetry.pop("_device_type", "unknown")
        timestamp = telemetry.pop("_timestamp", None)
        poll_duration = telemetry.pop("_poll_duration_ms", None)

        # Remove device_id from data (stored separately)
        telemetry.pop("_device_id", None)

        # Parse timestamp
        if timestamp:
            try:
                ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                ts = datetime.now(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        record = {
            "time": ts,
            "device_id": device_id,
            "serial_number": serial_number,
            "protocol_id": protocol_id,
            "device_type": device_type,
            "data": telemetry,
            "poll_duration_ms": poll_duration,
        }

        async with self._batch_lock:
            self._batch.append(record)

            # Flush if batch size reached
            if len(self._batch) >= self.settings.storage.batch_size:
                await self._flush_batch()

        return True

    async def flush(self) -> None:
        """Flush buffered data to database."""
        async with self._batch_lock:
            await self._flush_batch()

    async def _flush_batch(self) -> None:
        """Flush current batch to database (must hold lock)."""
        if not self._batch or not self._pool:
            return

        batch = self._batch
        self._batch = []

        try:
            async with self._pool.acquire() as conn:
                # Prepare insert statement
                await conn.executemany(
                    """
                    INSERT INTO device_telemetry
                    (time, device_id, serial_number, protocol_id,
                     device_type, data, poll_duration_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    [
                        (
                            r["time"],
                            r["device_id"],
                            r["serial_number"],
                            r["protocol_id"],
                            r["device_type"],
                            json.dumps(r["data"]),
                            r["poll_duration_ms"],
                        )
                        for r in batch
                    ],
                )

            logger.debug(f"Flushed {len(batch)} telemetry records")

        except Exception as e:
            logger.error(f"Error flushing batch: {e}")
            # Put records back in batch for retry
            self._batch.extend(batch)

    async def _flush_loop(self) -> None:
        """Periodic flush loop."""
        while True:
            try:
                await asyncio.sleep(self.settings.storage.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in flush loop: {e}")

    async def query_latest(
        self,
        device_id: UUID,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Query latest telemetry for a device.

        Args:
            device_id: Device ID.
            limit: Number of records to return.

        Returns:
            List of telemetry records.
        """
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT time, data, poll_duration_ms
                    FROM device_telemetry
                    WHERE device_id = $1
                    ORDER BY time DESC
                    LIMIT $2
                    """,
                    device_id,
                    limit,
                )

                return [
                    {
                        "time": row["time"].isoformat(),
                        "data": json.loads(row["data"]),
                        "poll_duration_ms": row["poll_duration_ms"],
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Error querying telemetry: {e}")
            return []

    async def query_range(
        self,
        device_id: UUID,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Query telemetry for a time range.

        Args:
            device_id: Device ID.
            start_time: Start of range.
            end_time: End of range.
            limit: Maximum records to return.

        Returns:
            List of telemetry records.
        """
        if not self._pool:
            return []

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT time, data, poll_duration_ms
                    FROM device_telemetry
                    WHERE device_id = $1
                      AND time >= $2
                      AND time <= $3
                    ORDER BY time ASC
                    LIMIT $4
                    """,
                    device_id,
                    start_time,
                    end_time,
                    limit,
                )

                return [
                    {
                        "time": row["time"].isoformat(),
                        "data": json.loads(row["data"]),
                        "poll_duration_ms": row["poll_duration_ms"],
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Error querying telemetry range: {e}")
            return []
