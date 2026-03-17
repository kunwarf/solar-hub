"""
JK BMS binary telemetry parser.

Parses the dict produced from JK BMS 55 AA EB 90 status frames
(frame type 0x02) into normalized TelemetryMetric objects.

The dict schema matches the output of parse_jkbms_status_frame(), which
is called by TCPCommandAdapter.poll() for the jkbms_serial protocol:

    {
        "soc": int,                  # 0-100 %
        "soh": int,                  # 0-100 %
        "pack_voltage": float,       # V
        "current": float,            # A (negative = discharging)
        "power": float,              # W (unsigned, always positive)
        "temp1": float,              # °C (battery temp sensor 1)
        "temp2": float,              # °C (battery temp sensor 2)
        "temp3": float,              # °C (extra sensor)
        "temp4": float,              # °C (extra sensor)
        "mos_temp": float,           # °C (MOSFET temperature)
        "remaining_capacity": float, # Ah
        "total_capacity": float,     # Ah
        "cycle_count": int,
        "charge_switch": bool,
        "discharge_switch": bool,
        "balance_switch": bool,
        "balance_current": float,    # A
        "balance_action": bool,
        "cell_voltages": [float, ...],  # V per cell
    }
"""
import logging
import struct
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from .parser import TelemetryParser, TelemetryMetric

logger = logging.getLogger(__name__)

# JK BMS binary frame header and type
JKBMS_FRAME_HEADER = b'\x55\xAA\xEB\x90'
JKBMS_FRAME_TYPE_STATUS = 0x02


# ---------------------------------------------------------------------------
# Low-level binary frame helpers
# ---------------------------------------------------------------------------

def _read_int_le(
    data: bytes,
    offset: int,
    length: int,
    signed: bool = False,
    scale: float = 1.0,
) -> Optional[float]:
    """Read little-endian integer from bytes, apply scale, return float."""
    if offset + length > len(data):
        return None
    value = int.from_bytes(data[offset:offset + length], "little", signed=signed)
    return value / scale if scale != 1.0 else float(value)


def _read_bool(data: bytes, offset: int) -> Optional[bool]:
    if offset >= len(data):
        return None
    return bool(data[offset])


def parse_jkbms_status_frame(frame: bytes, cells_per_bms: int = 16) -> Optional[Dict[str, Any]]:
    """
    Parse a JK BMS ``55 AA EB 90 02`` status frame into a dict.

    Args:
        frame: Raw bytes starting at the ``55 AA EB 90`` header.
        cells_per_bms: Number of cell voltage slots to read.

    Returns:
        Parsed dict or None if the frame is too short / wrong type.
    """
    if len(frame) < 5 or frame[:4] != JKBMS_FRAME_HEADER:
        return None
    if frame[4] != JKBMS_FRAME_TYPE_STATUS:
        return None
    if len(frame) < 236:
        return None

    result: Dict[str, Any] = {}

    # Cell voltages: offset 6 + cell*2, 2 bytes LE, ÷1000 → V
    cell_voltages = []
    for cell in range(cells_per_bms):
        v = _read_int_le(frame, 6 + cell * 2, 2, signed=False, scale=1000.0)
        cell_voltages.append(round(v, 3) if v is not None else None)
    result["cell_voltages"] = [v for v in cell_voltages if v is not None]

    result["mos_temp"]           = _read_int_le(frame, 144, 2, signed=True, scale=10.0)
    result["power"]              = _read_int_le(frame, 154, 4, signed=False, scale=1000.0)
    result["current"]            = _read_int_le(frame, 158, 4, signed=True,  scale=1000.0)
    result["temp1"]              = _read_int_le(frame, 162, 2, signed=True, scale=10.0)
    result["temp2"]              = _read_int_le(frame, 164, 2, signed=True, scale=10.0)
    result["balance_current"]    = _read_int_le(frame, 170, 2, signed=True, scale=1000.0)
    result["balance_action"]     = _read_bool(frame, 172)

    if len(frame) > 173:
        result["soc"] = frame[173]
    result["remaining_capacity"] = _read_int_le(frame, 174, 4, signed=True, scale=1000.0)
    result["total_capacity"]     = _read_int_le(frame, 178, 4, signed=True, scale=1000.0)
    result["cycle_count"]        = _read_int_le(frame, 182, 4, signed=True, scale=1.0)
    if len(frame) > 190:
        result["soh"] = frame[190]

    result["charge_switch"]      = _read_bool(frame, 198)
    result["discharge_switch"]   = _read_bool(frame, 199)
    result["balance_switch"]     = _read_bool(frame, 200)
    result["pack_voltage"]       = _read_int_le(frame, 234, 2, signed=False, scale=100.0)

    if len(frame) > 255:
        result["temp3"] = _read_int_le(frame, 254, 2, signed=True, scale=10.0)
    if len(frame) > 259:
        result["temp4"] = _read_int_le(frame, 258, 2, signed=True, scale=10.0)

    return result


# ---------------------------------------------------------------------------
# TelemetryParser implementation
# ---------------------------------------------------------------------------

class JKBMSParser(TelemetryParser):
    """
    Parser for JK BMS telemetry received via the ESP32 serial bridge.

    Converts the dict produced by parse_jkbms_status_frame() into
    normalized TelemetryMetric objects for storage in TimescaleDB.
    """

    # Bank-level metric mappings: dict_key -> (metric_name, unit, category)
    BANK_METRIC_MAPPINGS: List[tuple] = [
        ("soc",                ("battery_soc_pct",      "%",   "battery")),
        ("soh",                ("battery_soh_pct",      "%",   "battery")),
        ("pack_voltage",       ("battery_voltage_v",    "V",   "battery")),
        ("current",            ("battery_current_a",    "A",   "battery")),
        ("power",              ("battery_w",            "W",   "power")),
        ("temp1",              ("battery_temp_c",       "C",   "temperature")),
        ("temp2",              ("battery_temp2_c",      "C",   "temperature")),
        ("mos_temp",           ("battery_mos_temp_c",   "C",   "temperature")),
        ("remaining_capacity", ("battery_remaining_ah", "Ah",  "battery")),
        ("total_capacity",     ("battery_total_ah",     "Ah",  "battery")),
        ("cycle_count",        ("battery_cycle_count",  "",    "battery")),
        ("balance_current",    ("battery_balance_a",    "A",   "battery")),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        """
        Parse JK BMS telemetry dict into normalized metrics.

        Args:
            telemetry_data: Dict from parse_jkbms_status_frame().
            device_id: Device UUID.
            site_id: Site UUID.
            timestamp: Telemetry timestamp.

        Returns:
            List of TelemetryMetric objects.
        """
        metrics: List[TelemetryMetric] = []

        # --- Bank-level scalars ---
        for dict_key, (metric_name, unit, category) in self.BANK_METRIC_MAPPINGS:
            value = telemetry_data.get(dict_key)
            if value is None:
                continue
            try:
                metrics.append(TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name=metric_name,
                    metric_value=float(value),
                    quality="good",
                    unit=unit,
                    source="telemetry",
                    tags={"category": category},
                ))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert {metric_name}={value} to float, skipping")

        # --- Boolean switch states as 0/1 metrics ---
        for bool_key, metric_name in [
            ("charge_switch",    "battery_charge_enabled"),
            ("discharge_switch", "battery_discharge_enabled"),
            ("balance_switch",   "battery_balance_enabled"),
            ("balance_action",   "battery_balancing_active"),
        ]:
            val = telemetry_data.get(bool_key)
            if val is not None:
                metrics.append(TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name=metric_name,
                    metric_value=1.0 if val else 0.0,
                    metric_value_str=str(val),
                    quality="good",
                    unit="bool",
                    source="telemetry",
                    tags={"category": "battery"},
                ))

        # --- Per-cell voltage metrics ---
        cell_voltages: List = telemetry_data.get("cell_voltages", [])
        for i, voltage in enumerate(cell_voltages):
            if voltage is None:
                continue
            try:
                metrics.append(TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name=f"battery_cell_{i + 1}_voltage_v",
                    metric_value=float(voltage),
                    quality="good",
                    unit="V",
                    source="telemetry",
                    tags={"category": "battery_cell", "cell": i + 1},
                ))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert cell {i + 1} voltage={voltage} to float")

        logger.debug(
            f"Parsed {len(metrics)} metrics from JK BMS telemetry "
            f"(device {device_id}, {len(cell_voltages)} cells)"
        )
        return metrics
