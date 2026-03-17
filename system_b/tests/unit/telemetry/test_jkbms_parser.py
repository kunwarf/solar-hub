"""
Unit tests for JKBMSParser and parse_jkbms_status_frame().

Tests:
- Binary frame parsing (parse_jkbms_status_frame)
- Frame builder (build_jkbms_status_frame)
- JKBMSParser metric mapping
- Edge cases (short frames, None values, zero values)
"""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from device_server.telemetry.jkbms_parser import (
    JKBMSParser,
    parse_jkbms_status_frame,
    JKBMS_FRAME_HEADER,
    JKBMS_FRAME_TYPE_STATUS,
)
from system_b.tests.simulators.jkbms_simulator import build_jkbms_status_frame


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_default_frame(**kwargs) -> dict:
    """Build a frame with defaults, optionally overriding fields."""
    frame = build_jkbms_status_frame(**kwargs)
    result = parse_jkbms_status_frame(frame)
    assert result is not None, "parse_jkbms_status_frame returned None for valid frame"
    return result


def _make_parser_args():
    return {
        "device_id": uuid4(),
        "site_id": uuid4(),
        "timestamp": datetime.now(timezone.utc),
    }


# ---------------------------------------------------------------------------
# Frame builder tests
# ---------------------------------------------------------------------------

class TestBuildFrame:
    def test_frame_starts_with_header(self):
        frame = build_jkbms_status_frame()
        assert frame[:4] == JKBMS_FRAME_HEADER

    def test_frame_type_byte(self):
        frame = build_jkbms_status_frame()
        assert frame[4] == JKBMS_FRAME_TYPE_STATUS

    def test_frame_minimum_length(self):
        frame = build_jkbms_status_frame()
        assert len(frame) >= 260

    def test_soc_encoded_correctly(self):
        frame = build_jkbms_status_frame(soc=65)
        assert frame[173] == 65

    def test_soh_encoded_correctly(self):
        frame = build_jkbms_status_frame(soh=90)
        assert frame[190] == 90

    def test_charge_switch_encoded(self):
        frame = build_jkbms_status_frame(charge_enabled=True)
        assert frame[198] == 1
        frame2 = build_jkbms_status_frame(charge_enabled=False)
        assert frame2[198] == 0

    def test_discharge_switch_encoded(self):
        frame = build_jkbms_status_frame(discharge_enabled=True)
        assert frame[199] == 1

    def test_pack_voltage_encoded(self):
        """Pack voltage at offset 234 (2B LE, ÷100 → V)."""
        frame = build_jkbms_status_frame(pack_voltage_v=51.2)
        raw = int.from_bytes(frame[234:236], "little", signed=False)
        assert abs(raw / 100.0 - 51.2) < 0.1


# ---------------------------------------------------------------------------
# parse_jkbms_status_frame tests
# ---------------------------------------------------------------------------

class TestParseFrame:
    def test_returns_none_for_empty(self):
        assert parse_jkbms_status_frame(b"") is None

    def test_returns_none_for_wrong_header(self):
        bad = b'\x00\x01\x02\x03\x02' + b'\x00' * 260
        assert parse_jkbms_status_frame(bad) is None

    def test_returns_none_for_wrong_type(self):
        frame = bytearray(b'\x55\xAA\xEB\x90\x01') + bytearray(260)
        assert parse_jkbms_status_frame(bytes(frame)) is None

    def test_returns_none_for_too_short(self):
        short = JKBMS_FRAME_HEADER + bytes([JKBMS_FRAME_TYPE_STATUS]) + b'\x00' * 10
        assert parse_jkbms_status_frame(short) is None

    def test_soc_round_trip(self):
        result = _parse_default_frame(soc=82)
        assert result["soc"] == 82

    def test_soh_round_trip(self):
        result = _parse_default_frame(soh=95)
        assert result["soh"] == 95

    def test_pack_voltage_round_trip(self):
        result = _parse_default_frame(pack_voltage_v=52.0)
        assert abs(result["pack_voltage"] - 52.0) < 0.1

    def test_current_negative_round_trip(self):
        result = _parse_default_frame(current_a=-10.5)
        assert abs(result["current"] - (-10.5)) < 0.01

    def test_temp1_round_trip(self):
        result = _parse_default_frame(temp1_c=30.5)
        assert abs(result["temp1"] - 30.5) < 0.1

    def test_mos_temp_round_trip(self):
        result = _parse_default_frame(mos_temp_c=35.0)
        assert abs(result["mos_temp"] - 35.0) < 0.1

    def test_cycle_count_round_trip(self):
        result = _parse_default_frame(cycle_count=200)
        assert int(result["cycle_count"]) == 200

    def test_remaining_capacity_round_trip(self):
        result = _parse_default_frame(remaining_ah=40.0)
        assert abs(result["remaining_capacity"] - 40.0) < 0.01

    def test_total_capacity_round_trip(self):
        result = _parse_default_frame(total_ah=50.0)
        assert abs(result["total_capacity"] - 50.0) < 0.01

    def test_cell_voltages_present(self):
        result = _parse_default_frame(num_cells=16)
        assert "cell_voltages" in result
        assert len(result["cell_voltages"]) == 16

    def test_cell_voltages_reasonable(self):
        """Each cell voltage should be close to pack/cells."""
        result = _parse_default_frame(pack_voltage_v=51.2, num_cells=16)
        for v in result["cell_voltages"]:
            assert 2.5 <= v <= 4.5, f"Cell voltage {v} out of range"

    def test_charge_switch_true(self):
        result = _parse_default_frame(charge_enabled=True)
        assert result["charge_switch"] is True

    def test_charge_switch_false(self):
        result = _parse_default_frame(charge_enabled=False)
        assert result["charge_switch"] is False

    def test_discharge_switch(self):
        result = _parse_default_frame(discharge_enabled=True)
        assert result["discharge_switch"] is True


# ---------------------------------------------------------------------------
# JKBMSParser metric mapping
# ---------------------------------------------------------------------------

class TestJKBMSParserMetrics:
    def _parse(self, **frame_kwargs):
        parser = JKBMSParser()
        data = _parse_default_frame(**frame_kwargs)
        return parser.parse(data, **_make_parser_args())

    def test_returns_list(self):
        metrics = self._parse()
        assert isinstance(metrics, list)
        assert len(metrics) > 0

    def test_soc_metric_present(self):
        metrics = self._parse(soc=75)
        names = {m.metric_name for m in metrics}
        assert "battery_soc_pct" in names

    def test_soc_value(self):
        metrics = self._parse(soc=75)
        soc = next(m for m in metrics if m.metric_name == "battery_soc_pct")
        assert soc.metric_value == 75.0

    def test_voltage_metric_present(self):
        metrics = self._parse(pack_voltage_v=51.2)
        names = {m.metric_name for m in metrics}
        assert "battery_voltage_v" in names

    def test_current_metric_present(self):
        metrics = self._parse(current_a=-5.0)
        names = {m.metric_name for m in metrics}
        assert "battery_current_a" in names

    def test_power_metric_present(self):
        metrics = self._parse(power_w=256.0)
        names = {m.metric_name for m in metrics}
        assert "battery_w" in names

    def test_temp_metric_present(self):
        metrics = self._parse(temp1_c=25.0)
        names = {m.metric_name for m in metrics}
        assert "battery_temp_c" in names

    def test_mos_temp_metric_present(self):
        metrics = self._parse(mos_temp_c=28.0)
        names = {m.metric_name for m in metrics}
        assert "battery_mos_temp_c" in names

    def test_soh_metric_present(self):
        metrics = self._parse(soh=98)
        names = {m.metric_name for m in metrics}
        assert "battery_soh_pct" in names

    def test_cycle_count_metric_present(self):
        metrics = self._parse(cycle_count=150)
        names = {m.metric_name for m in metrics}
        assert "battery_cycle_count" in names

    def test_remaining_capacity_metric_present(self):
        metrics = self._parse()
        names = {m.metric_name for m in metrics}
        assert "battery_remaining_ah" in names

    def test_cell_voltage_metrics_present(self):
        metrics = self._parse(num_cells=16)
        cell_metrics = [m for m in metrics if m.metric_name.startswith("battery_cell_")]
        assert len(cell_metrics) == 16

    def test_cell_metric_naming(self):
        metrics = self._parse(num_cells=4)
        names = {m.metric_name for m in metrics}
        for i in range(1, 5):
            assert f"battery_cell_{i}_voltage_v" in names

    def test_charge_enabled_metric_present(self):
        metrics = self._parse(charge_enabled=True)
        names = {m.metric_name for m in metrics}
        assert "battery_charge_enabled" in names

    def test_charge_enabled_value(self):
        metrics = self._parse(charge_enabled=True)
        m = next(m for m in metrics if m.metric_name == "battery_charge_enabled")
        assert m.metric_value == 1.0

    def test_discharge_enabled_metric(self):
        metrics = self._parse(discharge_enabled=False)
        m = next(m for m in metrics if m.metric_name == "battery_discharge_enabled")
        assert m.metric_value == 0.0

    def test_all_metrics_have_device_id(self):
        device_id = uuid4()
        parser = JKBMSParser()
        data = _parse_default_frame()
        metrics = parser.parse(
            data,
            device_id=device_id,
            site_id=uuid4(),
            timestamp=datetime.now(timezone.utc),
        )
        for m in metrics:
            assert m.device_id == device_id

    def test_all_metrics_have_timestamp(self):
        ts = datetime(2026, 3, 17, 12, 0, 0, tzinfo=timezone.utc)
        parser = JKBMSParser()
        data = _parse_default_frame()
        metrics = parser.parse(data, device_id=uuid4(), site_id=uuid4(), timestamp=ts)
        for m in metrics:
            assert m.time == ts


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_dict_returns_empty_list(self):
        parser = JKBMSParser()
        metrics = parser.parse({}, **_make_parser_args())
        assert isinstance(metrics, list)
        assert len(metrics) == 0

    def test_none_values_skipped(self):
        parser = JKBMSParser()
        data = {"soc": None, "pack_voltage": None, "cell_voltages": []}
        metrics = parser.parse(data, **_make_parser_args())
        assert len(metrics) == 0

    def test_zero_soc_is_valid(self):
        metrics_data = _parse_default_frame(soc=0)
        parser = JKBMSParser()
        metrics = parser.parse(metrics_data, **_make_parser_args())
        soc = next((m for m in metrics if m.metric_name == "battery_soc_pct"), None)
        assert soc is not None
        assert soc.metric_value == 0.0

    def test_full_soc_is_valid(self):
        metrics_data = _parse_default_frame(soc=100)
        parser = JKBMSParser()
        metrics = parser.parse(metrics_data, **_make_parser_args())
        soc = next((m for m in metrics if m.metric_name == "battery_soc_pct"), None)
        assert soc is not None
        assert soc.metric_value == 100.0

    def test_no_cells_returns_no_cell_metrics(self):
        parser = JKBMSParser()
        data = {"soc": 80, "cell_voltages": []}
        metrics = parser.parse(data, **_make_parser_args())
        cell_metrics = [m for m in metrics if "cell" in m.metric_name]
        assert len(cell_metrics) == 0

    def test_quality_is_good(self):
        parser = JKBMSParser()
        data = _parse_default_frame()
        metrics = parser.parse(data, **_make_parser_args())
        for m in metrics:
            assert m.quality == "good"

    def test_source_is_telemetry(self):
        parser = JKBMSParser()
        data = _parse_default_frame()
        metrics = parser.parse(data, **_make_parser_args())
        for m in metrics:
            assert m.source == "telemetry"
