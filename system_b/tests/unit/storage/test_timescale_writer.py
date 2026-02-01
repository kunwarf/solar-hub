"""
Unit tests for TimescaleWriter.

Tests dual write functionality (telemetry_raw + device_telemetry).
"""
import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4, UUID

from device_server.storage.timescale_writer import TimescaleWriter
from device_server.telemetry import DeyeHybridParser, TelemetryMetric


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.storage.host = "localhost"
    settings.storage.port = 5432
    settings.storage.name = "test_db"
    settings.storage.user = "test_user"
    settings.storage.password = "test_pass"
    settings.storage.batch_size = 10
    settings.storage.flush_interval = 1.0
    return settings


@pytest.fixture
def mock_pool():
    """Create mock asyncpg connection pool."""
    pool = MagicMock()
    conn = AsyncMock()

    # Mock connection context manager
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = acquire_cm
    pool.close = AsyncMock()

    return pool, conn


@pytest.fixture
def writer(mock_settings):
    """Create TimescaleWriter with mock settings."""
    return TimescaleWriter(settings=mock_settings)


@pytest.fixture
def sample_device_id():
    """Create sample device ID."""
    return uuid4()


@pytest.fixture
def sample_site_id():
    """Create sample site ID."""
    return uuid4()


@pytest.fixture
def sample_telemetry(sample_device_id):
    """Create sample telemetry data."""
    return {
        "_serial_number": "TEST123",
        "_protocol_id": "modbus",
        "_device_type": "deye_hybrid",
        "_timestamp": "2024-01-15T12:30:00Z",
        "_poll_duration_ms": 150.0,
        "_device_id": str(sample_device_id),
        "power": {
            "pv_total_w": 2500.0,
            "load_w": 1800.0,
            "grid_w": -500.0,
            "battery_w": 200.0,
        },
        "battery": {
            "soc_pct": 75.0,
            "voltage_v": 52.0,
            "current_a": 3.8,
            "charging": True,
        },
        "energy_today": {
            "pv_kwh": 15.5,
            "load_kwh": 12.3,
        },
        "grid": {
            "voltage_v": 230.0,
            "frequency_hz": 50.0,
        },
    }


class TestTimescaleWriterInit:
    """Test TimescaleWriter initialization."""

    def test_init_with_settings(self, mock_settings):
        """Test writer initializes with custom settings."""
        writer = TimescaleWriter(settings=mock_settings)

        assert writer.settings == mock_settings
        assert writer._pool is None
        assert writer._batch == []
        assert writer._flush_task is None
        assert isinstance(writer.parser, DeyeHybridParser)

    def test_init_without_settings(self):
        """Test writer initializes with default settings."""
        with patch('device_server.storage.timescale_writer.get_device_server_settings') as mock_get:
            mock_get.return_value = MagicMock()
            writer = TimescaleWriter()

            assert writer.settings is not None
            assert writer._pool is None


class TestConnection:
    """Test database connection."""

    @pytest.mark.asyncio
    async def test_connect_success(self, writer, mock_settings):
        """Test successful connection."""
        with patch('device_server.storage.timescale_writer.asyncpg') as mock_asyncpg:
            mock_pool = MagicMock()
            mock_conn = AsyncMock()

            # Mock connection context manager
            acquire_cm = MagicMock()
            acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
            acquire_cm.__aexit__ = AsyncMock(return_value=None)
            mock_pool.acquire.return_value = acquire_cm
            mock_pool.close = AsyncMock()

            # Mock create_pool as AsyncMock that returns the pool
            mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)

            await writer.connect()

            # Verify pool was created
            mock_asyncpg.create_pool.assert_called_once_with(
                host=mock_settings.storage.host,
                port=mock_settings.storage.port,
                database=mock_settings.storage.name,
                user=mock_settings.storage.user,
                password=mock_settings.storage.password,
                min_size=2,
                max_size=10,
            )

            assert writer._pool is not None

    @pytest.mark.asyncio
    async def test_connect_without_asyncpg(self, writer):
        """Test connection when asyncpg is not installed."""
        with patch('device_server.storage.timescale_writer.asyncpg', None):
            await writer.connect()

            # Should not create pool
            assert writer._pool is None

    @pytest.mark.asyncio
    async def test_disconnect(self, writer):
        """Test disconnection."""
        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()
        writer._pool = mock_pool

        # Create an async task mock that can be cancelled and awaited
        import asyncio
        async def dummy_task():
            pass

        mock_task = asyncio.create_task(dummy_task())
        mock_task.cancel()
        writer._flush_task = mock_task

        # Patch flush to avoid actual flushing
        with patch.object(writer, 'flush', new_callable=AsyncMock):
            try:
                await writer.disconnect()
            except asyncio.CancelledError:
                pass  # Expected when task is cancelled

        # Verify pool was closed
        mock_pool.close.assert_called_once()
        assert writer._pool is None


class TestWriteTelemetry:
    """Test telemetry write operations."""

    @pytest.mark.asyncio
    async def test_write_telemetry(self, writer, sample_device_id, sample_telemetry):
        """Test writing telemetry data."""
        writer._pool = MagicMock()  # Simulate connected

        result = await writer.write(sample_device_id, sample_telemetry.copy())

        assert result is True
        assert len(writer._batch) == 1

        # Check record structure
        record = writer._batch[0]
        assert record["device_id"] == sample_device_id
        assert record["serial_number"] == "TEST123"
        assert record["protocol_id"] == "modbus"
        assert record["device_type"] == "deye_hybrid"
        assert record["poll_duration_ms"] == 150.0
        assert isinstance(record["time"], datetime)

        # Metadata should be removed from data
        assert "_serial_number" not in record["data"]
        assert "_protocol_id" not in record["data"]
        assert "_device_id" not in record["data"]

        # Regular telemetry should remain
        assert "power" in record["data"]
        assert "battery" in record["data"]

    @pytest.mark.asyncio
    async def test_write_without_connection(self, writer, sample_device_id, sample_telemetry):
        """Test writing when not connected."""
        writer._pool = None

        result = await writer.write(sample_device_id, sample_telemetry)

        assert result is False
        assert len(writer._batch) == 0

    @pytest.mark.asyncio
    async def test_write_auto_flush_on_batch_size(self, writer, sample_device_id, sample_telemetry, mock_settings):
        """Test automatic flush when batch size is reached."""
        writer._pool = MagicMock()
        mock_settings.storage.batch_size = 2

        with patch.object(writer, '_flush_batch', new_callable=AsyncMock) as mock_flush:
            # Write 2 records (batch size)
            await writer.write(sample_device_id, sample_telemetry.copy())
            await writer.write(sample_device_id, sample_telemetry.copy())

            # Should trigger flush
            mock_flush.assert_called_once()


class TestDualWrite:
    """Test dual write functionality (telemetry_raw + device_telemetry)."""

    @pytest.mark.asyncio
    async def test_flush_batch_dual_write(self, writer, sample_device_id, sample_site_id, sample_telemetry):
        """Test dual write to both telemetry_raw and device_telemetry."""
        # Setup
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        writer._pool = mock_pool

        # Mock connection context manager
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acquire_cm

        # Mock site_id lookup
        mock_conn.fetch = AsyncMock(return_value=[
            {"device_id": sample_device_id, "site_id": sample_site_id}
        ])

        # Add record to batch
        await writer.write(sample_device_id, sample_telemetry.copy())

        # Mock parser to return some metrics
        with patch.object(writer.parser, 'parse') as mock_parse:
            mock_metrics = [
                TelemetryMetric(
                    time=datetime.now(timezone.utc),
                    device_id=sample_device_id,
                    site_id=sample_site_id,
                    metric_name="pv_total_w",
                    metric_value=2500.0,
                    quality="good",
                    unit="W",
                    source="power",
                ),
                TelemetryMetric(
                    time=datetime.now(timezone.utc),
                    device_id=sample_device_id,
                    site_id=sample_site_id,
                    metric_name="battery_soc_pct",
                    metric_value=75.0,
                    quality="good",
                    unit="%",
                    source="battery",
                ),
            ]
            mock_parse.return_value = mock_metrics

            # Execute flush
            await writer._flush_batch()

            # Verify site_id was fetched
            assert mock_conn.fetch.called
            fetch_calls = [str(call) for call in mock_conn.fetch.call_args_list]
            assert any("device_registry" in str(call) for call in fetch_calls)

            # Verify parser was called
            mock_parse.assert_called_once()

            # Verify executemany was called twice (telemetry_raw + device_telemetry)
            assert mock_conn.executemany.call_count == 2

            # Check first call (telemetry_raw - normalized metrics)
            raw_call = mock_conn.executemany.call_args_list[0]
            raw_query = raw_call[0][0]
            raw_values = raw_call[0][1]

            assert "INSERT INTO telemetry_raw" in raw_query
            assert "metric_name" in raw_query
            assert "metric_value" in raw_query
            assert len(raw_values) == 2  # 2 metrics

            # Check second call (device_telemetry - full JSON)
            json_call = mock_conn.executemany.call_args_list[1]
            json_query = json_call[0][0]
            json_values = json_call[0][1]

            assert "INSERT INTO device_telemetry" in json_query
            assert "data" in json_query
            assert len(json_values) == 1  # 1 telemetry record

    @pytest.mark.asyncio
    async def test_flush_batch_without_site_id(self, writer, sample_device_id, sample_telemetry):
        """Test flush when site_id is not found."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        writer._pool = mock_pool

        # Mock connection context manager
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acquire_cm

        # Mock empty site_id lookup
        mock_conn.fetch = AsyncMock(return_value=[])

        # Add record to batch
        await writer.write(sample_device_id, sample_telemetry.copy())

        # Execute flush
        await writer._flush_batch()

        # Should still write to device_telemetry (audit)
        # but skip telemetry_raw (normalized)
        assert mock_conn.executemany.call_count == 1  # Only device_telemetry

        call_args = mock_conn.executemany.call_args_list[0]
        query = call_args[0][0]
        assert "device_telemetry" in query

    @pytest.mark.asyncio
    async def test_flush_batch_parser_error(self, writer, sample_device_id, sample_site_id, sample_telemetry):
        """Test flush when parser raises an error."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        writer._pool = mock_pool

        # Mock connection context manager
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acquire_cm

        # Mock site_id lookup
        mock_conn.fetch = AsyncMock(return_value=[
            {"device_id": sample_device_id, "site_id": sample_site_id}
        ])

        # Add record to batch
        await writer.write(sample_device_id, sample_telemetry.copy())

        # Mock parser to raise exception
        with patch.object(writer.parser, 'parse', side_effect=Exception("Parse error")):
            # Execute flush - should not raise
            await writer._flush_batch()

            # Should still write to device_telemetry (audit)
            assert mock_conn.executemany.call_count == 1

    @pytest.mark.asyncio
    async def test_flush_batch_empty(self, writer):
        """Test flushing empty batch."""
        writer._pool = MagicMock()

        # Should not error on empty batch
        await writer._flush_batch()

        # Batch should still be empty
        assert len(writer._batch) == 0


class TestBatchManagement:
    """Test batch buffering and flushing."""

    @pytest.mark.asyncio
    async def test_manual_flush(self, writer, sample_device_id, sample_telemetry):
        """Test manual flush operation."""
        writer._pool = MagicMock()

        with patch.object(writer, '_flush_batch', new_callable=AsyncMock) as mock_flush:
            # Add some data
            await writer.write(sample_device_id, sample_telemetry.copy())

            # Manual flush
            await writer.flush()

            mock_flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_error_recovery(self, writer, sample_device_id, sample_site_id, sample_telemetry):
        """Test that batch is preserved on flush error for retry."""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        writer._pool = mock_pool

        # Mock connection context manager
        acquire_cm = MagicMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = acquire_cm

        # Mock site_id lookup
        mock_conn.fetch = AsyncMock(return_value=[
            {"device_id": sample_device_id, "site_id": sample_site_id}
        ])

        # Mock database error
        mock_conn.executemany = AsyncMock(side_effect=Exception("DB error"))

        # Add record to batch
        await writer.write(sample_device_id, sample_telemetry.copy())
        initial_batch_size = len(writer._batch)

        # Execute flush - should not raise
        await writer._flush_batch()

        # Batch should be restored for retry
        assert len(writer._batch) == initial_batch_size


class TestTimestampHandling:
    """Test timestamp parsing and handling."""

    @pytest.mark.asyncio
    async def test_parse_iso_timestamp(self, writer, sample_device_id):
        """Test parsing ISO format timestamp."""
        writer._pool = MagicMock()

        telemetry = {
            "_serial_number": "TEST123",
            "_timestamp": "2024-01-15T12:30:00Z",
            "power": {"pv_total_w": 1000.0},
        }

        await writer.write(sample_device_id, telemetry)

        record = writer._batch[0]
        assert isinstance(record["time"], datetime)
        assert record["time"].year == 2024
        assert record["time"].month == 1
        assert record["time"].day == 15

    @pytest.mark.asyncio
    async def test_missing_timestamp_uses_now(self, writer, sample_device_id):
        """Test that missing timestamp uses current time."""
        writer._pool = MagicMock()

        telemetry = {
            "_serial_number": "TEST123",
            # No _timestamp
            "power": {"pv_total_w": 1000.0},
        }

        before = datetime.now(timezone.utc)
        await writer.write(sample_device_id, telemetry)
        after = datetime.now(timezone.utc)

        record = writer._batch[0]
        assert isinstance(record["time"], datetime)
        assert before <= record["time"] <= after

    @pytest.mark.asyncio
    async def test_invalid_timestamp_uses_now(self, writer, sample_device_id):
        """Test that invalid timestamp falls back to current time."""
        writer._pool = MagicMock()

        telemetry = {
            "_serial_number": "TEST123",
            "_timestamp": "invalid_timestamp",
            "power": {"pv_total_w": 1000.0},
        }

        before = datetime.now(timezone.utc)
        await writer.write(sample_device_id, telemetry)
        after = datetime.now(timezone.utc)

        record = writer._batch[0]
        assert isinstance(record["time"], datetime)
        assert before <= record["time"] <= after


class TestMetadataHandling:
    """Test metadata extraction and cleanup."""

    @pytest.mark.asyncio
    async def test_metadata_extraction(self, writer, sample_device_id, sample_telemetry):
        """Test that metadata is extracted correctly."""
        writer._pool = MagicMock()

        await writer.write(sample_device_id, sample_telemetry.copy())

        record = writer._batch[0]
        assert record["serial_number"] == "TEST123"
        assert record["protocol_id"] == "modbus"
        assert record["device_type"] == "deye_hybrid"
        assert record["poll_duration_ms"] == 150.0

    @pytest.mark.asyncio
    async def test_metadata_defaults(self, writer, sample_device_id):
        """Test default values for missing metadata."""
        writer._pool = MagicMock()

        telemetry = {
            # No metadata fields
            "power": {"pv_total_w": 1000.0},
        }

        await writer.write(sample_device_id, telemetry)

        record = writer._batch[0]
        assert record["serial_number"] == "unknown"
        assert record["protocol_id"] == "unknown"
        assert record["device_type"] == "unknown"
        assert record["poll_duration_ms"] is None

    @pytest.mark.asyncio
    async def test_metadata_removed_from_data(self, writer, sample_device_id, sample_telemetry):
        """Test that metadata is removed from telemetry data."""
        writer._pool = MagicMock()

        telemetry_copy = sample_telemetry.copy()
        await writer.write(sample_device_id, telemetry_copy)

        record = writer._batch[0]
        data = record["data"]

        # Metadata should not be in data
        assert "_serial_number" not in data
        assert "_protocol_id" not in data
        assert "_device_type" not in data
        assert "_timestamp" not in data
        assert "_poll_duration_ms" not in data
        assert "_device_id" not in data

        # Actual telemetry should remain
        assert "power" in data
        assert "battery" in data
        assert "energy_today" in data
