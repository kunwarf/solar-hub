"""
JK BMS binary telemetry parser.

Multi-unit RS485 support
------------------------
When multiple JK BMS units share an RS485 bus in broadcast mode, the ESP32
collects a raw bus dump that interleaves two frame types:

  Modbus request  (``<battery_id> 0x10 0x16 ...``): emitted by the master to
    address a specific unit; the battery_id byte identifies which unit's data
    frame follows next.

  Data frame      (``55 AA EB 90 0x02 ...``): status payload from the
    addressed unit.

``parse_jkbms_bus_dump()`` handles this combined stream, tracking
``current_battery_id`` across Modbus frames and attributing each data frame
to the correct unit.  When no Modbus frames are present (pure broadcast mode)
data frames are assigned unit IDs 1, 2, 3, … in order of appearance.

The returned dict contains standard bank-level scalars (aggregated over all
units) plus ``battery_units`` and ``battery_cells`` lists in the same format
used by the Pylontech parser so redis_cache and the frontend handle them
identically.
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

    # Cell resistances: offset 80 + cell*2, 2 bytes LE, ÷1000 → Ω
    cell_resistances = []
    for cell in range(cells_per_bms):
        r = _read_int_le(frame, 80 + cell * 2, 2, signed=True, scale=1000.0)
        if r is not None:
            cell_resistances.append(r)
    if cell_resistances:
        result["cell_resistances"] = cell_resistances

    result["mos_temp"]           = _read_int_le(frame, 144, 2, signed=True, scale=10.0)
    result["power"]              = _read_int_le(frame, 154, 4, signed=False, scale=1000.0)
    result["current"]            = _read_int_le(frame, 158, 4, signed=True,  scale=1000.0)
    result["temp1"]              = _read_int_le(frame, 162, 2, signed=True, scale=10.0)
    result["temp2"]              = _read_int_le(frame, 164, 2, signed=True, scale=10.0)
    result["temp3"]              = _read_int_le(frame, 254, 2, signed=True, scale=10.0)
    result["temp4"]              = _read_int_le(frame, 258, 2, signed=True, scale=10.0)
    result["balance_current"]    = _read_int_le(frame, 170, 2, signed=True, scale=1000.0)
    result["balance_action"]     = _read_bool(frame, 172)

    if len(frame) > 173:
        result["soc"] = frame[173]
    result["remaining_capacity"] = _read_int_le(frame, 174, 4, signed=True, scale=1000.0)
    result["total_capacity"]     = _read_int_le(frame, 178, 4, signed=True, scale=1000.0)
    result["cycle_count"]        = _read_int_le(frame, 182, 4, signed=True, scale=1.0)
    result["cycle_capacity"]     = _read_int_le(frame, 186, 4, signed=True, scale=100.0)
    if len(frame) > 190:
        result["soh"] = frame[190]
    result["total_runtime"]      = _read_int_le(frame, 194, 4, signed=False, scale=1.0)

    result["charge_switch"]      = _read_bool(frame, 198)
    result["discharge_switch"]   = _read_bool(frame, 199)
    result["balance_switch"]     = _read_bool(frame, 200)
    result["pack_voltage"]       = _read_int_le(frame, 234, 2, signed=False, scale=100.0)

    return result


# ---------------------------------------------------------------------------
# Multi-unit RS485 bus-dump parsing
# ---------------------------------------------------------------------------

# Modbus request frame: [battery_id] 0x10 0x16 0x20 [data...]
# Bytes 1-2 identify the frame as Modbus; byte 3 = 0x20 marks it as a master
# request (which sets current_battery_id). Response frames also match bytes 1-2
# but have a different type byte and must NOT update current_battery_id.
_MODBUS_PATTERN = b'\x10\x16'
_MODBUS_REQUEST_TYPE = 0x20


def _find_next_bus_frame(data: bytes, pos: int = 0):
    """Return (position, kind) of the next Modbus request or data frame, or (-1, None)."""
    data_pos = data.find(JKBMS_FRAME_HEADER, pos)

    modbus_pos = -1
    for i in range(pos, len(data) - 3):
        if data[i + 1:i + 3] == _MODBUS_PATTERN and data[i + 3] == _MODBUS_REQUEST_TYPE:
            modbus_pos = i
            break

    if data_pos >= 0 and (modbus_pos < 0 or data_pos <= modbus_pos):
        return data_pos, "data"
    elif modbus_pos >= 0:
        return modbus_pos, "modbus"
    return -1, None


def parse_jkbms_bus_dump(
    data: bytes,
    cells_per_bms: int = 16,
) -> Optional[Dict[str, Any]]:
    """
    Parse a raw RS485 bus dump that may contain frames from multiple JK BMS units.

    Handles both:
    - Pure broadcast dumps (only ``55 AA EB 90`` data frames)
    - Master-polled dumps (Modbus request frames interleaved with data frames)

    For single-unit dumps this is equivalent to ``parse_jkbms_status_frame()``.
    For multi-unit dumps it returns an aggregated dict with ``battery_units``
    and ``battery_cells`` in Pylontech-compatible format so redis_cache.py and
    the frontend display all units correctly.

    Args:
        data: Raw bytes from the RS485 bus (may span multiple frames).
        cells_per_bms: Number of cells per BMS unit.

    Returns:
        Aggregated dict or None if no valid frames found.
    """
    batteries: Dict[int, Dict] = {}
    current_battery_id = 0
    pos = 0

    while pos < len(data):
        next_pos, kind = _find_next_bus_frame(data, pos)
        if next_pos < 0:
            break

        if kind == "modbus":
            # First byte is battery_id; bytes 1-2 are 0x10 0x16
            battery_id = data[next_pos]
            if battery_id == 15:   # JK wraparound quirk
                battery_id = 0
            current_battery_id = battery_id
            pos = next_pos + 1

        elif kind == "data":
            slice_data = data[next_pos:]
            # Find end of this frame (start of next header or end of buffer)
            next_header = slice_data.find(JKBMS_FRAME_HEADER, 4)
            frame_bytes = slice_data[:next_header] if next_header > 0 else slice_data

            parsed = parse_jkbms_status_frame(frame_bytes, cells_per_bms)
            if parsed:
                b_id = current_battery_id
                if b_id not in batteries:
                    batteries[b_id] = {}
                batteries[b_id].update(parsed)

            pos = next_pos + (next_header if next_header > 0 else len(slice_data))
        else:
            pos = next_pos + 1

    if not batteries:
        # Fallback: try treating the whole blob as a single frame
        return parse_jkbms_status_frame(data, cells_per_bms)

    if len(batteries) == 1:
        # Single unit — return as-is for backward compat
        return list(batteries.values())[0]

    # Multiple units — aggregate bank-level scalars and build structured lists
    sorted_ids = sorted(batteries.keys())
    parsed_units = [batteries[bid] for bid in sorted_ids]

    result = dict(parsed_units[0])  # base from first unit

    soc_vals = [u['soc'] for u in parsed_units if 'soc' in u]
    if soc_vals:
        result['soc'] = sum(soc_vals) // len(soc_vals)   # average SOC for parallel pack

    current_vals = [u['current'] for u in parsed_units if 'current' in u]
    if current_vals:
        result['current'] = sum(current_vals)  # parallel pack: sum currents

    power_vals = [u['power'] for u in parsed_units if 'power' in u]
    if power_vals:
        result['power'] = sum(power_vals)

    remaining_vals = [u['remaining_capacity'] for u in parsed_units if 'remaining_capacity' in u]
    if remaining_vals:
        result['remaining_capacity'] = sum(remaining_vals)

    total_vals = [u['total_capacity'] for u in parsed_units if 'total_capacity' in u]
    if total_vals:
        result['total_capacity'] = sum(total_vals)

    # Build Pylontech-compatible battery_units and battery_cells
    battery_units = []
    battery_cells = []
    for unit_num, unit in enumerate(parsed_units, 1):
        entry: Dict[str, Any] = {"unit": unit_num}
        for dst, src in (
            ("voltage_v",    "pack_voltage"),
            ("current_a",    "current"),
            ("soc_pct",      "soc"),
            ("soh_pct",      "soh"),
            ("temp_c",       "temp1"),
            ("cycle_count",  "cycle_count"),
            ("remaining_ah", "remaining_capacity"),
            ("total_ah",     "total_capacity"),
        ):
            if src in unit and unit[src] is not None:
                entry[dst] = unit[src]
        if "voltage_v" in entry and "current_a" in entry:
            entry["power_w"] = round(entry["voltage_v"] * entry["current_a"], 1)
        battery_units.append(entry)

        for cell_idx, v in enumerate(unit.get("cell_voltages", []), 1):
            if v is not None:
                battery_cells.append({"unit": unit_num, "cell": cell_idx, "voltage_v": v})

    result["battery_units"] = battery_units
    result["battery_cells"] = battery_cells

    logger.info(
        f"JK BMS bus dump: {len(parsed_units)} units, {len(battery_cells)} cells total"
    )
    return result


# ---------------------------------------------------------------------------
# Stateful stream parser (reference approach)
# ---------------------------------------------------------------------------

class JKBMSStreamParser:
    """
    Stateful JK BMS RS485 stream parser.

    Accumulates raw bytes across multiple poll cycles and continuously
    parses frames from the byte stream.  Tracks ``current_battery_id``
    via Modbus request frames (``<battery_id> 0x10 0x16 0x20 ...``) which
    the JK BMS master controller emits before each unit's data frame,
    attributing each ``55 AA EB 90`` data frame to the correct unit.

    Unlike the stateless ``parse_jkbms_bus_dump()``, this class maintains
    per-unit state across polls so short byte chunks from the "dumb pipe"
    ESP32 accumulate into complete frames naturally.

    Cycle detection: when a ``battery_id`` that was already seen in a
    Modbus request re-appears as the lowest known id, a full RS485 bus
    cycle has completed.  After the first complete cycle the ``unit_count``
    property reflects how many units are on the bus.

    Usage::

        stream = JKBMSStreamParser(cells_per_bms=16)

        # On each poll, feed new bytes from the ESP32:
        stream.feed(raw_bytes)
        result = stream.get_result()   # None until first frame parsed
    """

    def __init__(self, cells_per_bms: int = 16) -> None:
        self._cells_per_bms = cells_per_bms
        self._buffer: bytes = b""
        self._current_battery_id: int = 0
        self._batteries: Dict[int, Dict[str, Any]] = {}
        self._known_ids: set = set()       # unit IDs seen in the current cycle
        self._unit_count: Optional[int] = None
        self._cycle_count: int = 0

    def feed(self, data: bytes) -> None:
        """Append raw bytes and parse all complete frames found."""
        self._buffer += data
        self._process()

    def _process(self) -> None:
        pos = 0
        while pos < len(self._buffer):
            next_pos, kind = _find_next_bus_frame(self._buffer, pos)
            if next_pos < 0:
                break

            if kind == "modbus":
                battery_id = self._buffer[next_pos]
                if battery_id == 15:   # JK wraparound quirk
                    battery_id = 0

                # Cycle detection: re-seeing the lowest known id means a new
                # cycle has started — record how many units the previous cycle had.
                if self._known_ids and battery_id in self._known_ids and battery_id == min(self._known_ids):
                    self._unit_count = len(self._known_ids)
                    self._cycle_count += 1
                    self._known_ids = set()
                    logger.debug(
                        f"JK BMS stream: cycle {self._cycle_count} complete, "
                        f"{self._unit_count} unit(s) on bus"
                    )

                self._known_ids.add(battery_id)
                self._current_battery_id = battery_id
                pos = next_pos + 1

            elif kind == "data":
                slice_data = self._buffer[next_pos:]
                next_header = slice_data.find(JKBMS_FRAME_HEADER, 4)
                if next_header < 0:
                    # Frame is incomplete — keep from here and wait for more bytes
                    pos = next_pos
                    break

                frame_bytes = slice_data[:next_header]
                parsed = parse_jkbms_status_frame(frame_bytes, self._cells_per_bms)
                if parsed:
                    b_id = self._current_battery_id
                    if b_id not in self._batteries:
                        logger.info(f"JK BMS stream: unit {b_id} discovered")
                    self._batteries[b_id] = parsed

                pos = next_pos + next_header

            else:
                pos = next_pos + 1

        # Discard consumed bytes; keep only unprocessed tail
        self._buffer = self._buffer[pos:]

        # Safety cap: prevent unbounded growth if framing is consistently broken
        if len(self._buffer) > 8192:
            self._buffer = self._buffer[-4096:]
            logger.warning("JK BMS stream buffer trimmed (framing issue?)")

    def get_result(self) -> Optional[Dict[str, Any]]:
        """
        Return aggregated telemetry from all discovered units.

        Returns None if no frames have been parsed yet.
        """
        if not self._batteries:
            return None

        if len(self._batteries) == 1:
            return dict(list(self._batteries.values())[0])

        # Multi-unit: aggregate bank-level scalars + build structured lists
        sorted_ids = sorted(self._batteries.keys())
        parsed_units = [self._batteries[bid] for bid in sorted_ids]

        result = dict(parsed_units[0])

        for key, agg in (
            ("soc",                lambda vs: sum(vs) // len(vs)),  # average SOC
            ("current",            sum),
            ("power",              sum),
            ("remaining_capacity", sum),
            ("total_capacity",     sum),
        ):
            vals = [u[key] for u in parsed_units if key in u and u[key] is not None]
            if vals:
                result[key] = agg(vals)

        battery_units: List[Dict[str, Any]] = []
        battery_cells: List[Dict[str, Any]] = []
        for unit_num, unit in enumerate(parsed_units, 1):
            entry: Dict[str, Any] = {"unit": unit_num}
            for dst, src in (
                ("voltage_v",    "pack_voltage"),
                ("current_a",    "current"),
                ("soc_pct",      "soc"),
                ("soh_pct",      "soh"),
                ("temp_c",       "temp1"),
                ("cycle_count",  "cycle_count"),
                ("remaining_ah", "remaining_capacity"),
                ("total_ah",     "total_capacity"),
            ):
                if src in unit and unit[src] is not None:
                    entry[dst] = unit[src]
            if "voltage_v" in entry and "current_a" in entry:
                entry["power_w"] = round(entry["voltage_v"] * entry["current_a"], 1)
            battery_units.append(entry)

            for cell_idx, v in enumerate(unit.get("cell_voltages", []), 1):
                if v is not None:
                    battery_cells.append({"unit": unit_num, "cell": cell_idx, "voltage_v": v})

        result["battery_units"] = battery_units
        result["battery_cells"] = battery_cells

        logger.debug(
            f"JK BMS stream result: {len(parsed_units)} units, "
            f"{len(battery_cells)} cells, cycle={self._cycle_count}"
        )
        return result

    @property
    def unit_count(self) -> Optional[int]:
        """Units discovered on the bus (None until first complete cycle)."""
        return self._unit_count

    @property
    def cycle_count(self) -> int:
        """Number of complete RS485 bus cycles parsed so far."""
        return self._cycle_count


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
        # Prefer battery_cells (multi-unit, unit-tagged) over cell_voltages (single-unit)
        battery_cells: List = telemetry_data.get("battery_cells", [])
        if battery_cells:
            total_cells = 0
            for cell_info in battery_cells:
                unit_num = cell_info.get("unit", 1)
                cell_num = cell_info.get("cell")
                voltage = cell_info.get("voltage_v")
                if cell_num is None or voltage is None:
                    continue
                try:
                    metrics.append(TelemetryMetric(
                        time=timestamp,
                        device_id=device_id,
                        site_id=site_id,
                        metric_name=f"battery_unit_{unit_num}_cell_{cell_num}_voltage_v",
                        metric_value=float(voltage),
                        quality="good",
                        unit="V",
                        source="telemetry",
                        tags={"category": "battery_cell", "unit": unit_num, "cell": cell_num},
                    ))
                    total_cells += 1
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert unit {unit_num} cell {cell_num} voltage={voltage}")
            logger.debug(
                f"Parsed {len(metrics)} metrics from JK BMS telemetry "
                f"(device {device_id}, {total_cells} cells across multi-unit)"
            )
        else:
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
