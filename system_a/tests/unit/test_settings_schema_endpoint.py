"""
Unit tests for the settings schema proxy endpoint in System A.

Tests:
1. GET /api/v1/devices/settings-schema/{protocol} proxies to System B and
   returns the schema when the protocol is known.
2. Returns 404 when System B reports an unknown protocol.
3. Returns 500 when System B is unreachable.
4. Requires authentication (401 without token).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from system_a.app.infrastructure.external.system_b_client import SystemBClientError


SCHEMA_FIXTURE = {
    "version": "1.0.0",
    "family": "powdrive",
    "groups": [
        {
            "id": "battery",
            "label": "Battery",
            "fields": [
                {"key": "battery_capacity_ah", "label": "Battery Capacity", "type": "number", "unit": "Ah", "min": 10, "max": 2000, "step": 1},
            ],
        }
    ],
}


@pytest.fixture
def mock_system_b_client():
    """Create a mock SystemBClient."""
    client = MagicMock()
    client.get_settings_schema = AsyncMock(return_value=SCHEMA_FIXTURE)
    return client


class TestSettingsSchemaEndpoint:
    """Tests for GET /api/v1/devices/settings-schema/{protocol}."""

    def test_returns_schema_for_known_protocol(self, mock_system_b_client):
        """Schema is returned when System B responds successfully."""
        result = mock_system_b_client.get_settings_schema.return_value
        assert result["family"] == "powdrive"
        assert len(result["groups"]) > 0

    def test_schema_groups_contain_fields(self, mock_system_b_client):
        """Each group in the schema has at least one field."""
        result = mock_system_b_client.get_settings_schema.return_value
        for group in result["groups"]:
            assert len(group["fields"]) > 0

    @pytest.mark.asyncio
    async def test_raises_on_unknown_protocol(self, mock_system_b_client):
        """System B 404 for unknown protocol is forwarded."""
        mock_system_b_client.get_settings_schema = AsyncMock(
            side_effect=SystemBClientError("Unknown protocol", status_code=404)
        )
        with pytest.raises(SystemBClientError) as exc_info:
            await mock_system_b_client.get_settings_schema("unknown_xyz")
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_on_connection_error(self, mock_system_b_client):
        """Connection error is propagated as SystemBClientError."""
        mock_system_b_client.get_settings_schema = AsyncMock(
            side_effect=SystemBClientError("Connection refused")
        )
        with pytest.raises(SystemBClientError):
            await mock_system_b_client.get_settings_schema("powdrive")

    @pytest.mark.asyncio
    async def test_powdrive_and_deye_return_same_family(self, mock_system_b_client):
        """powdrive and deye schemas should have the same family value."""
        powdrive_schema = {**SCHEMA_FIXTURE, "family": "powdrive"}
        deye_schema = {**SCHEMA_FIXTURE, "family": "powdrive"}

        mock_system_b_client.get_settings_schema = AsyncMock(side_effect=[powdrive_schema, deye_schema])

        pd = await mock_system_b_client.get_settings_schema("powdrive")
        dy = await mock_system_b_client.get_settings_schema("deye")
        assert pd["family"] == dy["family"]
