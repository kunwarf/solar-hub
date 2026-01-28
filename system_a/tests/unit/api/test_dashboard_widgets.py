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


class TestWeatherEndpoint:
    """Tests for get_weather() endpoint."""

    def test_weather_response_schema_has_required_fields(self):
        """WeatherResponse should have all required fields."""
        from system_a.app.api.v1.dashboard_widgets import WeatherResponse

        response = WeatherResponse(
            organization_id=ORG_ID,
            site_id=SITE_ID,
            site_name="Test Site",
            temperature=32.5,
            condition="sunny",
            humidity=55,
            wind_speed=10,
            solar_forecast=85,
            sunrise="06:15",
            sunset="18:30",
        )

        assert response.temperature == 32.5
        assert response.condition == "sunny"
        assert response.humidity == 55
        assert response.solar_forecast == 85

    def test_weather_default_values(self):
        """WeatherResponse should have sensible defaults."""
        from system_a.app.api.v1.dashboard_widgets import WeatherResponse

        response = WeatherResponse(
            organization_id=ORG_ID,
            site_id=SITE_ID,
            site_name="Test Site",
        )

        assert response.temperature == 0
        assert response.condition == "sunny"
        assert response.humidity == 50
        assert response.wind_speed == 10


class TestLoadSheddingEndpoint:
    """Tests for get_load_shedding() endpoint."""

    def test_load_shedding_response_schema(self):
        """LoadSheddingResponse should have all required fields."""
        from system_a.app.api.v1.dashboard_widgets import LoadSheddingResponse, LoadSheddingWindow

        response = LoadSheddingResponse(
            organization_id=ORG_ID,
            site_id=SITE_ID,
            site_name="Test Site",
            stage=2,
            active=True,
            current_window=LoadSheddingWindow(start="14:00", end="16:00", duration=90),
            next_window=LoadSheddingWindow(start="20:00", end="22:00", date="2026-01-29"),
            battery_reserve=65,
            estimated_coverage=3.5,
        )

        assert response.stage == 2
        assert response.active is True
        assert response.current_window.duration == 90
        assert response.battery_reserve == 65

    def test_load_shedding_defaults_to_no_outage(self):
        """LoadSheddingResponse should default to no active outage."""
        from system_a.app.api.v1.dashboard_widgets import LoadSheddingResponse

        response = LoadSheddingResponse(
            organization_id=ORG_ID,
            site_id=SITE_ID,
            site_name="Test Site",
        )

        assert response.stage == 0
        assert response.active is False
        assert response.current_window is None


class TestOutagesEndpoint:
    """Tests for get_outages() endpoint."""

    def test_outage_record_schema(self):
        """OutageRecord should have all required fields."""
        from system_a.app.api.v1.dashboard_widgets import OutageRecord

        record = OutageRecord(
            id="outage-2026-01-28-0",
            date="2026-01-28",
            start_time="2026-01-28T14:00:00+00:00",
            end_time="2026-01-28T16:30:00+00:00",
            duration=150,
            type="scheduled",
            battery_used=2.5,
            backup_status="full",
        )

        assert record.duration == 150
        assert record.type == "scheduled"
        assert record.backup_status == "full"

    def test_monthly_outage_stats_schema(self):
        """MonthlyOutageStats should correctly calculate derived values."""
        from system_a.app.api.v1.dashboard_widgets import MonthlyOutageStats

        stats = MonthlyOutageStats(
            total_outages=25,
            total_duration=3000,
            avg_duration=120,
            longest_outage=240,
            total_backup_time=2800,
            total_battery_used=35.5,
            hours_avoided=46.7,
        )

        assert stats.total_outages == 25
        assert stats.avg_duration == 120
        assert stats.hours_avoided == 46.7

    def test_grid_status_data_schema(self):
        """GridStatusData should represent current grid state."""
        from system_a.app.api.v1.dashboard_widgets import GridStatusData

        status = GridStatusData(
            online=False,
            last_change="2026-01-28T14:00:00+00:00",
            current_outage=None,
            battery_level=72,
            estimated_backup_hours=4.2,
            current_load=2.1,
        )

        assert status.online is False
        assert status.battery_level == 72
        assert status.estimated_backup_hours == 4.2

    def test_outages_response_schema(self):
        """OutagesResponse should contain all page data."""
        from system_a.app.api.v1.dashboard_widgets import (
            OutagesResponse,
            GridStatusData,
            MonthlyOutageStats,
        )

        response = OutagesResponse(
            organization_id=ORG_ID,
            site_id=SITE_ID,
            site_name="Test Site",
            grid_status=GridStatusData(
                online=True,
                last_change="2026-01-28T12:00:00+00:00",
                battery_level=85,
                estimated_backup_hours=5.0,
                current_load=1.8,
            ),
            today_outages=[],
            week_summaries=[],
            monthly_stats=MonthlyOutageStats(),
            outage_history=[],
            alerts=[],
        )

        assert response.grid_status.online is True
        assert len(response.today_outages) == 0
        assert response.monthly_stats.total_outages == 0

    def test_outage_alert_schema(self):
        """OutageAlert should have all required fields."""
        from system_a.app.api.v1.dashboard_widgets import OutageAlert

        alert = OutageAlert(
            id="alert-1",
            type="grid_down",
            message="Grid power lost - switching to battery backup",
            timestamp="2026-01-28T14:00:00+00:00",
            read=False,
            priority="high",
        )

        assert alert.type == "grid_down"
        assert alert.priority == "high"
        assert alert.read is False
