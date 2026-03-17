"""
TimescaleDB writer for telemetry storage.

Writes telemetry data to TimescaleDB hypertables with
batching and async support.

Updated to support dual write:
1. Normalized metrics → telemetry_raw (for aggregations)
2. Full JSON → device_telemetry (optional audit trail)
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
from ..telemetry import DeyeHybridParser, PowdriveParser, PylontechParser, TelemetryMetric, TelemetryParser

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

        # Telemetry parsers for normalized storage
        self.parsers = {
            'deye_hybrid': DeyeHybridParser(),
            'powdrive': PowdriveParser(),
            'pylontech': PylontechParser(),
            'pytes': PylontechParser(),
        }
        # Default parser for backwards compatibility
        self.default_parser = self.parsers['powdrive']

    async def connect(self) -> None:
        """Connect to TimescaleDB."""
        if asyncpg is None:
            logger.warning(
                "asyncpg not installed, TimescaleDB writes disabled"
            )
            return

        storage = self.settings.storage
        try:
            logger.info(
                f"Connecting to TimescaleDB at {storage.host}:{storage.port}/{storage.name} "
                f"as user '{storage.user}'"
            )
            self._pool = await asyncpg.create_pool(
                host=storage.host,
                port=storage.port,
                database=storage.name,
                user=storage.user,
                password=storage.password,
                min_size=2,
                max_size=10,
            )
            logger.info(
                f"Connected to TimescaleDB at "
                f"{storage.host}:{storage.port}/{storage.name}"
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
                    poll_duration_ms FLOAT,
                    PRIMARY KEY (time, device_id)
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

    def _detect_parser(self, record: Dict[str, Any]) -> TelemetryParser:
        """
        Detect which parser to use based on protocol_id or JSON structure.

        Args:
            record: Telemetry record with 'data', 'protocol_id', etc.

        Returns:
            Appropriate parser instance
        """
        # Method 1: Use protocol_id if available
        protocol_id = record.get("protocol_id", "").lower()
        if "deye" in protocol_id:
            return self.parsers['deye_hybrid']
        elif "pylontech" in protocol_id or "pytes" in protocol_id:
            return self.parsers['pylontech']
        elif "powdrive" in protocol_id:
            return self.parsers['powdrive']

        # Method 2: Auto-detect based on JSON structure
        telemetry_data = record.get("data", {})

        # Deye format has nested sections (power, battery, energy_today, etc.)
        deye_sections = {'power', 'battery', 'energy_today', 'temperatures', 'grid'}
        if any(section in telemetry_data for section in deye_sections):
            logger.debug(f"Detected Deye format for device {record.get('device_id')}")
            return self.parsers['deye_hybrid']

        # Pylontech/Pytes format has battery_units list
        if "battery_units" in telemetry_data:
            logger.debug(f"Detected Pylontech format for device {record.get('device_id')}")
            return self.parsers['pylontech']

        # Powdrive format has flat structure with specific fields
        powdrive_fields = {'pv1_power_w', 'battery_power_w', 'grid_power_w', 'load_power_w'}
        if any(field in telemetry_data for field in powdrive_fields):
            logger.debug(f"Detected Powdrive format for device {record.get('device_id')}")
            return self.parsers['powdrive']

        # Default to powdrive parser (most common)
        logger.warning(
            f"Could not detect telemetry format for device {record.get('device_id')}, "
            f"using default Powdrive parser"
        )
        return self.default_parser

    async def _flush_batch(self) -> None:
        """
        Flush current batch to database with dual write.

        Writes to:
        1. telemetry_raw: Normalized metrics for TimescaleDB aggregations
        2. device_telemetry: Optional full JSON for audit (7-day retention)
        """
        if not self._batch or not self._pool:
            return

        batch = self._batch
        self._batch = []

        try:
            async with self._pool.acquire() as conn:
                # =====================================================
                # Write 1: Normalized metrics to telemetry_raw
                # =====================================================
                # Get site_id for each device from registry
                device_ids = list(set(r["device_id"] for r in batch))
                device_site_map = {}

                if device_ids:
                    site_rows = await conn.fetch(
                        """
                        SELECT device_id, site_id
                        FROM device_registry
                        WHERE device_id = ANY($1::uuid[])
                        """,
                        device_ids
                    )
                    device_site_map = {row['device_id']: row['site_id'] for row in site_rows}

                # Parse each record and collect all metrics
                all_metrics: List[TelemetryMetric] = []
                for record in batch:
                    site_id = device_site_map.get(record["device_id"])
                    if not site_id:
                        logger.warning(
                            f"No site_id found for device {record['device_id']}, "
                            f"skipping normalized write"
                        )
                        continue

                    # Detect which parser to use based on protocol or JSON structure
                    parser = self._detect_parser(record)

                    # Parse telemetry into normalized metrics
                    try:
                        metrics = parser.parse(
                            telemetry_data=record["data"],
                            device_id=record["device_id"],
                            site_id=site_id,
                            timestamp=record["time"]
                        )
                        all_metrics.extend(metrics)
                    except Exception as e:
                        logger.error(
                            f"Error parsing telemetry for device {record['device_id']}: {e}",
                            exc_info=True
                        )
                        continue

                # Batch insert normalized metrics
                if all_metrics:
                    await conn.executemany(
                        """
                        INSERT INTO telemetry_raw
                        (time, device_id, metric_name, site_id, metric_value,
                         metric_value_str, quality, unit, source, tags)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        ON CONFLICT (time, device_id, metric_name) DO UPDATE SET
                            metric_value = EXCLUDED.metric_value,
                            quality = EXCLUDED.quality
                        """,
                        [m.to_db_tuple() for m in all_metrics]
                    )
                    logger.info(
                        f"Wrote {len(all_metrics)} normalized metrics "
                        f"from {len(batch)} telemetry records to telemetry_raw"
                    )
                else:
                    logger.warning(
                        f"No metrics extracted from {len(batch)} telemetry records - "
                        f"check JSON structure or parser compatibility"
                    )

                # =====================================================
                # Write 2: Full JSON to device_telemetry (optional)
                # =====================================================
                # Keep for 7-day audit trail
                await conn.executemany(
                    """
                    INSERT INTO device_telemetry
                    (time, device_id, serial_number, protocol_id,
                     device_type, data, poll_duration_ms)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (time, device_id) DO UPDATE SET
                        data = EXCLUDED.data,
                        poll_duration_ms = EXCLUDED.poll_duration_ms
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

            logger.info(f"Flushed {len(batch)} telemetry records (dual write complete)")

        except Exception as e:
            logger.error(f"Error flushing batch: {e}", exc_info=True)
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
