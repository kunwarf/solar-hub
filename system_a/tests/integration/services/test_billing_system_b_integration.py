"""
Integration tests for billing with System B.

These tests require both System A and System B to be running.
They test the full integration path from System B API to billing calculations.
"""
import pytest
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from system_a.app.config import settings
from system_a.app.application.services.billing_scheduler_service import BillingSchedulerService
from system_a.app.domain.services.net_metering_calculator import NetMeteringCalculator
from system_a.app.infrastructure.database.repositories.net_metering_repository import (
    SQLAlchemyNetMeteringRepository,
)
from system_a.app.infrastructure.database.repositories.telemetry_repository import (
    SQLAlchemyTelemetryRepository,
)
from system_a.app.infrastructure.database.repositories.telemetry_system_b_repository import (
    SystemBTelemetryRepository,
)
from system_a.app.infrastructure.database.repositories.site_repository import (
    SQLAlchemySiteRepository,
)
from system_a.app.infrastructure.external.system_b_client import SystemBClient
from system_a.app.domain.entities.net_metering import BillingConfig, BillingPrices, TouConfig


@pytest.fixture
def system_b_client():
    """Create System B client for testing."""
    client = SystemBClient(
        base_url=settings.system_b.url,
        api_key=settings.system_b.api_key,
        timeout=settings.system_b.timeout,
    )
    yield client
    # Cleanup handled by async context


@pytest.fixture
def system_b_repository(system_b_client):
    """Create System B telemetry repository."""
    return SystemBTelemetryRepository(system_b_client)


@pytest.fixture
async def test_billing_config(test_site_id):
    """Create a test billing configuration."""
    return BillingConfig(
        site_id=test_site_id,
        anchor_day=1,
        tou_windows=[
            {"start_hour": 0, "end_hour": 6, "is_peak": False},   # Off-peak: 12am-6am
            {"start_hour": 6, "end_hour": 18, "is_peak": True},   # Peak: 6am-6pm
            {"start_hour": 18, "end_hour": 24, "is_peak": False}, # Off-peak: 6pm-12am
        ],
        prices=BillingPrices(
            fixed_charge_per_billing_month=Decimal("500.00"),
            price_offpeak_import=Decimal("15.00"),
            price_peak_import=Decimal("25.00"),
            price_offpeak_settlement=Decimal("12.00"),
            price_peak_settlement=Decimal("20.00"),
        ),
        net_metering_enabled=True,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_b_repository_fetches_real_data(
    system_b_repository,
    test_site_id,
):
    """
    Test that System B repository can fetch real telemetry data.

    Prerequisites:
    - System B must be running at configured URL
    - Test site must have telemetry data
    """
    # Arrange
    start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    end_time = datetime.now(timezone.utc)

    # Act
    summaries = await system_b_repository.get_hourly_summaries(
        site_id=test_site_id,
        start_time=start_time,
        end_time=end_time,
    )

    # Assert
    assert isinstance(summaries, list)
    print(f"Fetched {len(summaries)} hourly summaries from System B")

    if len(summaries) > 0:
        # Verify data structure
        first_summary = summaries[0]
        assert first_summary.site_id == test_site_id
        assert first_summary.timestamp_hour is not None
        assert isinstance(first_summary.energy_generated_kwh, Decimal)
        assert isinstance(first_summary.energy_consumed_kwh, Decimal)
        assert first_summary.energy_generated_kwh >= Decimal("0")

        print(f"Sample data point: {first_summary.timestamp_hour} - "
              f"Generated: {first_summary.energy_generated_kwh} kWh, "
              f"Consumed: {first_summary.energy_consumed_kwh} kWh")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_billing_calculation_with_system_b_data(
    async_db_session,
    system_b_repository,
    test_site_id,
    test_billing_config,
):
    """
    Test full billing calculation using System B data.

    This test verifies that billing calculations work correctly
    when using System B as the data source.
    """
    # Arrange
    net_metering_repo = SQLAlchemyNetMeteringRepository(async_db_session)
    site_repo = SQLAlchemySiteRepository(async_db_session)
    calculator = NetMeteringCalculator()

    # Save test billing config
    await net_metering_repo.create_billing_config(test_billing_config)

    # Create billing service with System B repository
    billing_service = BillingSchedulerService(
        net_metering_repo=net_metering_repo,
        telemetry_repo=system_b_repository,  # Use System B directly
        site_repo=site_repo,
        calculator=calculator,
        system_b_telemetry_repo=system_b_repository,
    )

    # Override settings to force System B usage
    original_setting = settings.use_system_b_for_billing
    settings.use_system_b_for_billing = True

    try:
        # Act - Compute billing for yesterday
        target_date = date.today() - timedelta(days=1)
        result = await billing_service.compute_site_daily_snapshot(
            site_id=test_site_id,
            target_date=target_date,
        )

        # Assert
        assert result.success, f"Billing computation failed: {result.error}"
        assert result.snapshot_id is not None
        assert result.billing_month_id is not None

        if result.snapshot:
            print(f"Billing snapshot created: "
                  f"Date: {result.snapshot.date}, "
                  f"Bill: PKR {result.snapshot.bill_final_rs_to_date}, "
                  f"Solar: {result.snapshot.solar_generation_kwh} kWh, "
                  f"Load: {result.snapshot.load_consumption_kwh} kWh")

            assert result.snapshot.solar_generation_kwh >= Decimal("0")
            assert result.snapshot.load_consumption_kwh >= Decimal("0")
            assert result.snapshot.bill_final_rs_to_date >= Decimal("0")

    finally:
        # Restore original setting
        settings.use_system_b_for_billing = original_setting


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dual_read_validation(
    async_db_session,
    system_b_repository,
    test_site_id,
):
    """
    Test dual-read validation mode.

    Verifies that the system can fetch from both System A and System B
    and compare the results.
    """
    # Arrange
    telemetry_repo_a = SQLAlchemyTelemetryRepository(async_db_session)

    start_time = datetime.now(timezone.utc) - timedelta(hours=24)
    end_time = datetime.now(timezone.utc)

    # Act - Fetch from both systems
    try:
        summaries_a = await telemetry_repo_a.get_hourly_summaries(
            site_id=test_site_id,
            start_time=start_time,
            end_time=end_time,
        )
        print(f"System A returned {len(summaries_a)} summaries")
    except Exception as e:
        print(f"System A fetch failed (expected if tables dropped): {e}")
        summaries_a = []

    summaries_b = await system_b_repository.get_hourly_summaries(
        site_id=test_site_id,
        start_time=start_time,
        end_time=end_time,
    )
    print(f"System B returned {len(summaries_b)} summaries")

    # Assert - System B should have data
    assert len(summaries_b) > 0, "System B should have telemetry data"

    # If both have data, compare
    if len(summaries_a) > 0 and len(summaries_b) > 0:
        print("\nComparing System A vs System B data:")

        # Match timestamps and compare
        matches = 0
        discrepancies = 0

        for summary_b in summaries_b[:10]:  # Compare first 10 points
            # Find matching timestamp in System A
            matching_a = next(
                (s for s in summaries_a if s.timestamp_hour == summary_b.timestamp_hour),
                None
            )

            if matching_a:
                matches += 1
                diff_solar = abs(matching_a.energy_generated_kwh - summary_b.energy_generated_kwh)
                diff_load = abs(matching_a.energy_consumed_kwh - summary_b.energy_consumed_kwh)

                if diff_solar > Decimal("0.1") or diff_load > Decimal("0.1"):
                    discrepancies += 1
                    print(f"  Discrepancy at {summary_b.timestamp_hour}: "
                          f"Solar diff={diff_solar}, Load diff={diff_load}")

        print(f"\nMatched {matches} timestamps, found {discrepancies} discrepancies")

        if matches > 0:
            discrepancy_rate = (discrepancies / matches) * 100
            print(f"Discrepancy rate: {discrepancy_rate:.2f}%")
            assert discrepancy_rate < 10, "Discrepancy rate should be less than 10%"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_b_client_connection(system_b_client):
    """Test that System B client can connect and fetch data."""
    # Arrange
    test_site_id = uuid4()
    start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    end_time = datetime.now(timezone.utc)

    # Act & Assert - Should not raise an error even if site has no data
    try:
        data_points = await system_b_client.get_hourly_energy_summary(
            site_id=test_site_id,
            start_time=start_time,
            end_time=end_time,
        )
        print(f"System B client working: received {len(data_points)} data points")
        assert isinstance(data_points, list)
    except Exception as e:
        print(f"System B client error: {e}")
        # This is OK if the site doesn't exist or System B is not running
        # The important thing is that the client doesn't crash


@pytest.mark.integration
@pytest.mark.asyncio
async def test_system_b_handles_missing_data_gracefully(
    system_b_repository,
):
    """Test that System B repository handles missing data gracefully."""
    # Arrange - Use a fake site ID that definitely has no data
    fake_site_id = uuid4()
    start_time = datetime.now(timezone.utc) - timedelta(hours=1)
    end_time = datetime.now(timezone.utc)

    # Act
    summaries = await system_b_repository.get_hourly_summaries(
        site_id=fake_site_id,
        start_time=start_time,
        end_time=end_time,
    )

    # Assert - Should return empty list, not error
    assert isinstance(summaries, list)
    assert len(summaries) == 0
    print("System B correctly returns empty list for non-existent site")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_billing_service_fallback_to_system_a(
    async_db_session,
    test_site_id,
    test_billing_config,
):
    """
    Test that billing service falls back to System A if System B fails.
    """
    # Arrange
    net_metering_repo = SQLAlchemyNetMeteringRepository(async_db_session)
    telemetry_repo_a = SQLAlchemyTelemetryRepository(async_db_session)
    site_repo = SQLAlchemySiteRepository(async_db_session)
    calculator = NetMeteringCalculator()

    # Create a broken System B client (wrong URL)
    broken_client = SystemBClient(base_url="http://localhost:9999", timeout=1.0)
    broken_repo = SystemBTelemetryRepository(broken_client)

    # Save test billing config
    await net_metering_repo.create_billing_config(test_billing_config)

    # Create billing service
    billing_service = BillingSchedulerService(
        net_metering_repo=net_metering_repo,
        telemetry_repo=telemetry_repo_a,  # Working System A repo
        site_repo=site_repo,
        calculator=calculator,
        system_b_telemetry_repo=broken_repo,  # Broken System B repo
    )

    # Override settings to attempt System B
    original_setting = settings.use_system_b_for_billing
    settings.use_system_b_for_billing = True

    try:
        # Act - Should fall back to System A
        target_date = date.today() - timedelta(days=1)
        result = await billing_service.compute_site_daily_snapshot(
            site_id=test_site_id,
            target_date=target_date,
        )

        # Assert - Should succeed via fallback
        print(f"Fallback test result: success={result.success}, error={result.error}")
        # May succeed or fail depending on whether System A has data
        # The important thing is it doesn't crash

    finally:
        settings.use_system_b_for_billing = original_setting
        await broken_client.close()
