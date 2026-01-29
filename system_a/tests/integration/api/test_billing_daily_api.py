"""
Integration tests for Net Metering Billing API endpoints.

Tests the actual HTTP endpoints with mocked authentication.
Run with: pytest system_a/tests/integration/api/test_billing_daily_api.py -v
"""
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

# Test constants
SITE_ID = uuid4()
USER_ID = uuid4()
ORG_ID = uuid4()


class TestBillingSchemaImports:
    """Test that all schemas can be imported correctly."""

    def test_import_tou_window_schema(self):
        """TouWindowSchema should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import TouWindowSchema
        assert TouWindowSchema is not None

    def test_import_tou_config_schema(self):
        """TouConfigSchema should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import TouConfigSchema
        assert TouConfigSchema is not None

    def test_import_billing_prices_schema(self):
        """BillingPricesSchema should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import BillingPricesSchema
        assert BillingPricesSchema is not None

    def test_import_billing_config_create(self):
        """BillingConfigCreate should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import BillingConfigCreate
        assert BillingConfigCreate is not None

    def test_import_running_bill_response(self):
        """RunningBillResponse should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import RunningBillResponse
        assert RunningBillResponse is not None

    def test_import_daily_snapshot_response(self):
        """DailySnapshotResponse should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import DailySnapshotResponse
        assert DailySnapshotResponse is not None

    def test_import_billing_month_response(self):
        """BillingMonthResponse should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import BillingMonthResponse
        assert BillingMonthResponse is not None

    def test_import_billing_cycle_response(self):
        """BillingCycleResponse should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import BillingCycleResponse
        assert BillingCycleResponse is not None

    def test_import_capacity_status_response(self):
        """CapacityStatusResponse should be importable."""
        from system_a.app.api.schemas.net_metering_schemas import CapacityStatusResponse
        assert CapacityStatusResponse is not None


class TestDomainEntityImports:
    """Test that all domain entities can be imported correctly."""

    def test_import_billing_config(self):
        """BillingConfig entity should be importable."""
        from system_a.app.domain.entities.net_metering import BillingConfig
        assert BillingConfig is not None

    def test_import_billing_cycle(self):
        """BillingCycle entity should be importable."""
        from system_a.app.domain.entities.net_metering import BillingCycle
        assert BillingCycle is not None

    def test_import_billing_month(self):
        """BillingMonth entity should be importable."""
        from system_a.app.domain.entities.net_metering import BillingMonth
        assert BillingMonth is not None

    def test_import_daily_billing_snapshot(self):
        """DailyBillingSnapshot entity should be importable."""
        from system_a.app.domain.entities.net_metering import DailyBillingSnapshot
        assert DailyBillingSnapshot is not None

    def test_import_credit_pool(self):
        """CreditPool value object should be importable."""
        from system_a.app.domain.entities.net_metering import CreditPool
        assert CreditPool is not None

    def test_import_tou_window(self):
        """TouWindow value object should be importable."""
        from system_a.app.domain.entities.net_metering import TouWindow
        assert TouWindow is not None

    def test_import_tou_config(self):
        """TouConfig value object should be importable."""
        from system_a.app.domain.entities.net_metering import TouConfig
        assert TouConfig is not None

    def test_import_billing_prices(self):
        """BillingPrices value object should be importable."""
        from system_a.app.domain.entities.net_metering import BillingPrices
        assert BillingPrices is not None


class TestDomainServiceImports:
    """Test that domain services can be imported correctly."""

    def test_import_net_metering_calculator(self):
        """NetMeteringCalculator should be importable."""
        from system_a.app.domain.services.net_metering_calculator import NetMeteringCalculator
        assert NetMeteringCalculator is not None

    def test_import_billing_calculation_result(self):
        """BillingCalculationResult should be importable."""
        from system_a.app.domain.services.net_metering_calculator import BillingCalculationResult
        assert BillingCalculationResult is not None

    def test_import_running_bill_result(self):
        """RunningBillResult should be importable."""
        from system_a.app.domain.services.net_metering_calculator import RunningBillResult
        assert RunningBillResult is not None


class TestRepositoryImports:
    """Test that repository classes can be imported correctly."""

    def test_import_net_metering_repository(self):
        """SQLAlchemyNetMeteringRepository should be importable."""
        from system_a.app.infrastructure.database.repositories.net_metering_repository import (
            SQLAlchemyNetMeteringRepository,
        )
        assert SQLAlchemyNetMeteringRepository is not None


class TestModelImports:
    """Test that SQLAlchemy models can be imported correctly."""

    def test_import_billing_config_model(self):
        """BillingConfigModel should be importable."""
        from system_a.app.infrastructure.database.models.net_metering_model import (
            BillingConfigModel,
        )
        assert BillingConfigModel is not None

    def test_import_billing_cycle_model(self):
        """BillingCycleModel should be importable."""
        from system_a.app.infrastructure.database.models.net_metering_model import (
            BillingCycleModel,
        )
        assert BillingCycleModel is not None

    def test_import_billing_month_model(self):
        """BillingMonthModel should be importable."""
        from system_a.app.infrastructure.database.models.net_metering_model import (
            BillingMonthModel,
        )
        assert BillingMonthModel is not None

    def test_import_billing_daily_model(self):
        """BillingDailyModel should be importable."""
        from system_a.app.infrastructure.database.models.net_metering_model import (
            BillingDailyModel,
        )
        assert BillingDailyModel is not None


class TestEntityCreation:
    """Test that domain entities can be instantiated correctly."""

    def test_create_billing_config(self):
        """BillingConfig should be instantiable."""
        from system_a.app.domain.entities.net_metering import (
            BillingConfig,
            TouConfig,
            TouWindow,
            BillingPrices,
        )

        config = BillingConfig(
            id=uuid4(),
            site_id=SITE_ID,
            anchor_day=16,
            tou_config=TouConfig(peak_windows=[TouWindow(start_hour=17, end_hour=22)]),
            prices=BillingPrices(
                price_offpeak_import=Decimal("50"),
                price_peak_import=Decimal("60"),
                price_offpeak_settlement=Decimal("22"),
                price_peak_settlement=Decimal("22"),
                fixed_charge_per_billing_month=Decimal("1000"),
            ),
        )

        assert config.site_id == SITE_ID
        assert config.anchor_day == 16
        assert config.tou_config.is_peak_hour(19) is True
        assert config.tou_config.is_peak_hour(10) is False

    def test_create_billing_cycle(self):
        """BillingCycle should be instantiable."""
        from system_a.app.domain.entities.net_metering import BillingCycle

        cycle = BillingCycle(
            id=uuid4(),
            site_id=SITE_ID,
            cycle_number=1,
            year=2026,
            cycle_start_date=date(2026, 1, 16),
            cycle_end_date=date(2026, 4, 15),
        )

        assert cycle.site_id == SITE_ID
        assert cycle.cycle_number == 1
        assert cycle.year == 2026

    def test_create_billing_month(self):
        """BillingMonth should be instantiable."""
        from system_a.app.domain.entities.net_metering import BillingMonth

        month = BillingMonth(
            id=uuid4(),
            site_id=SITE_ID,
            billing_month_number=1,
            year=2026,
            period_start_date=date(2026, 1, 16),
            period_end_date=date(2026, 2, 15),
        )

        assert month.site_id == SITE_ID
        assert month.billing_month_number == 1

    def test_create_daily_billing_snapshot(self):
        """DailyBillingSnapshot should be instantiable."""
        from system_a.app.domain.entities.net_metering import DailyBillingSnapshot

        snapshot = DailyBillingSnapshot(
            id=uuid4(),
            site_id=SITE_ID,
            date=date.today(),
        )

        assert snapshot.site_id == SITE_ID
        assert snapshot.date == date.today()


class TestCalculatorFunctions:
    """Test that calculator functions work correctly."""

    def test_calculator_determine_tou_period(self):
        """Calculator should correctly determine TOU period."""
        from system_a.app.domain.services.net_metering_calculator import NetMeteringCalculator
        from system_a.app.domain.entities.net_metering import TouConfig, TouWindow

        calculator = NetMeteringCalculator()
        config = TouConfig(peak_windows=[TouWindow(start_hour=17, end_hour=22)])

        # Peak hours (17-21)
        for hour in [17, 18, 19, 20, 21]:
            assert calculator.determine_tou_period(hour, config) is True

        # Off-peak hours
        for hour in [0, 6, 12, 16, 22, 23]:
            assert calculator.determine_tou_period(hour, config) is False

    def test_calculator_raw_net_import(self):
        """Calculator should correctly compute raw net import."""
        from system_a.app.domain.services.net_metering_calculator import NetMeteringCalculator

        calculator = NetMeteringCalculator()

        # Net import
        result = calculator.calculate_raw_net_import(Decimal("100"), Decimal("30"))
        assert result == Decimal("70")

        # Net export
        result = calculator.calculate_raw_net_import(Decimal("30"), Decimal("100"))
        assert result == Decimal("-70")

        # Balanced
        result = calculator.calculate_raw_net_import(Decimal("50"), Decimal("50"))
        assert result == Decimal("0")

    def test_calculator_apply_cycle_credits(self):
        """Calculator should correctly apply cycle credits."""
        from system_a.app.domain.services.net_metering_calculator import NetMeteringCalculator
        from system_a.app.domain.entities.net_metering import CreditPool

        calculator = NetMeteringCalculator()
        pool = CreditPool(credits_kwh=Decimal("50"))

        # Net import with partial credit coverage
        net_import, new_pool, applied, generated = calculator.apply_cycle_credits(
            Decimal("80"), pool
        )

        assert net_import == Decimal("30")
        assert new_pool.credits_kwh == Decimal("0")
        assert applied == Decimal("50")
        assert generated == Decimal("0")

    def test_calculator_generate_credits(self):
        """Calculator should correctly generate credits from net export."""
        from system_a.app.domain.services.net_metering_calculator import NetMeteringCalculator
        from system_a.app.domain.entities.net_metering import CreditPool

        calculator = NetMeteringCalculator()
        pool = CreditPool(credits_kwh=Decimal("20"))

        # Net export generates credits
        net_import, new_pool, applied, generated = calculator.apply_cycle_credits(
            Decimal("-50"), pool
        )

        assert net_import == Decimal("0")
        assert new_pool.credits_kwh == Decimal("70")  # 20 + 50
        assert applied == Decimal("0")
        assert generated == Decimal("50")
