"""
Unit tests for SystemBTelemetryRepository.

Tests the repository adapter that fetches telemetry data from System B
and maps it to System A domain models.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from system_a.app.infrastructure.database.repositories.telemetry_system_b_repository import (
    SystemBTelemetryRepository,
)
from system_a.app.infrastructure.database.models.telemetry_model import (
    TelemetryHourlySummaryModel,
)
from system_a.app.infrastructure.external.system_b_client import SystemBClientError


@pytest.fixture
def mock_system_b_client():
    """Create mock System B client."""
    client = AsyncMock()
    client.get_hourly_energy_summary = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def repo(mock_system_b_client):
    """Create repository with mock System B client."""
    return SystemBTelemetryRepository(mock_system_b_client)


class TestGetHourlySummaries:
    """Tests for get_hourly_summaries method."""

    @pytest.mark.asyncio
    async def test_fetch_and_map_hourly_data(self, repo, mock_system_b_client):
        """Should fetch data from System B and map to TelemetryHourlySummaryModel."""
        site_id = uuid4()
        start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 2, 1, 23, 59, tzinfo=timezone.utc)

        # Mock System B response with typical data
        mock_system_b_client.get_hourly_energy_summary.return_value = [
            {
                "timestamp": "2026-02-01T00:00:00Z",
                "pv_kwh": 0.5,
                "load_kwh": 1.2,
                "grid_import_kwh": 0.8,
                "grid_export_kwh": 0.1,
                "battery_charge_kwh": 0.0,
                "battery_discharge_kwh": 0.0,
            },
            {
                "timestamp": "2026-02-01T01:00:00Z",
                "pv_kwh": 0.8,
                "load_kwh": 1.5,
                "grid_import_kwh": 0.9,
                "grid_export_kwh": 0.2,
                "battery_charge_kwh": 0.0,
                "battery_discharge_kwh": 0.0,
            },
        ]

        # Call repository method
        result = await repo.get_hourly_summaries(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify System B client was called correctly
        mock_system_b_client.get_hourly_energy_summary.assert_called_once_with(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify result is list of models
        assert len(result) == 2
        assert all(isinstance(model, TelemetryHourlySummaryModel) for model in result)

        # Verify first model mapping
        model_1 = result[0]
        assert model_1.site_id == site_id
        assert model_1.device_id is None  # System B returns site-level
        assert model_1.timestamp_hour == datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
        assert model_1.energy_generated_kwh == Decimal("0.5")
        assert model_1.energy_consumed_kwh == Decimal("1.2")
        assert model_1.energy_imported_kwh == Decimal("0.8")
        assert model_1.energy_exported_kwh == Decimal("0.1")

        # Verify second model mapping
        model_2 = result[1]
        assert model_2.energy_generated_kwh == Decimal("0.8")
        assert model_2.energy_consumed_kwh == Decimal("1.5")

    @pytest.mark.asyncio
    async def test_handles_updated_at_field(self, repo, mock_system_b_client):
        """Should handle System B responses that include updated_at field."""
        site_id = uuid4()
        start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc)

        # Mock System B response WITH updated_at field
        mock_system_b_client.get_hourly_energy_summary.return_value = [
            {
                "timestamp": "2026-02-01T00:00:00Z",
                "pv_kwh": 2.5,
                "load_kwh": 3.0,
                "grid_import_kwh": 1.0,
                "grid_export_kwh": 0.5,
                "battery_charge_kwh": 0.2,
                "battery_discharge_kwh": 0.1,
                "updated_at": "2026-02-01T01:05:00Z",  # This field caused the error
            },
        ]

        # Call repository method - should not raise error
        result = await repo.get_hourly_summaries(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify model was created successfully
        assert len(result) == 1
        model = result[0]
        assert isinstance(model, TelemetryHourlySummaryModel)
        assert model.energy_generated_kwh == Decimal("2.5")
        assert model.energy_consumed_kwh == Decimal("3.0")
        # updated_at should be None if not explicitly set (model has the field but we don't map it)
        assert model.updated_at is None or isinstance(model.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_handles_missing_optional_fields(self, repo, mock_system_b_client):
        """Should handle System B responses with missing optional fields."""
        site_id = uuid4()
        start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc)

        # Mock System B response with minimal fields (battery fields missing)
        mock_system_b_client.get_hourly_energy_summary.return_value = [
            {
                "timestamp": "2026-02-01T00:00:00Z",
                "pv_kwh": 1.0,
                "load_kwh": 0.8,
                "grid_import_kwh": 0.0,
                "grid_export_kwh": 0.2,
                # battery_charge_kwh and battery_discharge_kwh missing
            },
        ]

        # Call repository method
        result = await repo.get_hourly_summaries(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify model was created with defaults for missing fields
        assert len(result) == 1
        model = result[0]
        assert model.energy_stored_kwh == Decimal("0.0")
        assert model.energy_discharged_kwh == Decimal("0.0")

    @pytest.mark.asyncio
    async def test_handles_datetime_objects(self, repo, mock_system_b_client):
        """Should handle System B responses with datetime objects instead of strings."""
        site_id = uuid4()
        start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc)

        # Mock System B response with datetime object instead of string
        timestamp = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
        mock_system_b_client.get_hourly_energy_summary.return_value = [
            {
                "timestamp": timestamp,  # datetime object, not string
                "pv_kwh": 1.5,
                "load_kwh": 2.0,
                "grid_import_kwh": 0.5,
                "grid_export_kwh": 0.0,
                "battery_charge_kwh": 0.0,
                "battery_discharge_kwh": 0.0,
            },
        ]

        # Call repository method
        result = await repo.get_hourly_summaries(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Verify timestamp was handled correctly
        assert len(result) == 1
        model = result[0]
        assert model.timestamp_hour == timestamp

    @pytest.mark.asyncio
    async def test_handles_system_b_client_error(self, repo, mock_system_b_client):
        """Should propagate SystemBClientError when System B API fails."""
        site_id = uuid4()
        start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc)

        # Mock System B client raising an error
        mock_system_b_client.get_hourly_energy_summary.side_effect = SystemBClientError(
            "Connection timeout"
        )

        # Call should raise SystemBClientError
        with pytest.raises(SystemBClientError, match="Connection timeout"):
            await repo.get_hourly_summaries(
                site_id=site_id,
                start_time=start_time,
                end_time=end_time,
            )

    @pytest.mark.asyncio
    async def test_warns_on_device_id_filter(self, repo, mock_system_b_client, caplog):
        """Should log warning when device_id is provided (not supported)."""
        site_id = uuid4()
        device_id = uuid4()
        start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc)

        mock_system_b_client.get_hourly_energy_summary.return_value = []

        # Call with device_id parameter
        await repo.get_hourly_summaries(
            site_id=site_id,
            start_time=start_time,
            end_time=end_time,
            device_id=device_id,  # Should trigger warning
        )

        # Verify warning was logged
        assert "Device-level filtering not supported" in caplog.text


class TestMapToHourlySummaryModel:
    """Tests for _map_to_hourly_summary_model method."""

    def test_maps_all_fields_correctly(self, repo):
        """Should map all System B fields to System A model fields."""
        site_id = uuid4()
        data_point = {
            "timestamp": "2026-02-01T12:00:00Z",
            "pv_kwh": 5.5,
            "load_kwh": 3.2,
            "grid_import_kwh": 0.5,
            "grid_export_kwh": 2.8,
            "battery_charge_kwh": 1.0,
            "battery_discharge_kwh": 0.8,
            "temperature_c": 35.2,
        }

        model = repo._map_to_hourly_summary_model(
            site_id=site_id,
            device_id=None,
            data_point=data_point,
        )

        assert isinstance(model, TelemetryHourlySummaryModel)
        assert model.site_id == site_id
        assert model.device_id is None
        assert model.timestamp_hour == datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
        assert model.energy_generated_kwh == Decimal("5.5")
        assert model.energy_consumed_kwh == Decimal("3.2")
        assert model.energy_imported_kwh == Decimal("0.5")
        assert model.energy_exported_kwh == Decimal("2.8")
        assert model.energy_stored_kwh == Decimal("1.0")
        assert model.energy_discharged_kwh == Decimal("0.8")
        assert model.avg_temperature_c == 35.2
        assert model.sample_count == 1

    def test_handles_timezone_aware_timestamp(self, repo):
        """Should ensure timestamp is timezone-aware."""
        site_id = uuid4()

        # Test with naive datetime (no timezone)
        data_point = {
            "timestamp": datetime(2026, 2, 1, 10, 0),  # Naive datetime
            "pv_kwh": 1.0,
            "load_kwh": 1.0,
            "grid_import_kwh": 0.0,
            "grid_export_kwh": 0.0,
        }

        model = repo._map_to_hourly_summary_model(
            site_id=site_id,
            device_id=None,
            data_point=data_point,
        )

        # Should convert to UTC
        assert model.timestamp_hour.tzinfo == timezone.utc


class TestClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_closes_system_b_client(self, repo, mock_system_b_client):
        """Should call close on the System B client."""
        await repo.close()
        mock_system_b_client.close.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
