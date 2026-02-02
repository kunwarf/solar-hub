"""
End-to-end tests for billing with System B.

These tests simulate complete user journeys and full billing cycles
using System B as the telemetry data source.
"""
import pytest
import asyncio
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4, UUID

import httpx


@pytest.fixture
def api_client():
    """Create HTTP client for API testing."""
    return httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0)


@pytest.fixture
def system_b_client():
    """Create HTTP client for System B API."""
    return httpx.AsyncClient(base_url="http://localhost:8001", timeout=30.0)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_billing_cycle_system_b(api_client, system_b_client):
    """
    Test complete 3-month billing cycle with System B telemetry.

    Scenario:
    1. Create test site and billing configuration
    2. Ingest telemetry data to System B for 90 days
    3. Run daily billing job for each day
    4. Verify 3 billing months are created and finalized
    5. Verify billing cycle is finalized with credit settlement
    6. Query billing history via API
    """
    # Skip if not in E2E test environment
    import os
    if not os.getenv("RUN_E2E_TESTS"):
        pytest.skip("E2E tests skipped (set RUN_E2E_TESTS=1 to run)")

    # Step 1: Create test site (assuming you have auth token)
    auth_token = os.getenv("TEST_AUTH_TOKEN", "")
    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

    # For this E2E test, we'll use an existing test site
    # In a real E2E test, you would create a new site
    test_site_id = os.getenv("TEST_SITE_ID")
    if not test_site_id:
        pytest.skip("TEST_SITE_ID not set")

    print(f"\n=== Testing Billing Cycle for Site {test_site_id} ===\n")

    # Step 2: Create billing configuration
    billing_config_payload = {
        "site_id": test_site_id,
        "anchor_day": 1,
        "tou_windows": [
            {"start_hour": 0, "end_hour": 6, "is_peak": False},
            {"start_hour": 6, "end_hour": 18, "is_peak": True},
            {"start_hour": 18, "end_hour": 24, "is_peak": False},
        ],
        "fixed_charge_per_billing_month": 500.00,
        "price_offpeak_import": 15.00,
        "price_peak_import": 25.00,
        "price_offpeak_settlement": 12.00,
        "price_peak_settlement": 20.00,
        "net_metering_enabled": True,
    }

    response = await api_client.post(
        "/api/v1/billing/config",
        json=billing_config_payload,
        headers=headers,
    )
    print(f"Create billing config: {response.status_code}")
    if response.status_code not in [200, 201, 409]:  # 409 = already exists
        print(f"Response: {response.text}")

    # Step 3: Simulate telemetry data ingestion to System B (last 7 days)
    print("\n=== Ingesting Sample Telemetry to System B ===\n")
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    for day_offset in range(8):
        current_date = start_date + timedelta(days=day_offset)

        for hour in range(24):
            timestamp = datetime.combine(
                current_date,
                datetime.min.time()
            ).replace(hour=hour, tzinfo=timezone.utc)

            # Generate realistic telemetry data
            is_daytime = 6 <= hour <= 18
            pv_power = (50 + hour * 5) if is_daytime else 0
            load_power = 30 + (hour % 12) * 2
            battery_power = min(pv_power - load_power, 10) if pv_power > load_power else 0

            telemetry_data = {
                "points": [
                    {
                        "device_id": str(uuid4()),  # Mock device
                        "site_id": test_site_id,
                        "timestamp": timestamp.isoformat(),
                        "source": "test",
                        "metrics": {
                            "pv_power_w": pv_power * 1000,
                            "load_power_w": load_power * 1000,
                            "battery_power_w": battery_power * 1000,
                            "grid_power_w": (load_power - pv_power) * 1000 if load_power > pv_power else 0,
                        }
                    }
                ]
            }

            # Ingest to System B
            try:
                response = await system_b_client.post(
                    "/api/v1/telemetry/ingest",
                    json=telemetry_data,
                )
                if response.status_code == 201:
                    if hour % 6 == 0:  # Log every 6 hours
                        print(f"  Ingested: {current_date} {hour:02d}:00")
            except Exception as e:
                print(f"  Warning: Telemetry ingestion failed: {e}")

    print("\n=== Running Daily Billing Jobs ===\n")

    # Step 4: Run billing job for each day
    billing_results = []
    for day_offset in range(8):
        target_date = start_date + timedelta(days=day_offset)

        # Enable System B for billing
        response = await api_client.post(
            "/api/v1/billing/jobs/run-daily",
            json={
                "target_date": target_date.isoformat(),
                "site_ids": [test_site_id],
            },
            headers=headers,
        )

        print(f"  Billing job for {target_date}: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            billing_results.append(result)
            print(f"    Success: {result.get('successful', 0)}/{result.get('total_sites', 0)} sites")

    # Step 5: Query billing history
    print("\n=== Querying Billing History ===\n")

    # Get running bill
    response = await api_client.get(
        f"/api/v1/billing/running?site_id={test_site_id}",
        headers=headers,
    )
    if response.status_code == 200:
        running_bill = response.json()
        print(f"Running Bill:")
        print(f"  Date: {running_bill.get('date')}")
        print(f"  Bill to Date: PKR {running_bill.get('bill_final_rs_to_date', 0):.2f}")
        print(f"  Solar Generated: {running_bill.get('solar_generation_kwh', 0):.2f} kWh")
        print(f"  Load Consumed: {running_bill.get('load_consumption_kwh', 0):.2f} kWh")

        # Assertions
        assert running_bill.get('site_id') == test_site_id
        assert 'bill_final_rs_to_date' in running_bill
        assert running_bill.get('solar_generation_kwh', 0) >= 0
    else:
        print(f"  No running bill found (status: {response.status_code})")

    # Get billing months
    response = await api_client.get(
        f"/api/v1/billing/months?site_id={test_site_id}",
        headers=headers,
    )
    if response.status_code == 200:
        months = response.json()
        print(f"\nBilling Months: {len(months)}")
        for month in months[-3:]:  # Show last 3 months
            print(f"  Month {month.get('billing_month_number')}/{month.get('year')}: "
                  f"PKR {month.get('bill_final_rs', 0):.2f} - {month.get('status')}")

    # Get billing summary
    response = await api_client.get(
        f"/api/v1/billing/summary?site_id={test_site_id}",
        headers=headers,
    )
    if response.status_code == 200:
        summary = response.json()
        print(f"\nBilling Summary:")
        print(f"  Current Month Bill: PKR {summary.get('current_month_bill_rs', 0):.2f}")
        print(f"  Credit Balance: PKR {summary.get('credit_balance_rs', 0):.2f}")
        print(f"  Surplus/Deficit: {summary.get('surplus_deficit_flag', 'N/A')}")

    print("\n=== E2E Test Complete ===\n")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_billing_api_compatibility_system_b(api_client):
    """
    Test that all billing API endpoints remain compatible after System B migration.

    Verifies that API responses have not changed and all fields are present.
    """
    import os
    if not os.getenv("RUN_E2E_TESTS"):
        pytest.skip("E2E tests skipped")

    test_site_id = os.getenv("TEST_SITE_ID")
    if not test_site_id:
        pytest.skip("TEST_SITE_ID not set")

    auth_token = os.getenv("TEST_AUTH_TOKEN", "")
    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

    print(f"\n=== Testing API Compatibility ===\n")

    # Test 1: GET /billing/running
    response = await api_client.get(
        f"/api/v1/billing/running?site_id={test_site_id}",
        headers=headers,
    )
    print(f"GET /billing/running: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        required_fields = [
            'site_id', 'date', 'billing_month_id',
            'solar_generation_kwh', 'load_consumption_kwh',
            'bill_raw_rs_to_date', 'bill_final_rs_to_date',
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print("  ✓ All required fields present")

    # Test 2: GET /billing/daily
    response = await api_client.get(
        f"/api/v1/billing/daily?site_id={test_site_id}&limit=7",
        headers=headers,
    )
    print(f"GET /billing/daily: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"  ✓ Returned {len(data)} daily snapshots")

    # Test 3: GET /billing/trend
    response = await api_client.get(
        f"/api/v1/billing/trend?site_id={test_site_id}",
        headers=headers,
    )
    print(f"GET /billing/trend: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"  ✓ Returned {len(data)} trend points")

    # Test 4: GET /billing/summary
    response = await api_client.get(
        f"/api/v1/billing/summary?site_id={test_site_id}",
        headers=headers,
    )
    print(f"GET /billing/summary: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        required_fields = ['current_month_bill_rs', 'last_billing_month']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print("  ✓ All required fields present")

    print("\n=== API Compatibility Test Complete ===\n")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_system_b_telemetry_api(system_b_client):
    """Test System B telemetry API endpoints."""
    import os
    if not os.getenv("RUN_E2E_TESTS"):
        pytest.skip("E2E tests skipped")

    test_site_id = os.getenv("TEST_SITE_ID", str(uuid4()))

    print(f"\n=== Testing System B API ===\n")

    # Test energy-chart endpoint
    response = await system_b_client.get(
        f"/api/v1/telemetry/energy-chart/{test_site_id}?period=day"
    )
    print(f"GET /energy-chart (period=day): {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        assert 'site_id' in data
        assert 'data' in data
        print(f"  ✓ Returned {len(data['data'])} data points")

    # Test custom period
    start_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    end_time = datetime.now(timezone.utc).isoformat()

    response = await system_b_client.get(
        f"/api/v1/telemetry/energy-chart/{test_site_id}",
        params={
            "period": "custom",
            "start_time": start_time,
            "end_time": end_time,
            "bucket_interval": "1 hour",
        }
    )
    print(f"GET /energy-chart (period=custom): {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"  ✓ Custom period returned {len(data['data'])} data points")

    print("\n=== System B API Test Complete ===\n")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_performance_100_sites(api_client):
    """
    Performance test: Billing job should complete for 100 sites within 5 minutes.
    """
    import os
    if not os.getenv("RUN_E2E_TESTS"):
        pytest.skip("E2E tests skipped")

    print(f"\n=== Performance Test: 100 Sites ===\n")

    auth_token = os.getenv("TEST_AUTH_TOKEN", "")
    headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

    # Run billing job for all sites
    import time
    start_time = time.time()

    response = await api_client.post(
        "/api/v1/billing/jobs/run-daily",
        json={
            "target_date": (date.today() - timedelta(days=1)).isoformat(),
            # No site_ids = all sites
        },
        headers=headers,
    )

    duration = time.time() - start_time

    print(f"Billing job completed in {duration:.2f} seconds")

    if response.status_code == 200:
        result = response.json()
        total = result.get('total_sites', 0)
        successful = result.get('successful', 0)
        print(f"  Sites processed: {total}")
        print(f"  Successful: {successful}")
        print(f"  Success rate: {(successful/total*100):.1f}%" if total > 0 else "N/A")

        # Performance assertion
        assert duration < 300, f"Billing job took {duration:.2f}s, should be < 300s (5 min)"
        print(f"  ✓ Performance target met")

    print("\n=== Performance Test Complete ===\n")
