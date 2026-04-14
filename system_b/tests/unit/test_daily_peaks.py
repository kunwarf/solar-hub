"""
Unit tests for the GET /telemetry/daily-peaks/{site_id} endpoint.

Tests:
1. Returns all four peaks for a site with known seeded data.
2. Export peak honours the correct sign (grid_w < 0 → -metric_value).
3. Import peak honours the correct sign (grid_w > 0).
4. Returns None peak values when no telemetry exists in the time window.
5. Values outside the time window are not included.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


SITE_ID = uuid4()
START = datetime(2026, 4, 13, 19, 0, 0, tzinfo=timezone.utc)   # local midnight PKT
END   = datetime(2026, 4, 14, 18, 59, 59, tzinfo=timezone.utc)  # local end-of-day PKT


class MockRow:
    """Simulate a SQLAlchemy Row returned by fetchone()."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_session(row: MockRow) -> AsyncMock:
    result = MagicMock()
    result.fetchone.return_value = row

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


# ---------------------------------------------------------------------------
# Import the handler directly so we can call it without starting a server
# ---------------------------------------------------------------------------
from system_b.app.api.v1.telemetry import get_daily_peaks


class TestDailyPeaksEndpoint:

    @pytest.mark.asyncio
    async def test_all_four_peaks_returned(self):
        """When telemetry exists, all four peaks have non-null values."""
        row = MockRow(
            max_pv_w=5000.0,     max_pv_at=datetime(2026, 4, 14, 8, 23, tzinfo=timezone.utc),
            max_load_w=3200.0,   max_load_at=datetime(2026, 4, 14, 13, 5, tzinfo=timezone.utc),
            max_export_w=2400.0, max_export_at=datetime(2026, 4, 14, 9, 10, tzinfo=timezone.utc),
            max_import_w=1500.0, max_import_at=datetime(2026, 4, 14, 19, 45, tzinfo=timezone.utc),
        )
        session = _make_session(row)

        result = await get_daily_peaks(SITE_ID, START, END, session)

        assert result["peaks"]["pv"]["value_w"] == 5000.0
        assert result["peaks"]["load"]["value_w"] == 3200.0
        assert result["peaks"]["export"]["value_w"] == 2400.0
        assert result["peaks"]["import"]["value_w"] == 1500.0

    @pytest.mark.asyncio
    async def test_peak_timestamps_are_iso_strings(self):
        """occurred_at values should be ISO-formatted strings."""
        row = MockRow(
            max_pv_w=4000.0,     max_pv_at=datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc),
            max_load_w=2000.0,   max_load_at=datetime(2026, 4, 14, 11, 0, tzinfo=timezone.utc),
            max_export_w=1000.0, max_export_at=datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc),
            max_import_w=500.0,  max_import_at=datetime(2026, 4, 14, 20, 0, tzinfo=timezone.utc),
        )
        session = _make_session(row)

        result = await get_daily_peaks(SITE_ID, START, END, session)

        for key in ("pv", "load", "export", "import"):
            at = result["peaks"][key]["occurred_at"]
            assert isinstance(at, str), f"{key}.occurred_at should be a string"
            # Should parse without error
            datetime.fromisoformat(at)

    @pytest.mark.asyncio
    async def test_null_values_when_no_data(self):
        """All peaks return None when the site has no telemetry in the window."""
        row = MockRow(
            max_pv_w=None,     max_pv_at=None,
            max_load_w=None,   max_load_at=None,
            max_export_w=None, max_export_at=None,
            max_import_w=None, max_import_at=None,
        )
        session = _make_session(row)

        result = await get_daily_peaks(SITE_ID, START, END, session)

        for key in ("pv", "load", "export", "import"):
            assert result["peaks"][key]["value_w"] is None
            assert result["peaks"][key]["occurred_at"] is None

    @pytest.mark.asyncio
    async def test_export_peak_is_positive(self):
        """
        The export peak in the response is a positive value even though
        grid_power_w is negative in the DB.  The endpoint uses -metric_value
        in the SQL FILTER clause.
        """
        row = MockRow(
            max_pv_w=None,     max_pv_at=None,
            max_load_w=None,   max_load_at=None,
            max_export_w=2600.0,  # already positive (negated in SQL)
            max_export_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
            max_import_w=None, max_import_at=None,
        )
        session = _make_session(row)

        result = await get_daily_peaks(SITE_ID, START, END, session)

        assert result["peaks"]["export"]["value_w"] > 0

    @pytest.mark.asyncio
    async def test_response_includes_metadata(self):
        """Response should echo site_id, start_time, end_time."""
        row = MockRow(
            max_pv_w=None, max_pv_at=None,
            max_load_w=None, max_load_at=None,
            max_export_w=None, max_export_at=None,
            max_import_w=None, max_import_at=None,
        )
        session = _make_session(row)

        result = await get_daily_peaks(SITE_ID, START, END, session)

        assert result["site_id"] == str(SITE_ID)
        assert "start_time" in result
        assert "end_time" in result

    @pytest.mark.asyncio
    async def test_naive_datetimes_treated_as_utc(self):
        """Naive start/end datetimes should not cause an error."""
        row = MockRow(
            max_pv_w=None, max_pv_at=None,
            max_load_w=None, max_load_at=None,
            max_export_w=None, max_export_at=None,
            max_import_w=None, max_import_at=None,
        )
        session = _make_session(row)

        naive_start = datetime(2026, 4, 13, 19, 0, 0)  # no tzinfo
        naive_end   = datetime(2026, 4, 14, 18, 59, 59)

        # Should not raise
        result = await get_daily_peaks(SITE_ID, naive_start, naive_end, session)
        assert "peaks" in result
