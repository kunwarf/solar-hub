"""
Unit tests for TelemetryRepository.

Tests telemetry data ingestion, querying, and aggregation.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.infrastructure.database.repositories.telemetry_repository import TelemetryRepository
from app.domain.entities.telemetry import (
    TelemetryPoint,
    TelemetryBatch,
    DataQuality,
)


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def repository(mock_session):
    """Create a TelemetryRepository with mock session."""
    return TelemetryRepository(mock_session)


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


@pytest.fixture
def sample_telemetry_point(sample_device_id, sample_site_id):
    """Create a sample telemetry point."""
    return TelemetryPoint(
        time=datetime.now(timezone.utc),
        device_id=sample_device_id,
        site_id=sample_site_id,
        metric_name="battery_soc_pct",
        metric_value=75.5,
        quality=DataQuality.GOOD,
        unit="%",
        source="modbus",
    )


@pytest.fixture
def sample_telemetry_batch(sample_device_id, sample_site_id):
    """Create a sample telemetry batch."""
    now = datetime.now(timezone.utc)
    points = []

    for i in range(10):
        points.append(TelemetryPoint(
            time=now - timedelta(seconds=i * 60),
            device_id=sample_device_id,
            site_id=sample_site_id,
            metric_name=f"metric_{i % 3}",
            metric_value=float(i * 10),
            quality=DataQuality.GOOD,
            unit="W",
            source="modbus",
        ))

    return TelemetryBatch(
        batch_id=uuid4(),
        source_type="modbus",
        source_identifier="test_device",
        points=points,
    )


class TestTelemetryRepositoryInit:
    """Test TelemetryRepository initialization."""

    def test_init_with_session(self, mock_session):
        """Test repository initializes with session."""
        repo = TelemetryRepository(mock_session)
        assert repo._session == mock_session


class TestIngestBatch:
    """Test batch ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_empty_batch_returns_zero(self, repository):
        """Test ingesting empty batch returns (0, 0)."""
        batch = TelemetryBatch(
            batch_id=uuid4(),
            source_type="test",
            points=[],
        )

        inserted, failed = await repository.ingest_batch(batch)

        assert inserted == 0
        assert failed == 0

    @pytest.mark.asyncio
    async def test_ingest_batch_creates_tracking_record(
        self, repository, mock_session, sample_telemetry_batch
    ):
        """Test batch ingestion creates tracking record."""
        mock_session.execute = AsyncMock()

        await repository.ingest_batch(sample_telemetry_batch)

        # Verify add was called for batch tracking record
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_ingest_batch_returns_correct_count(
        self, repository, mock_session, sample_telemetry_batch
    ):
        """Test batch ingestion returns correct count."""
        mock_session.execute = AsyncMock()

        inserted, failed = await repository.ingest_batch(sample_telemetry_batch)

        assert inserted == len(sample_telemetry_batch.points)
        assert failed == 0

    @pytest.mark.asyncio
    async def test_ingest_batch_commits_on_success(
        self, repository, mock_session, sample_telemetry_batch
    ):
        """Test batch ingestion commits transaction."""
        mock_session.execute = AsyncMock()

        await repository.ingest_batch(sample_telemetry_batch)

        mock_session.commit.assert_called()


class TestIngestPoints:
    """Test individual point ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_empty_list_returns_zero(self, repository):
        """Test ingesting empty list returns 0."""
        result = await repository.ingest_points([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_ingest_points_executes_upsert(
        self, repository, mock_session, sample_telemetry_point
    ):
        """Test point ingestion executes upsert statement."""
        mock_session.execute = AsyncMock()

        result = await repository.ingest_points([sample_telemetry_point])

        assert result == 1
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_multiple_points(
        self, repository, mock_session, sample_device_id, sample_site_id
    ):
        """Test ingesting multiple points."""
        mock_session.execute = AsyncMock()

        points = [
            TelemetryPoint(
                time=datetime.now(timezone.utc) - timedelta(seconds=i),
                device_id=sample_device_id,
                site_id=sample_site_id,
                metric_name="power_w",
                metric_value=float(i * 100),
                quality=DataQuality.GOOD,
            )
            for i in range(5)
        ]

        result = await repository.ingest_points(points)

        assert result == 5


class TestGetLatestReadings:
    """Test getting latest readings."""

    @pytest.mark.asyncio
    async def test_get_latest_returns_empty_dict_when_no_data(
        self, repository, mock_session, sample_device_id
    ):
        """Test returns empty dict when no data."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_latest_readings(sample_device_id)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_latest_with_metric_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test getting latest readings with metric filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_latest_readings(
            sample_device_id,
            metric_names=["battery_soc_pct", "pv_power_w"]
        )

        # Verify execute was called
        mock_session.execute.assert_called()


class TestGetTimeRange:
    """Test time range queries."""

    @pytest.mark.asyncio
    async def test_get_time_range_returns_empty_list_when_no_data(
        self, repository, mock_session, sample_device_id
    ):
        """Test returns empty list when no data in range."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        now = datetime.now(timezone.utc)
        result = await repository.get_time_range(
            device_id=sample_device_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_time_range_with_metric_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test time range query with metric filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        now = datetime.now(timezone.utc)
        await repository.get_time_range(
            device_id=sample_device_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
            metric_names=["power_w"],
        )

        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_time_range_respects_limit(
        self, repository, mock_session, sample_device_id
    ):
        """Test time range query respects limit parameter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        now = datetime.now(timezone.utc)
        await repository.get_time_range(
            device_id=sample_device_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
            limit=100,
        )

        mock_session.execute.assert_called()


class TestGetSiteTimeRange:
    """Test site-wide time range queries."""

    @pytest.mark.asyncio
    async def test_get_site_time_range_returns_empty_list(
        self, repository, mock_session, sample_site_id
    ):
        """Test returns empty list when no data."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        now = datetime.now(timezone.utc)
        result = await repository.get_site_time_range(
            site_id=sample_site_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_get_site_time_range_with_device_filter(
        self, repository, mock_session, sample_site_id, sample_device_id
    ):
        """Test site time range with device filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        now = datetime.now(timezone.utc)
        await repository.get_site_time_range(
            site_id=sample_site_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
            device_ids=[sample_device_id],
        )

        mock_session.execute.assert_called()


class TestGetTimeBucketAggregates:
    """Test time bucket aggregation."""

    @pytest.mark.asyncio
    async def test_get_aggregates_returns_empty_when_no_site(
        self, repository, mock_session, sample_device_id
    ):
        """Test returns empty list when device has no site_id."""
        # First query for site_id returns None
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=None))
        )

        now = datetime.now(timezone.utc)
        result = await repository.get_time_bucket_aggregates(
            device_id=sample_device_id,
            metric_name="power_w",
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        assert result == []


class TestDeleteOldData:
    """Test data deletion."""

    @pytest.mark.asyncio
    async def test_delete_old_data_returns_count(
        self, repository, mock_session
    ):
        """Test delete returns row count."""
        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_session.execute = AsyncMock(return_value=mock_result)

        older_than = datetime.now(timezone.utc) - timedelta(days=7)
        result = await repository.delete_old_data(older_than)

        assert result == 100

    @pytest.mark.asyncio
    async def test_delete_old_data_with_device_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test delete with device filter."""
        mock_result = MagicMock()
        mock_result.rowcount = 50
        mock_session.execute = AsyncMock(return_value=mock_result)

        older_than = datetime.now(timezone.utc) - timedelta(days=7)
        result = await repository.delete_old_data(older_than, device_id=sample_device_id)

        assert result == 50
        mock_session.execute.assert_called()


class TestMarkAsProcessed:
    """Test marking data as processed."""

    @pytest.mark.asyncio
    async def test_mark_as_processed_returns_count(
        self, repository, mock_session, sample_device_id
    ):
        """Test mark as processed returns updated count."""
        mock_result = MagicMock()
        mock_result.rowcount = 25
        mock_session.execute = AsyncMock(return_value=mock_result)

        before_time = datetime.now(timezone.utc)
        result = await repository.mark_as_processed(sample_device_id, before_time)

        assert result == 25


class TestGetDeviceStats:
    """Test device statistics."""

    @pytest.mark.asyncio
    async def test_get_device_stats_returns_dict(
        self, repository, mock_session, sample_device_id
    ):
        """Test returns stats dictionary."""
        now = datetime.now(timezone.utc)
        mock_row = MagicMock()
        mock_row.total_count = 1000
        mock_row.first_time = now - timedelta(days=30)
        mock_row.last_time = now
        mock_row.metric_count = 15

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_device_stats(sample_device_id)

        assert result["total_records"] == 1000
        assert result["distinct_metrics"] == 15


class TestGetIngestionStats:
    """Test ingestion statistics."""

    @pytest.mark.asyncio
    async def test_get_ingestion_stats_returns_dict(
        self, repository, mock_session
    ):
        """Test returns ingestion stats dictionary."""
        mock_row = MagicMock()
        mock_row.batch_count = 50
        mock_row.total_inserted = 5000
        mock_row.total_failed = 10
        mock_row.avg_time_ms = 150.5

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        since = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await repository.get_ingestion_stats(since)

        assert result["batch_count"] == 50
        assert result["total_inserted"] == 5000
        assert result["total_failed"] == 10
        assert result["avg_processing_time_ms"] == 150.5

    @pytest.mark.asyncio
    async def test_get_ingestion_stats_handles_none_values(
        self, repository, mock_session
    ):
        """Test handles None values in stats."""
        mock_row = MagicMock()
        mock_row.batch_count = None
        mock_row.total_inserted = None
        mock_row.total_failed = None
        mock_row.avg_time_ms = None

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)

        since = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await repository.get_ingestion_stats(since)

        assert result["batch_count"] == 0
        assert result["total_inserted"] == 0
        assert result["total_failed"] == 0
        assert result["avg_processing_time_ms"] == 0
