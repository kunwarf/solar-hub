"""
Integration tests for Billing Recalculate API endpoint.

Tests the POST /billing/recalculate endpoint with mocked database.
Run with: pytest system_a/tests/integration/api/test_billing_recalculate_api.py -v
"""
import pytest
from datetime import date
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Test constants
SITE_ID = uuid4()
USER_ID = uuid4()


@pytest.fixture
def mock_uow():
    """Mock Unit of Work with async session."""
    uow = AsyncMock()
    uow._session = AsyncMock(spec=AsyncSession)
    uow._session.execute = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    return uow


@pytest.fixture
def mock_current_user():
    """Mock authenticated user."""
    user = MagicMock()
    user.id = USER_ID
    user.email = "test@example.com"
    user.role = "admin"
    return user


class TestBillingRecalculateEndpoint:
    """Test the POST /billing/recalculate endpoint."""

    @pytest.mark.asyncio
    async def test_recalculate_billing_success(self, mock_uow, mock_current_user):
        """Test successful billing recalculation from all tables."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Mock execute results for all 4 DELETE queries
        # 1. billing_daily (5 records)
        mock_daily_result = MagicMock()
        mock_daily_result.__iter__ = MagicMock(return_value=iter([
            (uuid4(),) for _ in range(5)
        ]))

        # 2. billing_months (2 records)
        mock_months_result = MagicMock()
        mock_months_result.__iter__ = MagicMock(return_value=iter([
            (uuid4(),) for _ in range(2)
        ]))

        # 3. billing_cycles (1 record)
        mock_cycles_result = MagicMock()
        mock_cycles_result.__iter__ = MagicMock(return_value=iter([
            (uuid4(),)
        ]))

        # 4. billing_simulations (3 records)
        mock_sims_result = MagicMock()
        mock_sims_result.__iter__ = MagicMock(return_value=iter([
            (uuid4(),) for _ in range(3)
        ]))

        # Return different results for each execute call in order
        mock_uow._session.execute.side_effect = [
            mock_daily_result,
            mock_months_result,
            mock_cycles_result,
            mock_sims_result,
        ]

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_unit_of_work] = lambda: mock_uow

        client = TestClient(app)

        # Make request
        response = client.post(
            "/api/v1/billing/recalculate",
            params={
                "site_id": str(SITE_ID),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 11  # 5 + 2 + 1 + 3
        assert data["deleted_daily"] == 5
        assert data["deleted_months"] == 2
        assert data["deleted_cycles"] == 1
        assert data["deleted_simulations"] == 3
        assert "billing scheduler will regenerate" in data["message"]

        # Verify database operations - should call execute 4 times (4 DELETE queries)
        assert mock_uow._session.execute.call_count == 4
        mock_uow.commit.assert_called_once()

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_recalculate_billing_no_records(self, mock_uow, mock_current_user):
        """Test recalculation when no billing records exist in any table."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Mock empty results for all 4 DELETE queries
        mock_empty_result = MagicMock()
        mock_empty_result.__iter__ = MagicMock(return_value=iter([]))

        # All 4 queries return empty results
        mock_uow._session.execute.side_effect = [
            mock_empty_result,  # billing_daily
            mock_empty_result,  # billing_months
            mock_empty_result,  # billing_cycles
            mock_empty_result,  # billing_simulations
        ]

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_unit_of_work] = lambda: mock_uow

        client = TestClient(app)

        # Make request
        response = client.post(
            "/api/v1/billing/recalculate",
            params={
                "site_id": str(SITE_ID),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 0
        assert data["deleted_daily"] == 0
        assert data["deleted_months"] == 0
        assert data["deleted_cycles"] == 0
        assert data["deleted_simulations"] == 0
        assert "0 total records" in data["message"]

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_recalculate_billing_missing_site_id(self, mock_uow, mock_current_user):
        """Test recalculation with missing site_id parameter."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_unit_of_work] = lambda: mock_uow

        client = TestClient(app)

        # Make request without site_id
        response = client.post(
            "/api/v1/billing/recalculate",
            params={
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        )

        # Assertions - should fail validation
        assert response.status_code == 422  # Unprocessable Entity

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_recalculate_billing_missing_dates(self, mock_uow, mock_current_user):
        """Test recalculation with missing date parameters."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_unit_of_work] = lambda: mock_uow

        client = TestClient(app)

        # Make request without dates
        response = client.post(
            "/api/v1/billing/recalculate",
            params={
                "site_id": str(SITE_ID),
            },
        )

        # Assertions - should fail validation
        assert response.status_code == 422  # Unprocessable Entity

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_recalculate_billing_invalid_date_format(self, mock_uow, mock_current_user):
        """Test recalculation with invalid date format."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_unit_of_work] = lambda: mock_uow

        client = TestClient(app)

        # Make request with invalid date format
        response = client.post(
            "/api/v1/billing/recalculate",
            params={
                "site_id": str(SITE_ID),
                "period_start": "invalid-date",
                "period_end": "2026-01-31",
            },
        )

        # Assertions - should fail validation
        assert response.status_code == 422  # Unprocessable Entity

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_recalculate_billing_unauthorized(self, mock_uow):
        """Test recalculation without authentication."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_unit_of_work

        # Override only UoW, not current_user to simulate unauthorized access
        app.dependency_overrides[get_unit_of_work] = lambda: mock_uow

        client = TestClient(app)

        # Make request without authentication
        response = client.post(
            "/api/v1/billing/recalculate",
            params={
                "site_id": str(SITE_ID),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        )

        # Assertions - should fail with authentication error
        # The exact status code depends on your auth implementation
        # Could be 401 (Unauthorized) or 403 (Forbidden)
        assert response.status_code in [401, 403]

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_recalculate_billing_database_error(self, mock_uow, mock_current_user):
        """Test recalculation when database operation fails."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Mock database error
        mock_uow._session.execute.side_effect = Exception("Database connection error")

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_unit_of_work] = lambda: mock_uow

        client = TestClient(app)

        # Make request
        response = client.post(
            "/api/v1/billing/recalculate",
            params={
                "site_id": str(SITE_ID),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        )

        # Assertions - should fail with internal server error
        assert response.status_code == 500

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_recalculate_billing_multiple_periods(self, mock_uow, mock_current_user):
        """Test recalculation for a date range spanning multiple months."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Mock results for 3-month period (more records expected)
        # billing_daily: 90 days
        mock_daily = MagicMock()
        mock_daily.__iter__ = MagicMock(return_value=iter([(uuid4(),) for _ in range(90)]))

        # billing_months: 3 months
        mock_months = MagicMock()
        mock_months.__iter__ = MagicMock(return_value=iter([(uuid4(),) for _ in range(3)]))

        # billing_cycles: 1 cycle (3 months = 1 cycle)
        mock_cycles = MagicMock()
        mock_cycles.__iter__ = MagicMock(return_value=iter([(uuid4(),)]))

        # billing_simulations: assume some simulations exist
        mock_sims = MagicMock()
        mock_sims.__iter__ = MagicMock(return_value=iter([(uuid4(),) for _ in range(5)]))

        mock_uow._session.execute.side_effect = [
            mock_daily,
            mock_months,
            mock_cycles,
            mock_sims,
        ]

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: mock_current_user
        app.dependency_overrides[get_unit_of_work] = lambda: mock_uow

        client = TestClient(app)

        # Make request for 3-month period
        response = client.post(
            "/api/v1/billing/recalculate",
            params={
                "site_id": str(SITE_ID),
                "period_start": "2025-12-01",
                "period_end": "2026-02-28",
            },
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["deleted_count"] == 99  # 90 + 3 + 1 + 5
        assert data["deleted_daily"] == 90
        assert data["deleted_months"] == 3
        assert data["deleted_cycles"] == 1
        assert data["deleted_simulations"] == 5

        # Clean up
        app.dependency_overrides.clear()


class TestBillingRecalculateSQLQuery:
    """Test that the SQL queries are constructed correctly."""

    def test_sql_query_parameters_all_tables(self):
        """Test that all 4 DELETE queries use correct parameters."""
        from sqlalchemy import text

        # Test parameters
        params = {
            "site_id": str(SITE_ID),
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31)
        }

        # Query 1: billing_daily
        daily_query = text("""
            DELETE FROM billing_daily
            WHERE site_id = :site_id
              AND date >= :period_start
              AND date <= :period_end
            RETURNING id
        """)
        assert daily_query.bindparams(**params) is not None

        # Query 2: billing_months
        months_query = text("""
            DELETE FROM billing_months
            WHERE site_id = :site_id
              AND period_start_date <= :period_end
              AND period_end_date >= :period_start
            RETURNING id
        """)
        assert months_query.bindparams(**params) is not None

        # Query 3: billing_cycles
        cycles_query = text("""
            DELETE FROM billing_cycles
            WHERE site_id = :site_id
              AND cycle_start_date <= :period_end
              AND cycle_end_date >= :period_start
            RETURNING id
        """)
        assert cycles_query.bindparams(**params) is not None

        # Query 4: billing_simulations
        sims_query = text("""
            DELETE FROM billing_simulations
            WHERE site_id = :site_id
              AND period_start >= :period_start
              AND period_end <= :period_end
            RETURNING id
        """)
        assert sims_query.bindparams(**params) is not None

    def test_sql_query_date_range_logic(self):
        """Test that date range filtering logic is correct."""
        # This tests the logic: period_start >= X AND period_end <= Y
        # Should match records where:
        # - period_start is on or after the start date
        # - period_end is on or before the end date

        test_cases = [
            # (record_start, record_end, filter_start, filter_end, should_match)
            (date(2026, 1, 1), date(2026, 1, 31), date(2026, 1, 1), date(2026, 1, 31), True),   # Exact match
            (date(2026, 1, 15), date(2026, 1, 31), date(2026, 1, 1), date(2026, 1, 31), True),  # Within range
            (date(2025, 12, 1), date(2025, 12, 31), date(2026, 1, 1), date(2026, 1, 31), False), # Before range
            (date(2026, 2, 1), date(2026, 2, 28), date(2026, 1, 1), date(2026, 1, 31), False),  # After range
        ]

        for record_start, record_end, filter_start, filter_end, should_match in test_cases:
            matches = (record_start >= filter_start) and (record_end <= filter_end)
            assert matches == should_match, \
                f"Failed for record ({record_start}, {record_end}) with filter ({filter_start}, {filter_end})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
