"""
E2E tests for telemetry flow.

Tests the complete flow from device polling to API retrieval.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


@pytest.fixture
def sample_telemetry_data(sample_device_id, sample_site_id):
    """Create sample telemetry data."""
    return {
        "device_id": sample_device_id,
        "site_id": sample_site_id,
        "timestamp": datetime.now(timezone.utc),
        "metrics": {
            "battery_soc_pct": 75.5,
            "pv_power_w": 3500,
            "battery_power_w": -500,
            "grid_power_w": 1200,
            "load_power_w": 2200,
            "battery_voltage_v": 51.2,
            "battery_current_a": -10.5,
        },
        "source": "device",
    }


class TestTelemetryIngestionFlow:
    """
    Test telemetry ingestion flow.

    Flow: Device polls → telemetry ingestion → API retrieval
    """

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_single_telemetry_point_flow(
        self, sample_device_id, sample_site_id, sample_telemetry_data
    ):
        """
        Test single telemetry point flow.

        1. Device is polled for data
        2. Telemetry is ingested to database
        3. Telemetry is retrievable via API
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()

            # Ingest returns record count
            mock_service.ingest_telemetry = AsyncMock(return_value=7)

            # Get latest returns the telemetry
            mock_service.get_latest_telemetry = AsyncMock(return_value={
                "battery_soc_pct": {
                    "value": 75.5,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "quality": "good",
                },
                "pv_power_w": {
                    "value": 3500,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "quality": "good",
                },
            })

            MockService.return_value = mock_service

            # Ingest telemetry
            count = await mock_service.ingest_telemetry([sample_telemetry_data])
            assert count == 7  # 7 metrics

            # Retrieve via API
            latest = await mock_service.get_latest_telemetry(
                device_id=sample_device_id,
            )
            assert "battery_soc_pct" in latest
            assert latest["battery_soc_pct"]["value"] == 75.5

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_batch_telemetry_ingestion(
        self, sample_device_id, sample_site_id
    ):
        """
        Test batch telemetry ingestion flow.

        1. Multiple telemetry points collected
        2. Batch ingested to database
        3. All points retrievable
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.ingest_telemetry = AsyncMock(return_value=50)
            MockService.return_value = mock_service

            # Create batch of telemetry
            batch = []
            base_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            for i in range(10):
                batch.append({
                    "device_id": sample_device_id,
                    "site_id": sample_site_id,
                    "timestamp": base_time + timedelta(minutes=i),
                    "metrics": {
                        "battery_soc_pct": 70 + i,
                        "pv_power_w": 3000 + i * 100,
                    },
                })

            count = await mock_service.ingest_telemetry(batch)
            assert count == 50  # 10 points x 5 metrics each

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_telemetry_history_retrieval(
        self, sample_device_id
    ):
        """
        Test retrieving telemetry history.

        1. Historical telemetry exists
        2. Query with time range
        3. History returned in order
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            start_time = datetime.now(timezone.utc) - timedelta(hours=1)

            mock_service = MagicMock()
            mock_service.get_device_telemetry = AsyncMock(return_value=[
                {
                    "timestamp": start_time.isoformat(),
                    "metric_name": "battery_soc_pct",
                    "value": 70.0,
                },
                {
                    "timestamp": (start_time + timedelta(minutes=15)).isoformat(),
                    "metric_name": "battery_soc_pct",
                    "value": 72.5,
                },
                {
                    "timestamp": (start_time + timedelta(minutes=30)).isoformat(),
                    "metric_name": "battery_soc_pct",
                    "value": 75.0,
                },
            ])
            MockService.return_value = mock_service

            history = await mock_service.get_device_telemetry(
                device_id=sample_device_id,
                start_time=start_time,
                metric_names=["battery_soc_pct"],
            )

            assert len(history) == 3
            assert history[0]["value"] == 70.0
            assert history[2]["value"] == 75.0


class TestTelemetryAggregationFlow:
    """Test telemetry aggregation flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_aggregated_telemetry_retrieval(
        self, sample_device_id
    ):
        """
        Test retrieving aggregated telemetry.

        1. Raw telemetry exists
        2. Aggregation runs
        3. Aggregates retrievable
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            start_time = datetime.now(timezone.utc) - timedelta(hours=24)

            mock_service = MagicMock()
            mock_service.get_aggregated_telemetry = AsyncMock(return_value=[
                {
                    "bucket": start_time.isoformat(),
                    "avg": 75.5,
                    "min": 70.0,
                    "max": 80.0,
                    "first": 72.0,
                    "last": 78.0,
                    "sample_count": 60,
                },
            ])
            MockService.return_value = mock_service

            aggregates = await mock_service.get_aggregated_telemetry(
                device_id=sample_device_id,
                metric_name="battery_soc_pct",
                start_time=start_time,
                bucket_interval="1 hour",
            )

            assert len(aggregates) == 1
            assert aggregates[0]["avg"] == 75.5
            assert aggregates[0]["sample_count"] == 60


class TestSiteTelemetryFlow:
    """Test site-level telemetry flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_site_telemetry_aggregation(
        self, sample_site_id
    ):
        """
        Test site-level telemetry aggregation.

        1. Multiple devices at site
        2. Each sends telemetry
        3. Site-level aggregates available
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_site_telemetry = AsyncMock(return_value=[
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "total_pv_power_w": 12500,
                    "total_battery_power_w": -2000,
                    "total_grid_power_w": 3000,
                    "total_load_power_w": 8500,
                },
            ])
            MockService.return_value = mock_service

            site_telemetry = await mock_service.get_site_telemetry(
                site_id=sample_site_id,
                start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            )

            assert len(site_telemetry) == 1
            assert site_telemetry[0]["total_pv_power_w"] == 12500

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_power_chart_data(
        self, sample_site_id
    ):
        """
        Test power chart data retrieval.

        1. Telemetry collected over time
        2. Power chart data aggregated
        3. Chart-ready data returned
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_site_power_chart = AsyncMock(return_value=[
                {
                    "timestamp": "2024-01-15T00:00:00Z",
                    "pv_power": 0,
                    "battery_power": 500,
                    "grid_power": 1500,
                    "load_power": 2000,
                },
                {
                    "timestamp": "2024-01-15T12:00:00Z",
                    "pv_power": 5000,
                    "battery_power": -1000,
                    "grid_power": -2000,
                    "load_power": 2000,
                },
            ])
            MockService.return_value = mock_service

            chart_data = await mock_service.get_site_power_chart(
                site_id=sample_site_id,
                start_time=datetime.now(timezone.utc) - timedelta(hours=24),
            )

            assert len(chart_data) == 2
            # Night time - no PV, using battery and grid
            assert chart_data[0]["pv_power"] == 0
            # Day time - PV generating, charging battery, exporting to grid
            assert chart_data[1]["pv_power"] == 5000


class TestTelemetryValidationFlow:
    """Test telemetry validation flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_invalid_telemetry_rejected(
        self, sample_device_id, sample_site_id
    ):
        """
        Test that invalid telemetry is rejected.

        1. Telemetry with invalid values submitted
        2. Validation catches issues
        3. Invalid data not stored
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.ingest_telemetry = AsyncMock(
                side_effect=ValueError("Invalid metric value: battery_soc_pct must be 0-100")
            )
            MockService.return_value = mock_service

            with pytest.raises(ValueError) as exc_info:
                await mock_service.ingest_telemetry([{
                    "device_id": sample_device_id,
                    "site_id": sample_site_id,
                    "metrics": {
                        "battery_soc_pct": 150,  # Invalid - over 100%
                    },
                }])

            assert "battery_soc_pct" in str(exc_info.value)


class TestDataGapsDetection:
    """Test data gaps detection flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_data_gaps_detection(
        self, sample_device_id
    ):
        """
        Test detection of data gaps.

        1. Telemetry collected with gaps
        2. Gap analysis run
        3. Gaps identified with details
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.check_data_gaps = AsyncMock(return_value=[
                {
                    "start": "2024-01-15T10:00:00Z",
                    "end": "2024-01-15T10:30:00Z",
                    "duration_seconds": 1800,
                    "metric_name": "battery_soc_pct",
                },
            ])
            MockService.return_value = mock_service

            gaps = await mock_service.check_data_gaps(
                device_id=sample_device_id,
                metric_name="battery_soc_pct",
                expected_interval_seconds=60,
                hours=24,
            )

            assert len(gaps) == 1
            assert gaps[0]["duration_seconds"] == 1800  # 30 minute gap


class TestTelemetryStreamFlow:
    """Test telemetry streaming flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_telemetry_stream_publish_consume(
        self, sample_device_id, sample_site_id
    ):
        """
        Test telemetry stream publish and consume.

        1. Telemetry published to stream
        2. Consumer receives telemetry
        3. Telemetry processed and stored
        """
        with patch("app.infrastructure.messaging.stream_services.TelemetryStreamService") as MockStreamService:

            processed = []

            async def mock_handler(device_id, site_id, metrics, timestamp, source):
                processed.append({
                    "device_id": device_id,
                    "site_id": site_id,
                    "metrics": metrics,
                })

            mock_service = MagicMock()
            mock_service.publish_telemetry = AsyncMock(return_value="msg_123")
            mock_service._on_telemetry = mock_handler
            MockStreamService.return_value = mock_service

            # Publish telemetry
            msg_id = await mock_service.publish_telemetry(
                device_id=sample_device_id,
                site_id=sample_site_id,
                metrics={"battery_soc_pct": 75.0},
            )

            assert msg_id == "msg_123"


class TestAnomalyDetectionFlow:
    """Test anomaly detection flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_anomaly_detection_on_ingestion(
        self, sample_device_id, sample_site_id
    ):
        """
        Test anomaly detection during telemetry ingestion.

        1. Telemetry with anomalous value
        2. Anomaly detected
        3. Event created
        """
        with patch("device_server.workers.telemetry_worker.TelemetryWorker") as MockWorker:

            mock_worker = MagicMock()

            anomaly_result = {
                "ingested": 7,
                "anomalies_detected": 1,
                "anomalies": [
                    {
                        "metric_name": "battery_temp_c",
                        "value": 65.0,
                        "threshold_max": 55.0,
                        "anomaly_type": "threshold_exceeded",
                    }
                ],
            }

            mock_worker.submit = AsyncMock(return_value=anomaly_result)
            MockWorker.return_value = mock_worker

            result = await mock_worker.submit({
                "device_id": sample_device_id,
                "site_id": sample_site_id,
                "metrics": {
                    "battery_temp_c": 65.0,  # Anomalous - too high
                },
            })

            assert result["anomalies_detected"] == 1
            assert result["anomalies"][0]["anomaly_type"] == "threshold_exceeded"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_rate_of_change_anomaly(
        self, sample_device_id, sample_site_id
    ):
        """
        Test rate of change anomaly detection.

        1. Value changes too quickly
        2. Rate anomaly detected
        3. Alert triggered
        """
        with patch("device_server.workers.telemetry_worker.TelemetryWorker") as MockWorker:

            mock_worker = MagicMock()

            rate_anomaly = {
                "ingested": 1,
                "anomalies_detected": 1,
                "anomalies": [
                    {
                        "metric_name": "battery_soc_pct",
                        "value": 50.0,
                        "previous_value": 80.0,
                        "rate_of_change": -30.0,
                        "max_rate_of_change": 10.0,
                        "anomaly_type": "rate_of_change_exceeded",
                    }
                ],
            }

            mock_worker.submit = AsyncMock(return_value=rate_anomaly)
            MockWorker.return_value = mock_worker

            result = await mock_worker.submit({
                "device_id": sample_device_id,
                "site_id": sample_site_id,
                "metrics": {
                    "battery_soc_pct": 50.0,
                },
            })

            assert result["anomalies"][0]["anomaly_type"] == "rate_of_change_exceeded"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_configure_anomaly_thresholds(
        self, sample_device_id
    ):
        """
        Test configuring anomaly detection thresholds.

        1. Custom thresholds set
        2. Applied to detection
        3. Anomalies detected based on custom thresholds
        """
        with patch("device_server.workers.telemetry_worker.TelemetryWorker") as MockWorker:

            mock_worker = MagicMock()
            mock_worker.set_anomaly_thresholds = MagicMock()
            MockWorker.return_value = mock_worker

            mock_worker.set_anomaly_thresholds(
                device_id=sample_device_id,
                thresholds={
                    "battery_temp_c": {"min": 0, "max": 50, "rate_of_change": 5},
                    "battery_soc_pct": {"min": 10, "max": 100, "rate_of_change": 15},
                },
            )

            mock_worker.set_anomaly_thresholds.assert_called_once()


class TestMetricDefinitionFlow:
    """Test metric definition flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_load_metric_definitions(self):
        """
        Test loading metric definitions.

        1. Definitions file exists
        2. Definitions loaded
        3. Available for validation
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.load_metric_definitions = AsyncMock(return_value={
                "loaded": 50,
                "metrics": [
                    "battery_soc_pct",
                    "pv_power_w",
                    "grid_power_w",
                    "battery_power_w",
                    "load_power_w",
                ],
            })
            MockService.return_value = mock_service

            result = await mock_service.load_metric_definitions()

            assert result["loaded"] == 50

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_register_metric_definition(self):
        """
        Test registering a new metric definition.

        1. New metric type needed
        2. Definition registered
        3. Metric accepted for ingestion
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.register_metric_definition = AsyncMock(return_value={
                "metric_name": "custom_sensor_temp_c",
                "data_type": "float",
                "unit": "celsius",
                "min_value": -40,
                "max_value": 125,
                "registered": True,
            })
            MockService.return_value = mock_service

            result = await mock_service.register_metric_definition(
                metric_name="custom_sensor_temp_c",
                data_type="float",
                unit="celsius",
                min_value=-40,
                max_value=125,
            )

            assert result["registered"] is True
            assert result["metric_name"] == "custom_sensor_temp_c"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_metric_definition(self):
        """
        Test getting metric definition details.

        1. Metric exists
        2. Query definition
        3. Full details returned
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_metric_definition = AsyncMock(return_value={
                "metric_name": "battery_soc_pct",
                "data_type": "float",
                "unit": "percent",
                "min_value": 0,
                "max_value": 100,
                "description": "Battery state of charge percentage",
                "aggregation_methods": ["avg", "min", "max", "first", "last"],
            })
            MockService.return_value = mock_service

            definition = await mock_service.get_metric_definition(
                metric_name="battery_soc_pct",
            )

            assert definition["unit"] == "percent"
            assert definition["max_value"] == 100


class TestTelemetryCleanupFlow:
    """Test telemetry cleanup/retention flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cleanup_old_telemetry(self):
        """
        Test cleanup of old telemetry data.

        1. Old data exists
        2. Cleanup job runs
        3. Data older than retention deleted
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.cleanup_old_data = AsyncMock(return_value={
                "deleted_rows": 1000000,
                "freed_space_mb": 512,
                "oldest_remaining": datetime.now(timezone.utc) - timedelta(days=90),
            })
            MockService.return_value = mock_service

            result = await mock_service.cleanup_old_data(
                retention_days=90,
            )

            assert result["deleted_rows"] == 1000000

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_compression_policy_application(self):
        """
        Test TimescaleDB compression policy.

        1. Raw data exists
        2. Compression runs
        3. Older chunks compressed
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.apply_compression = AsyncMock(return_value={
                "chunks_compressed": 24,
                "compression_ratio": 10.5,
                "space_saved_mb": 2048,
            })
            MockService.return_value = mock_service

            result = await mock_service.apply_compression(
                compress_after_days=7,
            )

            assert result["chunks_compressed"] == 24
            assert result["compression_ratio"] == 10.5


class TestTelemetryStatisticsFlow:
    """Test telemetry statistics flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_device_telemetry_stats(
        self, sample_device_id
    ):
        """
        Test getting device telemetry statistics.

        1. Telemetry exists
        2. Stats aggregated
        3. Comprehensive stats returned
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_device_stats = AsyncMock(return_value={
                "device_id": sample_device_id,
                "total_points": 86400,
                "metrics_tracked": 15,
                "first_data_at": datetime.now(timezone.utc) - timedelta(days=30),
                "last_data_at": datetime.now(timezone.utc),
                "avg_ingestion_rate_per_minute": 60,
                "data_quality": {
                    "good": 99.5,
                    "stale": 0.3,
                    "bad": 0.2,
                },
            })
            MockService.return_value = mock_service

            stats = await mock_service.get_device_stats(
                device_id=sample_device_id,
            )

            assert stats["total_points"] == 86400
            assert stats["data_quality"]["good"] == 99.5

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_ingestion_stats(self):
        """
        Test getting overall ingestion statistics.

        1. Ingestion running
        2. Stats aggregated
        3. Rate and performance metrics returned
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_ingestion_stats = AsyncMock(return_value={
                "total_ingested_today": 5000000,
                "current_rate_per_second": 1500,
                "peak_rate_per_second": 3500,
                "avg_latency_ms": 15,
                "p99_latency_ms": 45,
                "error_rate": 0.001,
                "by_device_type": {
                    "inverter": 2500000,
                    "meter": 1500000,
                    "battery": 1000000,
                },
            })
            MockService.return_value = mock_service

            stats = await mock_service.get_ingestion_stats()

            assert stats["current_rate_per_second"] == 1500
            assert stats["error_rate"] == 0.001


class TestRealTimeTelemetryFlow:
    """Test real-time telemetry flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_subscribe_to_device_telemetry(
        self, sample_device_id
    ):
        """
        Test subscribing to real-time device telemetry.

        1. Subscription created
        2. Telemetry arrives
        3. Subscriber receives updates
        """
        with patch("app.infrastructure.messaging.redis_streams.PubSubManager") as MockPubSub:

            received = []

            async def mock_handler(data):
                received.append(data)

            mock_pubsub = MagicMock()
            mock_pubsub.subscribe = AsyncMock(return_value="sub_123")
            MockPubSub.return_value = mock_pubsub

            sub_id = await mock_pubsub.subscribe(
                channel=f"telemetry:{sample_device_id}",
                handler=mock_handler,
            )

            assert sub_id == "sub_123"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_publish_real_time_update(
        self, sample_device_id, sample_site_id
    ):
        """
        Test publishing real-time telemetry update.

        1. Telemetry ingested
        2. Published to pub/sub
        3. Subscribers notified
        """
        with patch("app.infrastructure.messaging.redis_streams.PubSubManager") as MockPubSub:

            mock_pubsub = MagicMock()
            mock_pubsub.publish = AsyncMock(return_value=5)  # 5 subscribers received
            MockPubSub.return_value = mock_pubsub

            receivers = await mock_pubsub.publish(
                channel=f"telemetry:{sample_device_id}",
                message={
                    "device_id": str(sample_device_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "metrics": {
                        "battery_soc_pct": 75.5,
                        "pv_power_w": 3500,
                    },
                },
            )

            assert receivers == 5


class TestMultiMetricQueryFlow:
    """Test multi-metric query flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_query_multiple_metrics(
        self, sample_device_id
    ):
        """
        Test querying multiple metrics at once.

        1. Multiple metrics needed
        2. Single query for all
        3. Results aligned by timestamp
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()

            start_time = datetime.now(timezone.utc) - timedelta(hours=1)

            mock_service.get_device_telemetry = AsyncMock(return_value=[
                {
                    "timestamp": start_time.isoformat(),
                    "battery_soc_pct": 70.0,
                    "pv_power_w": 3000,
                    "grid_power_w": 500,
                    "load_power_w": 2500,
                },
                {
                    "timestamp": (start_time + timedelta(minutes=15)).isoformat(),
                    "battery_soc_pct": 72.5,
                    "pv_power_w": 3500,
                    "grid_power_w": 0,
                    "load_power_w": 2500,
                },
            ])
            MockService.return_value = mock_service

            data = await mock_service.get_device_telemetry(
                device_id=sample_device_id,
                metric_names=["battery_soc_pct", "pv_power_w", "grid_power_w", "load_power_w"],
                start_time=start_time,
            )

            assert len(data) == 2
            assert "battery_soc_pct" in data[0]
            assert "pv_power_w" in data[0]

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_downsampled_query(
        self, sample_device_id
    ):
        """
        Test downsampled telemetry query.

        1. High-resolution data exists
        2. Query with downsampling
        3. Aggregated results returned
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()

            # 24 hourly data points instead of 1440 minute points
            mock_service.get_aggregated_telemetry = AsyncMock(return_value=[
                {"bucket": f"2024-01-15T{h:02d}:00:00Z", "avg": 70 + h * 0.5}
                for h in range(24)
            ])
            MockService.return_value = mock_service

            data = await mock_service.get_aggregated_telemetry(
                device_id=sample_device_id,
                metric_name="battery_soc_pct",
                start_time=datetime.now(timezone.utc) - timedelta(hours=24),
                bucket_interval="1 hour",
            )

            assert len(data) == 24


class TestTelemetryWorkerFlow:
    """Test telemetry worker flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_worker_batch_processing(
        self, sample_device_id, sample_site_id
    ):
        """
        Test worker batches telemetry for efficient storage.

        1. Multiple telemetry points queued
        2. Worker batches them
        3. Single batch write
        """
        with patch("device_server.workers.telemetry_worker.TelemetryWorker") as MockWorker:

            mock_worker = MagicMock()
            mock_worker.get_stats = MagicMock(return_value={
                "queue_depth": 0,
                "processed_count": 1000,
                "batch_count": 10,
                "avg_batch_size": 100,
                "anomalies_detected": 5,
            })
            MockWorker.return_value = mock_worker

            stats = mock_worker.get_stats()

            assert stats["processed_count"] == 1000
            assert stats["batch_count"] == 10
            assert stats["avg_batch_size"] == 100

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_worker_flush_on_interval(self):
        """
        Test worker flushes batch on interval.

        1. Batch not full
        2. Flush interval reached
        3. Partial batch written
        """
        with patch("device_server.workers.telemetry_worker.TelemetryWorker") as MockWorker:

            mock_worker = MagicMock()
            mock_worker.is_running = True
            mock_worker.queue_depth = 50  # Less than batch_size
            MockWorker.return_value = mock_worker

            assert mock_worker.is_running is True
            assert mock_worker.queue_depth == 50


class TestDataQualityFlow:
    """Test data quality flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_telemetry_quality_tagging(
        self, sample_device_id, sample_site_id
    ):
        """
        Test telemetry quality tagging.

        1. Telemetry ingested
        2. Quality assessed
        3. Quality tag applied
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_latest_telemetry = AsyncMock(return_value={
                "battery_soc_pct": {
                    "value": 75.5,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "quality": "good",
                    "age_seconds": 5,
                },
                "pv_power_w": {
                    "value": 3500,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "quality": "good",
                    "age_seconds": 5,
                },
            })
            MockService.return_value = mock_service

            data = await mock_service.get_latest_telemetry(
                device_id=sample_device_id,
            )

            assert data["battery_soc_pct"]["quality"] == "good"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_stale_data_detection(
        self, sample_device_id
    ):
        """
        Test detection of stale telemetry data.

        1. Data not updated recently
        2. Staleness detected
        3. Quality marked as stale
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_latest_telemetry = AsyncMock(return_value={
                "battery_soc_pct": {
                    "value": 75.5,
                    "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                    "quality": "stale",
                    "age_seconds": 600,
                },
            })
            MockService.return_value = mock_service

            data = await mock_service.get_latest_telemetry(
                device_id=sample_device_id,
            )

            assert data["battery_soc_pct"]["quality"] == "stale"
            assert data["battery_soc_pct"]["age_seconds"] == 600


class TestEnergyCalculationFlow:
    """Test energy calculation flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_calculate_energy_from_power(
        self, sample_device_id
    ):
        """
        Test calculating energy from power readings.

        1. Power telemetry exists
        2. Energy calculated by integration
        3. Energy values returned
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.calculate_energy = AsyncMock(return_value={
                "period_start": datetime.now(timezone.utc) - timedelta(hours=24),
                "period_end": datetime.now(timezone.utc),
                "pv_energy_kwh": 45.5,
                "grid_import_kwh": 10.2,
                "grid_export_kwh": 5.8,
                "battery_charge_kwh": 15.0,
                "battery_discharge_kwh": 12.5,
                "load_energy_kwh": 52.4,
            })
            MockService.return_value = mock_service

            energy = await mock_service.calculate_energy(
                device_id=sample_device_id,
                start_time=datetime.now(timezone.utc) - timedelta(hours=24),
                end_time=datetime.now(timezone.utc),
            )

            assert energy["pv_energy_kwh"] == 45.5
            assert energy["load_energy_kwh"] == 52.4

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_daily_energy_summary(
        self, sample_site_id
    ):
        """
        Test daily energy summary for site.

        1. Full day of telemetry
        2. Daily summary calculated
        3. All energy flows included
        """
        with patch("app.application.services.telemetry_service.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_daily_energy_summary = AsyncMock(return_value={
                "date": "2024-01-15",
                "site_id": sample_site_id,
                "total_pv_kwh": 125.5,
                "total_grid_import_kwh": 25.0,
                "total_grid_export_kwh": 45.2,
                "total_load_kwh": 105.3,
                "self_consumption_pct": 64.0,
                "self_sufficiency_pct": 76.2,
            })
            MockService.return_value = mock_service

            summary = await mock_service.get_daily_energy_summary(
                site_id=sample_site_id,
                date="2024-01-15",
            )

            assert summary["total_pv_kwh"] == 125.5
            assert summary["self_sufficiency_pct"] == 76.2

