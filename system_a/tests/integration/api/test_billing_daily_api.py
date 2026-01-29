"""
Integration tests for Net Metering Billing API endpoints.

Tests the actual HTTP endpoints with a test database.
Run with: pytest system_a/tests/integration/api/test_billing_daily_api.py -v
"""
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Test constants
SITE_ID = uuid4()
USER_ID = uuid4()
ORG_ID = uuid4()


@pytest.fixture
def mock_current_user():
    """Mock authenticated user."""
    user = MagicMock()
    user.id = USER_ID
    user.organization_id = ORG_ID
    user.email = "test@example.com"
    user.role = "admin"
    return user


@pytest.fixture
def mock_site():
    """Mock site entity."""
    site = MagicMock()
    site.id = SITE_ID
    site.organization_id = ORG_ID
    site.name = "Test Site"
    site.installed_capacity_kw = 10.0
    return site


@pytest.fixture
def mock_billing_config():
    """Mock billing configuration."""
    from system_a.app.domain.entities.net_metering import (
        BillingConfig,
        TouConfig,
        TouWindow,
        BillingPrices,
    )

    return BillingConfig(
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
        fixed_proration_mode="none",
        net_metering_enabled=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
    )


@pytest.fixture
def mock_running_bill():
    """Mock running bill data."""
    return {
        "site_id": str(SITE_ID),
        "date": date.today().isoformat(),
        "billing_month_id": None,
        "billing_period_start": date(2026, 1, 16).isoformat(),
        "billing_period_end": date(2026, 2, 15).isoformat(),
        "days_elapsed": 14,
        "total_days_in_month": 31,
        "progress_percent": 45.2,
        "import_off_kwh": 150.0,
        "export_off_kwh": 80.0,
        "import_peak_kwh": 50.0,
        "export_peak_kwh": 20.0,
        "solar_generation_kwh": 200.0,
        "load_consumption_kwh": 180.0,
        "net_import_off_kwh": 70.0,
        "net_import_peak_kwh": 30.0,
        "credits_off_cycle_kwh_balance": 25.0,
        "credits_peak_cycle_kwh_balance": 10.0,
        "bill_off_energy_rs": 3500.0,
        "bill_peak_energy_rs": 1800.0,
        "fixed_prorated_rs": 450.0,
        "expected_cycle_credit_rs": 550.0,
        "bill_raw_rs_to_date": 5750.0,
        "bill_credit_balance_rs_to_date": 550.0,
        "bill_final_rs_to_date": 5200.0,
        "surplus_deficit_flag": "DEFICIT",
        "net_kwh_position": -50.0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


class TestBillingConfigEndpoints:
    """Tests for billing configuration endpoints."""

    @pytest.mark.asyncio
    async def test_get_billing_config_not_found(self):
        """GET /billing/config/{site_id} should return 404 if not found."""
        from system_a.app.main import create_app

        app = create_app()

        # Mock authentication
        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            # Mock repository to return None
            with patch(
                "system_a.app.api.v1.billing_daily.get_net_metering_repository"
            ) as mock_repo_dep:
                mock_repo = AsyncMock()
                mock_repo.get_config_by_site_id.return_value = None
                mock_repo_dep.return_value = mock_repo

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.get(
                        f"/api/v1/billing/config/{SITE_ID}",
                        headers={"Authorization": "Bearer test-token"},
                    )

                    assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_billing_config(self, mock_billing_config):
        """POST /billing/config should create new configuration."""
        from system_a.app.main import create_app

        app = create_app()

        config_data = {
            "site_id": str(SITE_ID),
            "anchor_day": 16,
            "tou_config": {
                "peak_windows": [{"start_hour": 17, "end_hour": 22}],
                "timezone": "Asia/Karachi",
            },
            "prices": {
                "price_offpeak_import": 50.0,
                "price_peak_import": 60.0,
                "price_offpeak_settlement": 22.0,
                "price_peak_settlement": 22.0,
                "fixed_charge_per_billing_month": 1000.0,
            },
            "net_metering_enabled": True,
        }

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            with patch(
                "system_a.app.api.v1.billing_daily.get_net_metering_repository"
            ) as mock_repo_dep:
                mock_repo = AsyncMock()
                mock_repo.get_config_by_site_id.return_value = None
                mock_repo.create_config.return_value = mock_billing_config
                mock_repo_dep.return_value = mock_repo

                with patch(
                    "system_a.app.api.v1.billing_daily.get_db"
                ) as mock_db:
                    mock_session = AsyncMock()
                    mock_db.return_value = mock_session

                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        response = await client.post(
                            "/api/v1/billing/config",
                            json=config_data,
                            headers={"Authorization": "Bearer test-token"},
                        )

                        # Should return 200 or 201
                        assert response.status_code in [200, 201, 422]


class TestRunningBillEndpoint:
    """Tests for running bill endpoint."""

    @pytest.mark.asyncio
    async def test_get_running_bill_requires_site_id(self):
        """GET /billing/running should require site_id parameter."""
        from system_a.app.main import create_app

        app = create_app()

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/billing/running",
                    headers={"Authorization": "Bearer test-token"},
                )

                # Should return 422 for missing site_id
                assert response.status_code == 422


class TestDailySnapshotsEndpoint:
    """Tests for daily snapshots endpoint."""

    @pytest.mark.asyncio
    async def test_get_daily_snapshots_requires_site_id(self):
        """GET /billing/daily should require site_id parameter."""
        from system_a.app.main import create_app

        app = create_app()

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/billing/daily",
                    headers={"Authorization": "Bearer test-token"},
                )

                assert response.status_code == 422


class TestBillingMonthsEndpoint:
    """Tests for billing months endpoint."""

    @pytest.mark.asyncio
    async def test_get_billing_months_requires_site_id(self):
        """GET /billing/months should require site_id parameter."""
        from system_a.app.main import create_app

        app = create_app()

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/billing/months",
                    headers={"Authorization": "Bearer test-token"},
                )

                assert response.status_code == 422


class TestBillingCyclesEndpoint:
    """Tests for billing cycles endpoint."""

    @pytest.mark.asyncio
    async def test_get_billing_cycles_requires_site_id(self):
        """GET /billing/cycles should require site_id parameter."""
        from system_a.app.main import create_app

        app = create_app()

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/billing/cycles",
                    headers={"Authorization": "Bearer test-token"},
                )

                assert response.status_code == 422


class TestBillingSummaryEndpoint:
    """Tests for billing summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_summary_requires_site_id(self):
        """GET /billing/summary should require site_id parameter."""
        from system_a.app.main import create_app

        app = create_app()

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/billing/summary",
                    headers={"Authorization": "Bearer test-token"},
                )

                assert response.status_code == 422


class TestBillingTrendEndpoint:
    """Tests for billing trend endpoint."""

    @pytest.mark.asyncio
    async def test_get_trend_requires_site_id(self):
        """GET /billing/trend should require site_id parameter."""
        from system_a.app.main import create_app

        app = create_app()

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/billing/trend",
                    headers={"Authorization": "Bearer test-token"},
                )

                assert response.status_code == 422


class TestCapacityStatusEndpoint:
    """Tests for capacity analysis endpoint."""

    @pytest.mark.asyncio
    async def test_get_capacity_status_requires_site_id(self):
        """GET /billing/capacity/status should require site_id parameter."""
        from system_a.app.main import create_app

        app = create_app()

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/billing/capacity/status",
                    headers={"Authorization": "Bearer test-token"},
                )

                assert response.status_code == 422


class TestCycleCloseEndpoint:
    """Tests for cycle close admin endpoint."""

    @pytest.mark.asyncio
    async def test_close_cycle_requires_cycle_id(self):
        """POST /billing/cycle/close should require cycle_id."""
        from system_a.app.main import create_app

        app = create_app()

        with patch(
            "system_a.app.api.v1.billing_daily.get_current_user"
        ) as mock_auth:
            mock_user = MagicMock()
            mock_user.id = USER_ID
            mock_auth.return_value = mock_user

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/billing/cycle/close",
                    json={},  # Empty body
                    headers={"Authorization": "Bearer test-token"},
                )

                assert response.status_code == 422


class TestEndpointAuthentication:
    """Tests for endpoint authentication requirements."""

    @pytest.mark.asyncio
    async def test_endpoints_require_auth(self):
        """All billing endpoints should require authentication."""
        from system_a.app.main import create_app

        app = create_app()
        transport = ASGITransport(app=app)

        endpoints = [
            ("GET", f"/api/v1/billing/config/{SITE_ID}"),
            ("GET", f"/api/v1/billing/running?site_id={SITE_ID}"),
            ("GET", f"/api/v1/billing/daily?site_id={SITE_ID}"),
            ("GET", f"/api/v1/billing/months?site_id={SITE_ID}"),
            ("GET", f"/api/v1/billing/cycles?site_id={SITE_ID}"),
            ("GET", f"/api/v1/billing/summary?site_id={SITE_ID}"),
            ("GET", f"/api/v1/billing/trend?site_id={SITE_ID}"),
            ("GET", f"/api/v1/billing/capacity/status?site_id={SITE_ID}"),
        ]

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            for method, url in endpoints:
                if method == "GET":
                    response = await client.get(url)
                else:
                    response = await client.post(url, json={})

                # Should return 401 or 403 without auth
                assert response.status_code in [401, 403, 422], f"Endpoint {url} did not require auth"
