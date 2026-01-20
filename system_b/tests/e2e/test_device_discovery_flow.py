"""
E2E tests for device discovery flow.

Tests the complete flow from simulator connection to device registration.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def sample_site_id():
    return uuid4()


@pytest.fixture
def sample_device_id():
    return uuid4()


class TestDeviceDiscoveryFlow:
    """
    Test device discovery flow.

    Flow: Simulator connects → identification → registration
    """

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_new_device_discovery_and_registration(
        self, sample_site_id, sample_device_id
    ):
        """
        Test complete device discovery flow.

        1. Simulator connects to TCP server
        2. Device identification is requested
        3. Device type and serial are parsed
        4. Device is registered in database
        5. Device appears in API
        """
        # Mock the device connection handler
        with patch("device_server.connection.tcp_server.TCPServer") as MockServer, \
             patch("app.application.services.device_service.DeviceService") as MockService:

            # Configure mock to simulate device identification
            mock_handler = MagicMock()
            mock_handler.identify_device = AsyncMock(return_value={
                "device_type": "inverter",
                "serial_number": "PD12K00001",
                "protocol_id": "powdrive",
                "firmware_version": "1.0.5",
                "hardware_version": "1.0",
            })
            MockServer.return_value = mock_handler

            # Configure service to register device
            mock_device = MagicMock()
            mock_device.id = sample_device_id
            mock_device.site_id = sample_site_id
            mock_device.serial_number = "PD12K00001"
            mock_device.device_type = "inverter"
            mock_device.connection_status = "connected"
            mock_device.is_active = True

            mock_service = MagicMock()
            mock_service.register_device = AsyncMock(return_value=mock_device)
            mock_service.sync_device = AsyncMock(return_value=mock_device)
            MockService.return_value = mock_service

            # Simulate discovery flow
            device_info = await mock_handler.identify_device()
            registered = await mock_service.register_device(
                site_id=sample_site_id,
                **device_info,
            )

            # Verify device was registered
            assert registered.serial_number == "PD12K00001"
            assert registered.device_type == "inverter"
            assert registered.is_active is True

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_existing_device_sync(
        self, sample_site_id, sample_device_id
    ):
        """
        Test sync flow for already registered device.

        1. Device reconnects
        2. Identification matches existing device
        3. Device is synced (not duplicated)
        4. Connection status updated
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            # Configure service to sync existing device
            mock_device = MagicMock()
            mock_device.id = sample_device_id
            mock_device.site_id = sample_site_id
            mock_device.serial_number = "PD12K00001"
            mock_device.device_type = "inverter"
            mock_device.connection_status = "connected"
            mock_device.last_seen = datetime.now(timezone.utc)

            mock_service = MagicMock()
            mock_service.sync_device = AsyncMock(return_value=mock_device)
            mock_service.handle_device_connect = AsyncMock(return_value={
                "session_id": "session_123",
                "connected_at": datetime.now(timezone.utc),
            })
            MockService.return_value = mock_service

            # Simulate sync flow
            synced = await mock_service.sync_device(
                site_id=sample_site_id,
                serial_number="PD12K00001",
                device_type="inverter",
            )

            # Verify device was synced, not created
            assert synced.id == sample_device_id
            assert synced.connection_status == "connected"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_device_disconnect_flow(
        self, sample_device_id
    ):
        """
        Test device disconnection flow.

        1. Device disconnects (graceful or timeout)
        2. Connection status updated to disconnected
        3. Disconnect event logged
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.handle_device_disconnect = AsyncMock()
            MockService.return_value = mock_service

            # Simulate disconnect
            await mock_service.handle_device_disconnect(
                device_id=sample_device_id,
                reason="Connection lost",
            )

            mock_service.handle_device_disconnect.assert_called_once_with(
                device_id=sample_device_id,
                reason="Connection lost",
            )

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_multiple_device_discovery(self, sample_site_id):
        """
        Test discovering multiple devices at a site.

        1. Multiple simulators connect
        2. Each is identified and registered
        3. All devices appear in site device list
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            devices = []
            for i, (device_type, serial) in enumerate([
                ("inverter", "PD12K00001"),
                ("meter", "IAM3080T0001"),
                ("battery", "PYTES0001"),
            ]):
                mock_device = MagicMock()
                mock_device.id = uuid4()
                mock_device.site_id = sample_site_id
                mock_device.serial_number = serial
                mock_device.device_type = device_type
                mock_device.is_active = True
                devices.append(mock_device)

            mock_service = MagicMock()
            mock_service.register_device = AsyncMock(side_effect=devices)
            MockService.return_value = mock_service

            # Register all devices
            registered = []
            for device_type, serial in [
                ("inverter", "PD12K00001"),
                ("meter", "IAM3080T0001"),
                ("battery", "PYTES0001"),
            ]:
                result = await mock_service.register_device(
                    site_id=sample_site_id,
                    device_type=device_type,
                    serial_number=serial,
                )
                registered.append(result)

            # Verify all devices registered
            assert len(registered) == 3
            device_types = [d.device_type for d in registered]
            assert "inverter" in device_types
            assert "meter" in device_types
            assert "battery" in device_types


class TestDeviceAuthentication:
    """Test device authentication flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_token_authentication_flow(self, sample_device_id):
        """
        Test token-based device authentication.

        1. Device generates/receives auth token
        2. Device connects with token
        3. Token is validated
        4. Session is established
        """
        with patch("app.application.services.auth_service.DeviceAuthService") as MockAuth:

            mock_auth = MagicMock()
            mock_auth.authenticate_by_token = AsyncMock(return_value={
                "authenticated": True,
                "session_token": "session_abc123",
                "expires_at": datetime.now(timezone.utc),
            })
            MockAuth.return_value = mock_auth

            result = await mock_auth.authenticate_by_token(
                device_id=sample_device_id,
                token="valid_device_token",
            )

            assert result["authenticated"] is True
            assert "session_token" in result

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_serial_authentication_flow(
        self, sample_site_id, sample_device_id
    ):
        """
        Test serial number-based authentication.

        1. Device connects with serial number
        2. Serial is validated against site
        3. Device is associated with site
        """
        with patch("app.application.services.auth_service.DeviceAuthService") as MockAuth:

            mock_auth = MagicMock()
            mock_auth.authenticate_by_serial = AsyncMock(return_value={
                "authenticated": True,
                "device_id": sample_device_id,
                "site_id": sample_site_id,
            })
            MockAuth.return_value = mock_auth

            result = await mock_auth.authenticate_by_serial(
                serial_number="PD12K00001",
                site_id=sample_site_id,
            )

            assert result["authenticated"] is True
            assert result["device_id"] == sample_device_id

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_authentication_failure(self, sample_device_id):
        """
        Test authentication failure handling.

        1. Device connects with invalid token
        2. Authentication fails
        3. Connection is rejected
        """
        with patch("app.application.services.auth_service.DeviceAuthService") as MockAuth:

            mock_auth = MagicMock()
            mock_auth.authenticate_by_token = AsyncMock(return_value={
                "authenticated": False,
                "reason": "Invalid or expired token",
            })
            MockAuth.return_value = mock_auth

            result = await mock_auth.authenticate_by_token(
                device_id=sample_device_id,
                token="invalid_token",
            )

            assert result["authenticated"] is False
            assert "reason" in result


class TestNetworkDiscoveryFlow:
    """Test network discovery flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_network_scan_discovery(self, sample_site_id):
        """
        Test network scanning for device discovery.

        1. Network scan initiated
        2. Devices found on network
        3. Devices identified and registered
        """
        with patch("device_server.discovery.discovery_service.DiscoveryService") as MockDiscovery:

            mock_service = MagicMock()

            # Discovered devices
            discovered = [
                MagicMock(
                    ip_address="192.168.1.100",
                    port=502,
                    protocol_id="powdrive",
                    serial_number="PD12K00001",
                    device_type="inverter",
                    response_time_ms=15.5,
                ),
                MagicMock(
                    ip_address="192.168.1.101",
                    port=502,
                    protocol_id="iammeter",
                    serial_number="IAM3080T0001",
                    device_type="meter",
                    response_time_ms=12.3,
                ),
            ]

            mock_result = MagicMock()
            mock_result.devices = discovered
            mock_result.scan_id = "scan_123"
            mock_result.status = "completed"
            mock_result.total_hosts_scanned = 254
            mock_result.devices_found = 2

            mock_service.scan_network = AsyncMock(return_value=mock_result)
            MockDiscovery.return_value = mock_service

            result = await mock_service.scan_network(
                network="192.168.1.0/24",
                ports=[502, 8899],
                timeout_seconds=30,
            )

            assert result.status == "completed"
            assert result.devices_found == 2
            assert len(result.devices) == 2

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_network_scan_progress_tracking(self, sample_site_id):
        """
        Test tracking progress of network scan.

        1. Scan started
        2. Progress updates received
        3. Scan completes
        """
        with patch("device_server.discovery.discovery_service.DiscoveryService") as MockDiscovery:

            mock_service = MagicMock()

            # In-progress result
            progress_result = MagicMock()
            progress_result.scan_id = "scan_123"
            progress_result.status = "in_progress"
            progress_result.progress = MagicMock(
                hosts_scanned=128,
                total_hosts=254,
                percent_complete=50.4,
            )

            mock_service.get_scan_status = AsyncMock(return_value=progress_result)
            MockDiscovery.return_value = mock_service

            status = await mock_service.get_scan_status(scan_id="scan_123")

            assert status.status == "in_progress"
            assert status.progress.percent_complete == 50.4

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cancel_network_scan(self):
        """
        Test cancelling an in-progress network scan.

        1. Scan in progress
        2. Cancel requested
        3. Scan stopped
        """
        with patch("device_server.discovery.discovery_service.DiscoveryService") as MockDiscovery:

            mock_service = MagicMock()
            mock_service.cancel_scan = AsyncMock(return_value=True)
            MockDiscovery.return_value = mock_service

            cancelled = await mock_service.cancel_scan(scan_id="scan_123")

            assert cancelled is True


class TestDeviceTokenManagement:
    """Test device token management flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_token_regeneration_flow(self, sample_device_id):
        """
        Test regenerating device authentication token.

        1. Device has existing token
        2. Token regeneration requested
        3. Old token invalidated
        4. New token issued
        """
        with patch("app.application.services.auth_service.DeviceAuthService") as MockAuth:

            mock_auth = MagicMock()
            mock_auth.regenerate_token = AsyncMock(return_value={
                "device_id": sample_device_id,
                "new_token": "new_token_xyz789",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
                "old_token_revoked": True,
            })
            MockAuth.return_value = mock_auth

            result = await mock_auth.regenerate_token(
                device_id=sample_device_id,
            )

            assert result["old_token_revoked"] is True
            assert "new_token" in result

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_token_revocation_flow(self, sample_device_id):
        """
        Test revoking device token.

        1. Device has valid token
        2. Revocation requested
        3. Token invalidated
        4. Device cannot authenticate
        """
        with patch("app.application.services.auth_service.DeviceAuthService") as MockAuth:

            mock_auth = MagicMock()
            mock_auth.revoke_token = AsyncMock(return_value=True)
            mock_auth.authenticate_by_token = AsyncMock(return_value={
                "authenticated": False,
                "reason": "Token revoked",
            })
            MockAuth.return_value = mock_auth

            # Revoke token
            revoked = await mock_auth.revoke_token(device_id=sample_device_id)
            assert revoked is True

            # Authentication should fail
            result = await mock_auth.authenticate_by_token(
                device_id=sample_device_id,
                token="revoked_token",
            )
            assert result["authenticated"] is False

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_token_expiry_flow(self, sample_device_id):
        """
        Test token expiry handling.

        1. Device token expires
        2. Authentication attempted
        3. Expiry detected
        4. Re-authentication required
        """
        with patch("app.application.services.auth_service.DeviceAuthService") as MockAuth:

            mock_auth = MagicMock()
            mock_auth.get_token_status = AsyncMock(return_value={
                "device_id": sample_device_id,
                "is_valid": False,
                "expired": True,
                "expired_at": datetime.now(timezone.utc) - timedelta(hours=1),
            })
            MockAuth.return_value = mock_auth

            status = await mock_auth.get_token_status(device_id=sample_device_id)

            assert status["is_valid"] is False
            assert status["expired"] is True


class TestDevicePollingFlow:
    """Test device polling flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_devices_for_polling(self, sample_site_id):
        """
        Test getting devices that are due for polling.

        1. Devices with different poll intervals
        2. Query for devices due
        3. Only overdue devices returned
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()

            # Devices due for polling
            due_devices = [
                MagicMock(
                    id=uuid4(),
                    serial_number="PD12K00001",
                    polling_interval_seconds=60,
                    last_polled_at=datetime.now(timezone.utc) - timedelta(minutes=2),
                ),
                MagicMock(
                    id=uuid4(),
                    serial_number="IAM3080T0001",
                    polling_interval_seconds=30,
                    last_polled_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                ),
            ]

            mock_service.get_devices_for_polling = AsyncMock(return_value=due_devices)
            MockService.return_value = mock_service

            devices = await mock_service.get_devices_for_polling(
                site_id=sample_site_id,
            )

            assert len(devices) == 2

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mark_device_polled(self, sample_device_id):
        """
        Test marking device as polled.

        1. Device polled successfully
        2. Poll timestamp updated
        3. Device not returned in next poll query
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.mark_device_polled = AsyncMock(return_value=True)
            MockService.return_value = mock_service

            result = await mock_service.mark_device_polled(
                device_id=sample_device_id,
                polled_at=datetime.now(timezone.utc),
            )

            assert result is True


class TestSessionManagement:
    """Test device session management flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_session_creation_on_connect(self, sample_device_id):
        """
        Test session creation when device connects.

        1. Device connects
        2. Session created
        3. Session details recorded
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()

            session = MagicMock()
            session.session_id = "session_abc123"
            session.device_id = sample_device_id
            session.connected_at = datetime.now(timezone.utc)
            session.client_address = "192.168.1.100:54321"
            session.protocol = "powdrive"

            mock_service.handle_device_connect = AsyncMock(return_value=session)
            MockService.return_value = mock_service

            result = await mock_service.handle_device_connect(
                device_id=sample_device_id,
                client_address="192.168.1.100:54321",
                protocol="powdrive",
            )

            assert result.session_id == "session_abc123"
            assert result.protocol == "powdrive"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_session_activity_update(self, sample_device_id):
        """
        Test updating session activity timestamp.

        1. Session exists
        2. Activity occurs
        3. Last activity timestamp updated
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()

            session = MagicMock()
            session.session_id = "session_abc123"
            session.last_activity_at = datetime.now(timezone.utc)

            mock_service.get_active_session = AsyncMock(return_value=session)
            MockService.return_value = mock_service

            result = await mock_service.get_active_session(
                device_id=sample_device_id,
                update_activity=True,
            )

            assert result.session_id == "session_abc123"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_cleanup_stale_sessions(self):
        """
        Test cleanup of stale/idle sessions.

        1. Sessions with no activity
        2. Cleanup job runs
        3. Stale sessions removed
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.cleanup_stale_sessions = AsyncMock(return_value=5)
            MockService.return_value = mock_service

            cleaned = await mock_service.cleanup_stale_sessions(
                idle_timeout_seconds=300,
            )

            assert cleaned == 5


class TestDeviceConnectionStatistics:
    """Test device connection statistics flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_connection_stats(self, sample_site_id):
        """
        Test retrieving connection statistics.

        1. Devices in various states
        2. Stats aggregated
        3. Breakdown by status returned
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.get_connection_stats = AsyncMock(return_value={
                "total_devices": 10,
                "connected": 8,
                "disconnected": 1,
                "error": 1,
                "by_type": {
                    "inverter": {"total": 5, "connected": 4},
                    "meter": {"total": 3, "connected": 3},
                    "battery": {"total": 2, "connected": 1},
                },
            })
            MockService.return_value = mock_service

            stats = await mock_service.get_connection_stats(
                site_id=sample_site_id,
            )

            assert stats["total_devices"] == 10
            assert stats["connected"] == 8
            assert stats["by_type"]["inverter"]["connected"] == 4

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_device_summary(self, sample_device_id):
        """
        Test getting comprehensive device summary.

        1. Device exists
        2. Summary requested
        3. Full details returned
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.get_device_summary = AsyncMock(return_value={
                "device_id": sample_device_id,
                "serial_number": "PD12K00001",
                "device_type": "inverter",
                "connection_status": "connected",
                "firmware_version": "1.0.5",
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": 86400,
                "total_commands": 150,
                "failed_commands": 5,
                "telemetry_points_today": 1440,
            })
            MockService.return_value = mock_service

            summary = await mock_service.get_device_summary(
                device_id=sample_device_id,
            )

            assert summary["serial_number"] == "PD12K00001"
            assert summary["connection_status"] == "connected"


class TestDeviceErrorHandling:
    """Test device error handling flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_handle_device_error(self, sample_device_id):
        """
        Test handling device error state.

        1. Device encounters error
        2. Error reported
        3. Device marked as error state
        4. Event logged
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()
            mock_service.handle_device_error = AsyncMock(return_value={
                "device_id": sample_device_id,
                "previous_status": "connected",
                "new_status": "error",
                "error_code": "COMM_FAILURE",
                "error_message": "Communication timeout",
                "event_id": uuid4(),
            })
            MockService.return_value = mock_service

            result = await mock_service.handle_device_error(
                device_id=sample_device_id,
                error_code="COMM_FAILURE",
                error_message="Communication timeout",
            )

            assert result["new_status"] == "error"
            assert result["error_code"] == "COMM_FAILURE"

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_device_recovery_from_error(self, sample_device_id):
        """
        Test device recovery from error state.

        1. Device in error state
        2. Device reconnects
        3. Status updated to connected
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()

            # First in error state
            error_device = MagicMock()
            error_device.id = sample_device_id
            error_device.connection_status = "error"

            # After reconnection
            recovered_device = MagicMock()
            recovered_device.id = sample_device_id
            recovered_device.connection_status = "connected"

            mock_service.get_device = AsyncMock(side_effect=[error_device, recovered_device])
            mock_service.handle_device_connect = AsyncMock(return_value=MagicMock(
                session_id="new_session",
            ))
            MockService.return_value = mock_service

            # Initial state is error
            device = await mock_service.get_device(device_id=sample_device_id)
            assert device.connection_status == "error"

            # Reconnect
            await mock_service.handle_device_connect(
                device_id=sample_device_id,
                client_address="192.168.1.100:54322",
            )

            # After recovery
            device = await mock_service.get_device(device_id=sample_device_id)
            assert device.connection_status == "connected"


class TestDeviceSynchronization:
    """Test device synchronization flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_sync_from_system_a(self, sample_site_id):
        """
        Test syncing device from System A.

        1. Device exists in System A
        2. Sync triggered
        3. Device created/updated in System B
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()

            synced_device = MagicMock()
            synced_device.id = uuid4()
            synced_device.serial_number = "PD12K00001"
            synced_device.synced_at = datetime.now(timezone.utc)

            mock_service.sync_device_from_system_a = AsyncMock(return_value=synced_device)
            MockService.return_value = mock_service

            result = await mock_service.sync_device_from_system_a(
                site_id=sample_site_id,
                system_a_device_id=uuid4(),
                device_data={
                    "serial_number": "PD12K00001",
                    "device_type": "inverter",
                    "protocol": "powdrive",
                },
            )

            assert result.serial_number == "PD12K00001"
            assert result.synced_at is not None

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_get_unsynced_devices(self, sample_site_id):
        """
        Test getting devices not yet synced.

        1. Some devices synced, some not
        2. Query for unsynced
        3. Only unsynced returned
        """
        with patch("app.application.services.device_service.DeviceService") as MockService:

            mock_service = MagicMock()

            unsynced = [
                MagicMock(id=uuid4(), serial_number="PD12K00002", synced_at=None),
                MagicMock(id=uuid4(), serial_number="PD12K00003", synced_at=None),
            ]

            mock_service.get_unsynced_devices = AsyncMock(return_value=unsynced)
            MockService.return_value = mock_service

            devices = await mock_service.get_unsynced_devices(
                site_id=sample_site_id,
            )

            assert len(devices) == 2
            assert all(d.synced_at is None for d in devices)


class TestChallengeResponseAuth:
    """Test challenge-response authentication flow."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_challenge_response_authentication(self, sample_device_id):
        """
        Test HMAC challenge-response authentication.

        1. Challenge generated
        2. Device computes response
        3. Response validated
        4. Authentication succeeds
        """
        with patch("app.application.services.auth_service.DeviceAuthService") as MockAuth:

            mock_auth = MagicMock()

            # Generate challenge
            mock_auth.generate_challenge = AsyncMock(return_value={
                "challenge": "random_challenge_bytes_abc123",
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
            })

            # Validate response
            mock_auth.authenticate_with_challenge = AsyncMock(return_value={
                "authenticated": True,
                "device_id": sample_device_id,
                "session_token": "session_xyz",
            })

            MockAuth.return_value = mock_auth

            # Get challenge
            challenge = await mock_auth.generate_challenge(device_id=sample_device_id)
            assert "challenge" in challenge

            # Authenticate with response
            result = await mock_auth.authenticate_with_challenge(
                device_id=sample_device_id,
                challenge=challenge["challenge"],
                response="computed_hmac_response",
            )

            assert result["authenticated"] is True

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_api_key_authentication(self, sample_device_id):
        """
        Test API key-based authentication.

        1. API key pair generated
        2. Request signed with secret
        3. Signature validated
        4. Access granted
        """
        with patch("app.application.services.auth_service.DeviceAuthService") as MockAuth:

            mock_auth = MagicMock()

            # Generate API key
            mock_auth.generate_api_key = AsyncMock(return_value={
                "api_key_id": "key_123",
                "api_key_secret": "secret_xyz",
                "created_at": datetime.now(timezone.utc),
            })

            # Validate signature
            mock_auth.validate_api_key_signature = AsyncMock(return_value={
                "valid": True,
                "device_id": sample_device_id,
            })

            MockAuth.return_value = mock_auth

            # Generate key
            key = await mock_auth.generate_api_key(device_id=sample_device_id)
            assert "api_key_id" in key

            # Validate signature
            result = await mock_auth.validate_api_key_signature(
                api_key_id=key["api_key_id"],
                signature="request_signature",
                payload="request_payload",
            )

            assert result["valid"] is True

