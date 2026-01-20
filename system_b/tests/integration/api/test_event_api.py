"""
Integration tests for Event API endpoints.

Tests event creation, retrieval, acknowledgment, and analytics endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import events
from app.api.v1.events import router


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


@pytest.fixture
def sample_event_id():
    return uuid4()


@pytest.fixture
def sample_event_data(sample_event_id, sample_device_id, sample_site_id):
    """Create sample event data."""
    return {
        "id": sample_event_id,
        "device_id": sample_device_id,
        "site_id": sample_site_id,
        "event_type": "alarm",
        "severity": "warning",
        "code": "LOW_BATTERY",
        "message": "Battery SOC below 20%",
        "details": {"soc": 18.5},
        "acknowledged": False,
        "acknowledged_at": None,
        "acknowledged_by": None,
        "created_at": datetime.now(timezone.utc),
    }


class TestCreateEvent:
    """Test event creation endpoint."""

    def test_create_event_success(
        self, client, sample_device_id, sample_site_id, sample_event_data
    ):
        """Test successful event creation."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_event = MagicMock(**sample_event_data)
            mock_service = MagicMock()
            mock_service.create_event = AsyncMock(return_value=mock_event)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/events/",
                json={
                    "device_id": str(sample_device_id),
                    "site_id": str(sample_site_id),
                    "event_type": "alarm",
                    "severity": "warning",
                    "code": "LOW_BATTERY",
                    "message": "Battery SOC below 20%",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["event_type"] == "alarm"
            assert data["severity"] == "warning"

    def test_create_event_validation_error(
        self, client, sample_device_id, sample_site_id
    ):
        """Test event creation with invalid data."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.create_event = AsyncMock(
                side_effect=ValueError("Invalid severity level")
            )
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/events/",
                json={
                    "device_id": str(sample_device_id),
                    "site_id": str(sample_site_id),
                    "event_type": "alarm",
                    "severity": "invalid",
                    "code": "LOW_BATTERY",
                },
            )

            assert response.status_code == 400


class TestGetDeviceEvents:
    """Test get device events endpoint."""

    def test_get_device_events(
        self, client, sample_device_id, sample_event_data
    ):
        """Test getting events for a device."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_event = MagicMock(**sample_event_data)
            mock_service = MagicMock()
            mock_service.get_device_events = AsyncMock(return_value=[mock_event])
            mock_service.count_device_events = AsyncMock(return_value=1)
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/events/device/{sample_device_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert len(data["events"]) == 1

    def test_get_device_events_with_filters(
        self, client, sample_device_id
    ):
        """Test getting device events with filters."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.get_device_events = AsyncMock(return_value=[])
            mock_service.count_device_events = AsyncMock(return_value=0)
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/events/device/{sample_device_id}",
                params={
                    "event_type": "alarm",
                    "severity": "critical",
                    "acknowledged": False,
                },
            )

            assert response.status_code == 200


class TestGetSiteEvents:
    """Test get site events endpoint."""

    def test_get_site_events(
        self, client, sample_site_id, sample_event_data
    ):
        """Test getting events for a site."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_event = MagicMock(**sample_event_data)
            mock_service = MagicMock()
            mock_service.get_site_events = AsyncMock(return_value=[mock_event])
            mock_service.count_site_events = AsyncMock(return_value=1)
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/events/site/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1


class TestAcknowledgeEvent:
    """Test event acknowledgment endpoint."""

    def test_acknowledge_event_success(
        self, client, sample_event_id, sample_event_data
    ):
        """Test successful event acknowledgment."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            acknowledged_event = MagicMock(**sample_event_data)
            acknowledged_event.acknowledged = True
            acknowledged_event.acknowledged_at = datetime.now(timezone.utc)
            acknowledged_event.acknowledged_by = "operator@example.com"

            mock_service = MagicMock()
            mock_service.acknowledge_event = AsyncMock(return_value=acknowledged_event)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/events/acknowledge",
                json={
                    "event_id": str(sample_event_id),
                    "acknowledged_by": "operator@example.com",
                    "notes": "Acknowledged and monitoring",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["acknowledged"] is True

    def test_acknowledge_event_not_found(
        self, client, sample_event_id
    ):
        """Test acknowledging non-existent event."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.acknowledge_event = AsyncMock(return_value=None)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/events/acknowledge",
                json={
                    "event_id": str(sample_event_id),
                    "acknowledged_by": "operator@example.com",
                },
            )

            assert response.status_code == 404


class TestBulkAcknowledge:
    """Test bulk event acknowledgment endpoint."""

    def test_bulk_acknowledge_success(self, client):
        """Test bulk acknowledgment of events."""
        event_ids = [uuid4() for _ in range(3)]

        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.acknowledge_bulk = AsyncMock(return_value=3)
            MockService.return_value = mock_service

            response = client.post(
                "/api/v1/events/acknowledge-bulk",
                json={
                    "event_ids": [str(eid) for eid in event_ids],
                    "acknowledged_by": "operator@example.com",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["acknowledged_count"] == 3


class TestGetEventCounts:
    """Test event counts endpoint."""

    def test_get_event_counts(self, client, sample_site_id):
        """Test getting event counts by severity."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.get_event_counts = AsyncMock(return_value={
                "critical": 5,
                "warning": 15,
                "info": 50,
                "total": 70,
                "unacknowledged": 20,
            })
            MockService.return_value = mock_service

            response = client.get(
                "/api/v1/events/counts",
                params={"site_id": str(sample_site_id)},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["critical"] == 5
            assert data["total"] == 70


class TestGetEventTimeline:
    """Test event timeline endpoint."""

    def test_get_event_timeline(self, client, sample_site_id):
        """Test getting event timeline."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            start_time = datetime.now(timezone.utc) - timedelta(hours=24)

            mock_service = MagicMock()
            mock_service.get_event_timeline = AsyncMock(return_value=[
                {
                    "hour": start_time.isoformat(),
                    "critical": 1,
                    "warning": 3,
                    "info": 10,
                }
            ])
            MockService.return_value = mock_service

            response = client.get(
                "/api/v1/events/timeline",
                params={
                    "site_id": str(sample_site_id),
                    "start_time": start_time.isoformat(),
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1


class TestGetEventStats:
    """Test event stats endpoint."""

    def test_get_event_stats(self, client, sample_device_id):
        """Test getting event statistics."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.get_device_event_stats = AsyncMock(return_value={
                "total_events": 100,
                "events_last_24h": 15,
                "events_last_7d": 45,
                "most_common_code": "LOW_BATTERY",
                "avg_acknowledgment_time_seconds": 300,
            })
            MockService.return_value = mock_service

            response = client.get(
                f"/api/v1/events/stats/{sample_device_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_events"] == 100


class TestGetTopErrors:
    """Test top errors endpoint."""

    def test_get_top_errors(self, client, sample_site_id):
        """Test getting top error codes."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.get_top_errors = AsyncMock(return_value=[
                {"code": "LOW_BATTERY", "count": 50, "severity": "warning"},
                {"code": "COMM_FAILURE", "count": 25, "severity": "critical"},
                {"code": "TEMP_HIGH", "count": 10, "severity": "warning"},
            ])
            MockService.return_value = mock_service

            response = client.get(
                "/api/v1/events/top-errors",
                params={"site_id": str(sample_site_id), "limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3
            assert data[0]["code"] == "LOW_BATTERY"


class TestGetUnacknowledgedEvents:
    """Test unacknowledged events endpoint."""

    def test_get_unacknowledged_events(
        self, client, sample_site_id, sample_event_data
    ):
        """Test getting unacknowledged events."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            mock_event = MagicMock(**sample_event_data)
            mock_service = MagicMock()
            mock_service.get_unacknowledged_events = AsyncMock(return_value=[mock_event])
            MockService.return_value = mock_service

            response = client.get(
                "/api/v1/events/unacknowledged",
                params={"site_id": str(sample_site_id)},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1


class TestGetRecentCritical:
    """Test recent critical events endpoint."""

    def test_get_recent_critical_events(
        self, client, sample_site_id, sample_event_data
    ):
        """Test getting recent critical events."""
        with patch("app.api.v1.events.EventRepository") as MockRepo, \
             patch("app.api.v1.events.EventService") as MockService:

            sample_event_data["severity"] = "critical"
            mock_event = MagicMock(**sample_event_data)

            mock_service = MagicMock()
            mock_service.get_recent_critical = AsyncMock(return_value=[mock_event])
            MockService.return_value = mock_service

            response = client.get(
                "/api/v1/events/recent-critical",
                params={"site_id": str(sample_site_id), "hours": 24},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1

