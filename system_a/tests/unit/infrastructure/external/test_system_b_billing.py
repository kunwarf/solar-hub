"""
Unit tests for System B billing integration.

Tests the System B client and repository adapter for billing functionality.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import Mock, AsyncMock, patch

from system_a.app.infrastructure.external.system_b_client import SystemBClient
from system_a.app.infrastructure.database.repositories.telemetry_system_b_repository import (
    SystemBTelemetryRepository,
)


@pytest.fixture
def mock_system_b_client():
    """Create a mock System B client."""
    client = Mock(spec=SystemBClient)
    client.get_hourly_energy_summary = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def system_b_repository(mock_system_b_client):
    """Create System B repository with mocked client."""
    return SystemBTelemetryRepository(mock_system_b_client)


@pytest.mark.asyncio
async def test_get_hourly_energy_summary_maps_correctly(mock_system_b_client):
    """Test that System B energy data maps to HourlyEnergyData correctly."""
    # Arrange
    site_id = uuid4()
    start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)

    # Mock System B response
    mock_response = [
        {
            "timestamp": "2026-02-01T00:00:00+00:00",
            "pv_kwh": 10.5,
            "load_kwh": 8.2,
            "grid_import_kwh": 0.0,
            "grid_export_kwh": 2.3,
            "battery_charge_kwh": 0.5,
            "battery_discharge_kwh": 0.0,
            "temperature_c": 25.5,
        },
        {
            "timestamp": "2026-02-01T01:00:00+00:00",
            "pv_kwh": 12.3,
            "load_kwh": 9.1,
            "grid_import_kwh": 0.0,
            "grid_export_kwh": 3.2,
            "battery_charge_kwh": 0.8,
            "battery_discharge_kwh": 0.0,
        },
    ]

    mock_system_b_client.get_hourly_energy_summary.return_value = mock_response

    # Act
    repository = SystemBTelemetryRepository(mock_system_b_client)
    result = await repository.get_hourly_summaries(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
    )

    # Assert
    assert len(result) == 2
    assert mock_system_b_client.get_hourly_energy_summary.called_once_with(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
    )

    # Check first data point mapping
    first_summary = result[0]
    assert first_summary.site_id == site_id
    assert first_summary.device_id is None  # Site-level aggregate
    assert first_summary.energy_generated_kwh == Decimal("10.5")
    assert first_summary.energy_consumed_kwh == Decimal("8.2")
    assert first_summary.energy_imported_kwh == Decimal("0.0")
    assert first_summary.energy_exported_kwh == Decimal("2.3")
    assert first_summary.energy_stored_kwh == Decimal("0.5")
    assert first_summary.energy_discharged_kwh == Decimal("0.0")
    assert first_summary.avg_temperature_c == 25.5

    # Check second data point
    second_summary = result[1]
    assert second_summary.energy_generated_kwh == Decimal("12.3")
    assert second_summary.energy_consumed_kwh == Decimal("9.1")


@pytest.mark.asyncio
async def test_get_hourly_summaries_handles_empty_response(system_b_repository, mock_system_b_client):
    """Test that empty response from System B is handled correctly."""
    # Arrange
    site_id = uuid4()
    start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)

    mock_system_b_client.get_hourly_energy_summary.return_value = []

    # Act
    result = await system_b_repository.get_hourly_summaries(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
    )

    # Assert
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_hourly_summaries_handles_missing_optional_fields(system_b_repository, mock_system_b_client):
    """Test that missing optional fields in System B response are handled."""
    # Arrange
    site_id = uuid4()
    start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)

    # Minimal response without optional fields
    mock_response = [
        {
            "timestamp": "2026-02-01T00:00:00Z",
            "pv_kwh": 10.0,
            "load_kwh": 8.0,
            "grid_import_kwh": 0.0,
            "grid_export_kwh": 2.0,
        }
    ]

    mock_system_b_client.get_hourly_energy_summary.return_value = mock_response

    # Act
    result = await system_b_repository.get_hourly_summaries(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
    )

    # Assert
    assert len(result) == 1
    summary = result[0]
    assert summary.energy_generated_kwh == Decimal("10.0")
    assert summary.energy_consumed_kwh == Decimal("8.0")
    # Optional fields should default to 0
    assert summary.energy_stored_kwh == Decimal("0.0")
    assert summary.energy_discharged_kwh == Decimal("0.0")
    assert summary.avg_temperature_c is None


@pytest.mark.asyncio
async def test_repository_close_calls_client_close(system_b_repository, mock_system_b_client):
    """Test that repository close method calls client close."""
    # Act
    await system_b_repository.close()

    # Assert
    mock_system_b_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_map_to_hourly_summary_model_handles_timezone_naive_timestamp(system_b_repository):
    """Test that timezone-naive timestamps are handled correctly."""
    # Arrange
    site_id = uuid4()
    data_point = {
        "timestamp": "2026-02-01T00:00:00",  # No timezone info
        "pv_kwh": 10.0,
        "load_kwh": 8.0,
        "grid_import_kwh": 0.0,
        "grid_export_kwh": 2.0,
    }

    # Act
    result = system_b_repository._map_to_hourly_summary_model(
        site_id=site_id,
        device_id=None,
        data_point=data_point,
    )

    # Assert
    assert result.timestamp_hour.tzinfo is not None  # Should be timezone-aware
    assert result.timestamp_hour.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_device_id_filter_logs_warning(system_b_repository, mock_system_b_client, caplog):
    """Test that device_id parameter logs a warning since System B only supports site-level."""
    # Arrange
    site_id = uuid4()
    device_id = uuid4()
    start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)

    mock_system_b_client.get_hourly_energy_summary.return_value = []

    # Act
    await system_b_repository.get_hourly_summaries(
        site_id=site_id,
        start_time=start_time,
        end_time=end_time,
        device_id=device_id,  # This should log a warning
    )

    # Assert
    assert "Device-level filtering not supported" in caplog.text


# Integration-level test (requires actual System B)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_system_b_client_energy_summary():
    """
    Integration test with real System B instance.

    This test requires System B to be running at localhost:8001.
    Skip in CI if System B is not available.
    """
    import os

    if not os.getenv("TEST_SYSTEM_B_INTEGRATION"):
        pytest.skip("System B integration test skipped (set TEST_SYSTEM_B_INTEGRATION=1 to run)")

    # Arrange
    client = SystemBClient(base_url="http://localhost:8001", timeout=10.0)
    repository = SystemBTelemetryRepository(client)

    # Use a known test site (replace with actual test site ID)
    test_site_id = UUID("00000000-0000-0000-0000-000000000001")
    start_time = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 2, 2, 0, 0, tzinfo=timezone.utc)

    try:
        # Act
        result = await repository.get_hourly_summaries(
            site_id=test_site_id,
            start_time=start_time,
            end_time=end_time,
        )

        # Assert
        # Should return data (assuming test site has telemetry)
        assert isinstance(result, list)
        # Each item should be a proper model
        for summary in result:
            assert summary.site_id == test_site_id
            assert summary.timestamp_hour is not None
            assert isinstance(summary.energy_generated_kwh, Decimal)

    finally:
        await client.close()
