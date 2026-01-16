"""
Unit tests for TelemetryService.

Tests telemetry ingestion, validation, and retrieval operations.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.application.services.telemetry_service import TelemetryService
from app.domain.entities.telemetry import (
    TelemetryPoint,
    TelemetryBatch,
    TelemetryAggregate,
    MetricDefinition,
    DataQuality,
)


@pytest.fixture
def mock_telemetry_repo():
    """Create a mock telemetry repository."""
    repo = AsyncMock()
    repo.ingest_points = AsyncMock(return_value=5)
    repo.ingest_batch = AsyncMock(return_value=(10, 0))
    repo.get_latest_readings = AsyncMock(return_value={})
    repo.get_time_range = AsyncMock(return_value=[])
    repo.get_site_time_range = AsyncMock(return_value=[])
    repo.get_time_bucket_aggregates = AsyncMock(return_value=[])
    repo.get_site_power_aggregate = AsyncMock(return_value=[])
    repo.get_metric_definitions = AsyncMock(return_value=[])
    repo.upsert_metric_definition = AsyncMock()
    repo.get_device_stats = AsyncMock(return_value={})
    repo.get_ingestion_stats = AsyncMock(return_value={})
    repo.delete_old_data = AsyncMock(return_value=100)
    return repo


@pytest.fixture
def mock_event_repo():
    """Create a mock event repository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def service(mock_telemetry_repo, mock_event_repo):
    """Create a TelemetryService with mock repositories."""
    return TelemetryService(mock_telemetry_repo, mock_event_repo)


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


class TestTelemetryServiceInit:
    """Test service initialization."""

    def test_init_with_repos(self, mock_telemetry_repo, mock_event_repo):
        """Test service initializes with repositories."""
        service = TelemetryService(mock_telemetry_repo, mock_event_repo)
        assert service._telemetry_repo == mock_telemetry_repo
        assert service._event_repo == mock_event_repo

    def test_init_without_event_repo(self, mock_telemetry_repo):
        """Test service initializes without event repository."""
        service = TelemetryService(mock_telemetry_repo)
        assert service._telemetry_repo == mock_telemetry_repo
        assert service._event_repo is None


class TestIngestTelemetry:
    """Test telemetry ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_telemetry_returns_count(
        self, service, mock_telemetry_repo, sample_device_id, sample_site_id
    ):
        """Test ingest returns count of metrics."""
        mock_telemetry_repo.ingest_points = AsyncMock(return_value=3)

        metrics = {
            "battery_soc_pct": 75.5,
            "pv_power_w": 3500,
            "grid_power_w": -500,
        }

        result = await service.ingest_telemetry(
            device_id=sample_device_id,
            site_id=sample_site_id,
            metrics=metrics,
        )

        assert result == 3
        mock_telemetry_repo.ingest_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_telemetry_with_timestamp(
        self, service, mock_telemetry_repo, sample_device_id, sample_site_id
    ):
        """Test ingest with custom timestamp."""
        mock_telemetry_repo.ingest_points = AsyncMock(return_value=1)

        timestamp = datetime.now(timezone.utc) - timedelta(hours=1)
        metrics = {"battery_soc_pct": 75.5}

        await service.ingest_telemetry(
            device_id=sample_device_id,
            site_id=sample_site_id,
            metrics=metrics,
            timestamp=timestamp,
        )

        # Verify timestamp was passed
        call_args = mock_telemetry_repo.ingest_points.call_args
        points = call_args[0][0]
        assert points[0].time == timestamp

    @pytest.mark.asyncio
    async def test_ingest_telemetry_skips_none_values(
        self, service, mock_telemetry_repo, sample_device_id, sample_site_id
    ):
        """Test ingest skips None values."""
        mock_telemetry_repo.ingest_points = AsyncMock(return_value=2)

        metrics = {
            "battery_soc_pct": 75.5,
            "pv_power_w": None,  # Should be skipped
            "grid_power_w": -500,
        }

        await service.ingest_telemetry(
            device_id=sample_device_id,
            site_id=sample_site_id,
            metrics=metrics,
        )

        # Verify only 2 points were passed
        call_args = mock_telemetry_repo.ingest_points.call_args
        points = call_args[0][0]
        assert len(points) == 2

    @pytest.mark.asyncio
    async def test_ingest_telemetry_handles_string_values(
        self, service, mock_telemetry_repo, sample_device_id, sample_site_id
    ):
        """Test ingest handles string metric values."""
        mock_telemetry_repo.ingest_points = AsyncMock(return_value=1)

        metrics = {"device_state": "running"}

        await service.ingest_telemetry(
            device_id=sample_device_id,
            site_id=sample_site_id,
            metrics=metrics,
        )

        call_args = mock_telemetry_repo.ingest_points.call_args
        points = call_args[0][0]
        assert points[0].metric_value_str == "running"

    @pytest.mark.asyncio
    async def test_ingest_telemetry_returns_zero_for_empty(
        self, service, sample_device_id, sample_site_id
    ):
        """Test ingest returns 0 for empty metrics."""
        result = await service.ingest_telemetry(
            device_id=sample_device_id,
            site_id=sample_site_id,
            metrics={},
        )

        assert result == 0


class TestIngestBatch:
    """Test batch telemetry ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_batch_returns_counts(
        self, service, mock_telemetry_repo
    ):
        """Test batch ingest returns inserted and failed counts."""
        mock_telemetry_repo.ingest_batch = AsyncMock(return_value=(10, 2))

        batch = TelemetryBatch(
            source_type="modbus",
            points=[],  # Would contain actual points
        )

        inserted, failed = await service.ingest_batch(batch)

        assert inserted == 10
        assert failed == 2

    @pytest.mark.asyncio
    async def test_ingest_batch_assigns_batch_id(
        self, service, mock_telemetry_repo
    ):
        """Test batch ingest assigns batch ID if missing."""
        mock_telemetry_repo.ingest_batch = AsyncMock(return_value=(0, 0))

        batch = TelemetryBatch(
            source_type="modbus",
            points=[],
        )
        assert batch.batch_id is None

        await service.ingest_batch(batch)

        assert batch.batch_id is not None


class TestGetLatestTelemetry:
    """Test getting latest telemetry."""

    @pytest.mark.asyncio
    async def test_get_latest_returns_formatted_dict(
        self, service, mock_telemetry_repo, sample_device_id
    ):
        """Test returns properly formatted telemetry dict."""
        now = datetime.now(timezone.utc)
        mock_point = MagicMock()
        mock_point.metric_value = 75.5
        mock_point.metric_value_str = None
        mock_point.time = now
        mock_point.quality = DataQuality.GOOD
        mock_point.unit = "%"

        mock_telemetry_repo.get_latest_readings = AsyncMock(
            return_value={"battery_soc_pct": mock_point}
        )

        result = await service.get_latest_telemetry(sample_device_id)

        assert "battery_soc_pct" in result
        assert result["battery_soc_pct"]["value"] == 75.5
        assert result["battery_soc_pct"]["quality"] == "good"
        assert result["battery_soc_pct"]["unit"] == "%"

    @pytest.mark.asyncio
    async def test_get_latest_returns_empty_dict(
        self, service, mock_telemetry_repo, sample_device_id
    ):
        """Test returns empty dict when no data."""
        mock_telemetry_repo.get_latest_readings = AsyncMock(return_value={})

        result = await service.get_latest_telemetry(sample_device_id)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_latest_with_metric_filter(
        self, service, mock_telemetry_repo, sample_device_id
    ):
        """Test get latest with metric filter."""
        mock_telemetry_repo.get_latest_readings = AsyncMock(return_value={})

        await service.get_latest_telemetry(
            sample_device_id,
            metric_names=["battery_soc_pct", "pv_power_w"]
        )

        mock_telemetry_repo.get_latest_readings.assert_called_once_with(
            sample_device_id,
            ["battery_soc_pct", "pv_power_w"]
        )


class TestGetDeviceTelemetry:
    """Test getting device telemetry history."""

    @pytest.mark.asyncio
    async def test_get_device_telemetry_returns_list(
        self, service, mock_telemetry_repo, sample_device_id
    ):
        """Test returns list of telemetry dicts."""
        now = datetime.now(timezone.utc)
        mock_point = MagicMock()
        mock_point.time = now
        mock_point.metric_name = "battery_soc_pct"
        mock_point.metric_value = 75.5
        mock_point.metric_value_str = None
        mock_point.quality = DataQuality.GOOD
        mock_point.unit = "%"

        mock_telemetry_repo.get_time_range = AsyncMock(return_value=[mock_point])

        result = await service.get_device_telemetry(
            device_id=sample_device_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        assert len(result) == 1
        assert result[0]["metric_name"] == "battery_soc_pct"
        assert result[0]["value"] == 75.5


class TestGetSiteTelemetry:
    """Test getting site-wide telemetry."""

    @pytest.mark.asyncio
    async def test_get_site_telemetry_returns_list(
        self, service, mock_telemetry_repo, sample_site_id, sample_device_id
    ):
        """Test returns site telemetry with device IDs."""
        now = datetime.now(timezone.utc)
        mock_point = MagicMock()
        mock_point.time = now
        mock_point.device_id = sample_device_id
        mock_point.metric_name = "pv_power_w"
        mock_point.metric_value = 3500
        mock_point.metric_value_str = None
        mock_point.quality = DataQuality.GOOD
        mock_point.unit = "W"

        mock_telemetry_repo.get_site_time_range = AsyncMock(return_value=[mock_point])

        result = await service.get_site_telemetry(
            site_id=sample_site_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        assert len(result) == 1
        assert result[0]["device_id"] == str(sample_device_id)


class TestGetAggregatedTelemetry:
    """Test aggregated telemetry queries."""

    @pytest.mark.asyncio
    async def test_get_aggregated_telemetry_returns_formatted(
        self, service, mock_telemetry_repo, sample_device_id
    ):
        """Test returns formatted aggregate data."""
        now = datetime.now(timezone.utc)
        mock_agg = MagicMock()
        mock_agg.bucket = now
        mock_agg.avg_value = 75.5
        mock_agg.min_value = 70.0
        mock_agg.max_value = 80.0
        mock_agg.first_value = 72.0
        mock_agg.last_value = 78.0
        mock_agg.delta_value = 6.0
        mock_agg.sample_count = 60
        mock_agg.data_quality_percent = 98.5

        mock_telemetry_repo.get_time_bucket_aggregates = AsyncMock(
            return_value=[mock_agg]
        )

        result = await service.get_aggregated_telemetry(
            device_id=sample_device_id,
            metric_name="battery_soc_pct",
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        assert len(result) == 1
        assert result[0]["avg"] == 75.5
        assert result[0]["min"] == 70.0
        assert result[0]["max"] == 80.0
        assert result[0]["sample_count"] == 60


class TestMetricDefinitions:
    """Test metric definition management."""

    @pytest.mark.asyncio
    async def test_load_metric_definitions(
        self, service, mock_telemetry_repo
    ):
        """Test loading metric definitions."""
        mock_def = MagicMock()
        mock_def.metric_name = "battery_soc_pct"
        mock_telemetry_repo.get_metric_definitions = AsyncMock(return_value=[mock_def])

        await service.load_metric_definitions()

        assert "battery_soc_pct" in service._metric_definitions

    @pytest.mark.asyncio
    async def test_register_metric_definition(
        self, service, mock_telemetry_repo
    ):
        """Test registering a metric definition."""
        metric_def = MetricDefinition(
            metric_name="test_metric",
            display_name="Test Metric",
            unit="units",
            min_value=0,
            max_value=100,
        )

        await service.register_metric_definition(metric_def)

        mock_telemetry_repo.upsert_metric_definition.assert_called_once_with(metric_def)
        assert service.get_metric_definition("test_metric") == metric_def


class TestGetDeviceStats:
    """Test device statistics."""

    @pytest.mark.asyncio
    async def test_get_device_stats(
        self, service, mock_telemetry_repo, sample_device_id
    ):
        """Test gets device stats from repository."""
        expected_stats = {
            "total_records": 1000,
            "distinct_metrics": 15,
        }
        mock_telemetry_repo.get_device_stats = AsyncMock(return_value=expected_stats)

        result = await service.get_device_stats(sample_device_id)

        assert result == expected_stats


class TestGetIngestionStats:
    """Test ingestion statistics."""

    @pytest.mark.asyncio
    async def test_get_ingestion_stats(
        self, service, mock_telemetry_repo
    ):
        """Test gets ingestion stats."""
        expected_stats = {
            "batch_count": 50,
            "total_inserted": 5000,
        }
        mock_telemetry_repo.get_ingestion_stats = AsyncMock(return_value=expected_stats)

        result = await service.get_ingestion_stats(hours=24)

        assert result == expected_stats


class TestCheckDataGaps:
    """Test data gap detection."""

    @pytest.mark.asyncio
    async def test_check_data_gaps_returns_empty_for_insufficient_data(
        self, service, mock_telemetry_repo, sample_device_id
    ):
        """Test returns empty when insufficient data."""
        mock_telemetry_repo.get_time_range = AsyncMock(return_value=[])

        result = await service.check_data_gaps(
            device_id=sample_device_id,
            metric_name="battery_soc_pct",
            expected_interval_seconds=60,
        )

        assert result == []


class TestCleanupOldData:
    """Test data cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_old_data_returns_count(
        self, service, mock_telemetry_repo
    ):
        """Test cleanup returns deleted count."""
        mock_telemetry_repo.delete_old_data = AsyncMock(return_value=100)

        result = await service.cleanup_old_data(retention_days=90)

        assert result == 100
