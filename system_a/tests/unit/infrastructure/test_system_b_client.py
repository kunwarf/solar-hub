"""
Unit tests for SystemBClient telemetry query methods.

Tests use mocked httpx responses to verify parsing and error handling.
"""
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4

import httpx
import pytest

from system_a.app.infrastructure.external.system_b_client import (
    SystemBClient,
    SystemBClientError,
    TelemetryAggregate,
    DeviceLatestTelemetry,
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


class TestGetDeviceAggregates:
    """Tests for get_device_aggregates method."""

    @pytest.mark.asyncio
    async def test_success_returns_aggregate_list(
        self, client, sample_device_id, sample_aggregate_response
    ):
        """Should parse aggregate response into TelemetryAggregate list."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(
            return_value=_mock_response(200, sample_aggregate_response)
        )
        client._client = mock_http_client

        result = await client.get_device_aggregates(
            device_id=sample_device_id,
            metric_name="pv_power_w",
            start_time=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        )

        assert len(result) == 2
        assert isinstance(result[0], TelemetryAggregate)
        assert result[0].avg == 5200.5
        assert result[0].min == 3100.0
        assert result[0].max == 7400.0
        assert result[0].sample_count == 60
        assert result[0].quality_percent == 98.5
        assert result[1].avg == 8100.0

    @pytest.mark.asyncio
    async def test_empty_response(self, client, sample_device_id):
        """Should return empty list for device with no data."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(return_value=_mock_response(200, []))
        client._client = mock_http_client

        result = await client.get_device_aggregates(
            device_id=sample_device_id,
            metric_name="pv_power_w",
            start_time=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_passes_bucket_interval(self, client, sample_device_id):
        """Should pass bucket_interval as query parameter."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(return_value=_mock_response(200, []))
        client._client = mock_http_client

        await client.get_device_aggregates(
            device_id=sample_device_id,
            metric_name="pv_power_w",
            start_time=datetime(2026, 1, 28, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 29, 0, 0, tzinfo=timezone.utc),
            bucket_interval="1 day",
        )

        call_args = mock_http_client.get.call_args
        assert call_args.kwargs["params"]["bucket_interval"] == "1 day"

    @pytest.mark.asyncio
    async def test_server_error_raises(self, client, sample_device_id):
        """Should raise SystemBClientError on HTTP 500."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(
            return_value=_mock_response(500, text="Internal Server Error")
        )
        client._client = mock_http_client

        with pytest.raises(SystemBClientError):
            await client.get_device_aggregates(
                device_id=sample_device_id,
                metric_name="pv_power_w",
                start_time=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
            )


class TestGetSiteTelemetry:
    """Tests for get_site_telemetry method."""

    @pytest.mark.asyncio
    async def test_success_returns_records(self, client, sample_site_id):
        """Should return raw telemetry records."""
        records = [
            {
                "time": "2026-01-28T12:00:00+00:00",
                "device_id": str(uuid4()),
                "metric_name": "pv_power_w",
                "value": 5234.0,
            }
        ]
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(return_value=_mock_response(200, records))
        client._client = mock_http_client

        result = await client.get_site_telemetry(
            site_id=sample_site_id,
            start_time=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        )

        assert len(result) == 1
        assert result[0]["metric_name"] == "pv_power_w"

    @pytest.mark.asyncio
    async def test_passes_optional_filters(self, client, sample_site_id, sample_device_id):
        """Should pass metric_names and device_ids as query parameters."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(return_value=_mock_response(200, []))
        client._client = mock_http_client

        await client.get_site_telemetry(
            site_id=sample_site_id,
            start_time=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
            metric_names=["pv_power_w", "load_power_w"],
            device_ids=[sample_device_id],
        )

        call_args = mock_http_client.get.call_args
        assert call_args.kwargs["params"]["metric_names"] == ["pv_power_w", "load_power_w"]


class TestGetSitePowerChart:
    """Tests for get_site_power_chart method."""

    @pytest.mark.asyncio
    async def test_success_returns_chart_data(self, client, sample_site_id):
        """Should parse power chart response."""
        chart_data = [
            {
                "timestamp": "2026-01-28T12:00:00+00:00",
                "solar_w": 5234.0,
                "grid_w": 100.0,
                "load_w": 1200.0,
                "battery_w": 800.0,
            }
        ]
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(return_value=_mock_response(200, chart_data))
        client._client = mock_http_client

        result = await client.get_site_power_chart(
            site_id=sample_site_id,
            start_time=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
        )

        assert len(result) == 1
        assert result[0]["solar_w"] == 5234.0


class TestGetDeviceLatest:
    """Tests for get_device_latest method."""

    @pytest.mark.asyncio
    async def test_success_returns_latest(
        self, client, sample_device_id, sample_latest_response
    ):
        """Should return DeviceLatestTelemetry with readings."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(
            return_value=_mock_response(200, sample_latest_response)
        )
        client._client = mock_http_client

        result = await client.get_device_latest(device_id=sample_device_id)

        assert isinstance(result, DeviceLatestTelemetry)
        assert result.device_id == sample_device_id
        assert "pv_power_w" in result.readings
        assert result.readings["pv_power_w"]["value"] == 5234.0

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self, client, sample_device_id):
        """Should return None when device has no telemetry."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not found"

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(return_value=mock_response)
        client._client = mock_http_client

        result = await client.get_device_latest(device_id=sample_device_id)

        assert result is None


class TestConnectionErrors:
    """Tests for connection error handling across all methods."""

    @pytest.mark.asyncio
    async def test_connection_error_raises_system_b_client_error(self, client, sample_device_id):
        """Should wrap httpx.RequestError into SystemBClientError."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(
            side_effect=httpx.RequestError("Connection refused", request=MagicMock())
        )
        client._client = mock_http_client

        with pytest.raises(SystemBClientError, match="Connection error"):
            await client.get_device_aggregates(
                device_id=sample_device_id,
                metric_name="pv_power_w",
                start_time=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_connection_error_on_site_telemetry(self, client, sample_site_id):
        """Should wrap connection error for site telemetry."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(
            side_effect=httpx.RequestError("Timeout", request=MagicMock())
        )
        client._client = mock_http_client

        with pytest.raises(SystemBClientError, match="Connection error"):
            await client.get_site_telemetry(
                site_id=sample_site_id,
                start_time=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc),
            )

    @pytest.mark.asyncio
    async def test_connection_error_on_latest(self, client, sample_device_id):
        """Should wrap connection error for latest telemetry."""
        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.get = AsyncMock(
            side_effect=httpx.RequestError("Timeout", request=MagicMock())
        )
        client._client = mock_http_client

        with pytest.raises(SystemBClientError, match="Connection error"):
            await client.get_device_latest(device_id=sample_device_id)
