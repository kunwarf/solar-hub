"""
Unit tests for device command API endpoints.

Tests command forwarding to System B and command status retrieval.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from system_a.app.api.v1.devices import send_device_command, get_command_status
from system_a.app.api.schemas.device_schemas import DeviceCommandRequest
from system_a.app.domain.entities.device import Device, DeviceType, DeviceStatus, ProtocolType
from system_a.app.infrastructure.external.system_b_client import SystemBClientError

from fastapi import HTTPException


def _make_device(
    device_id: UUID = None,
    site_id: UUID = None,
    org_id: UUID = None,
    status: DeviceStatus = DeviceStatus.ONLINE,
) -> MagicMock:
    """Create a mock Device."""
    device = MagicMock(spec=Device)
    device.id = device_id or uuid4()
    device.site_id = site_id or uuid4()
    device.organization_id = org_id or uuid4()
    device.status = status
    device.device_type = DeviceType.INVERTER
    device.serial_number = "TEST-001"
    device.name = "Test Inverter"
    return device


class TestSendDeviceCommand:
    """Tests for send_device_command endpoint."""

    @pytest.mark.asyncio
    async def test_send_command_forwards_to_system_b(self):
        """Should forward command to System B and return response."""
        device_id = uuid4()
        site_id = uuid4()
        command_id = uuid4()

        device = _make_device(device_id=device_id, site_id=site_id)

        mock_uow = AsyncMock()
        mock_uow.devices.get_by_id = AsyncMock(return_value=device)
        mock_uow.sites.get_by_id = AsyncMock(return_value=MagicMock(organization_id=uuid4()))
        mock_uow.organizations.get_by_id = AsyncMock(
            return_value=MagicMock(is_member=MagicMock(return_value=True))
        )

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.role = MagicMock()
        mock_user.role.value = "admin"

        mock_system_b = AsyncMock()
        mock_system_b.send_command = AsyncMock(return_value={
            "id": str(command_id),
            "status": "pending",
            "command_type": "set_battery_mode",
        })

        request = DeviceCommandRequest(
            command="set_battery_mode",
            parameters={"mode": "force_charge"},
        )

        # Patch check_site_access to avoid complex auth mock
        with patch("system_a.app.api.v1.devices.check_site_access", new_callable=AsyncMock):
            result = await send_device_command(
                device_id=device_id,
                request=request,
                current_user=mock_user,
                uow=mock_uow,
                system_b_client=mock_system_b,
            )

        assert result.command_id == command_id
        assert result.status == "pending"
        assert result.command == "set_battery_mode"
        mock_system_b.send_command.assert_called_once_with(
            device_id=device_id,
            site_id=site_id,
            command_type="set_battery_mode",
            command_params={"mode": "force_charge"},
        )

    @pytest.mark.asyncio
    async def test_send_command_offline_device_returns_400(self):
        """Should return 400 when device is offline."""
        device = _make_device(status=DeviceStatus.OFFLINE)

        mock_uow = AsyncMock()
        mock_uow.devices.get_by_id = AsyncMock(return_value=device)

        mock_user = MagicMock()

        request = DeviceCommandRequest(command="set_battery_mode")

        with patch("system_a.app.api.v1.devices.check_site_access", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await send_device_command(
                    device_id=device.id,
                    request=request,
                    current_user=mock_user,
                    uow=mock_uow,
                    system_b_client=AsyncMock(),
                )

        assert exc_info.value.status_code == 400
        assert "offline" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_send_command_nonexistent_device_returns_404(self):
        """Should return 404 when device not found."""
        mock_uow = AsyncMock()
        mock_uow.devices.get_by_id = AsyncMock(return_value=None)

        request = DeviceCommandRequest(command="set_battery_mode")

        with pytest.raises(HTTPException) as exc_info:
            await send_device_command(
                device_id=uuid4(),
                request=request,
                current_user=MagicMock(),
                uow=mock_uow,
                system_b_client=AsyncMock(),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_send_command_system_b_error_returns_502(self):
        """Should return 502 when System B fails."""
        device = _make_device()

        mock_uow = AsyncMock()
        mock_uow.devices.get_by_id = AsyncMock(return_value=device)

        mock_system_b = AsyncMock()
        mock_system_b.send_command = AsyncMock(
            side_effect=SystemBClientError("System B unreachable", status_code=None)
        )

        request = DeviceCommandRequest(command="set_battery_mode")

        with patch("system_a.app.api.v1.devices.check_site_access", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await send_device_command(
                    device_id=device.id,
                    request=request,
                    current_user=MagicMock(),
                    uow=mock_uow,
                    system_b_client=mock_system_b,
                )

        assert exc_info.value.status_code == 502


class TestGetCommandStatus:
    """Tests for get_command_status endpoint."""

    @pytest.mark.asyncio
    async def test_get_command_status_success(self):
        """Should return command status from System B."""
        device = _make_device()
        command_id = uuid4()

        mock_uow = AsyncMock()
        mock_uow.devices.get_by_id = AsyncMock(return_value=device)

        mock_system_b = AsyncMock()
        mock_system_b.get_command_status = AsyncMock(return_value={
            "id": str(command_id),
            "command_type": "set_battery_mode",
            "status": "completed",
            "created_at": "2026-01-28T12:00:00+00:00",
        })

        with patch("system_a.app.api.v1.devices.check_site_access", new_callable=AsyncMock):
            result = await get_command_status(
                device_id=device.id,
                command_id=command_id,
                current_user=MagicMock(),
                uow=mock_uow,
                system_b_client=mock_system_b,
            )

        assert result.command_id == command_id
        assert result.status == "completed"
        assert result.command == "set_battery_mode"

    @pytest.mark.asyncio
    async def test_get_command_status_not_found(self):
        """Should return 404 when command not found in System B."""
        device = _make_device()

        mock_uow = AsyncMock()
        mock_uow.devices.get_by_id = AsyncMock(return_value=device)

        mock_system_b = AsyncMock()
        mock_system_b.get_command_status = AsyncMock(
            side_effect=SystemBClientError("Command not found", status_code=404)
        )

        with patch("system_a.app.api.v1.devices.check_site_access", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await get_command_status(
                    device_id=device.id,
                    command_id=uuid4(),
                    current_user=MagicMock(),
                    uow=mock_uow,
                    system_b_client=mock_system_b,
                )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_command_status_device_not_found(self):
        """Should return 404 when device not found."""
        mock_uow = AsyncMock()
        mock_uow.devices.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_command_status(
                device_id=uuid4(),
                command_id=uuid4(),
                current_user=MagicMock(),
                uow=mock_uow,
                system_b_client=AsyncMock(),
            )

        assert exc_info.value.status_code == 404
