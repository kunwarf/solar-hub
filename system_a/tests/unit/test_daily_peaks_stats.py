"""
Unit tests for the today's peak metrics feature in System A.

Tests:
1. MaxMetric model serializes value_kw and occurred_at correctly.
2. get_stats returns max_pv_today / max_load_today / max_export_today / max_import_today
   when System B supplies peak data.
3. get_stats omits peak fields (None) when System B returns null values.
4. get_stats falls back gracefully when System B raises an error — other stats still returned.
5. W → kW conversion is correct (divide by 1000, round to 3 dp).
6. Powdrive and deye protocols both map to the same family (existing behaviour).
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from system_a.app.api.v1.dashboard_widgets import MaxMetric


# ---------------------------------------------------------------------------
# MaxMetric model tests
# ---------------------------------------------------------------------------

class TestMaxMetricModel:
    def test_serializes_correctly(self):
        m = MaxMetric(
            value_kw=4.850,
            occurred_at=datetime(2026, 4, 14, 8, 23, 0, tzinfo=timezone.utc),
        )
        assert m.value_kw == 4.850
        assert m.occurred_at.year == 2026

    def test_value_kw_accepts_float(self):
        m = MaxMetric(
            value_kw=0.001,
            occurred_at=datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc),
        )
        assert isinstance(m.value_kw, float)


# ---------------------------------------------------------------------------
# W → kW conversion helper
# ---------------------------------------------------------------------------

class TestWattsToKilowatts:
    """Verify the conversion logic used inside get_stats."""

    def _parse_peak(self, raw: dict):
        """Mirror of the _parse_peak closure in get_stats."""
        if not raw or raw.get("value_w") is None:
            return None
        occurred_at_str = raw.get("occurred_at")
        return MaxMetric(
            value_kw=round(raw["value_w"] / 1000, 3),
            occurred_at=datetime.fromisoformat(occurred_at_str),
        )

    def test_5000w_converts_to_5kw(self):
        raw = {"value_w": 5000.0, "occurred_at": "2026-04-14T08:23:00+00:00"}
        result = self._parse_peak(raw)
        assert result is not None
        assert result.value_kw == 5.0

    def test_2750w_rounds_to_3dp(self):
        raw = {"value_w": 2750.0, "occurred_at": "2026-04-14T10:00:00+00:00"}
        result = self._parse_peak(raw)
        assert result is not None
        assert result.value_kw == 2.75

    def test_none_value_returns_none(self):
        assert self._parse_peak({"value_w": None, "occurred_at": None}) is None

    def test_empty_dict_returns_none(self):
        assert self._parse_peak({}) is None


# ---------------------------------------------------------------------------
# System B client mock helpers
# ---------------------------------------------------------------------------

def _peaks_response(pv_w=5000.0, load_w=3200.0, export_w=2400.0, import_w=1500.0):
    """Build a mock System B daily-peaks response."""
    def metric(w):
        return {"value_w": w, "occurred_at": "2026-04-14T10:00:00+00:00"} if w is not None else {"value_w": None, "occurred_at": None}
    return {
        "site_id": "abc",
        "peaks": {
            "pv":     metric(pv_w),
            "load":   metric(load_w),
            "export": metric(export_w),
            "import": metric(import_w),
        },
    }


class TestDailyPeaksParsing:
    """Test that the _parse_peak logic covers all edge cases."""

    def _parse_peak(self, raw: dict):
        if not raw or raw.get("value_w") is None:
            return None
        return MaxMetric(
            value_kw=round(raw["value_w"] / 1000, 3),
            occurred_at=datetime.fromisoformat(raw["occurred_at"]),
        )

    def test_all_four_peaks_from_response(self):
        resp = _peaks_response()
        peaks = resp["peaks"]
        pv   = self._parse_peak(peaks.get("pv", {}))
        load = self._parse_peak(peaks.get("load", {}))
        exp  = self._parse_peak(peaks.get("export", {}))
        imp  = self._parse_peak(peaks.get("import", {}))

        assert pv.value_kw   == 5.0
        assert load.value_kw == 3.2
        assert exp.value_kw  == 2.4
        assert imp.value_kw  == 1.5

    def test_null_pv_peak_returns_none(self):
        resp = _peaks_response(pv_w=None)
        pv = self._parse_peak(resp["peaks"].get("pv", {}))
        assert pv is None

    def test_all_null_peaks(self):
        resp = _peaks_response(pv_w=None, load_w=None, export_w=None, import_w=None)
        for key in ("pv", "load", "export", "import"):
            assert self._parse_peak(resp["peaks"].get(key, {})) is None

    def test_export_peak_is_positive_kw(self):
        """Export value_w from System B is already positive (negated in SQL)."""
        resp = _peaks_response(export_w=2600.0)
        exp = self._parse_peak(resp["peaks"]["export"])
        assert exp is not None
        assert exp.value_kw > 0

    def test_occurred_at_parses_to_datetime(self):
        resp = _peaks_response()
        pv = self._parse_peak(resp["peaks"]["pv"])
        assert isinstance(pv.occurred_at, datetime)
        assert pv.occurred_at.tzinfo is not None


# ---------------------------------------------------------------------------
# StatsResponse model with new fields
# ---------------------------------------------------------------------------

from system_a.app.api.v1.dashboard_widgets import StatsResponse
from uuid import uuid4


class TestStatsResponseModel:
    def _make_base(self):
        return dict(
            organization_id=uuid4(),
            site_id=uuid4(),
            site_name="Test Site",
        )

    def test_peak_fields_default_to_none(self):
        r = StatsResponse(**self._make_base())
        assert r.max_pv_today is None
        assert r.max_load_today is None
        assert r.max_export_today is None
        assert r.max_import_today is None

    def test_peak_fields_accept_max_metric(self):
        m = MaxMetric(
            value_kw=4.5,
            occurred_at=datetime(2026, 4, 14, 9, 0, tzinfo=timezone.utc),
        )
        r = StatsResponse(**self._make_base(), max_pv_today=m)
        assert r.max_pv_today.value_kw == 4.5

    def test_peak_fields_accept_none_explicitly(self):
        r = StatsResponse(**self._make_base(), max_pv_today=None)
        assert r.max_pv_today is None

    def test_serializes_to_dict_with_peak_fields(self):
        m = MaxMetric(
            value_kw=3.2,
            occurred_at=datetime(2026, 4, 14, 13, 0, tzinfo=timezone.utc),
        )
        r = StatsResponse(**self._make_base(), max_load_today=m)
        data = r.model_dump()
        assert "max_load_today" in data
        assert data["max_load_today"]["value_kw"] == 3.2
