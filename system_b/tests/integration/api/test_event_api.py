"""
Integration tests for Event API endpoints.

Tests event creation, retrieval, acknowledgment, and analytics endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.events import router
from app.domain.entities.event import EventType, EventSeverity


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
def sample_user_id():
    return uuid4()


@pytest.fixture
def sample_event_data(sample_device_id, sample_site_id):
    """Create sample event data matching DeviceEvent entity."""
    return {
        "time": datetime.now(timezone.utc),
        "device_id": sample_device_id,
        "site_id": sample_site_id,
        "event_type": EventType.ERROR,
        "severity": EventSeverity.WARNING,
        "event_code": "LOW_BATTERY",
        "message": "Battery SOC below 20%",
        "details": {"soc": 18.5},
        "acknowledged": False,
        "acknowledged_at": None,
        "acknowledged_by": None,
    }


class TestCreateEvent:
    """Test event creation endpoint."""

    def test_create_event_success(
        self, client, sample_device_id, sample_site_id, sample_event_data
    ):
        """Test successful event creation."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_event = MagicMock(**sample_event_data)
            mock_repo = MagicMock()
            mock_repo.create = AsyncMock(return_value=mock_event)
            MockRepo.return_value = mock_repo

            response = client.post(
                "/api/v1/events/",
                json={
                    "device_id": str(sample_device_id),
                    "site_id": str(sample_site_id),
                    "event_type": "error",
                    "severity": "warning",
                    "event_code": "LOW_BATTERY",
                    "message": "Battery SOC below 20%",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["event_type"] == "error"
            assert data["severity"] == "warning"

    def test_create_event_validation_error(
        self, client, sample_device_id, sample_site_id
    ):
        """Test event creation with missing required fields."""
        response = client.post(
            "/api/v1/events/",
            json={
                "device_id": str(sample_device_id),
                # Missing site_id, event_type, severity
            },
        )

        assert response.status_code == 422


class TestGetDeviceEvents:
    """Test get device events endpoint."""

    def test_get_device_events(
        self, client, sample_device_id, sample_event_data
    ):
        """Test getting events for a device."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_event = MagicMock(**sample_event_data)
            mock_repo = MagicMock()
            mock_repo.get_device_events = AsyncMock(return_value=[mock_event])
            mock_repo.count_device_events = AsyncMock(return_value=1)
            MockRepo.return_value = mock_repo

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
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_device_events = AsyncMock(return_value=[])
            mock_repo.count_device_events = AsyncMock(return_value=0)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/events/device/{sample_device_id}",
                params={
                    "event_types": ["error"],
                    "severities": ["critical"],
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
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_event = MagicMock(**sample_event_data)
            mock_repo = MagicMock()
            mock_repo.get_site_events = AsyncMock(return_value=[mock_event])
            mock_repo.count_site_events = AsyncMock(return_value=1)
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/events/site/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1


class TestAcknowledgeEvent:
    """Test event acknowledgment endpoint."""

    def test_acknowledge_event_success(
        self, client, sample_device_id, sample_user_id, sample_event_data
    ):
        """Test successful event acknowledgment."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.acknowledge_event = AsyncMock(return_value=True)
            MockRepo.return_value = mock_repo

            event_time = datetime.now(timezone.utc)
            response = client.post(
                "/api/v1/events/acknowledge",
                json={
                    "device_id": str(sample_device_id),
                    "event_time": event_time.isoformat(),
                    "event_type": "error",
                    "acknowledged_by": str(sample_user_id),
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_acknowledge_event_not_found(
        self, client, sample_device_id, sample_user_id
    ):
        """Test acknowledging non-existent event."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.acknowledge_event = AsyncMock(return_value=False)
            MockRepo.return_value = mock_repo

            event_time = datetime.now(timezone.utc)
            response = client.post(
                "/api/v1/events/acknowledge",
                json={
                    "device_id": str(sample_device_id),
                    "event_time": event_time.isoformat(),
                    "event_type": "error",
                    "acknowledged_by": str(sample_user_id),
                },
            )

            assert response.status_code == 404


class TestBulkAcknowledge:
    """Test bulk event acknowledgment endpoint."""

    def test_bulk_acknowledge_success(self, client, sample_device_id, sample_user_id):
        """Test bulk acknowledgment of events."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.acknowledge_events_bulk = AsyncMock(return_value=3)
            MockRepo.return_value = mock_repo

            response = client.post(
                "/api/v1/events/acknowledge-bulk",
                json={
                    "device_id": str(sample_device_id),
                    "acknowledged_by": str(sample_user_id),
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["acknowledged_count"] == 3


class TestGetEventCounts:
    """Test event counts endpoint."""

    def test_get_event_counts(self, client, sample_site_id):
        """Test getting event counts by severity."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_event_counts = AsyncMock(return_value={
                "error": {
                    "critical": 5,
                    "warning": 15,
                    "info": 50,
                }
            })
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/events/counts/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert "counts" in data


class TestGetEventTimeline:
    """Test event timeline endpoint."""

    def test_get_event_timeline(self, client, sample_site_id):
        """Test getting event timeline."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            start_time = datetime.now(timezone.utc) - timedelta(hours=24)

            mock_repo = MagicMock()
            mock_repo.get_event_timeline = AsyncMock(return_value=[
                {
                    "bucket": start_time,
                    "info": 10,
                    "warning": 3,
                    "error": 1,
                    "critical": 0,
                }
            ])
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/events/timeline/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert "timeline" in data


class TestGetEventStats:
    """Test event stats endpoint."""

    def test_get_event_stats(self, client, sample_site_id):
        """Test getting event statistics."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_event_stats = AsyncMock(return_value={
                "total_events": 100,
                "unacknowledged_events": 20,
                "recent_errors_24h": 5,
                "first_event": datetime.now(timezone.utc) - timedelta(days=30),
                "last_event": datetime.now(timezone.utc),
            })
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/events/stats/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_events"] == 100


class TestGetTopErrors:
    """Test top errors endpoint."""

    def test_get_top_errors(self, client, sample_site_id, sample_device_id):
        """Test getting top error devices."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_repo = MagicMock()
            mock_repo.get_top_error_devices = AsyncMock(return_value=[
                {
                    "device_id": sample_device_id,
                    "error_count": 50,
                    "last_error": datetime.now(timezone.utc),
                },
            ])
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/events/top-errors/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1


class TestGetUnacknowledgedEvents:
    """Test unacknowledged events endpoint."""

    def test_get_unacknowledged_events(
        self, client, sample_site_id, sample_event_data
    ):
        """Test getting unacknowledged events."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            mock_event = MagicMock(**sample_event_data)
            mock_repo = MagicMock()
            mock_repo.get_unacknowledged_events = AsyncMock(return_value=[mock_event])
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/events/unacknowledged/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["events"]) == 1


class TestGetRecentCritical:
    """Test recent critical events endpoint."""

    def test_get_recent_critical_events(
        self, client, sample_site_id, sample_event_data
    ):
        """Test getting recent critical events."""
        with patch("app.api.v1.events.EventRepository") as MockRepo:
            sample_event_data["severity"] = EventSeverity.CRITICAL
            mock_event = MagicMock(**sample_event_data)

            mock_repo = MagicMock()
            mock_repo.get_site_events = AsyncMock(return_value=[mock_event])
            MockRepo.return_value = mock_repo

            response = client.get(
                f"/api/v1/events/recent-critical/{sample_site_id}",
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["events"]) == 1
