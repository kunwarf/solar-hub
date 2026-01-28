"""
Unit tests for SQLAlchemyTelemetryRepository upsert and aggregation methods.

Tests use mocked AsyncSession to verify SQL statement construction
and that flush() (not commit()) is called per UoW invariant.
"""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import UUID, uuid4

import pytest

from system_a.app.infrastructure.database.repositories.telemetry_repository import (
    SQLAlchemyTelemetryRepository,
)


@pytest.fixture
def repo(mock_db_session):
    """Create repository with mock session."""
    return SQLAlchemyTelemetryRepository(mock_db_session)


class TestUpsertHourlySummary:
    """Tests for upsert_hourly_summary."""

    @pytest.mark.asyncio
    async def test_upsert_with_device_id(self, repo, mock_db_session, sample_site_id, sample_device_id):
        """Upsert with specific device_id should execute and flush."""
        data = {
            "energy_generated_kwh": 1.5,
            "energy_consumed_kwh": 0.8,
            "peak_power_kw": 5.2,
            "average_power_kw": 3.1,
            "sample_count": 60,
        }

        await repo.upsert_hourly_summary(
            site_id=sample_site_id,
            device_id=sample_device_id,
            timestamp_hour=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
            data=data,
        )

        mock_db_session.execute.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_site_level(self, repo, mock_db_session, sample_site_id):
        """Upsert with device_id=None (site-level) should execute and flush."""
        data = {
            "energy_generated_kwh": 5.0,
            "peak_power_kw": 10.0,
        }

        await repo.upsert_hourly_summary(
            site_id=sample_site_id,
            device_id=None,
            timestamp_hour=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
            data=data,
        )

        mock_db_session.execute.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_flush_not_commit(self, repo, mock_db_session, sample_site_id):
        """Verify flush is called, not commit (UoW invariant)."""
        await repo.upsert_hourly_summary(
            site_id=sample_site_id,
            device_id=None,
            timestamp_hour=datetime(2026, 1, 28, 10, 0, tzinfo=timezone.utc),
            data={"energy_generated_kwh": 1.0},
        )

        mock_db_session.flush.assert_called_once()
        mock_db_session.commit.assert_not_called()


class TestUpsertDailySummary:
    """Tests for upsert_daily_summary."""

    @pytest.mark.asyncio
    async def test_upsert_with_device_id(self, repo, mock_db_session, sample_site_id, sample_device_id):
        """Upsert daily summary with specific device."""
        data = {
            "energy_generated_kwh": 25.5,
            "energy_consumed_kwh": 12.0,
            "peak_power_kw": 8.5,
            "co2_avoided_kg": 12.1,
        }

        await repo.upsert_daily_summary(
            site_id=sample_site_id,
            device_id=sample_device_id,
            summary_date=date(2026, 1, 28),
            data=data,
        )

        mock_db_session.execute.assert_called_once()
        mock_db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_site_level(self, repo, mock_db_session, sample_site_id):
        """Upsert daily summary at site level."""
        data = {
            "energy_generated_kwh": 45.0,
            "net_energy_kwh": 20.0,
        }

        await repo.upsert_daily_summary(
            site_id=sample_site_id,
            device_id=None,
            summary_date=date(2026, 1, 28),
            data=data,
        )

        mock_db_session.execute.assert_called_once()
        mock_db_session.flush.assert_called_once()


class TestUpsertMonthlySummary:
    """Tests for upsert_monthly_summary."""

    @pytest.mark.asyncio
    async def test_upsert_monthly(self, repo, mock_db_session, sample_site_id):
        """Monthly upsert should execute and flush."""
        data = {
            "energy_generated_kwh": 750.0,
            "energy_consumed_kwh": 400.0,
            "peak_power_kw": 10.5,
            "days_with_data": 28,
        }

        await repo.upsert_monthly_summary(
            site_id=sample_site_id,
            device_id=None,
            year=2026,
            month=1,
            data=data,
        )

        mock_db_session.execute.assert_called_once()
        mock_db_session.flush.assert_called_once()
        mock_db_session.commit.assert_not_called()


class TestAggregateHourlyToDaily:
    """Tests for aggregate_hourly_to_daily."""

    @pytest.mark.asyncio
    async def test_returns_aggregated_dict(self, repo, mock_db_session, sample_site_id):
        """Aggregation should return a dict with all expected keys."""
        # Mock the query result
        mock_row = MagicMock()
        mock_row.energy_generated_kwh = 25.5
        mock_row.energy_consumed_kwh = 12.0
        mock_row.energy_exported_kwh = 8.0
        mock_row.energy_imported_kwh = 3.0
        mock_row.energy_stored_kwh = 5.0
        mock_row.energy_discharged_kwh = 4.0
        mock_row.peak_power_kw = 8.5
        mock_row.average_power_kw = 4.2
        mock_row.avg_irradiance_w_m2 = 650.0
        mock_row.avg_temperature_c = 32.0
        mock_row.max_temperature_c = 38.0
        mock_row.min_temperature_c = 22.0
        mock_row.avg_battery_soc_percent = 75.0
        mock_row.avg_grid_voltage_v = 230.0
        mock_row.avg_power_factor = 0.95
        mock_row.total_samples = 720
        mock_row.hours_with_data = 12

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        result = await repo.aggregate_hourly_to_daily(
            site_id=sample_site_id,
            device_id=None,
            target_date=date(2026, 1, 28),
        )

        assert isinstance(result, dict)
        assert result["energy_generated_kwh"] == 25.5
        assert result["energy_consumed_kwh"] == 12.0
        assert result["peak_power_kw"] == 8.5
        assert result["net_energy_kwh"] == 25.5 - 12.0
        assert result["hours_with_data"] == 12
        assert result["co2_avoided_kg"] == pytest.approx(25.5 * 0.475)
        assert result["data_completeness_percent"] == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_handles_no_data(self, repo, mock_db_session, sample_site_id):
        """Should return zeros when no hourly data exists."""
        mock_row = MagicMock()
        mock_row.energy_generated_kwh = 0.0
        mock_row.energy_consumed_kwh = 0.0
        mock_row.energy_exported_kwh = 0.0
        mock_row.energy_imported_kwh = 0.0
        mock_row.energy_stored_kwh = 0.0
        mock_row.energy_discharged_kwh = 0.0
        mock_row.peak_power_kw = 0.0
        mock_row.average_power_kw = None
        mock_row.avg_irradiance_w_m2 = None
        mock_row.avg_temperature_c = None
        mock_row.max_temperature_c = None
        mock_row.min_temperature_c = None
        mock_row.avg_battery_soc_percent = None
        mock_row.avg_grid_voltage_v = None
        mock_row.avg_power_factor = None
        mock_row.total_samples = 0
        mock_row.hours_with_data = 0

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        result = await repo.aggregate_hourly_to_daily(
            site_id=sample_site_id,
            device_id=None,
            target_date=date(2026, 1, 28),
        )

        assert result["energy_generated_kwh"] == 0.0
        assert result["data_completeness_percent"] == 0.0
        assert result["avg_temperature_c"] is None


class TestAggregateDailyToMonthly:
    """Tests for aggregate_daily_to_monthly."""

    @pytest.mark.asyncio
    async def test_returns_monthly_aggregation(self, repo, mock_db_session, sample_site_id):
        """Should aggregate daily values into monthly totals."""
        mock_row = MagicMock()
        mock_row.energy_generated_kwh = 750.0
        mock_row.energy_consumed_kwh = 400.0
        mock_row.energy_exported_kwh = 200.0
        mock_row.energy_imported_kwh = 100.0
        mock_row.energy_stored_kwh = 150.0
        mock_row.energy_discharged_kwh = 140.0
        mock_row.peak_power_kw = 10.5
        mock_row.total_sunshine_hours = 180.0
        mock_row.total_production_hours = 170.0
        mock_row.total_grid_outage_minutes = 45
        mock_row.avg_temperature_c = 30.0
        mock_row.performance_ratio = 0.82
        mock_row.capacity_factor = 0.35
        mock_row.co2_avoided_kg = 356.25
        mock_row.estimated_savings_pkr = 18750.0
        mock_row.days_with_data = 28

        mock_result = MagicMock()
        mock_result.one.return_value = mock_row
        mock_db_session.execute.return_value = mock_result

        result = await repo.aggregate_daily_to_monthly(
            site_id=sample_site_id,
            device_id=None,
            year=2026,
            month=1,
        )

        assert isinstance(result, dict)
        assert result["energy_generated_kwh"] == 750.0
        assert result["net_energy_kwh"] == 350.0
        assert result["peak_power_kw"] == 10.5
        assert result["average_daily_generation_kwh"] == pytest.approx(750.0 / 28)
        assert result["days_with_data"] == 28
        assert result["total_sunshine_hours"] == 180.0
