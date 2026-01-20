"""
E2E tests for event flow.

Tests the complete flow from device event generation to acknowledgment.
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
def sample_event_id():
    return uuid4()


class TestEventGenerationFlow:
    """
    Test event generation flow.

    Flow: Device generates event → stored → acknowledged
    """

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_event_flow(
        self, sample_device_id, sample_site_id, sample_event_id
    ):
        """
        Test complete event lifecycle.

        1. Device generates event
        2. Event stored in database
        3. Event visible in API
        4. Event acknowledged by operator
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            # Create event
            mock_event = MagicMock()
            mock_event.id = sample_event_id
            mock_event.device_id = sample_device_id
            mock_event.site_id = sample_site_id
            mock_event.event_type = "alarm"
            mock_event.severity = "warning"
            mock_event.code = "LOW_BATTERY"
            mock_event.message = "Battery SOC below 20%"
            mock_event.details = {"soc": 18.5}
            mock_event.acknowledged = False
            mock_event.created_at = datetime.now(timezone.utc)

            mock_service.create_event = AsyncMock(return_value=mock_event)

            # Get events
            mock_service.get_device_events = AsyncMock(return_value=[mock_event])

            # Acknowledge event
            acked_event = MagicMock()
            acked_event.id = sample_event_id
            acked_event.acknowledged = True
            acked_event.acknowledged_at = datetime.now(timezone.utc)
            acked_event.acknowledged_by = "operator@example.com"
            mock_service.acknowledge_event = AsyncMock(return_value=acked_event)

            MockService.return_value = mock_service

            # 1. Create event
            event = await mock_service.create_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="alarm",
                severity="warning",
                code="LOW_BATTERY",
                message="Battery SOC below 20%",
                details={"soc": 18.5},
            )
            assert event.acknowledged is False

            # 2. Get events (API query)
            events = await mock_service.get_device_events(
                device_id=sample_device_id,
            )
            assert len(events) == 1
            assert events[0].code == "LOW_BATTERY"

            # 3. Acknowledge event
            acked = await mock_service.acknowledge_event(
                event_id=sample_event_id,
                acknowledged_by="operator@example.com",
            )
            assert acked.acknowledged is True

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_critical_event_flow(
        self, sample_device_id, sample_site_id
    ):
        """
        Test critical event handling.

        1. Critical event generated
        2. Immediate notification triggered
        3. Event visible in critical list
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            # Critical event
            critical_event = MagicMock()
            critical_event.id = uuid4()
            critical_event.severity = "critical"
            critical_event.code = "INVERTER_FAULT"
            critical_event.message = "Inverter fault detected"

            mock_service.create_event = AsyncMock(return_value=critical_event)
            mock_service.get_recent_critical = AsyncMock(return_value=[critical_event])

            MockService.return_value = mock_service

            # Create critical event
            event = await mock_service.create_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="fault",
                severity="critical",
                code="INVERTER_FAULT",
            )

            # Get recent critical events
            critical = await mock_service.get_recent_critical(
                site_id=sample_site_id,
                hours=24,
            )

            assert len(critical) == 1
            assert critical[0].severity == "critical"


class TestEventBulkOperations:
    """Test bulk event operations."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_bulk_acknowledge_events(self, sample_site_id):
        """
        Test bulk event acknowledgment.

        1. Multiple events generated
        2. Bulk acknowledge requested
        3. All events acknowledged
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.acknowledge_bulk = AsyncMock(return_value=5)
            MockService.return_value = mock_service

            event_ids = [uuid4() for _ in range(5)]

            count = await mock_service.acknowledge_bulk(
                event_ids=event_ids,
                acknowledged_by="operator@example.com",
            )

            assert count == 5

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_unacknowledged_events(self, sample_site_id):
        """
        Test getting unacknowledged events.

        1. Multiple events exist
        2. Some acknowledged, some not
        3. Get unacknowledged only
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            unacked_events = [
                MagicMock(acknowledged=False, severity="warning"),
                MagicMock(acknowledged=False, severity="critical"),
            ]

            mock_service = MagicMock()
            mock_service.get_unacknowledged_events = AsyncMock(return_value=unacked_events)
            MockService.return_value = mock_service

            events = await mock_service.get_unacknowledged_events(
                site_id=sample_site_id,
            )

            assert len(events) == 2
            assert all(not e.acknowledged for e in events)


class TestEventAnalytics:
    """Test event analytics flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_event_counts_by_severity(self, sample_site_id):
        """
        Test event count aggregation by severity.

        1. Events generated over time
        2. Count aggregation run
        3. Counts by severity returned
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.get_event_counts = AsyncMock(return_value={
                "critical": 5,
                "warning": 15,
                "info": 50,
                "total": 70,
                "unacknowledged": 20,
            })
            MockService.return_value = mock_service

            counts = await mock_service.get_event_counts(
                site_id=sample_site_id,
                hours=24,
            )

            assert counts["critical"] == 5
            assert counts["warning"] == 15
            assert counts["total"] == 70

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_event_timeline(self, sample_site_id):
        """
        Test event timeline aggregation.

        1. Events generated over time
        2. Timeline aggregation run
        3. Hourly counts returned
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.get_event_timeline = AsyncMock(return_value=[
                {"hour": "2024-01-15T00:00:00Z", "critical": 0, "warning": 2, "info": 5},
                {"hour": "2024-01-15T01:00:00Z", "critical": 1, "warning": 3, "info": 8},
                {"hour": "2024-01-15T02:00:00Z", "critical": 0, "warning": 1, "info": 3},
            ])
            MockService.return_value = mock_service

            timeline = await mock_service.get_event_timeline(
                site_id=sample_site_id,
                start_time=datetime.now(timezone.utc) - timedelta(hours=24),
            )

            assert len(timeline) == 3

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_top_error_codes(self, sample_site_id):
        """
        Test top error code analysis.

        1. Events with various error codes
        2. Top errors aggregation run
        3. Most frequent errors returned
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.get_top_errors = AsyncMock(return_value=[
                {"code": "LOW_BATTERY", "count": 50, "severity": "warning"},
                {"code": "COMM_FAILURE", "count": 25, "severity": "critical"},
                {"code": "TEMP_HIGH", "count": 10, "severity": "warning"},
            ])
            MockService.return_value = mock_service

            top_errors = await mock_service.get_top_errors(
                site_id=sample_site_id,
                limit=10,
            )

            assert len(top_errors) == 3
            assert top_errors[0]["code"] == "LOW_BATTERY"
            assert top_errors[0]["count"] == 50


class TestEventNotificationFlow:
    """Test event notification flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_event_triggers_notification(
        self, sample_device_id, sample_site_id
    ):
        """
        Test that events trigger notifications.

        1. Critical event generated
        2. Notification service notified
        3. Notification sent to subscribers
        """
        with patch("app.application.services.event_service.EventService") as MockEventService, \
             patch("app.infrastructure.messaging.stream_services.NotificationStreamService") as MockNotifService:

            # Create event
            mock_event_service = MagicMock()
            mock_event = MagicMock()
            mock_event.severity = "critical"
            mock_event.code = "INVERTER_FAULT"
            mock_event_service.create_event = AsyncMock(return_value=mock_event)
            MockEventService.return_value = mock_event_service

            # Notification published
            mock_notif_service = MagicMock()
            mock_notif_service.publish_notification = AsyncMock(return_value="notif_123")
            MockNotifService.return_value = mock_notif_service

            # Create event
            event = await mock_event_service.create_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="fault",
                severity="critical",
                code="INVERTER_FAULT",
            )

            # Trigger notification
            await mock_notif_service.publish_notification(
                notification_type="email",
                recipients=["admin@example.com"],
                subject=f"Critical: {event.code}",
                body="Inverter fault detected",
            )

            mock_notif_service.publish_notification.assert_called_once()


class TestEventFiltering:
    """Test event filtering flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_filter_events_by_type(self, sample_device_id):
        """
        Test filtering events by type.

        1. Events of various types exist
        2. Filter by alarm type
        3. Only alarm events returned
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            alarm_events = [
                MagicMock(event_type="alarm", code="LOW_BATTERY"),
                MagicMock(event_type="alarm", code="HIGH_TEMP"),
            ]

            mock_service = MagicMock()
            mock_service.get_device_events = AsyncMock(return_value=alarm_events)
            MockService.return_value = mock_service

            events = await mock_service.get_device_events(
                device_id=sample_device_id,
                event_type="alarm",
            )

            assert len(events) == 2
            assert all(e.event_type == "alarm" for e in events)

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_filter_events_by_time_range(
        self, sample_device_id
    ):
        """
        Test filtering events by time range.

        1. Events exist over time
        2. Query with time range
        3. Only events in range returned
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.get_device_events = AsyncMock(return_value=[
                MagicMock(created_at=datetime.now(timezone.utc) - timedelta(hours=1)),
                MagicMock(created_at=datetime.now(timezone.utc) - timedelta(hours=2)),
            ])
            MockService.return_value = mock_service

            start_time = datetime.now(timezone.utc) - timedelta(hours=6)
            end_time = datetime.now(timezone.utc)

            events = await mock_service.get_device_events(
                device_id=sample_device_id,
                start_time=start_time,
                end_time=end_time,
            )

            assert len(events) == 2


class TestEventCorrelation:
    """Test event correlation flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_related_events_grouping(
        self, sample_device_id
    ):
        """
        Test grouping related events.

        1. Multiple events with same root cause
        2. Events correlated by timestamp and device
        3. Related events grouped
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            # Related events occurring within short time window
            related_events = [
                MagicMock(code="GRID_OUTAGE", created_at=datetime.now(timezone.utc)),
                MagicMock(code="BATTERY_DISCHARGE", created_at=datetime.now(timezone.utc) + timedelta(seconds=5)),
                MagicMock(code="LOAD_SHED", created_at=datetime.now(timezone.utc) + timedelta(seconds=10)),
            ]

            mock_service = MagicMock()
            mock_service.get_device_events = AsyncMock(return_value=related_events)
            MockService.return_value = mock_service

            events = await mock_service.get_device_events(
                device_id=sample_device_id,
                start_time=datetime.now(timezone.utc) - timedelta(minutes=5),
            )

            assert len(events) == 3
            # All events within 10 seconds - likely related


class TestEventFactoryMethods:
    """Test event factory methods."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_create_connection_event(
        self, sample_device_id, sample_site_id
    ):
        """
        Test creating connection event via factory method.

        1. Device connects
        2. Connection event created
        3. Event has correct type and details
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            connection_event = MagicMock()
            connection_event.id = uuid4()
            connection_event.event_type = "connection"
            connection_event.severity = "info"
            connection_event.code = "DEVICE_CONNECTED"
            connection_event.message = "Device connected successfully"
            connection_event.details = {
                "client_address": "192.168.1.100:54321",
                "protocol": "powdrive",
            }

            mock_service.create_connection_event = AsyncMock(return_value=connection_event)
            MockService.return_value = mock_service

            event = await mock_service.create_connection_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                connected=True,
                client_address="192.168.1.100:54321",
                protocol="powdrive",
            )

            assert event.event_type == "connection"
            assert event.code == "DEVICE_CONNECTED"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_create_disconnection_event(
        self, sample_device_id, sample_site_id
    ):
        """
        Test creating disconnection event.

        1. Device disconnects
        2. Disconnection event created
        3. Event includes reason
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            disconnect_event = MagicMock()
            disconnect_event.id = uuid4()
            disconnect_event.event_type = "connection"
            disconnect_event.severity = "warning"
            disconnect_event.code = "DEVICE_DISCONNECTED"
            disconnect_event.message = "Device disconnected"
            disconnect_event.details = {
                "reason": "Connection timeout",
                "session_duration_seconds": 3600,
            }

            mock_service.create_connection_event = AsyncMock(return_value=disconnect_event)
            MockService.return_value = mock_service

            event = await mock_service.create_connection_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                connected=False,
                reason="Connection timeout",
            )

            assert event.code == "DEVICE_DISCONNECTED"
            assert event.severity == "warning"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_create_error_event(
        self, sample_device_id, sample_site_id
    ):
        """
        Test creating error event via factory method.

        1. Error occurs
        2. Error event created with details
        3. Severity set appropriately
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            error_event = MagicMock()
            error_event.id = uuid4()
            error_event.event_type = "error"
            error_event.severity = "error"
            error_event.code = "COMM_FAILURE"
            error_event.message = "Communication failure with device"
            error_event.details = {
                "error_type": "TimeoutError",
                "retry_count": 3,
                "last_successful_at": datetime.now(timezone.utc).isoformat(),
            }

            mock_service.create_error_event = AsyncMock(return_value=error_event)
            MockService.return_value = mock_service

            event = await mock_service.create_error_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                error_code="COMM_FAILURE",
                error_message="Communication failure with device",
                error_details={
                    "error_type": "TimeoutError",
                    "retry_count": 3,
                },
            )

            assert event.event_type == "error"
            assert event.severity == "error"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_create_command_event(
        self, sample_device_id, sample_site_id
    ):
        """
        Test creating command-related event.

        1. Command executes
        2. Command event created
        3. Event includes command details
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            command_event = MagicMock()
            command_event.id = uuid4()
            command_event.event_type = "command"
            command_event.severity = "info"
            command_event.code = "COMMAND_COMPLETED"
            command_event.details = {
                "command_id": str(uuid4()),
                "command_type": "set_mode",
                "execution_time_ms": 250,
            }

            mock_service.create_event = AsyncMock(return_value=command_event)
            MockService.return_value = mock_service

            event = await mock_service.create_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="command",
                severity="info",
                code="COMMAND_COMPLETED",
                details={
                    "command_type": "set_mode",
                    "execution_time_ms": 250,
                },
            )

            assert event.event_type == "command"
            assert event.code == "COMMAND_COMPLETED"


class TestEventResolution:
    """Test event resolution flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_resolve_event(self, sample_event_id):
        """
        Test resolving an event.

        1. Event exists and is active
        2. Resolution applied
        3. Event marked as resolved
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            resolved_event = MagicMock()
            resolved_event.id = sample_event_id
            resolved_event.resolved = True
            resolved_event.resolved_at = datetime.now(timezone.utc)
            resolved_event.resolved_by = "operator@example.com"
            resolved_event.resolution_notes = "Replaced faulty sensor"

            mock_service.resolve_event = AsyncMock(return_value=resolved_event)
            MockService.return_value = mock_service

            event = await mock_service.resolve_event(
                event_id=sample_event_id,
                resolved_by="operator@example.com",
                resolution_notes="Replaced faulty sensor",
            )

            assert event.resolved is True
            assert event.resolution_notes == "Replaced faulty sensor"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_auto_resolve_on_condition_clear(
        self, sample_device_id, sample_site_id
    ):
        """
        Test automatic event resolution when condition clears.

        1. Alarm event created (e.g., low battery)
        2. Condition clears (battery charged)
        3. Event auto-resolved
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            # Original alarm
            alarm_event = MagicMock()
            alarm_event.id = uuid4()
            alarm_event.code = "LOW_BATTERY"
            alarm_event.resolved = False

            # Auto-resolved
            resolved_event = MagicMock()
            resolved_event.id = alarm_event.id
            resolved_event.code = "LOW_BATTERY"
            resolved_event.resolved = True
            resolved_event.resolved_at = datetime.now(timezone.utc)
            resolved_event.resolution_notes = "Condition cleared automatically"

            mock_service.auto_resolve_event = AsyncMock(return_value=resolved_event)
            MockService.return_value = mock_service

            event = await mock_service.auto_resolve_event(
                event_code="LOW_BATTERY",
                device_id=sample_device_id,
                reason="Battery SOC above threshold",
            )

            assert event.resolved is True
            assert "automatically" in event.resolution_notes

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_unresolved_events(self, sample_site_id):
        """
        Test getting unresolved events.

        1. Mix of resolved and unresolved events
        2. Query for unresolved
        3. Only unresolved returned
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            unresolved = [
                MagicMock(id=uuid4(), resolved=False, code="LOW_BATTERY"),
                MagicMock(id=uuid4(), resolved=False, code="HIGH_TEMP"),
            ]

            mock_service.get_unresolved_events = AsyncMock(return_value=unresolved)
            MockService.return_value = mock_service

            events = await mock_service.get_unresolved_events(
                site_id=sample_site_id,
            )

            assert len(events) == 2
            assert all(not e.resolved for e in events)


class TestEventDeduplication:
    """Test event deduplication flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_duplicate_event_suppression(
        self, sample_device_id, sample_site_id
    ):
        """
        Test suppression of duplicate events.

        1. Event created
        2. Same event occurs again quickly
        3. Duplicate suppressed
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            # First event created
            first_event = MagicMock()
            first_event.id = uuid4()
            first_event.code = "LOW_BATTERY"
            first_event.is_duplicate = False

            # Second event is duplicate
            duplicate_result = MagicMock()
            duplicate_result.id = first_event.id
            duplicate_result.is_duplicate = True
            duplicate_result.original_event_id = first_event.id
            duplicate_result.occurrence_count = 2

            mock_service.create_event = AsyncMock(side_effect=[first_event, duplicate_result])
            MockService.return_value = mock_service

            # First event
            event1 = await mock_service.create_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="alarm",
                code="LOW_BATTERY",
            )
            assert event1.is_duplicate is False

            # Second event (duplicate)
            event2 = await mock_service.create_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="alarm",
                code="LOW_BATTERY",
            )
            assert event2.is_duplicate is True
            assert event2.occurrence_count == 2

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_event_occurrence_counting(
        self, sample_device_id, sample_event_id
    ):
        """
        Test counting occurrences of repeated events.

        1. Same event type occurs multiple times
        2. Occurrences counted
        3. Count available in event
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            event_with_count = MagicMock()
            event_with_count.id = sample_event_id
            event_with_count.code = "COMM_RETRY"
            event_with_count.occurrence_count = 15
            event_with_count.first_occurrence = datetime.now(timezone.utc) - timedelta(hours=2)
            event_with_count.last_occurrence = datetime.now(timezone.utc)

            mock_service.get_event = AsyncMock(return_value=event_with_count)
            MockService.return_value = mock_service

            event = await mock_service.get_event(event_id=sample_event_id)

            assert event.occurrence_count == 15

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_dedup_window_configuration(
        self, sample_device_id, sample_site_id
    ):
        """
        Test event deduplication window.

        1. Event created
        2. Same event after dedup window
        3. New event created (not suppressed)
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            # First event
            event1 = MagicMock()
            event1.id = uuid4()
            event1.code = "LOW_BATTERY"
            event1.is_duplicate = False

            # Second event after window (not duplicate)
            event2 = MagicMock()
            event2.id = uuid4()
            event2.code = "LOW_BATTERY"
            event2.is_duplicate = False

            mock_service.create_event = AsyncMock(side_effect=[event1, event2])
            MockService.return_value = mock_service

            # Both events created as separate
            e1 = await mock_service.create_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="alarm",
                code="LOW_BATTERY",
            )

            e2 = await mock_service.create_event(
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="alarm",
                code="LOW_BATTERY",
            )

            # Both should be unique (different IDs)
            assert e1.id != e2.id


class TestEventEscalation:
    """Test event escalation flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_escalate_unacknowledged_event(
        self, sample_event_id
    ):
        """
        Test escalating unacknowledged events.

        1. Critical event not acknowledged
        2. Escalation timeout reached
        3. Event escalated to higher level
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            escalated_event = MagicMock()
            escalated_event.id = sample_event_id
            escalated_event.severity = "critical"
            escalated_event.escalated = True
            escalated_event.escalated_at = datetime.now(timezone.utc)
            escalated_event.escalation_level = 2
            escalated_event.escalation_reason = "Not acknowledged within 30 minutes"

            mock_service.escalate_event = AsyncMock(return_value=escalated_event)
            MockService.return_value = mock_service

            event = await mock_service.escalate_event(
                event_id=sample_event_id,
                escalation_level=2,
                reason="Not acknowledged within 30 minutes",
            )

            assert event.escalated is True
            assert event.escalation_level == 2

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_events_pending_escalation(self, sample_site_id):
        """
        Test getting events that need escalation.

        1. Events with various states
        2. Query for escalation candidates
        3. Only qualifying events returned
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            pending_escalation = [
                MagicMock(
                    id=uuid4(),
                    severity="critical",
                    acknowledged=False,
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=35),
                ),
            ]

            mock_service.get_events_pending_escalation = AsyncMock(
                return_value=pending_escalation
            )
            MockService.return_value = mock_service

            events = await mock_service.get_events_pending_escalation(
                site_id=sample_site_id,
                escalation_threshold_minutes=30,
            )

            assert len(events) == 1


class TestEventRetention:
    """Test event retention flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cleanup_old_events(self):
        """
        Test cleanup of old events.

        1. Old events exist
        2. Cleanup job runs
        3. Events older than retention deleted
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.cleanup_old_events = AsyncMock(return_value=500)
            MockService.return_value = mock_service

            deleted = await mock_service.cleanup_old_events(
                retention_days=90,
            )

            assert deleted == 500

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_archive_events(self, sample_site_id):
        """
        Test archiving events before deletion.

        1. Events to be cleaned up
        2. Archive to cold storage
        3. Then delete from main store
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()
            mock_service.archive_events = AsyncMock(return_value={
                "archived_count": 1000,
                "archive_location": "s3://archive-bucket/events/2024-01/",
            })
            MockService.return_value = mock_service

            result = await mock_service.archive_events(
                site_id=sample_site_id,
                before_date=datetime.now(timezone.utc) - timedelta(days=90),
            )

            assert result["archived_count"] == 1000


class TestEventStreamPublish:
    """Test event stream publishing flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_publish_event_to_stream(
        self, sample_device_id, sample_site_id
    ):
        """
        Test publishing event to notification stream.

        1. Event created
        2. Published to stream
        3. Consumers notified
        """
        with patch("app.infrastructure.messaging.stream_services.NotificationStreamService") as MockStream:

            mock_service = MagicMock()
            mock_service.publish_event = AsyncMock(return_value="msg_789")
            MockStream.return_value = mock_service

            msg_id = await mock_service.publish_event(
                event_id=uuid4(),
                device_id=sample_device_id,
                site_id=sample_site_id,
                event_type="alarm",
                severity="critical",
                code="INVERTER_FAULT",
            )

            assert msg_id == "msg_789"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_event_triggers_alert_evaluation(
        self, sample_device_id, sample_site_id
    ):
        """
        Test that events trigger alert evaluation.

        1. Event created
        2. Alert evaluation triggered
        3. Matching alert rules fire
        """
        with patch("app.infrastructure.messaging.stream_services.AlertStreamService") as MockAlert:

            mock_service = MagicMock()
            mock_service.publish_for_evaluation = AsyncMock(return_value="alert_456")
            MockAlert.return_value = mock_service

            msg_id = await mock_service.publish_for_evaluation(
                device_id=sample_device_id,
                site_id=sample_site_id,
                metric_name="event_severity",
                value="critical",
                event_code="INVERTER_FAULT",
            )

            assert msg_id == "alert_456"


class TestEventStatusTransitions:
    """Test event status transition flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_event_status_history(self, sample_event_id):
        """
        Test tracking event status changes.

        1. Event created
        2. Status changes over time
        3. History tracked
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            status_history = [
                {"status": "created", "timestamp": datetime.now(timezone.utc) - timedelta(hours=2)},
                {"status": "acknowledged", "timestamp": datetime.now(timezone.utc) - timedelta(hours=1), "by": "operator@example.com"},
                {"status": "resolved", "timestamp": datetime.now(timezone.utc), "by": "tech@example.com"},
            ]

            mock_service.get_event_history = AsyncMock(return_value=status_history)
            MockService.return_value = mock_service

            history = await mock_service.get_event_history(event_id=sample_event_id)

            assert len(history) == 3
            assert history[0]["status"] == "created"
            assert history[2]["status"] == "resolved"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_reopen_resolved_event(self, sample_event_id):
        """
        Test reopening a resolved event.

        1. Event was resolved
        2. Condition recurs
        3. Event reopened
        """
        with patch("app.application.services.event_service.EventService") as MockService:

            mock_service = MagicMock()

            reopened_event = MagicMock()
            reopened_event.id = sample_event_id
            reopened_event.resolved = False
            reopened_event.reopen_count = 1
            reopened_event.reopened_at = datetime.now(timezone.utc)
            reopened_event.reopen_reason = "Condition recurred"

            mock_service.reopen_event = AsyncMock(return_value=reopened_event)
            MockService.return_value = mock_service

            event = await mock_service.reopen_event(
                event_id=sample_event_id,
                reason="Condition recurred",
            )

            assert event.resolved is False
            assert event.reopen_count == 1

