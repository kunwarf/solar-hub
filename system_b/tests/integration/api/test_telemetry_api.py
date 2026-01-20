"""
Integration tests for Telemetry API endpoints.

Tests telemetry ingestion, retrieval, and aggregation endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import telemetry
from app.api.v1.telemetry import router


@pytest.fixture
def app():
    """Create a test FastAPI application."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_device_id():
    return uuid4()


@pytest.fixture
def sample_site_id():
    return uuid4()


class TestIngestTelemetry:
    """Test telemetry ingestion endpoints."""

    def test_ingest_telemetry_batch(
        self, client, sample_device_id, sample_site_id
    ):
        """Test batch telemetry ingestion."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.ingest_telemetry = AsyncMock(return_value=3)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/telemetry/ingest",
                json={
                    "points": [
                        {
                            "device_id": str(sample_device_id),
                            "site_id": str(sample_site_id),
                            "metrics": {
                                "battery_soc_pct": 75.5,
                                "pv_power_w": 3500,
                                "grid_power_w": -500,
                            },
                            "source": "device",
                        }
                    ]
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["success"] is True
            assert data["inserted"] == 3

    def test_ingest_telemetry_empty_batch(self, client):
        """Test ingestion with empty batch."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.ingest_telemetry = AsyncMock(return_value=0)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/telemetry/ingest",
                json={"points": []},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["success"] is True
            assert data["inserted"] == 0


class TestGetLatestTelemetry:
    """Test latest telemetry endpoint."""

    def test_get_latest_telemetry(
        self, client, sample_device_id
    ):
        """Test getting latest telemetry."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_latest_telemetry = AsyncMock(return_value={
                "battery_soc_pct": {
                    "value": 75.5,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "quality": "good",
                    "unit": "%",
                }
            })
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/telemetry/latest/{sample_device_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["device_id"] == str(sample_device_id)
            assert "battery_soc_pct" in data["readings"]

    def test_get_latest_telemetry_with_filter(
        self, client, sample_device_id
    ):
        """Test getting latest telemetry with metric filter."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_latest_telemetry = AsyncMock(return_value={})
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/telemetry/latest/{sample_device_id}",
                params={"metric_names": ["battery_soc_pct", "pv_power_w"]},
            )

            assert response.status_code == 200
            mock_service.get_latest_telemetry.assert_called_once()


class TestGetTelemetryHistory:
    """Test telemetry history endpoint."""

    def test_get_telemetry_history(
        self, client, sample_device_id
    ):
        """Test getting telemetry history."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            start_time = datetime.now(timezone.utc) - timedelta(hours=1)

            mock_service = MagicMock()
            mock_service.get_device_telemetry = AsyncMock(return_value=[
                {
                    "timestamp": start_time.isoformat(),
                    "metric_name": "battery_soc_pct",
                    "value": 75.5,
                }
            ])
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/telemetry/history/{sample_device_id}",
                params={"start_time": start_time.isoformat()},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1


class TestGetSiteTelemetry:
    """Test site telemetry endpoint."""

    def test_get_site_telemetry(
        self, client, sample_site_id
    ):
        """Test getting site-wide telemetry."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            start_time = datetime.now(timezone.utc) - timedelta(hours=1)

            mock_service = MagicMock()
            mock_service.get_site_telemetry = AsyncMock(return_value=[])
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/telemetry/site/{sample_site_id}",
                params={"start_time": start_time.isoformat()},
            )

            assert response.status_code == 200


class TestGetAggregatedTelemetry:
    """Test aggregated telemetry endpoint."""

    def test_get_aggregated_telemetry(
        self, client, sample_device_id
    ):
        """Test getting aggregated telemetry."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            start_time = datetime.now(timezone.utc) - timedelta(hours=24)
            bucket_time = datetime.now(timezone.utc) - timedelta(hours=23)

            mock_service = MagicMock()
            mock_service.get_aggregated_telemetry = AsyncMock(return_value=[
                {
                    "bucket": bucket_time.isoformat(),
                    "avg": 75.5,
                    "min": 70.0,
                    "max": 80.0,
                    "first": 72.0,
                    "last": 78.0,
                    "delta": 6.0,
                    "sample_count": 60,
                    "quality_percent": 98.5,
                }
            ])
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/telemetry/aggregate/{sample_device_id}/battery_soc_pct",
                params={
                    "start_time": start_time.isoformat(),
                    "bucket_interval": "1 hour",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["avg"] == 75.5


class TestGetPowerChart:
    """Test power chart endpoint."""

    def test_get_power_chart(
        self, client, sample_site_id
    ):
        """Test getting power chart data."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            start_time = datetime.now(timezone.utc) - timedelta(hours=24)

            mock_service = MagicMock()
            mock_service.get_site_power_chart = AsyncMock(return_value=[])
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/telemetry/power-chart/{sample_site_id}",
                params={"start_time": start_time.isoformat()},
            )

            assert response.status_code == 200


class TestGetTelemetryStats:
    """Test telemetry stats endpoint."""

    def test_get_telemetry_stats(
        self, client, sample_device_id
    ):
        """Test getting telemetry stats."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_device_stats = AsyncMock(return_value={
                "total_records": 10000,
                "first_reading": datetime.now(timezone.utc).isoformat(),
                "last_reading": datetime.now(timezone.utc).isoformat(),
                "distinct_metrics": 15,
            })
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/telemetry/stats/{sample_device_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_records"] == 10000


class TestGetIngestionStats:
    """Test ingestion stats endpoint."""

    def test_get_ingestion_stats(self, client):
        """Test getting ingestion stats."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.get_ingestion_stats = AsyncMock(return_value={
                "batch_count": 500,
                "total_records": 50000,
            })
            MockService.return_value = mock_service

            response = client.get(
                "/api/v1/telemetry/ingestion-stats",
                params={"hours": 24},
            )

            assert response.status_code == 200


class TestCheckDataGaps:
    """Test data gaps endpoint."""

    def test_check_data_gaps(
        self, client, sample_device_id
    ):
        """Test checking for data gaps."""
        with patch("app.api.v1.telemetry.TelemetryRepository") as MockRepo, \
             patch("app.api.v1.telemetry.TelemetryService") as MockService:

            mock_service = MagicMock()
            mock_service.check_data_gaps = AsyncMock(return_value=[
                {
                    "start": datetime.now(timezone.utc).isoformat(),
                    "end": datetime.now(timezone.utc).isoformat(),
                    "duration_seconds": 300,
                }
            ])
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/telemetry/gaps/{sample_device_id}/battery_soc_pct",
                params={"expected_interval_seconds": 60, "hours": 24},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
