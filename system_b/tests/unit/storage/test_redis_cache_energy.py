"""
Unit tests for TelemetryCacheWriter._format_telemetry_for_cache.

Focuses on energy_total field mapping, including Powdrive-specific aliases
(import_energy_total_kwh / export_energy_total_kwh) and the Senergy aliases
already present in energy_today.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from system_b.device_server.storage.redis_cache import TelemetryCacheWriter


@pytest.fixture
def writer():
    settings = MagicMock()
    settings.redis.host = "localhost"
    settings.redis.port = 6379
    settings.redis.db = 0
    settings.redis.password = None
    settings.redis.ssl = False
    settings.redis.telemetry_ttl = 300
    settings.redis.status_ttl = 60
    writer = TelemetryCacheWriter(settings=settings)
    return writer


SERIAL = "SH01GWAT9Q7YDV90"


# ---------------------------------------------------------------------------
# energy_total mapping
# ---------------------------------------------------------------------------

class TestEnergyTotalMapping:
    """Tests for lifetime energy field normalisation."""

    def test_senergy_total_field_names_are_mapped(self, writer):
        """Senergy uses grid_import_energy_total_kwh / grid_export_energy_total_kwh."""
        telemetry = {
            "grid_import_energy_total_kwh": 1234.5,
            "grid_export_energy_total_kwh": 567.8,
            "battery_charge_energy_total_kwh": 300.0,
            "battery_discharge_energy_total_kwh": 280.0,
            "pv_energy_total_kwh": 9000.0,
            "load_energy_total_kwh": 8500.0,
        }
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        et = result["energy_total"]
        assert et["grid_import_kwh"] == 1234.5
        assert et["grid_export_kwh"] == 567.8
        assert et["battery_charge_kwh"] == 300.0
        assert et["battery_discharge_kwh"] == 280.0
        assert et["pv_kwh"] == 9000.0
        assert et["load_kwh"] == 8500.0

    def test_powdrive_alias_import_energy_total_kwh(self, writer):
        """Powdrive uses import_energy_total_kwh (no 'grid_' prefix)."""
        telemetry = {
            "import_energy_total_kwh": 500.0,
            "export_energy_total_kwh": 200.0,
            "pv_energy_total_kwh": 8000.0,
            "load_energy_total_kwh": 7500.0,
            "battery_charge_energy_total_kwh": 1000.0,
            "battery_discharge_energy_total_kwh": 950.0,
        }
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        et = result["energy_total"]
        assert et["grid_import_kwh"] == 500.0
        assert et["grid_export_kwh"] == 200.0

    def test_senergy_name_takes_priority_over_powdrive_alias(self, writer):
        """When both names present, Senergy (grid_import_energy_total_kwh) wins."""
        telemetry = {
            "grid_import_energy_total_kwh": 999.0,   # Senergy — listed first in mappings
            "import_energy_total_kwh": 111.0,         # Powdrive alias — should be ignored
        }
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        assert result["energy_total"]["grid_import_kwh"] == 999.0

    def test_no_total_fields_produces_no_energy_total_section(self, writer):
        """When no total fields present, energy_total key should be absent."""
        telemetry = {"pv_power_w": 1000.0}
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        assert "energy_total" not in result


# ---------------------------------------------------------------------------
# energy_today mapping
# ---------------------------------------------------------------------------

class TestEnergyTodayMapping:
    """Tests for daily energy field normalisation including Senergy aliases."""

    def test_standard_field_names(self, writer):
        telemetry = {
            "pv_energy_today_kwh": 10.0,
            "grid_import_today_kwh": 2.0,
            "grid_export_today_kwh": 1.5,
            "battery_charge_today_kwh": 3.0,
            "battery_discharge_today_kwh": 2.5,
            "load_energy_today_kwh": 9.5,
        }
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        ed = result["energy_today"]
        assert ed["pv_kwh"] == 10.0
        assert ed["grid_import_kwh"] == 2.0
        assert ed["grid_export_kwh"] == 1.5
        assert ed["battery_charge_kwh"] == 3.0
        assert ed["battery_discharge_kwh"] == 2.5
        assert ed["load_kwh"] == 9.5

    def test_senergy_today_aliases(self, writer):
        """Senergy uses grid_import_energy_today_kwh style names for daily energy."""
        telemetry = {
            "grid_import_energy_today_kwh": 4.0,
            "grid_export_energy_today_kwh": 0.5,
            "battery_charge_energy_today_kwh": 1.2,
            "battery_discharge_energy_today_kwh": 0.9,
        }
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        ed = result["energy_today"]
        assert ed["grid_import_kwh"] == 4.0
        assert ed["grid_export_kwh"] == 0.5
        assert ed["battery_charge_kwh"] == 1.2
        assert ed["battery_discharge_kwh"] == 0.9


# ---------------------------------------------------------------------------
# device_type propagation
# ---------------------------------------------------------------------------

class TestDeviceTypeField:
    """Tests that _device_type metadata is surfaced correctly."""

    def test_inverter_device_type(self, writer):
        telemetry = {"_device_type": "inverter", "pv_power_w": 500.0}
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        assert result["device_type"] == "inverter"

    def test_battery_device_type(self, writer):
        telemetry = {"_device_type": "battery", "pack_voltage": 52.0}
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        assert result["device_type"] == "battery"

    def test_missing_device_type_defaults_to_empty_string(self, writer):
        telemetry = {"pv_power_w": 500.0}
        result = writer._format_telemetry_for_cache(SERIAL, telemetry)
        assert result["device_type"] == ""
