"""
Unit tests for EventRepository.

Tests event storage, querying, and acknowledgment operations.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.infrastructure.database.repositories.event_repository import EventRepository
from app.domain.entities.event import DeviceEvent, EventType, EventSeverity


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
    """Create an EventRepository with mock session."""
    return EventRepository(mock_session)


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
def sample_event(sample_device_id, sample_site_id):
    """Create a sample device event entity."""
    return DeviceEvent(
        time=datetime.now(timezone.utc),
        device_id=sample_device_id,
        site_id=sample_site_id,
        event_type=EventType.ALARM,
        severity=EventSeverity.WARNING,
        event_code="E001",
        message="High temperature warning",
        details={"temperature": 85.5, "threshold": 80.0},
        acknowledged=False,
    )


class TestEventRepositoryInit:
    """Test repository initialization."""

    def test_init_with_session(self, mock_session):
        """Test repository initializes with session."""
        repo = EventRepository(mock_session)
        assert repo._session == mock_session


class TestCreate:
    """Test event creation."""

    @pytest.mark.asyncio
    async def test_create_adds_model_to_session(
        self, repository, mock_session, sample_event
    ):
        """Test create adds model to session."""
        result = await repository.create(sample_event)

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        assert result.time == sample_event.time


class TestCreateBatch:
    """Test batch event creation."""

    @pytest.mark.asyncio
    async def test_create_batch_returns_zero_for_empty(
        self, repository
    ):
        """Test returns 0 for empty batch."""
        result = await repository.create_batch([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_batch_returns_count(
        self, repository, mock_session, sample_device_id, sample_site_id
    ):
        """Test returns correct count."""
        mock_session.execute = AsyncMock()

        events = [
            DeviceEvent(
                time=datetime.now(timezone.utc) - timedelta(seconds=i),
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type=EventType.STATUS_CHANGE,
                severity=EventSeverity.INFO,
                message=f"Event {i}",
            )
            for i in range(5)
        ]

        result = await repository.create_batch(events)

        assert result == 5
        mock_session.execute.assert_called_once()


class TestGetDeviceEvents:
    """Test getting device events."""

    @pytest.mark.asyncio
    async def test_get_device_events_returns_empty_list(
        self, repository, mock_session, sample_device_id
    ):
        """Test returns empty list when no events."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_device_events(sample_device_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_device_events_with_time_range(
        self, repository, mock_session, sample_device_id
    ):
        """Test get events with time range filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        now = datetime.now(timezone.utc)
        await repository.get_device_events(
            sample_device_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_device_events_with_type_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test get events with event type filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_device_events(
            sample_device_id,
            event_types=[EventType.ALARM, EventType.FAULT],
        )

        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_device_events_with_severity_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test get events with severity filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_device_events(
            sample_device_id,
            severities=[EventSeverity.ERROR, EventSeverity.CRITICAL],
        )

        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_device_events_unacknowledged_only(
        self, repository, mock_session, sample_device_id
    ):
        """Test get only unacknowledged events."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_device_events(
            sample_device_id,
            unacknowledged_only=True,
        )

        mock_session.execute.assert_called()


class TestGetSiteEvents:
    """Test getting site events."""

    @pytest.mark.asyncio
    async def test_get_site_events_returns_empty_list(
        self, repository, mock_session, sample_site_id
    ):
        """Test returns empty list when no events."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_site_events(sample_site_id)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_site_events_with_device_filter(
        self, repository, mock_session, sample_site_id, sample_device_id
    ):
        """Test get site events filtered by device."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_site_events(
            sample_site_id,
            device_ids=[sample_device_id],
        )

        mock_session.execute.assert_called()


class TestGetRecentErrors:
    """Test getting recent errors."""

    @pytest.mark.asyncio
    async def test_get_recent_errors_returns_empty_list(
        self, repository, mock_session
    ):
        """Test returns empty list when no errors."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_recent_errors()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_recent_errors_with_device_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test get recent errors for device."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_recent_errors(device_id=sample_device_id)

        mock_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_get_recent_errors_with_site_filter(
        self, repository, mock_session, sample_site_id
    ):
        """Test get recent errors for site."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_recent_errors(site_id=sample_site_id)

        mock_session.execute.assert_called()


class TestGetUnacknowledgedEvents:
    """Test getting unacknowledged events."""

    @pytest.mark.asyncio
    async def test_get_unacknowledged_events(
        self, repository, mock_session
    ):
        """Test gets unacknowledged events."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_unacknowledged_events()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_unacknowledged_with_severity_filter(
        self, repository, mock_session
    ):
        """Test get unacknowledged with severity filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_unacknowledged_events(
            severities=[EventSeverity.CRITICAL]
        )

        mock_session.execute.assert_called()


class TestAcknowledgeEvent:
    """Test event acknowledgment."""

    @pytest.mark.asyncio
    async def test_acknowledge_event_returns_true(
        self, repository, mock_session, sample_device_id, sample_user_id
    ):
        """Test acknowledge returns True when successful."""
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.acknowledge_event(
            sample_device_id,
            datetime.now(timezone.utc),
            EventType.ALARM,
            sample_user_id,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_acknowledge_event_returns_false_when_not_found(
        self, repository, mock_session, sample_device_id, sample_user_id
    ):
        """Test acknowledge returns False when event not found."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.acknowledge_event(
            sample_device_id,
            datetime.now(timezone.utc),
            EventType.ALARM,
            sample_user_id,
        )

        assert result is False


class TestAcknowledgeDeviceEvents:
    """Test acknowledging all device events."""

    @pytest.mark.asyncio
    async def test_acknowledge_device_events_returns_count(
        self, repository, mock_session, sample_device_id, sample_user_id
    ):
        """Test returns count of acknowledged events."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.acknowledge_device_events(
            sample_device_id,
            sample_user_id,
        )

        assert result == 5

    @pytest.mark.asyncio
    async def test_acknowledge_device_events_with_type_filter(
        self, repository, mock_session, sample_device_id, sample_user_id
    ):
        """Test acknowledge with event type filter."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.acknowledge_device_events(
            sample_device_id,
            sample_user_id,
            event_types=[EventType.ALARM],
        )

        assert result == 3


class TestAcknowledgeSiteEvents:
    """Test acknowledging all site events."""

    @pytest.mark.asyncio
    async def test_acknowledge_site_events_returns_count(
        self, repository, mock_session, sample_site_id, sample_user_id
    ):
        """Test returns count of acknowledged events."""
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.acknowledge_site_events(
            sample_site_id,
            sample_user_id,
        )

        assert result == 10


class TestGetEventCounts:
    """Test event count aggregation."""

    @pytest.mark.asyncio
    async def test_get_event_counts(
        self, repository, mock_session
    ):
        """Test gets event counts by type and severity."""
        mock_rows = [
            MagicMock(event_type="alarm", severity="warning", count=10),
            MagicMock(event_type="alarm", severity="error", count=3),
            MagicMock(event_type="status_change", severity="info", count=50),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_event_counts()

        assert result["alarm"]["warning"] == 10
        assert result["alarm"]["error"] == 3
        assert result["status_change"]["info"] == 50

    @pytest.mark.asyncio
    async def test_get_event_counts_with_filters(
        self, repository, mock_session, sample_device_id
    ):
        """Test event counts with filters."""
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        now = datetime.now(timezone.utc)
        await repository.get_event_counts(
            device_id=sample_device_id,
            start_time=now - timedelta(hours=1),
            end_time=now,
        )

        mock_session.execute.assert_called()


class TestGetEventTimeline:
    """Test event timeline aggregation."""

    @pytest.mark.asyncio
    async def test_get_event_timeline(
        self, repository, mock_session, sample_site_id
    ):
        """Test gets event timeline."""
        now = datetime.now(timezone.utc)
        mock_rows = [
            MagicMock(bucket=now - timedelta(hours=2), severity="info", count=5),
            MagicMock(bucket=now - timedelta(hours=2), severity="warning", count=2),
            MagicMock(bucket=now - timedelta(hours=1), severity="info", count=8),
        ]
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter(mock_rows)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_event_timeline(
            sample_site_id,
            start_time=now - timedelta(hours=3),
            end_time=now,
        )

        assert len(result) == 2


class TestGetTopErrorDevices:
    """Test getting devices with most errors."""

    @pytest.mark.asyncio
    async def test_get_top_error_devices(
        self, repository, mock_session, sample_site_id
    ):
        """Test gets top error devices."""
        device1 = uuid4()
        device2 = uuid4()
        now = datetime.now(timezone.utc)

        mock_rows = [
            MagicMock(device_id=device1, error_count=15, last_error=now),
            MagicMock(device_id=device2, error_count=8, last_error=now - timedelta(hours=1)),
        ]
        mock_result = MagicMock()
        mock_result.all.return_value = mock_rows
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_top_error_devices(sample_site_id)

        assert len(result) == 2
        assert result[0]["device_id"] == device1
        assert result[0]["error_count"] == 15


class TestDeleteOldEvents:
    """Test event deletion."""

    @pytest.mark.asyncio
    async def test_delete_old_events_returns_count(
        self, repository, mock_session
    ):
        """Test delete returns count."""
        mock_result = MagicMock()
        mock_result.rowcount = 100
        mock_session.execute = AsyncMock(return_value=mock_result)

        older_than = datetime.now(timezone.utc) - timedelta(days=30)
        result = await repository.delete_old_events(older_than)

        assert result == 100

    @pytest.mark.asyncio
    async def test_delete_old_events_with_device_filter(
        self, repository, mock_session, sample_device_id
    ):
        """Test delete with device filter."""
        mock_result = MagicMock()
        mock_result.rowcount = 50
        mock_session.execute = AsyncMock(return_value=mock_result)

        older_than = datetime.now(timezone.utc) - timedelta(days=30)
        result = await repository.delete_old_events(
            older_than, device_id=sample_device_id
        )

        assert result == 50

    @pytest.mark.asyncio
    async def test_delete_old_events_keep_unacknowledged(
        self, repository, mock_session
    ):
        """Test delete keeps unacknowledged events."""
        mock_result = MagicMock()
        mock_result.rowcount = 75
        mock_session.execute = AsyncMock(return_value=mock_result)

        older_than = datetime.now(timezone.utc) - timedelta(days=30)
        result = await repository.delete_old_events(
            older_than, keep_unacknowledged=True
        )

        assert result == 75


class TestGetEventStats:
    """Test event statistics."""

    @pytest.mark.asyncio
    async def test_get_event_stats(
        self, repository, mock_session
    ):
        """Test gets event stats."""
        now = datetime.now(timezone.utc)

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1000

        # Mock unack query
        mock_unack_result = MagicMock()
        mock_unack_result.scalar.return_value = 25

        # Mock error query
        mock_error_result = MagicMock()
        mock_error_result.scalar.return_value = 10

        # Mock range query
        mock_range_row = MagicMock()
        mock_range_row.first_event = now - timedelta(days=30)
        mock_range_row.last_event = now
        mock_range_result = MagicMock()
        mock_range_result.one.return_value = mock_range_row

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_count_result,
                mock_unack_result,
                mock_error_result,
                mock_range_result,
            ]
        )

        result = await repository.get_event_stats()

        assert result["total_events"] == 1000
        assert result["unacknowledged_events"] == 25
        assert result["recent_errors_24h"] == 10

    @pytest.mark.asyncio
    async def test_get_event_stats_with_site_filter(
        self, repository, mock_session, sample_site_id
    ):
        """Test event stats with site filter."""
        now = datetime.now(timezone.utc)

        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 500

        mock_unack_result = MagicMock()
        mock_unack_result.scalar.return_value = 10

        mock_error_result = MagicMock()
        mock_error_result.scalar.return_value = 5

        mock_range_row = MagicMock()
        mock_range_row.first_event = now - timedelta(days=15)
        mock_range_row.last_event = now
        mock_range_result = MagicMock()
        mock_range_result.one.return_value = mock_range_row

        mock_session.execute = AsyncMock(
            side_effect=[
                mock_count_result,
                mock_unack_result,
                mock_error_result,
                mock_range_result,
            ]
        )

        result = await repository.get_event_stats(site_id=sample_site_id)

        assert result["total_events"] == 500
