"""
Unit tests for Net Metering Billing API endpoints.

Tests the billing_daily API endpoints for:
- Billing configuration CRUD
- Running bill calculation
- Daily snapshots
- Billing months and cycles
- Summary and trend data
- Capacity analysis

Run with: pytest system_a/tests/unit/api/test_billing_daily.py -v
"""
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

# Sample IDs for tests
SITE_ID = uuid4()
ORG_ID = uuid4()
USER_ID = uuid4()
CONFIG_ID = uuid4()
CYCLE_ID = uuid4()
MONTH_ID = uuid4()


class TestBillingConfigSchemas:
    """Tests for billing configuration schemas."""

    def test_tou_window_schema(self):
        """TouWindowSchema should validate peak hour windows."""
        from system_a.app.api.schemas.net_metering_schemas import TouWindowSchema

        window = TouWindowSchema(start_hour=17, end_hour=22)

        assert window.start_hour == 17
        assert window.end_hour == 22

    def test_tou_window_validates_hour_range(self):
        """TouWindowSchema should validate hour range 0-23."""
        from system_a.app.api.schemas.net_metering_schemas import TouWindowSchema
        from pydantic import ValidationError

        # Valid range
        window = TouWindowSchema(start_hour=0, end_hour=23)
        assert window.start_hour == 0

        # Invalid range should raise
        with pytest.raises(ValidationError):
            TouWindowSchema(start_hour=-1, end_hour=22)

        with pytest.raises(ValidationError):
            TouWindowSchema(start_hour=17, end_hour=25)

    def test_tou_config_schema(self):
        """TouConfigSchema should have default peak windows."""
        from system_a.app.api.schemas.net_metering_schemas import TouConfigSchema

        config = TouConfigSchema()

        assert len(config.peak_windows) == 1
        assert config.peak_windows[0].start_hour == 17
        assert config.peak_windows[0].end_hour == 22
        assert config.timezone == "Asia/Karachi"

    def test_billing_prices_schema(self):
        """BillingPricesSchema should have all price fields."""
        from system_a.app.api.schemas.net_metering_schemas import BillingPricesSchema

        prices = BillingPricesSchema(
            price_offpeak_import=50.0,
            price_peak_import=60.0,
            price_offpeak_settlement=22.0,
            price_peak_settlement=22.0,
            fixed_charge_per_billing_month=1000.0,
        )

        assert prices.price_offpeak_import == 50.0
        assert prices.price_peak_import == 60.0
        assert prices.price_offpeak_settlement == 22.0
        assert prices.fixed_charge_per_billing_month == 1000.0

    def test_billing_config_create_schema(self):
        """BillingConfigCreate should have all required fields."""
        from system_a.app.api.schemas.net_metering_schemas import (
            BillingConfigCreate,
            BillingPricesSchema,
        )

        config = BillingConfigCreate(
            site_id=SITE_ID,
            anchor_day=16,
            prices=BillingPricesSchema(
                price_offpeak_import=50.0,
                price_peak_import=60.0,
                price_offpeak_settlement=22.0,
                price_peak_settlement=22.0,
                fixed_charge_per_billing_month=1000.0,
            ),
        )

        assert config.site_id == SITE_ID
        assert config.anchor_day == 16
        assert config.net_metering_enabled is True

    def test_billing_config_anchor_day_validation(self):
        """BillingConfigCreate should validate anchor day range 1-28."""
        from system_a.app.api.schemas.net_metering_schemas import (
            BillingConfigCreate,
            BillingPricesSchema,
        )
        from pydantic import ValidationError

        prices = BillingPricesSchema(
            price_offpeak_import=50.0,
            price_peak_import=60.0,
            price_offpeak_settlement=22.0,
            price_peak_settlement=22.0,
            fixed_charge_per_billing_month=1000.0,
        )

        # Valid anchor days
        for day in [1, 15, 28]:
            config = BillingConfigCreate(site_id=SITE_ID, anchor_day=day, prices=prices)
            assert config.anchor_day == day

        # Invalid anchor days
        with pytest.raises(ValidationError):
            BillingConfigCreate(site_id=SITE_ID, anchor_day=0, prices=prices)

        with pytest.raises(ValidationError):
            BillingConfigCreate(site_id=SITE_ID, anchor_day=29, prices=prices)


class TestRunningBillSchemas:
    """Tests for running bill response schemas."""

    def test_running_bill_response_schema(self):
        """RunningBillResponse should have all required fields."""
        from system_a.app.api.schemas.net_metering_schemas import RunningBillResponse

        response = RunningBillResponse(
            site_id=SITE_ID,
            date=date.today(),
            billing_month_id=MONTH_ID,
            billing_period_start=date(2026, 1, 16),
            billing_period_end=date(2026, 2, 15),
            days_elapsed=14,
            total_days_in_month=31,
            progress_percent=45.2,
            import_off_kwh=150.0,
            export_off_kwh=80.0,
            import_peak_kwh=50.0,
            export_peak_kwh=20.0,
            solar_generation_kwh=200.0,
            load_consumption_kwh=180.0,
            net_import_off_kwh=70.0,
            net_import_peak_kwh=30.0,
            credits_off_cycle_kwh_balance=25.0,
            credits_peak_cycle_kwh_balance=10.0,
            bill_off_energy_rs=3500.0,
            bill_peak_energy_rs=1800.0,
            fixed_prorated_rs=450.0,
            expected_cycle_credit_rs=550.0,
            bill_raw_rs_to_date=5750.0,
            bill_credit_balance_rs_to_date=550.0,
            bill_final_rs_to_date=5200.0,
            surplus_deficit_flag="DEFICIT",
            net_kwh_position=-50.0,
            generated_at=datetime.now(timezone.utc),
        )

        assert response.site_id == SITE_ID
        assert response.days_elapsed == 14
        assert response.progress_percent == 45.2
        assert response.surplus_deficit_flag == "DEFICIT"

    def test_surplus_deficit_flag_values(self):
        """surplus_deficit_flag should be SURPLUS, DEFICIT, or NEUTRAL."""
        from system_a.app.api.schemas.net_metering_schemas import RunningBillResponse

        # Test all valid values
        for flag in ["SURPLUS", "DEFICIT", "NEUTRAL"]:
            response = RunningBillResponse(
                site_id=SITE_ID,
                date=date.today(),
                billing_month_id=None,
                billing_period_start=date.today(),
                billing_period_end=date.today(),
                days_elapsed=0,
                total_days_in_month=30,
                progress_percent=0,
                import_off_kwh=0,
                export_off_kwh=0,
                import_peak_kwh=0,
                export_peak_kwh=0,
                solar_generation_kwh=0,
                load_consumption_kwh=0,
                net_import_off_kwh=0,
                net_import_peak_kwh=0,
                credits_off_cycle_kwh_balance=0,
                credits_peak_cycle_kwh_balance=0,
                bill_off_energy_rs=0,
                bill_peak_energy_rs=0,
                fixed_prorated_rs=0,
                expected_cycle_credit_rs=0,
                bill_raw_rs_to_date=0,
                bill_credit_balance_rs_to_date=0,
                bill_final_rs_to_date=0,
                surplus_deficit_flag=flag,
                net_kwh_position=0,
                generated_at=datetime.now(timezone.utc),
            )
            assert response.surplus_deficit_flag == flag


class TestDailySnapshotSchemas:
    """Tests for daily snapshot schemas."""

    def test_daily_snapshot_response_schema(self):
        """DailySnapshotResponse should have all required fields."""
        from system_a.app.api.schemas.net_metering_schemas import DailySnapshotResponse

        snapshot = DailySnapshotResponse(
            id=uuid4(),
            site_id=SITE_ID,
            date=date.today(),
            billing_month_id=MONTH_ID,
            import_off_kwh=25.0,
            export_off_kwh=15.0,
            import_peak_kwh=8.0,
            export_peak_kwh=3.0,
            solar_generation_kwh=35.0,
            load_consumption_kwh=30.0,
            bill_final_rs_to_date=1500.0,
            surplus_deficit_flag="SURPLUS",
            net_kwh_position=5.0,
            generated_at=datetime.now(timezone.utc),
        )

        assert snapshot.site_id == SITE_ID
        assert snapshot.import_off_kwh == 25.0
        assert snapshot.solar_generation_kwh == 35.0


class TestBillingMonthSchemas:
    """Tests for billing month schemas."""

    def test_billing_month_response_schema(self):
        """BillingMonthResponse should have all required fields."""
        from system_a.app.api.schemas.net_metering_schemas import BillingMonthResponse

        month = BillingMonthResponse(
            id=MONTH_ID,
            site_id=SITE_ID,
            billing_cycle_id=CYCLE_ID,
            billing_month_number=1,
            year=2026,
            period_start_date=date(2026, 1, 16),
            period_end_date=date(2026, 2, 15),
            import_off_kwh=500.0,
            export_off_kwh=300.0,
            import_peak_kwh=150.0,
            export_peak_kwh=80.0,
            solar_generation_kwh=600.0,
            load_consumption_kwh=550.0,
            net_import_off_kwh=200.0,
            net_import_peak_kwh=70.0,
            credits_applied_off_kwh=50.0,
            credits_applied_peak_kwh=20.0,
            credits_generated_off_kwh=100.0,
            credits_generated_peak_kwh=30.0,
            bill_off_energy_rs=10000.0,
            bill_peak_energy_rs=4200.0,
            bill_fixed_rs=1000.0,
            cycle_settlement_off_rs=0.0,
            cycle_settlement_peak_rs=0.0,
            bill_raw_rs=15200.0,
            opening_credit_balance_rs=0.0,
            closing_credit_balance_rs=0.0,
            bill_final_rs=15200.0,
            status="finalized",
            is_cycle_end_month=False,
            finalized_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )

        assert month.site_id == SITE_ID
        assert month.billing_month_number == 1
        assert month.bill_final_rs == 15200.0
        assert month.status == "finalized"


class TestBillingCycleSchemas:
    """Tests for billing cycle (3-month) schemas."""

    def test_billing_cycle_response_schema(self):
        """BillingCycleResponse should have all required fields."""
        from system_a.app.api.schemas.net_metering_schemas import BillingCycleResponse

        cycle = BillingCycleResponse(
            id=CYCLE_ID,
            site_id=SITE_ID,
            cycle_number=1,
            year=2026,
            cycle_start_date=date(2026, 1, 16),
            cycle_end_date=date(2026, 4, 15),
            opening_credit_off_kwh=0.0,
            opening_credit_peak_kwh=0.0,
            opening_cash_credit_rs=0.0,
            total_import_off_kwh=1500.0,
            total_export_off_kwh=900.0,
            total_import_peak_kwh=450.0,
            total_export_peak_kwh=240.0,
            credits_generated_off_kwh=300.0,
            credits_consumed_off_kwh=200.0,
            credits_generated_peak_kwh=100.0,
            credits_consumed_peak_kwh=80.0,
            closing_credit_off_kwh=100.0,
            closing_credit_peak_kwh=20.0,
            settlement_off_rs=2200.0,
            settlement_peak_rs=440.0,
            total_settlement_rs=2640.0,
            closing_cash_credit_rs=2640.0,
            status="closed",
            finalized_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )

        assert cycle.site_id == SITE_ID
        assert cycle.cycle_number == 1
        assert cycle.total_settlement_rs == 2640.0
        assert cycle.status == "closed"


class TestBillingSummarySchemas:
    """Tests for billing summary schemas."""

    def test_billing_summary_response_schema(self):
        """BillingSummaryResponse should have all required fields."""
        from system_a.app.api.schemas.net_metering_schemas import BillingSummaryResponse

        summary = BillingSummaryResponse(
            billing_month=1,
            year=2026,
            billing_period_start=date(2026, 1, 16),
            billing_period_end=date(2026, 2, 15),
            import_off_kwh=200.0,
            import_peak_kwh=60.0,
            export_off_kwh=120.0,
            export_peak_kwh=40.0,
            fixed_charge=1000.0,
            bill_amount=5500.0,
            credit_balance=800.0,
            days_elapsed=15,
            days_remaining=16,
            progress_percent=48.4,
        )

        assert summary.billing_month == 1
        assert summary.bill_amount == 5500.0
        assert summary.progress_percent == 48.4


class TestBillingTrendSchemas:
    """Tests for billing trend schemas."""

    def test_billing_trend_item_schema(self):
        """BillingTrendItem should have all required fields."""
        from system_a.app.api.schemas.net_metering_schemas import BillingTrendItem

        item = BillingTrendItem(
            year=2026,
            month=1,
            period_start="2026-01-16",
            period_end="2026-02-15",
            import_off_kwh=500.0,
            import_peak_kwh=150.0,
            export_off_kwh=300.0,
            export_peak_kwh=80.0,
            bill_final_rs=12500.0,
            status="finalized",
        )

        assert item.year == 2026
        assert item.month == 1
        assert item.bill_final_rs == 12500.0

    def test_billing_trend_response_schema(self):
        """BillingTrendResponse should contain trend items."""
        from system_a.app.api.schemas.net_metering_schemas import (
            BillingTrendResponse,
            BillingTrendItem,
        )

        response = BillingTrendResponse(
            trend=[
                BillingTrendItem(
                    year=2026,
                    month=1,
                    period_start="2026-01-16",
                    period_end="2026-02-15",
                    import_off_kwh=500.0,
                    import_peak_kwh=150.0,
                    export_off_kwh=300.0,
                    export_peak_kwh=80.0,
                    bill_final_rs=12500.0,
                    status="finalized",
                ),
            ],
            months=1,
        )

        assert len(response.trend) == 1
        assert response.months == 1


class TestCapacityStatusSchemas:
    """Tests for capacity analysis schemas."""

    def test_capacity_status_response_schema(self):
        """CapacityStatusResponse should have all required fields."""
        from system_a.app.api.schemas.net_metering_schemas import CapacityStatusResponse

        status = CapacityStatusResponse(
            site_id=SITE_ID,
            installed_kw=10.0,
            required_kw_for_zero_bill=12.5,
            deficit_kw=2.5,
            status="under-capacity",
            annual_bill_rs=45000.0,
            annual_import_kwh=3000.0,
            annual_export_kwh=1800.0,
            annual_solar_kwh=4500.0,
            months_with_positive_bill=10,
        )

        assert status.installed_kw == 10.0
        assert status.deficit_kw == 2.5
        assert status.status == "under-capacity"
        assert status.months_with_positive_bill == 10

    def test_capacity_status_values(self):
        """Capacity status should be under-capacity, over-capacity, or balanced."""
        from system_a.app.api.schemas.net_metering_schemas import CapacityStatusResponse

        for status_value in ["under-capacity", "over-capacity", "balanced"]:
            status = CapacityStatusResponse(
                site_id=SITE_ID,
                installed_kw=10.0,
                required_kw_for_zero_bill=10.0,
                deficit_kw=0.0,
                status=status_value,
                annual_bill_rs=0.0,
                annual_import_kwh=0.0,
                annual_export_kwh=0.0,
                annual_solar_kwh=0.0,
                months_with_positive_bill=0,
            )
            assert status.status == status_value


class TestAdminSchemas:
    """Tests for admin operation schemas."""

    def test_force_cycle_close_request_schema(self):
        """ForceCycleCloseRequest should require cycle_id."""
        from system_a.app.api.schemas.net_metering_schemas import ForceCycleCloseRequest

        request = ForceCycleCloseRequest(cycle_id=CYCLE_ID)
        assert request.cycle_id == CYCLE_ID

    def test_force_cycle_close_response_schema(self):
        """ForceCycleCloseResponse should have success and settlement info."""
        from system_a.app.api.schemas.net_metering_schemas import ForceCycleCloseResponse

        response = ForceCycleCloseResponse(
            success=True,
            cycle_id=CYCLE_ID,
            settlement_total_rs=2640.0,
            message="Cycle closed successfully",
        )

        assert response.success is True
        assert response.settlement_total_rs == 2640.0

    def test_backfill_request_schema(self):
        """BackfillRequest should have site_id and date range."""
        from system_a.app.api.schemas.net_metering_schemas import BackfillRequest

        request = BackfillRequest(
            site_id=SITE_ID,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        assert request.site_id == SITE_ID
        assert request.start_date == date(2026, 1, 1)
        assert request.end_date == date(2026, 1, 31)

    def test_backfill_response_schema(self):
        """BackfillResponse should have processing stats."""
        from system_a.app.api.schemas.net_metering_schemas import BackfillResponse

        response = BackfillResponse(
            site_id=SITE_ID,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            days_processed=31,
            days_successful=30,
            days_failed=1,
        )

        assert response.days_processed == 31
        assert response.days_successful == 30
        assert response.days_failed == 1


class TestDomainEntities:
    """Tests for net metering domain entities."""

    def test_credit_pool_apply_credits(self):
        """CreditPool.apply_credits should correctly apply credits to import."""
        from system_a.app.domain.entities.net_metering import CreditPool

        # Credits fully cover import
        pool = CreditPool(credits_kwh=Decimal("100"))
        new_pool, net_import = pool.apply_credits(Decimal("80"))

        assert new_pool.credits_kwh == Decimal("20")
        assert net_import == Decimal("0")

        # Credits partially cover import
        pool = CreditPool(credits_kwh=Decimal("50"))
        new_pool, net_import = pool.apply_credits(Decimal("80"))

        assert new_pool.credits_kwh == Decimal("0")
        assert net_import == Decimal("30")

    def test_credit_pool_add_credits(self):
        """CreditPool.add_credits should correctly add new credits."""
        from system_a.app.domain.entities.net_metering import CreditPool

        pool = CreditPool(credits_kwh=Decimal("50"))
        new_pool = pool.add_credits(Decimal("30"))

        assert new_pool.credits_kwh == Decimal("80")

    def test_tou_window_contains_hour(self):
        """TouWindow.contains_hour should correctly identify peak hours."""
        from system_a.app.domain.entities.net_metering import TouWindow

        # Standard window 17:00-22:00
        window = TouWindow(start_hour=17, end_hour=22)

        assert window.contains_hour(17) is True
        assert window.contains_hour(19) is True
        assert window.contains_hour(21) is True
        assert window.contains_hour(22) is False  # end is exclusive
        assert window.contains_hour(16) is False
        assert window.contains_hour(23) is False

    def test_tou_window_spans_midnight(self):
        """TouWindow.contains_hour should handle windows spanning midnight."""
        from system_a.app.domain.entities.net_metering import TouWindow

        # Window spanning midnight 22:00-06:00
        window = TouWindow(start_hour=22, end_hour=6)

        assert window.contains_hour(22) is True
        assert window.contains_hour(23) is True
        assert window.contains_hour(0) is True
        assert window.contains_hour(5) is True
        assert window.contains_hour(6) is False
        assert window.contains_hour(12) is False
        assert window.contains_hour(21) is False

    def test_tou_config_is_peak_hour(self):
        """TouConfig.is_peak_hour should check all windows."""
        from system_a.app.domain.entities.net_metering import TouConfig, TouWindow

        config = TouConfig(
            peak_windows=[
                TouWindow(start_hour=9, end_hour=11),
                TouWindow(start_hour=17, end_hour=22),
            ]
        )

        assert config.is_peak_hour(10) is True
        assert config.is_peak_hour(19) is True
        assert config.is_peak_hour(12) is False
        assert config.is_peak_hour(23) is False


class TestNetMeteringCalculator:
    """Tests for net metering calculator domain service."""

    def test_determine_tou_period_peak(self):
        """determine_tou_period should return True for peak hours."""
        from system_a.app.domain.services.net_metering_calculator import (
            NetMeteringCalculator,
        )
        from system_a.app.domain.entities.net_metering import TouConfig, TouWindow

        calculator = NetMeteringCalculator()
        config = TouConfig(peak_windows=[TouWindow(start_hour=17, end_hour=22)])
        result = calculator.determine_tou_period(19, config)

        assert result is True  # Peak hour

    def test_determine_tou_period_offpeak(self):
        """determine_tou_period should return False for off-peak hours."""
        from system_a.app.domain.services.net_metering_calculator import (
            NetMeteringCalculator,
        )
        from system_a.app.domain.entities.net_metering import TouConfig, TouWindow

        calculator = NetMeteringCalculator()
        config = TouConfig(peak_windows=[TouWindow(start_hour=17, end_hour=22)])
        result = calculator.determine_tou_period(10, config)

        assert result is False  # Off-peak hour

    def test_calculate_raw_net_import(self):
        """calculate_raw_net_import should compute net import correctly."""
        from system_a.app.domain.services.net_metering_calculator import (
            NetMeteringCalculator,
        )

        calculator = NetMeteringCalculator()

        # Net import case
        result = calculator.calculate_raw_net_import(
            import_kwh=Decimal("200"),
            export_kwh=Decimal("100"),
        )
        assert result == Decimal("100")  # 200 - 100 = 100 net import

        # Net export case
        result = calculator.calculate_raw_net_import(
            import_kwh=Decimal("50"),
            export_kwh=Decimal("150"),
        )
        assert result == Decimal("-100")  # 50 - 150 = -100 net export

    def test_apply_cycle_credits(self):
        """apply_cycle_credits should correctly apply credit pool."""
        from system_a.app.domain.services.net_metering_calculator import (
            NetMeteringCalculator,
        )
        from system_a.app.domain.entities.net_metering import CreditPool

        calculator = NetMeteringCalculator()
        credit_pool = CreditPool(credits_kwh=Decimal("50"))

        # Apply credits to net import
        net_import, new_pool, credits_applied, credits_generated = calculator.apply_cycle_credits(
            raw_net_import=Decimal("80"),
            credit_pool=credit_pool,
        )

        assert net_import == Decimal("30")  # 80 - 50 = 30 after credits
        assert new_pool.credits_kwh == Decimal("0")  # All credits used
        assert credits_applied == Decimal("50")
        assert credits_generated == Decimal("0")

    def test_apply_cycle_credits_generates_credits(self):
        """apply_cycle_credits should generate credits from net export."""
        from system_a.app.domain.services.net_metering_calculator import (
            NetMeteringCalculator,
        )
        from system_a.app.domain.entities.net_metering import CreditPool

        calculator = NetMeteringCalculator()
        credit_pool = CreditPool(credits_kwh=Decimal("10"))

        # Net export generates credits
        net_import, new_pool, credits_applied, credits_generated = calculator.apply_cycle_credits(
            raw_net_import=Decimal("-50"),  # Net export of 50
            credit_pool=credit_pool,
        )

        assert net_import == Decimal("0")  # No import
        assert new_pool.credits_kwh == Decimal("60")  # 10 + 50 = 60
        assert credits_applied == Decimal("0")
        assert credits_generated == Decimal("50")
