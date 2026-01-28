"""
Unit tests for SystemBClient command methods (send_command, get_command_status).
"""
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest

from system_a.app.infrastructure.external.system_b_client import (
    SystemBClient,
    SystemBClientError,
)


@pytest.fixture
def client():
    """Create a SystemBClient for testing."""
    return SystemBClient(base_url="http://test:8001", timeout=5.0)


def _mock_response(status_code: int = 200, json_data=None, text: str = ""):
    """Create a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = text or json.dumps(json_data or {})
    response.json.return_value = json_data or {}
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=response,
        )
    return response


class TestSendCommand:
    """Tests for send_command method."""

    @pytest.mark.asyncio
    async def test_send_command_success(self, client, sample_device_id, sample_site_id):
        """Should POST command to System B and return response."""
        command_id = str(uuid4())
        response_data = {
            "id": command_id,
            "device_id": str(sample_device_id),
            "site_id": str(sample_site_id),
            "command_type": "set_battery_mode",
            "status": "pending",
        }
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.post = AsyncMock(
            return_value=_mock_response(200, response_data)
        )
        client._client = mock_http_client

        result = await client.send_command(
            device_id=sample_device_id,
            site_id=sample_site_id,
            command_type="set_battery_mode",
        )

        assert result["id"] == command_id
        assert result["status"] == "pending"
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert call_args.args[0] == "/api/v1/commands/"
        payload = call_args.kwargs["json"]
        assert payload["device_id"] == str(sample_device_id)
        assert payload["command_type"] == "set_battery_mode"

    @pytest.mark.asyncio
    async def test_send_command_with_params(self, client, sample_device_id, sample_site_id):
        """Should include command_params in the POST payload."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.post = AsyncMock(
            return_value=_mock_response(200, {"id": str(uuid4()), "status": "pending"})
        )
        client._client = mock_http_client

        await client.send_command(
            device_id=sample_device_id,
            site_id=sample_site_id,
            command_type="set_battery_mode",
            command_params={"mode": "force_charge"},
            priority=8,
            expires_in_minutes=30,
        )

        call_args = mock_http_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["command_params"] == {"mode": "force_charge"}
        assert payload["priority"] == 8
        assert payload["expires_in_minutes"] == 30

    @pytest.mark.asyncio
    async def test_send_command_error_raises(self, client, sample_device_id, sample_site_id):
        """Should raise SystemBClientError on HTTP errors."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.post = AsyncMock(
            return_value=_mock_response(500, text="Internal Server Error")
        )
        client._client = mock_http_client

        with pytest.raises(SystemBClientError, match="Failed to send command"):
            await client.send_command(
                device_id=sample_device_id,
                site_id=sample_site_id,
                command_type="set_battery_mode",
            )

    @pytest.mark.asyncio
    async def test_send_command_connection_error(self, client, sample_device_id, sample_site_id):
        """Should wrap connection errors into SystemBClientError."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.post = AsyncMock(
            side_effect=httpx.RequestError("Connection refused", request=MagicMock())
        )
        client._client = mock_http_client

        with pytest.raises(SystemBClientError, match="Connection error"):
            await client.send_command(
                device_id=sample_device_id,
                site_id=sample_site_id,
                command_type="set_battery_mode",
            )


class TestGetCommandStatus:
    """Tests for get_command_status method."""

    @pytest.mark.asyncio
    async def test_get_command_status_success(self, client):
        """Should GET command status from System B."""
        command_id = uuid4()
        response_data = {
            "id": str(command_id),
            "command_type": "set_battery_mode",
            "status": "completed",
            "created_at": "2026-01-28T12:00:00+00:00",
        }
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(
            return_value=_mock_response(200, response_data)
        )
        client._client = mock_http_client

        result = await client.get_command_status(command_id)

        assert result["status"] == "completed"
        assert result["command_type"] == "set_battery_mode"
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert call_args.args[0] == f"/api/v1/commands/{command_id}"

    @pytest.mark.asyncio
    async def test_get_command_status_not_found(self, client):
        """Should raise SystemBClientError with 404 for missing command."""
        command_id = uuid4()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not found"

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        with pytest.raises(SystemBClientError, match="Command not found"):
            await client.get_command_status(command_id)

    @pytest.mark.asyncio
    async def test_get_command_status_connection_error(self, client):
        """Should wrap connection errors."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(
            side_effect=httpx.RequestError("Timeout", request=MagicMock())
        )
        client._client = mock_http_client

        with pytest.raises(SystemBClientError, match="Connection error"):
            await client.get_command_status(uuid4())
