"""
Unit tests for the snapshot cell-health detector.

Fixtures mirror the ``battery_bank.cells`` payload shape that System B
writes to Redis for the three supported battery families:

- Pytes / Pylontech: voltage_v, current_a, temperature, soc, and vendor
  status strings ``basic_st`` / ``volt_st`` / ``curr_st`` / ``temp_st``.
- JK BMS TCP/IP    : voltage_v only (no per-cell temp, current, status).
- JK BMS BLE       : voltage_v + derived temperature (per-cell temp not
  measured, inherited from unit sensor).
- Senergy          : no per-cell data at all (pack-level only).
"""
import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Load the detector by path so this suite runs without triggering the
# ``services`` package __init__, which imports SQLAlchemy / FastAPI /
# email transports transitively. The detector is intentionally pure
# Python — this import pattern documents and enforces that isolation.
_CELL_HEALTH_PATH = (
    Path(__file__).resolve().parents[3]
    / "app"
    / "application"
    / "services"
    / "cell_health_service.py"
)
_spec = importlib.util.spec_from_file_location(
    "cell_health_service_under_test", _CELL_HEALTH_PATH
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
ALGORITHM_VERSION = _module.ALGORITHM_VERSION
detect_snapshot = _module.detect_snapshot


# ─── Fixture builders ────────────────────────────────────────────────────────


def _pytes_cell(cell: int, voltage_v: float, **overrides: Any) -> Dict[str, Any]:
    """A Pytes cell with realistic per-cell noise in current and temperature.

    Baseline jitter (±0.6 °C, ±0.04 A) keeps MAD > 0 in "healthy" fixtures so
    the robust-Z detectors can distinguish an injected outlier from noise,
    while staying under the noise floors and min-deviation guards so no
    healthy cell trips a symptom on its own.
    """
    base = {
        "unit": 1,
        "cell": cell,
        "voltage_v": voltage_v,
        "current_a": 5.0 + (cell % 3) * 0.02,
        "temperature": 25.0 + (cell % 3) * 0.3,
        "soc": 80,
        "basic_st": "Charge",
        "volt_st": "Normal",
        "curr_st": "Normal",
        "temp_st": "Normal",
    }
    base.update(overrides)
    return base


def _healthy_voltage(cell: int, base: float = 3.32) -> float:
    """Small per-cell voltage jitter that stays under the noise floor."""
    return base + (cell % 3) * 0.001


def _jkbms_tcp_cell(cell: int, voltage_v: float, unit: int = 1) -> Dict[str, Any]:
    return {"unit": unit, "cell": cell, "voltage_v": voltage_v}


def _jkbms_ble_cell(
    cell: int, voltage_v: float, temperature: float = 25.0, unit: int = 1
) -> Dict[str, Any]:
    return {
        "unit": unit,
        "cell": cell,
        "voltage_v": voltage_v,
        "temperature": temperature,
    }


def _healthy_pytes_pack() -> List[Dict[str, Any]]:
    return [_pytes_cell(i, _healthy_voltage(i)) for i in range(1, 17)]


# ─── Empty / unavailable paths ───────────────────────────────────────────────


def test_none_cells_returns_no_recent_data():
    report = detect_snapshot(None)
    assert report["available"] is False
    assert report["reason"] == "no_recent_data"
    assert report["units"] == []
    assert report["total_candidates"] == 0
    assert report["algorithm"] == ALGORITHM_VERSION


def test_empty_cells_returns_pack_level_only():
    report = detect_snapshot([])
    assert report["available"] is False
    assert report["reason"] == "pack_level_only"


def test_healthy_pack_has_no_candidates():
    report = detect_snapshot(_healthy_pytes_pack())
    assert report["available"] is True
    assert report["total_candidates"] == 0
    assert len(report["units"]) == 1
    assert report["units"][0]["unit_index"] == 1
    assert report["units"][0]["candidates"] == []
    stats = report["units"][0]["stats"]
    assert stats["voltage_spread_v"] is not None
    assert stats["voltage_spread_v"] < 0.020


# ─── Pytes symptom detection ─────────────────────────────────────────────────


def test_pytes_voltage_outlier_low():
    cells = _healthy_pytes_pack()
    # Push cell 7 well below the rest
    cells[6] = _pytes_cell(7, 3.05)
    report = detect_snapshot(cells)
    assert report["total_candidates"] >= 1
    cand = report["units"][0]["candidates"][0]
    assert cand["cell_index"] == 7
    symptom_types = {s["type"] for s in cand["symptoms"]}
    assert "voltage_outlier" in symptom_types


def test_pytes_vendor_flag_wins_confidence():
    cells = _healthy_pytes_pack()
    cells[3] = _pytes_cell(4, 3.32, volt_st="UVP")  # vendor flag only
    report = detect_snapshot(cells)
    assert report["total_candidates"] == 1
    cand = report["units"][0]["candidates"][0]
    assert cand["cell_index"] == 4
    assert cand["confidence"] == "high"
    assert {s["type"] for s in cand["symptoms"]} == {"vendor_flag"}
    assert cand["symptoms"][0]["severity"] == "critical"
    assert cand["symptoms"][0]["source"] == "vendor"


def test_pytes_temp_outlier():
    cells = _healthy_pytes_pack()
    cells[9] = _pytes_cell(10, 3.32, temperature=40.0)  # 15 °C above median
    report = detect_snapshot(cells)
    cand = report["units"][0]["candidates"][0]
    assert cand["cell_index"] == 10
    assert any(s["type"] == "temp_outlier" for s in cand["symptoms"])


def test_pytes_current_mismatch():
    cells = _healthy_pytes_pack()
    cells[11] = _pytes_cell(12, 3.32, current_a=15.0)  # 10 A above median
    report = detect_snapshot(cells)
    cand = report["units"][0]["candidates"][0]
    assert cand["cell_index"] == 12
    assert any(s["type"] == "current_mismatch" for s in cand["symptoms"])


def test_pytes_multiple_symptoms_higher_score():
    cells = _healthy_pytes_pack()
    # Cell 5 has both a voltage outlier and a vendor flag
    cells[4] = _pytes_cell(5, 3.02, volt_st="Alarm")
    # Cell 9 has only a voltage outlier
    cells[8] = _pytes_cell(9, 3.05)
    report = detect_snapshot(cells)
    candidates = report["units"][0]["candidates"]
    assert candidates[0]["cell_index"] == 5  # highest score first
    assert candidates[0]["score"] > candidates[1]["score"]
    assert candidates[0]["confidence"] == "high"


def test_pytes_candidates_capped_per_unit():
    # Make every other cell an outlier to exceed the cap
    cells = _healthy_pytes_pack()
    for i in (0, 2, 4, 6, 8, 10, 12, 14):
        cells[i] = _pytes_cell(i + 1, 3.02, volt_st="UVP")
    report = detect_snapshot(cells)
    assert len(report["units"][0]["candidates"]) == 5


# ─── JK BMS TCP: voltage-only ────────────────────────────────────────────────


def test_jkbms_tcp_voltage_outlier():
    cells = [_jkbms_tcp_cell(i, _healthy_voltage(i, base=3.30)) for i in range(1, 17)]
    cells[3] = _jkbms_tcp_cell(4, 3.05)
    report = detect_snapshot(cells)
    cand = report["units"][0]["candidates"][0]
    assert cand["cell_index"] == 4
    assert {s["type"] for s in cand["symptoms"]} == {"voltage_outlier"}
    assert cand["confidence"] == "low"  # single symptom, no vendor flag


def test_jkbms_tcp_no_temp_or_current_symptoms():
    cells = [_jkbms_tcp_cell(i, _healthy_voltage(i, base=3.30)) for i in range(1, 17)]
    cells[7] = _jkbms_tcp_cell(8, 3.05)
    report = detect_snapshot(cells)
    for cand in report["units"][0]["candidates"]:
        for symptom in cand["symptoms"]:
            assert symptom["type"] not in {"temp_outlier", "current_mismatch"}


# ─── JK BMS BLE: voltage + derived temp ──────────────────────────────────────


def test_jkbms_ble_voltage_outlier():
    cells = [
        _jkbms_ble_cell(i, _healthy_voltage(i, base=3.30), 25.0) for i in range(1, 17)
    ]
    cells[2] = _jkbms_ble_cell(3, 3.05, 25.0)
    report = detect_snapshot(cells)
    cand = report["units"][0]["candidates"][0]
    assert cand["cell_index"] == 3
    assert any(s["type"] == "voltage_outlier" for s in cand["symptoms"])


# ─── Multi-unit grouping (Pylontech stack) ───────────────────────────────────


def test_multi_unit_analysed_independently():
    unit1 = _healthy_pytes_pack()
    unit1[5] = _pytes_cell(6, 3.02)  # outlier in unit 1
    unit2 = [dict(_pytes_cell(i, _healthy_voltage(i, base=3.34)), unit=2) for i in range(1, 17)]
    unit2[10] = dict(_pytes_cell(11, 3.04), unit=2)  # outlier in unit 2
    report = detect_snapshot(unit1 + unit2)
    assert len(report["units"]) == 2
    unit_indices = {u["unit_index"]: u for u in report["units"]}
    assert unit_indices[1]["candidates"][0]["cell_index"] == 6
    assert unit_indices[2]["candidates"][0]["cell_index"] == 11


def test_module_key_falls_back_to_unit():
    # Some System B parsers write "module" instead of "unit"
    cells = []
    for i in range(1, 17):
        c = _pytes_cell(i, _healthy_voltage(i))
        c.pop("unit")
        c["module"] = 3
        cells.append(c)
    cells[4]["voltage_v"] = 3.02
    report = detect_snapshot(cells)
    assert len(report["units"]) == 1
    assert report["units"][0]["unit_index"] == 3


# ─── Noise floors ────────────────────────────────────────────────────────────


def test_voltage_noise_floor_suppresses_flags():
    # 20 mV floor: a 15 mV spread should surface no voltage outliers
    cells = [_pytes_cell(i, 3.320 + i * 0.001) for i in range(1, 17)]
    report = detect_snapshot(cells)
    for cand in report["units"][0]["candidates"]:
        for s in cand["symptoms"]:
            assert s["type"] != "voltage_outlier"


def test_temperature_noise_floor_suppresses_flags():
    # <2 °C spread → no temp_outlier
    cells = [_pytes_cell(i, 3.32, temperature=25.0 + (i % 3) * 0.5) for i in range(1, 17)]
    report = detect_snapshot(cells)
    for cand in report["units"][0]["candidates"]:
        for s in cand["symptoms"]:
            assert s["type"] != "temp_outlier"


def test_stats_below_min_samples_skips_detectors():
    # 3 cells is under _MIN_SAMPLES_FOR_STATS (4)
    cells = [_pytes_cell(1, 3.05), _pytes_cell(2, 3.32), _pytes_cell(3, 3.33)]
    report = detect_snapshot(cells)
    # Only vendor_flag could still fire, and none set here → no candidates
    assert report["units"][0]["candidates"] == []


# ─── Vendor state classification ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "state,expected_severity",
    [
        ("Normal", None),
        ("Balance", None),
        ("Charge", None),
        ("UVP", "critical"),
        ("OVP", "critical"),
        ("Alarm", "critical"),
        ("Fault", "critical"),
        ("High", "warning"),
        ("WarnLow", "warning"),
        ("Weird", "watch"),
    ],
)
def test_vendor_state_classification(state, expected_severity):
    cells = _healthy_pytes_pack()
    cells[0] = _pytes_cell(1, 3.32, volt_st=state)
    report = detect_snapshot(cells)
    if expected_severity is None:
        assert report["total_candidates"] == 0
    else:
        cand = report["units"][0]["candidates"][0]
        vendor = next(s for s in cand["symptoms"] if s["type"] == "vendor_flag")
        assert vendor["severity"] == expected_severity


# ─── Structural invariants ───────────────────────────────────────────────────


def test_report_shape_available():
    report = detect_snapshot(_healthy_pytes_pack())
    assert set(report.keys()) == {
        "algorithm",
        "generated_at",
        "available",
        "reason",
        "units",
        "total_candidates",
    }
    unit = report["units"][0]
    assert set(unit.keys()) == {"unit_index", "cell_count", "candidates", "stats"}


def test_generated_at_is_utc():
    report = detect_snapshot(_healthy_pytes_pack())
    assert report["generated_at"].endswith("+00:00")
