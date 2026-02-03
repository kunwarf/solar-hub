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
        """Test successful billing recalculation."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Mock the execute result
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([
            (uuid4(),),
            (uuid4(),),
            (uuid4(),),
        ]))
        mock_uow._session.execute.return_value = mock_result

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
        assert data["deleted_count"] == 3
        assert "regenerate them automatically" in data["message"]

        # Verify database operations
        mock_uow._session.execute.assert_called_once()
        mock_uow.commit.assert_called_once()

        # Clean up
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_recalculate_billing_no_records(self, mock_uow, mock_current_user):
        """Test recalculation when no billing records exist."""
        from fastapi.testclient import TestClient
        from system_a.app.main import app
        from system_a.app.api.dependencies import get_current_user, get_unit_of_work

        # Mock empty result
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_uow._session.execute.return_value = mock_result

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
        assert "0 billing record(s)" in data["message"]

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

        # Mock result with many records
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([
            (uuid4(),) for _ in range(10)
        ]))
        mock_uow._session.execute.return_value = mock_result

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
        assert data["deleted_count"] == 10

        # Clean up
        app.dependency_overrides.clear()


class TestBillingRecalculateSQLQuery:
    """Test that the SQL query is constructed correctly."""

    def test_sql_query_parameters(self):
        """Test that SQL query uses correct parameters."""
        from sqlalchemy import text

        # The query from the endpoint
        query = text("""
            DELETE FROM billing_simulations
            WHERE site_id = :site_id
              AND period_start >= :period_start
              AND period_end <= :period_end
            RETURNING id
        """)

        # Test that it can be bound with parameters
        params = {
            "site_id": str(SITE_ID),
            "period_start": date(2026, 1, 1),
            "period_end": date(2026, 1, 31)
        }

        # Should not raise exception
        bound_query = query.bindparams(**params)
        assert bound_query is not None

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
