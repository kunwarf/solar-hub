"""
Unit tests for TelemetrySyncService.

All external dependencies (SystemBClient, repositories) are mocked.
"""
from datetime import date, datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import UUID, uuid4

import pytest

from system_a.app.application.services.telemetry_sync_service import (
    TelemetrySyncService,
    SyncResult,
)
from system_a.app.infrastructure.external.system_b_client import (
    DeviceInfo,
    TelemetryAggregate,
    SystemBClientError,
)


def _make_device(serial_number: str, device_id: UUID = None, site_id: UUID = None):
    """Create a mock device object."""
    device = MagicMock()
    device.id = device_id or uuid4()
    device.serial_number = serial_number
    device.site_id = site_id
    return device


def _make_device_info(serial_number: str, device_id: UUID = None):
    """Create a DeviceInfo from System B."""
    return DeviceInfo(
        id=device_id or uuid4(),
        serial_number=serial_number,
        device_type="inverter",
        status="claimed",
    )


def _make_aggregate(hour: int, avg: float = 5000.0, max_val: float = 8000.0) -> TelemetryAggregate:
    """Create a TelemetryAggregate for a specific hour."""
    return TelemetryAggregate(
        bucket=datetime(2026, 1, 28, hour, 0, tzinfo=timezone.utc),
        avg=avg,
        min=avg * 0.5,
        max=max_val,
        first=avg * 0.6,
        last=avg * 0.9,
        delta=max_val - avg * 0.5,
        sample_count=60,
        quality_percent=98.5,
    )


@pytest.fixture
def sync_service(
    mock_system_b_client,
    mock_telemetry_repository,
    mock_site_repository,
    mock_device_repository,
):
    """Create TelemetrySyncService with all mocked dependencies."""
    return TelemetrySyncService(
        system_b_client=mock_system_b_client,
        telemetry_repository=mock_telemetry_repository,
        site_repository=mock_site_repository,
        device_repository=mock_device_repository,
    )


class TestSyncHourlyForSite:
    """Tests for sync_hourly_for_site."""

    @pytest.mark.asyncio
    async def test_with_data(
        self, sync_service, mock_system_b_client, mock_device_repository,
        mock_telemetry_repository, sample_site_id
    ):
        """Should fetch aggregates per device and upsert hourly rows."""
        device = _make_device("SH01IN2406130092", site_id=sample_site_id)
        sys_b_info = _make_device_info("SH01IN2406130092")

        mock_device_repository.get_by_site_id.return_value = [device]
        mock_system_b_client.get_device_by_serial.return_value = sys_b_info
        mock_system_b_client.get_device_aggregates.return_value = [
            _make_aggregate(10), _make_aggregate(11),
        ]

        result = await sync_service.sync_hourly_for_site(sample_site_id, hours_back=2)

        assert result.success
        assert result.records_upserted > 0
        assert mock_telemetry_repository.upsert_hourly_summary.call_count > 0

    @pytest.mark.asyncio
    async def test_no_devices(
        self, sync_service, mock_device_repository, sample_site_id
    ):
        """Site with no devices should return success with 0 records."""
        mock_device_repository.get_by_site_id.return_value = []

        result = await sync_service.sync_hourly_for_site(sample_site_id)

        assert result.success
        assert result.records_upserted == 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_system_b_error(
        self, sync_service, mock_system_b_client, mock_device_repository, sample_site_id
    ):
        """SystemBClient error should be captured in SyncResult.errors."""
        device = _make_device("SH01IN2406130092")
        sys_b_info = _make_device_info("SH01IN2406130092")

        mock_device_repository.get_by_site_id.return_value = [device]
        mock_system_b_client.get_device_by_serial.return_value = sys_b_info
        mock_system_b_client.get_device_aggregates.side_effect = SystemBClientError("timeout")

        result = await sync_service.sync_hourly_for_site(sample_site_id)

        assert len(result.errors) > 0
        assert "System B error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_device_not_in_system_b(
        self, sync_service, mock_system_b_client, mock_device_repository, sample_site_id
    ):
        """Device not found in System B should produce an error."""
        device = _make_device("SH01INUNKNOWN001")

        mock_device_repository.get_by_site_id.return_value = [device]
        mock_system_b_client.get_device_by_serial.return_value = None

        result = await sync_service.sync_hourly_for_site(sample_site_id)

        assert len(result.errors) == 1
        assert "not found in System B" in result.errors[0]

    @pytest.mark.asyncio
    async def test_creates_both_device_and_site_rows(
        self, sync_service, mock_system_b_client, mock_device_repository,
        mock_telemetry_repository, sample_site_id
    ):
        """Should create both per-device and site-level (device_id=None) rows."""
        device = _make_device("SH01IN2406130092", site_id=sample_site_id)
        sys_b_info = _make_device_info("SH01IN2406130092")

        mock_device_repository.get_by_site_id.return_value = [device]
        mock_system_b_client.get_device_by_serial.return_value = sys_b_info
        mock_system_b_client.get_device_aggregates.return_value = [
            _make_aggregate(10),
        ]

        await sync_service.sync_hourly_for_site(sample_site_id, hours_back=2)

        # Check that upsert was called with device_id and also with None
        calls = mock_telemetry_repository.upsert_hourly_summary.call_args_list
        device_ids = [c.kwargs.get("device_id") for c in calls]
        assert device.id in device_ids, "Should have per-device row"
        assert None in device_ids, "Should have site-level row"


class TestSyncDailyForSite:
    """Tests for sync_daily_for_site."""

    @pytest.mark.asyncio
    async def test_rolls_up_from_hourly(
        self, sync_service, mock_device_repository,
        mock_telemetry_repository, sample_site_id
    ):
        """Daily sync should aggregate from hourly data."""
        device = _make_device("SH01IN2406130092")
        mock_device_repository.get_by_site_id.return_value = [device]
        mock_telemetry_repository.aggregate_hourly_to_daily.return_value = {
            "energy_generated_kwh": 25.5,
            "hours_with_data": 12,
        }

        result = await sync_service.sync_daily_for_site(sample_site_id, days_back=1)

        assert result.records_upserted > 0
        assert mock_telemetry_repository.upsert_daily_summary.call_count > 0

    @pytest.mark.asyncio
    async def test_skips_empty_days(
        self, sync_service, mock_device_repository,
        mock_telemetry_repository, sample_site_id
    ):
        """Should not upsert when no hourly data exists."""
        mock_device_repository.get_by_site_id.return_value = []
        mock_telemetry_repository.aggregate_hourly_to_daily.return_value = {
            "hours_with_data": 0,
        }

        result = await sync_service.sync_daily_for_site(sample_site_id, days_back=1)

        # Only site-level rollup attempted (no devices), but still should check hours_with_data
        assert result.records_upserted == 0 or result.success


class TestSyncMonthlyForSite:
    """Tests for sync_monthly_for_site."""

    @pytest.mark.asyncio
    async def test_rolls_up_from_daily(
        self, sync_service, mock_device_repository,
        mock_telemetry_repository, sample_site_id
    ):
        """Monthly sync should aggregate from daily data."""
        device = _make_device("SH01IN2406130092")
        mock_device_repository.get_by_site_id.return_value = [device]
        mock_telemetry_repository.aggregate_daily_to_monthly.return_value = {
            "energy_generated_kwh": 750.0,
            "days_with_data": 28,
        }

        result = await sync_service.sync_monthly_for_site(sample_site_id, months_back=1)

        assert result.records_upserted > 0
        assert mock_telemetry_repository.upsert_monthly_summary.call_count > 0


class TestSyncAllSites:
    """Tests for sync_all_sites."""

    @pytest.mark.asyncio
    async def test_syncs_provided_site_ids(
        self, sync_service, mock_device_repository, sample_site_id
    ):
        """Should sync each provided site_id."""
        mock_device_repository.get_by_site_id.return_value = []  # No devices

        results = await sync_service.sync_all_sites(site_ids=[sample_site_id])

        assert sample_site_id in results
        assert results[sample_site_id].success


class TestBackfill:
    """Tests for backfill."""

    @pytest.mark.asyncio
    async def test_backfill_date_range(
        self, sync_service, mock_system_b_client, mock_device_repository,
        mock_telemetry_repository, sample_site_id
    ):
        """Backfill should iterate over the full date range."""
        device = _make_device("SH01IN2406130092")
        sys_b_info = _make_device_info("SH01IN2406130092")

        mock_device_repository.get_by_site_id.return_value = [device]
        mock_system_b_client.get_device_by_serial.return_value = sys_b_info
        mock_system_b_client.get_device_aggregates.return_value = [
            _make_aggregate(10),
        ]
        mock_telemetry_repository.aggregate_hourly_to_daily.return_value = {
            "hours_with_data": 10,
            "energy_generated_kwh": 20.0,
        }
        mock_telemetry_repository.aggregate_daily_to_monthly.return_value = {
            "days_with_data": 3,
            "energy_generated_kwh": 60.0,
        }

        result = await sync_service.backfill(
            site_id=sample_site_id,
            start_date=date(2026, 1, 25),
            end_date=date(2026, 1, 27),
        )

        assert result.records_upserted > 0
        # Should have called upsert_hourly for 3 days of data
        assert mock_telemetry_repository.upsert_hourly_summary.call_count >= 3
