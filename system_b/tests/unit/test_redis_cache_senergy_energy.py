"""
Unit tests: Senergy energy field mapping in TelemetryCacheWriter.

Senergy inverters use protocol-specific register names that differ from the
generic field names expected by redis_cache.py.  These tests verify that:

1. Total energy hardware registers are captured in energy_total section.
2. Battery today energy hardware registers are captured in energy_today section.
3. Other protocols (Powdrive / generic) are unaffected.
4. Today energy fields that were already correct remain correct.
"""
import pytest

# Import the formatter directly — no Redis connection needed.
from system_b.device_server.storage.redis_cache import TelemetryCacheWriter


def _format(raw: dict) -> dict:
    """Invoke _format_telemetry_for_cache with a minimal raw telemetry dict."""
    writer = TelemetryCacheWriter.__new__(TelemetryCacheWriter)
    return writer._format_telemetry_for_cache("TEST123", raw)


# ---------------------------------------------------------------------------
# Total energy — Senergy raw register names
# ---------------------------------------------------------------------------

class TestSenergyEnergyTotalMapping:
    def _senergy_total_raw(self, **overrides) -> dict:
        base = {
            "_device_type": "inverter",
            "_protocol_id": "senergy",
            "total_energy": 13528.9,
            "accumulated_energy_positive": 421.3,
            "accumulated_energy_negative": 850.7,
            "accumulated_energy_of_load": 14200.0,
            "battery_accumulated_charge_energy": 6800.0,
            "battery_accumulated_discharge_energy": 6500.0,
        }
        base.update(overrides)
        return base

    def test_pv_total_kwh_captured(self):
        result = _format(self._senergy_total_raw())
        assert "energy_total" in result
        assert result["energy_total"]["pv_kwh"] == pytest.approx(13528.9)

    def test_grid_import_total_kwh_captured(self):
        result = _format(self._senergy_total_raw())
        assert result["energy_total"]["grid_import_kwh"] == pytest.approx(421.3)

    def test_grid_export_total_kwh_captured(self):
        result = _format(self._senergy_total_raw())
        assert result["energy_total"]["grid_export_kwh"] == pytest.approx(850.7)

    def test_load_total_kwh_captured(self):
        result = _format(self._senergy_total_raw())
        assert result["energy_total"]["load_kwh"] == pytest.approx(14200.0)

    def test_battery_charge_total_kwh_captured(self):
        result = _format(self._senergy_total_raw())
        assert result["energy_total"]["battery_charge_kwh"] == pytest.approx(6800.0)

    def test_battery_discharge_total_kwh_captured(self):
        result = _format(self._senergy_total_raw())
        assert result["energy_total"]["battery_discharge_kwh"] == pytest.approx(6500.0)

    def test_all_six_total_fields_present(self):
        result = _format(self._senergy_total_raw())
        et = result["energy_total"]
        for key in ("pv_kwh", "grid_import_kwh", "grid_export_kwh",
                    "load_kwh", "battery_charge_kwh", "battery_discharge_kwh"):
            assert key in et, f"energy_total.{key} missing"

    def test_partial_totals_still_captured(self):
        """If only pv and grid totals are present (other registers absent), they're still mapped."""
        raw = {"total_energy": 5000.0, "accumulated_energy_positive": 100.0}
        result = _format(raw)
        et = result.get("energy_total", {})
        assert et.get("pv_kwh") == pytest.approx(5000.0)
        assert et.get("grid_import_kwh") == pytest.approx(100.0)
        assert "battery_charge_kwh" not in et


# ---------------------------------------------------------------------------
# Battery today — Senergy raw register names
# ---------------------------------------------------------------------------

class TestSenergyBatteryTodayMapping:
    def _senergy_today_raw(self, **overrides) -> dict:
        base = {
            "_device_type": "inverter",
            "_protocol_id": "senergy",
            "today_pv_kwh": 9.87,
            "today_import_kwh": 1.66,
            "today_export_kwh": 1.01,
            "today_load_kwh": 1.02,
            "battery_daily_charge_energy": 26.06,
            "battery_daily_discharge_energy": 13.11,
        }
        base.update(overrides)
        return base

    def test_battery_charge_today_from_hardware_register(self):
        result = _format(self._senergy_today_raw())
        et = result.get("energy_today", {})
        assert et.get("battery_charge_kwh") == pytest.approx(26.06)

    def test_battery_discharge_today_from_hardware_register(self):
        result = _format(self._senergy_today_raw())
        et = result.get("energy_today", {})
        assert et.get("battery_discharge_kwh") == pytest.approx(13.11)

    def test_pv_today_still_correct(self):
        result = _format(self._senergy_today_raw())
        assert result["energy_today"]["pv_kwh"] == pytest.approx(9.87)

    def test_grid_import_today_still_correct(self):
        result = _format(self._senergy_today_raw())
        assert result["energy_today"]["grid_import_kwh"] == pytest.approx(1.66)

    def test_grid_export_today_still_correct(self):
        result = _format(self._senergy_today_raw())
        assert result["energy_today"]["grid_export_kwh"] == pytest.approx(1.01)

    def test_load_today_still_correct(self):
        result = _format(self._senergy_today_raw())
        assert result["energy_today"]["load_kwh"] == pytest.approx(1.02)


# ---------------------------------------------------------------------------
# Generic / Powdrive — must still work after the change
# ---------------------------------------------------------------------------

class TestGenericEnergyTotalUnaffected:
    def test_powdrive_import_total_still_mapped(self):
        raw = {"import_energy_total_kwh": 1234.5}
        result = _format(raw)
        assert result.get("energy_total", {}).get("grid_import_kwh") == pytest.approx(1234.5)

    def test_powdrive_export_total_still_mapped(self):
        raw = {"export_energy_total_kwh": 567.8}
        result = _format(raw)
        assert result.get("energy_total", {}).get("grid_export_kwh") == pytest.approx(567.8)

    def test_generic_pv_total_still_mapped(self):
        raw = {"pv_energy_total_kwh": 999.0}
        result = _format(raw)
        assert result.get("energy_total", {}).get("pv_kwh") == pytest.approx(999.0)

    def test_priority_generic_before_senergy(self):
        """If both generic and Senergy names present, generic name wins (first in list)."""
        raw = {
            "pv_energy_total_kwh": 100.0,
            "total_energy": 999.0,
        }
        result = _format(raw)
        assert result["energy_total"]["pv_kwh"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# No energy_total section when no matching fields present
# ---------------------------------------------------------------------------

class TestEmptyEnergyTotal:
    def test_no_energy_total_key_when_no_matching_fields(self):
        raw = {"battery_soc_pct": 80.0, "pv1_power_w": 2000.0}
        result = _format(raw)
        assert "energy_total" not in result
