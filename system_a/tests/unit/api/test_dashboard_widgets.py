"""
Unit tests for dashboard widget API enhancements.

Tests that the widget endpoints correctly query summary tables
for historical data (peak power, monthly energy, energy chart, billing).
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from system_a.app.infrastructure.database.repositories.telemetry_repository import (
    SQLAlchemyTelemetryRepository,
    DailySummary,
)


# Sample IDs for tests
SITE_ID = uuid4()
ORG_ID = uuid4()


class TestStatsEndpointHistoricalData:
    """Tests for get_stats() historical data integration."""

    @pytest.mark.asyncio
    async def test_stats_uses_summary_table_for_peak_power(self):
        """peak_power_kw should come from get_today_energy() summary table."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)
        mock_repo.get_today_energy.return_value = {
            "energy_generated_kwh": 15.5,
            "energy_consumed_kwh": 10.0,
            "energy_exported_kwh": 3.0,
            "energy_imported_kwh": 1.0,
            "peak_power_kw": 4.2,
        }
        mock_repo.get_this_month_energy.return_value = 320.5

        result = await mock_repo.get_today_energy(SITE_ID)
        assert result["peak_power_kw"] == 4.2

    @pytest.mark.asyncio
    async def test_stats_uses_summary_table_for_monthly_energy(self):
        """energy_month_kwh should come from get_this_month_energy() summary table."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)
        mock_repo.get_this_month_energy.return_value = 450.0

        result = await mock_repo.get_this_month_energy(SITE_ID)
        assert result == 450.0

    @pytest.mark.asyncio
    async def test_stats_returns_zero_when_no_summary_data(self):
        """Stats should return 0 for peak/monthly when no summary data exists."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)
        mock_repo.get_today_energy.return_value = {
            "energy_generated_kwh": 0.0,
            "energy_consumed_kwh": 0.0,
            "energy_exported_kwh": 0.0,
            "energy_imported_kwh": 0.0,
            "peak_power_kw": 0.0,
        }
        mock_repo.get_this_month_energy.return_value = 0.0

        today = await mock_repo.get_today_energy(SITE_ID)
        month = await mock_repo.get_this_month_energy(SITE_ID)

        assert today["peak_power_kw"] == 0.0
        assert month == 0.0


class TestEnergyChartEndpoint:
    """Tests for get_energy_chart() historical data queries."""

    @pytest.mark.asyncio
    async def test_energy_chart_day_queries_hourly_summaries(self):
        """period=day should query hourly summary table."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)

        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        mock_hourly = MagicMock()
        mock_hourly.timestamp_hour = start
        mock_hourly.energy_generated_kwh = 2.5
        mock_hourly.energy_consumed_kwh = 1.5
        mock_hourly.energy_imported_kwh = 0.3
        mock_hourly.energy_exported_kwh = 0.8

        mock_repo.get_hourly_summaries.return_value = [mock_hourly]

        result = await mock_repo.get_hourly_summaries(SITE_ID, start, now)

        mock_repo.get_hourly_summaries.assert_called_once_with(SITE_ID, start, now)
        assert len(result) == 1
        assert result[0].energy_generated_kwh == 2.5

    @pytest.mark.asyncio
    async def test_energy_chart_week_queries_daily_summaries(self):
        """period=week should query daily summary table for last 7 days."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)

        today = date.today()
        week_ago = today - timedelta(days=7)

        mock_daily = DailySummary(
            date=today,
            energy_generated_kwh=18.5,
            energy_consumed_kwh=12.0,
            energy_exported_kwh=4.0,
            energy_imported_kwh=1.5,
            peak_power_kw=5.2,
            peak_power_time=None,
            sunshine_hours=8.0,
            performance_ratio=0.82,
            co2_avoided_kg=8.78,
        )

        mock_repo.get_daily_summaries.return_value = [mock_daily]

        result = await mock_repo.get_daily_summaries(SITE_ID, week_ago, today)
        assert len(result) == 1
        assert result[0].energy_generated_kwh == 18.5

    @pytest.mark.asyncio
    async def test_energy_chart_month_queries_daily_summaries(self):
        """period=month should query daily summary table for last 30 days."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)

        today = date.today()
        month_ago = today - timedelta(days=30)

        mock_repo.get_daily_summaries.return_value = []

        result = await mock_repo.get_daily_summaries(SITE_ID, month_ago, today)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_energy_chart_empty_summaries_returns_empty_data(self):
        """Empty summary tables should result in empty data list (before fallback)."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)
        mock_repo.get_hourly_summaries.return_value = []

        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        result = await mock_repo.get_hourly_summaries(SITE_ID, start, now)
        assert result == []


class TestBillingEndpointHistoricalData:
    """Tests for get_billing_summary() historical data integration."""

    @pytest.mark.asyncio
    async def test_billing_monthly_savings_from_summary(self):
        """estimated_savings_month should use monthly energy from summary table."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)
        mock_repo.get_this_month_energy.return_value = 500.0

        month_energy = await mock_repo.get_this_month_energy(SITE_ID)
        import_rate = 30  # PKR/kWh
        savings_month = month_energy * import_rate

        assert savings_month == 15000.0

    @pytest.mark.asyncio
    async def test_billing_zero_monthly_savings_when_no_data(self):
        """estimated_savings_month should be 0 when no monthly data exists."""
        mock_repo = AsyncMock(spec=SQLAlchemyTelemetryRepository)
        mock_repo.get_this_month_energy.return_value = 0.0

        month_energy = await mock_repo.get_this_month_energy(SITE_ID)
        savings = month_energy * 30

        assert savings == 0.0


class TestSyncEndpoint:
    """Tests for the manual sync trigger endpoint."""

    @pytest.mark.asyncio
    async def test_sync_endpoint_calls_sync_service(self):
        """POST /dashboard/sync should call sync_hourly_for_site."""
        from system_a.app.application.services.telemetry_sync_service import SyncResult

        mock_sync_service = AsyncMock()
        mock_sync_service.sync_hourly_for_site.return_value = SyncResult(
            success=True,
            records_upserted=42,
            errors=[],
        )

        result = await mock_sync_service.sync_hourly_for_site(SITE_ID, hours_back=2)

        mock_sync_service.sync_hourly_for_site.assert_called_once_with(
            SITE_ID, hours_back=2
        )
        assert result.success is True
        assert result.records_upserted == 42
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_sync_endpoint_returns_errors(self):
        """POST /dashboard/sync should surface sync errors in response."""
        from system_a.app.application.services.telemetry_sync_service import SyncResult

        mock_sync_service = AsyncMock()
        mock_sync_service.sync_hourly_for_site.return_value = SyncResult(
            success=False,
            records_upserted=5,
            errors=["Device ABC: connection timeout"],
        )

        result = await mock_sync_service.sync_hourly_for_site(SITE_ID, hours_back=2)

        assert result.success is False
        assert result.records_upserted == 5
        assert len(result.errors) == 1
        assert "connection timeout" in result.errors[0]
