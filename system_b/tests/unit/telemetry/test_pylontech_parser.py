"""
Unit tests for PylontechParser.

Tests telemetry parsing for Pylontech/Pytes batteries connected via
the serial bridge (ESP32 + MAX3232 + RS232 console protocol).
"""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from device_server.telemetry.pylontech_parser import PylontechParser
from device_server.telemetry.parser import TelemetryMetric


@pytest.fixture
def parser():
    return PylontechParser()


@pytest.fixture
def device_id():
    return uuid4()


@pytest.fixture
def site_id():
    return uuid4()


@pytest.fixture
def timestamp():
    return datetime(2026, 3, 17, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def bank_telemetry():
    """Bank-level telemetry dict as produced by the Pylontech adapter."""
    return {
        "battery_soc_pct": 78.0,
        "battery_voltage_v": 51.2,
        "battery_current_a": 2.5,
        "battery_power_w": 128.0,
        "battery_temp_c": 25.0,
        "battery_soh_pct": 98.0,
        "battery_cycle_count": 120,
        "battery_units_count": 2,
        "battery_units": [
            {
                "unit": 1,
                "voltage_v": 51.3,
                "current_a": 2.5,
                "soc_pct": 78.0,
                "temp_c": 25.0,
                "soh_pct": 98.0,
                "cycle_count": 120,
                "power_w": 128.25,
                "has_alarm": False,
                "has_fault": False,
            },
            {
                "unit": 2,
                "voltage_v": 51.1,
                "current_a": 2.5,
                "soc_pct": 78.0,
                "temp_c": 25.2,
                "soh_pct": 97.5,
                "cycle_count": 118,
                "power_w": 127.75,
                "has_alarm": False,
                "has_fault": False,
            },
        ],
    }


@pytest.fixture
def bank_only_telemetry():
    """Bank-level telemetry without per-unit data."""
    return {
        "battery_soc_pct": 50.0,
        "battery_voltage_v": 48.0,
        "battery_current_a": -5.0,
        "battery_power_w": -240.0,
        "battery_temp_c": 22.0,
    }


class TestBankMetrics:
    """Test bank-level metric parsing."""

    def test_parse_soc(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_soc_pct" in d
        assert d["battery_soc_pct"].metric_value == 78.0
        assert d["battery_soc_pct"].unit == "%"
        assert d["battery_soc_pct"].tags["category"] == "battery"

    def test_parse_voltage(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_voltage_v" in d
        assert d["battery_voltage_v"].metric_value == 51.2
        assert d["battery_voltage_v"].unit == "V"

    def test_parse_current(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_current_a" in d
        assert d["battery_current_a"].metric_value == 2.5
        assert d["battery_current_a"].unit == "A"

    def test_parse_power(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        # battery_power_w maps to metric_name "battery_w"
        assert "battery_w" in d
        assert d["battery_w"].metric_value == 128.0
        assert d["battery_w"].unit == "W"
        assert d["battery_w"].tags["category"] == "power"

    def test_parse_temperature(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_temp_c" in d
        assert d["battery_temp_c"].metric_value == 25.0
        assert d["battery_temp_c"].unit == "C"

    def test_parse_soh(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_soh_pct" in d
        assert d["battery_soh_pct"].metric_value == 98.0

    def test_parse_cycle_count(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_cycle_count" in d
        assert d["battery_cycle_count"].metric_value == 120.0

    def test_parse_units_count(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_units_count" in d
        assert d["battery_units_count"].metric_value == 2.0

    def test_discharging_negative_power(
        self, parser, device_id, site_id, timestamp, bank_only_telemetry
    ):
        """Negative current and power indicate discharging — must be preserved."""
        metrics = parser.parse(bank_only_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert d["battery_current_a"].metric_value == -5.0
        assert d["battery_w"].metric_value == -240.0


class TestPerUnitMetrics:
    """Test per-unit metric parsing."""

    def test_unit_voltage(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_unit_1_voltage_v" in d
        assert d["battery_unit_1_voltage_v"].metric_value == 51.3
        assert d["battery_unit_1_voltage_v"].unit == "V"
        assert d["battery_unit_1_voltage_v"].tags["category"] == "battery_unit"
        assert d["battery_unit_1_voltage_v"].tags["unit"] == 1

        assert "battery_unit_2_voltage_v" in d
        assert d["battery_unit_2_voltage_v"].metric_value == 51.1

    def test_unit_soc(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_unit_1_soc_pct" in d
        assert d["battery_unit_1_soc_pct"].metric_value == 78.0

    def test_unit_temperature(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_unit_1_temp_c" in d
        assert d["battery_unit_1_temp_c"].metric_value == 25.0

        assert "battery_unit_2_temp_c" in d
        assert d["battery_unit_2_temp_c"].metric_value == 25.2

    def test_unit_power(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_unit_1_power_w" in d
        assert d["battery_unit_1_power_w"].metric_value == pytest.approx(128.25)

    def test_unit_alarm_flag_false(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_unit_1_alarm" in d
        assert d["battery_unit_1_alarm"].metric_value == 0.0
        assert d["battery_unit_1_alarm"].unit == "bool"

    def test_unit_fault_flag_true(self, parser, device_id, site_id, timestamp):
        """Fault flag True should produce metric_value 1.0."""
        data = {
            "battery_units": [
                {"unit": 1, "has_alarm": False, "has_fault": True},
            ]
        }
        metrics = parser.parse(data, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}

        assert "battery_unit_1_fault" in d
        assert d["battery_unit_1_fault"].metric_value == 1.0

    def test_no_units_produces_only_bank_metrics(
        self, parser, device_id, site_id, timestamp, bank_only_telemetry
    ):
        metrics = parser.parse(bank_only_telemetry, device_id, site_id, timestamp)
        names = [m.metric_name for m in metrics]

        assert not any("battery_unit_" in n for n in names)


class TestMetricMetadata:
    """Test that all metrics carry the correct metadata."""

    def test_timestamp_attached(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        for m in metrics:
            assert m.time == timestamp

    def test_device_and_site_ids_attached(
        self, parser, device_id, site_id, timestamp, bank_telemetry
    ):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        for m in metrics:
            assert m.device_id == device_id
            assert m.site_id == site_id

    def test_quality_is_good(self, parser, device_id, site_id, timestamp, bank_telemetry):
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        for m in metrics:
            assert m.quality == "good"

    def test_source_is_telemetry(self, parser, device_id, site_id, timestamp, bank_telemetry):
        """Bank-level metrics use source='telemetry'."""
        metrics = parser.parse(bank_telemetry, device_id, site_id, timestamp)
        bank_metrics = [m for m in metrics if not m.metric_name.startswith("battery_unit_")]
        for m in bank_metrics:
            assert m.source == "telemetry"


class TestEdgeCases:
    """Test robustness against bad/partial data."""

    def test_empty_dict_returns_empty_list(self, parser, device_id, site_id, timestamp):
        metrics = parser.parse({}, device_id, site_id, timestamp)
        assert metrics == []

    def test_missing_bank_fields_skipped(self, parser, device_id, site_id, timestamp):
        """Fields absent from telemetry_data dict are skipped (no KeyError)."""
        data = {"battery_soc_pct": 60.0}
        metrics = parser.parse(data, device_id, site_id, timestamp)
        names = [m.metric_name for m in metrics]
        assert "battery_soc_pct" in names
        # Missing fields must not appear at all
        assert "battery_voltage_v" not in names

    def test_none_value_skipped(self, parser, device_id, site_id, timestamp):
        data = {"battery_soc_pct": None, "battery_voltage_v": 51.0}
        metrics = parser.parse(data, device_id, site_id, timestamp)
        names = [m.metric_name for m in metrics]
        assert "battery_soc_pct" not in names
        assert "battery_voltage_v" in names

    def test_non_numeric_value_skipped(self, parser, device_id, site_id, timestamp):
        data = {"battery_soc_pct": "bad", "battery_voltage_v": 51.0}
        metrics = parser.parse(data, device_id, site_id, timestamp)
        names = [m.metric_name for m in metrics]
        assert "battery_soc_pct" not in names
        assert "battery_voltage_v" in names

    def test_string_float_converted(self, parser, device_id, site_id, timestamp):
        data = {"battery_soc_pct": "78.5"}
        metrics = parser.parse(data, device_id, site_id, timestamp)
        d = {m.metric_name: m for m in metrics}
        assert d["battery_soc_pct"].metric_value == 78.5

    def test_empty_units_list(self, parser, device_id, site_id, timestamp):
        data = {"battery_soc_pct": 78.0, "battery_units": []}
        metrics = parser.parse(data, device_id, site_id, timestamp)
        names = [m.metric_name for m in metrics]
        assert "battery_soc_pct" in names
        assert not any("battery_unit_" in n for n in names)

    def test_unit_missing_optional_field(self, parser, device_id, site_id, timestamp):
        """Units missing optional fields (e.g. soh_pct) should not crash."""
        data = {
            "battery_units": [
                {"unit": 1, "voltage_v": 51.0, "soc_pct": 80.0}
                # no soh_pct, cycle_count, power_w, has_alarm, has_fault
            ]
        }
        metrics = parser.parse(data, device_id, site_id, timestamp)
        names = [m.metric_name for m in metrics]
        assert "battery_unit_1_voltage_v" in names
        assert "battery_unit_1_soc_pct" in names
        # Missing fields should simply be absent
        assert "battery_unit_1_soh_pct" not in names
