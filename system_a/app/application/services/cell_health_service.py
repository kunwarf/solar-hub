"""
Cell Health Service.

Snapshot-based detector that flags candidate cells for inspection in a
Pylontech / Pytes or JK BMS pack, using the per-cell array already
present in the Redis ``device:{serial}:telemetry`` blob under
``battery_bank.cells``.

Consumes the raw cells list from System B's Redis cache (via the
battery-bank endpoint handler) and returns a report structure safe to
merge into the endpoint response. Pure Python — no SQLAlchemy, FastAPI,
Redis, or Pydantic imports at runtime.

Four symptoms are surfaced:
- ``vendor_flag``      : BMS-reported per-cell status is non-benign (Pytes)
- ``voltage_outlier``  : robust Z-score of cell voltage vs. unit median
- ``temp_outlier``     : robust Z-score of cell temperature vs. unit median
- ``current_mismatch`` : cell current deviates from unit median (Pytes)

This is Phase 1 (snapshot-only). "Charges quickly / discharges quickly"
detection requires per-cell time-series which is planned for Phase 2
(new ``battery_cell_samples`` hypertable in System B).

Wording note: candidates are labelled "candidates for inspection", not
"faulty" — the heuristic is diagnostic, not a warranty claim.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ALGORITHM_VERSION = "snapshot_v1"

# Vendor status strings we treat as normal / operational (Pytes vocabulary).
# Anything outside this set is surfaced as a vendor_flag.
_BENIGN_STATES = frozenset(
    {
        "",
        "normal",
        "idle",
        "charge",
        "charging",
        "dischg",
        "discharge",
        "discharging",
        "balance",
        "balancing",
        "standby",
        "sleep",
        "ok",
    }
)

# Substring hints for severity of non-benign vendor states.
_CRITICAL_HINTS = ("alarm", "fault", "ovp", "uvp", "otp", "utp", "short")
_WARNING_HINTS = ("warn", "high", "low", "over", "under")

# Voltage outlier detection
_VOLTAGE_Z_WARN = 3.0
_VOLTAGE_Z_CRIT = 4.5
_VOLTAGE_NOISE_FLOOR_V = 0.020  # skip if unit voltage spread below 20 mV

# Temperature outlier detection
_TEMP_Z_WARN = 3.0
_TEMP_Z_CRIT = 4.5
_TEMP_NOISE_FLOOR_C = 2.0

# Current mismatch detection (Pytes has per-cell current)
_CURRENT_Z_WARN = 3.0
_CURRENT_Z_CRIT = 4.5
_CURRENT_MIN_DEVIATION_A = 0.5  # ignore sub-half-amp noise

# Score weights per symptom severity.
_SEVERITY_WEIGHT = {"critical": 4, "warning": 2, "watch": 1}
# vendor_flag carries more weight because the BMS is authoritative.
_VENDOR_SEVERITY_WEIGHT = {"critical": 5, "warning": 3, "watch": 2}

# Minimum sample counts required for statistical detectors.
_MIN_SAMPLES_FOR_STATS = 4

# Cap on how many candidates per unit we surface.
_MAX_CANDIDATES_PER_UNIT = 5


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _mad(values: List[float], median: float) -> float:
    """Median absolute deviation."""
    if not values:
        return 0.0
    return _median([abs(v - median) for v in values])


def _robust_z(value: float, median: float, mad: float) -> float:
    """Robust Z-score. 1.4826 makes MAD consistent with std under normality."""
    if mad <= 0:
        return 0.0
    return abs(value - median) / (1.4826 * mad)


def _classify_vendor_state(state: Optional[str]) -> Optional[str]:
    """Return severity for a non-benign vendor state, or None if benign."""
    if state is None:
        return None
    s = str(state).strip().lower()
    if s in _BENIGN_STATES:
        return None
    for hint in _CRITICAL_HINTS:
        if hint in s:
            return "critical"
    for hint in _WARNING_HINTS:
        if hint in s:
            return "warning"
    return "watch"


def _detect_vendor_flag(cell: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """BMS reports a non-benign status on any of the ``*_st`` fields."""
    flagged: Dict[str, str] = {}
    severity_rank = {"watch": 0, "warning": 1, "critical": 2}
    max_severity: Optional[str] = None
    for field in ("basic_st", "volt_st", "curr_st", "temp_st"):
        val = cell.get(field)
        sev = _classify_vendor_state(val)
        if sev is None:
            continue
        flagged[field] = val
        if max_severity is None or severity_rank[sev] > severity_rank[max_severity]:
            max_severity = sev
    if not flagged:
        return None
    return {
        "type": "vendor_flag",
        "severity": max_severity or "watch",
        "source": "vendor",
        "evidence": flagged,
    }


def _detect_voltage_outlier(
    cell: Dict[str, Any], median: float, mad: float, spread: float
) -> Optional[Dict[str, Any]]:
    if spread < _VOLTAGE_NOISE_FLOOR_V:
        return None
    v = cell.get("voltage_v")
    if v is None:
        return None
    z = _robust_z(float(v), median, mad)
    if z < _VOLTAGE_Z_WARN:
        return None
    severity = "critical" if z >= _VOLTAGE_Z_CRIT else "warning"
    return {
        "type": "voltage_outlier",
        "severity": severity,
        "source": "computed",
        "evidence": {
            "voltage_v": round(float(v), 4),
            "median_v": round(median, 4),
            "mad_v": round(mad, 4),
            "robust_z": round(z, 2),
            "deviation_mv": round((float(v) - median) * 1000.0, 1),
        },
    }


def _detect_temp_outlier(
    cell: Dict[str, Any], median: float, mad: float, spread: float
) -> Optional[Dict[str, Any]]:
    if spread < _TEMP_NOISE_FLOOR_C:
        return None
    t = cell.get("temperature")
    if t is None:
        return None
    z = _robust_z(float(t), median, mad)
    if z < _TEMP_Z_WARN:
        return None
    severity = "critical" if z >= _TEMP_Z_CRIT else "warning"
    return {
        "type": "temp_outlier",
        "severity": severity,
        "source": "computed",
        "evidence": {
            "temperature_c": round(float(t), 2),
            "median_c": round(median, 2),
            "mad_c": round(mad, 2),
            "robust_z": round(z, 2),
            "deviation_c": round(float(t) - median, 2),
        },
    }


def _detect_current_mismatch(
    cell: Dict[str, Any], median: float, mad: float
) -> Optional[Dict[str, Any]]:
    c = cell.get("current_a")
    if c is None:
        return None
    if abs(float(c) - median) < _CURRENT_MIN_DEVIATION_A:
        return None
    z = _robust_z(float(c), median, mad)
    if z < _CURRENT_Z_WARN:
        return None
    severity = "critical" if z >= _CURRENT_Z_CRIT else "warning"
    return {
        "type": "current_mismatch",
        "severity": severity,
        "source": "computed",
        "evidence": {
            "current_a": round(float(c), 3),
            "median_a": round(median, 3),
            "mad_a": round(mad, 3),
            "robust_z": round(z, 2),
            "deviation_a": round(float(c) - median, 3),
        },
    }


def _score(symptoms: List[Dict[str, Any]]) -> float:
    total = 0.0
    for s in symptoms:
        weights = (
            _VENDOR_SEVERITY_WEIGHT if s["type"] == "vendor_flag" else _SEVERITY_WEIGHT
        )
        total += weights.get(s.get("severity", "watch"), 1)
    return round(total, 2)


def _confidence(symptoms: List[Dict[str, Any]]) -> str:
    if any(s["type"] == "vendor_flag" for s in symptoms):
        return "high"
    if len(symptoms) >= 2:
        return "medium"
    return "low"


def _unit_index(cell: Dict[str, Any]) -> int:
    """Cells may carry either ``module`` (Pylontech) or ``unit`` (JK BMS)."""
    return int(cell.get("unit") or cell.get("module") or 0)


def _analyse_unit(unit_index: int, cells: List[Dict[str, Any]]) -> Dict[str, Any]:
    voltages = [
        float(c["voltage_v"]) for c in cells if c.get("voltage_v") is not None
    ]
    temperatures = [
        float(c["temperature"]) for c in cells if c.get("temperature") is not None
    ]
    currents = [
        float(c["current_a"]) for c in cells if c.get("current_a") is not None
    ]

    v_median = _median(voltages) if voltages else 0.0
    v_mad = _mad(voltages, v_median) if voltages else 0.0
    v_spread = (max(voltages) - min(voltages)) if voltages else 0.0

    t_median = _median(temperatures) if temperatures else 0.0
    t_mad = _mad(temperatures, t_median) if temperatures else 0.0
    t_spread = (max(temperatures) - min(temperatures)) if temperatures else 0.0

    c_median = _median(currents) if currents else 0.0
    c_mad = _mad(currents, c_median) if currents else 0.0

    can_score_voltage = len(voltages) >= _MIN_SAMPLES_FOR_STATS
    can_score_temp = len(temperatures) >= _MIN_SAMPLES_FOR_STATS
    can_score_current = len(currents) >= _MIN_SAMPLES_FOR_STATS

    per_cell: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
    for cell in cells:
        symptoms: List[Dict[str, Any]] = []

        vendor = _detect_vendor_flag(cell)
        if vendor is not None:
            symptoms.append(vendor)

        if can_score_voltage:
            v_out = _detect_voltage_outlier(cell, v_median, v_mad, v_spread)
            if v_out is not None:
                symptoms.append(v_out)

        if can_score_temp:
            t_out = _detect_temp_outlier(cell, t_median, t_mad, t_spread)
            if t_out is not None:
                symptoms.append(t_out)

        if can_score_current:
            c_out = _detect_current_mismatch(cell, c_median, c_mad)
            if c_out is not None:
                symptoms.append(c_out)

        if symptoms:
            per_cell.append((cell, symptoms))

    candidates = [
        {
            "cell_index": cell.get("cell"),
            "score": _score(symptoms),
            "confidence": _confidence(symptoms),
            "symptoms": symptoms,
        }
        for cell, symptoms in per_cell
    ]
    candidates.sort(key=lambda c: c["score"], reverse=True)
    candidates = candidates[:_MAX_CANDIDATES_PER_UNIT]

    return {
        "unit_index": unit_index,
        "cell_count": len(cells),
        "candidates": candidates,
        "stats": {
            "voltage_median_v": round(v_median, 4) if voltages else None,
            "voltage_mad_v": round(v_mad, 4) if voltages else None,
            "voltage_spread_v": round(v_spread, 4) if voltages else None,
            "temp_median_c": round(t_median, 2) if temperatures else None,
            "temp_mad_c": round(t_mad, 2) if temperatures else None,
            "temp_spread_c": round(t_spread, 2) if temperatures else None,
            "current_median_a": round(c_median, 3) if currents else None,
            "current_mad_a": round(c_mad, 3) if currents else None,
        },
    }


def _empty_report(reason: str) -> Dict[str, Any]:
    return {
        "algorithm": ALGORITHM_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "available": False,
        "reason": reason,
        "units": [],
        "total_candidates": 0,
    }


def detect_snapshot(cells: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Analyse a single Redis snapshot's per-cell array.

    Args:
        cells: The ``battery_bank.cells`` list from the System B Redis blob.
               Each cell dict may carry ``unit`` or ``module`` (unit id),
               ``cell`` (index), ``voltage_v``, ``current_a``, ``temperature``,
               ``soc``, and vendor status strings ``basic_st``, ``volt_st``,
               ``curr_st``, ``temp_st``. Any field may be absent.

    Returns:
        A dict safe to embed in ``/api/v1/devices/{id}/battery/bank`` under a
        new ``cell_health`` key. When ``cells`` is ``None`` or empty the report
        has ``available=False`` and a machine-readable ``reason``.
    """
    if cells is None:
        return _empty_report("no_recent_data")
    if not cells:
        return _empty_report("pack_level_only")

    # Group by unit index. Cells may arrive interleaved from multiple units.
    by_unit: Dict[int, List[Dict[str, Any]]] = {}
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        by_unit.setdefault(_unit_index(cell), []).append(cell)

    units = [_analyse_unit(idx, by_unit[idx]) for idx in sorted(by_unit.keys())]
    total_candidates = sum(len(u["candidates"]) for u in units)

    return {
        "algorithm": ALGORITHM_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "available": True,
        "reason": None,
        "units": units,
        "total_candidates": total_candidates,
    }
