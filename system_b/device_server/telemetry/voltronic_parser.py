"""
Voltronic inverter telemetry parser.

Four parser classes — one per protocol family.  Do NOT unify them.  Each family
has different field counts, encodings, and battery-direction semantics.

The adapter stores 'voltronic_protocol_id' in the telemetry dict; timescale_writer
selects the right parser via that key or by falling back to JSON structure.

Protocol family reference:
  PI30 — Axpert / PIP / MKS series (21-field QPIGS, separate charge/discharge A)
  PI18 — Axpert MAX / InfiniSolar MAX (28-field GS, dual-MPPT, int×10 encoding)
  PI16 — SUNNY (PI15/PI16) series (22-field QPIGS, 3 MPPT, PBUS/SBUS voltage)
  PI17 — InfiniSolar 5KW (SEC frame, comma-separated, 28 fields)
  PI34 — MPPT-3000 solar charge controller (11-field QPIGS, no AC I/O)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from .parser import TelemetryParser, TelemetryMetric

logger = logging.getLogger(__name__)

# QPIWS warning/fault bit positions (0-indexed from left, same for PI30/PI18).
# A '1' at that position means the condition is active.
_PIWS_FLAGS: List[tuple] = [
    (1,  "fault_inverter"),
    (2,  "fault_bus_over"),
    (3,  "fault_bus_under"),
    (4,  "fault_bus_soft_fail"),
    (5,  "warning_line_fail"),
    (6,  "warning_opv_short"),
    (7,  "fault_inverter_voltage_low"),
    (8,  "fault_inverter_voltage_high"),
    (9,  "fault_over_temperature"),
    (10, "fault_fan_locked"),
    (11, "fault_battery_voltage_high"),
    (12, "warning_battery_low_alarm"),
    (14, "warning_battery_under_shutdown"),
    (16, "fault_overload"),
    (17, "warning_eeprom_fault"),
    (18, "fault_inverter_over_current"),
    (19, "fault_inverter_soft_start_failed"),
    (20, "fault_self_test_failed"),
    (21, "fault_op_dc_voltage_over"),
    (22, "fault_battery_open"),
    (23, "fault_current_sensor_fail"),
    (24, "fault_battery_short"),
    (25, "warning_power_limit"),
    (26, "warning_pv_voltage_high"),
    (27, "fault_mppt_overload"),
    (28, "warning_mppt_overload"),
    (29, "warning_battery_too_low_to_charge"),
]

# QMOD / PI18 MOD single-char working-mode values
_PI30_MODES: Dict[str, str] = {
    "P": "power_on",
    "S": "standby",
    "L": "line",
    "B": "battery",
    "F": "fault",
    "H": "power_saving",
    "Y": "bypass",
    "D": "shutdown",
    "G": "grid",
    "C": "bypass_with_pv_charging",
    "T": "test",
}


def _build_metric(
    metrics: List[TelemetryMetric],
    timestamp: datetime,
    device_id: UUID,
    site_id: UUID,
    name: str,
    value: float,
    unit: str,
    category: str,
    value_str: Optional[str] = None,
) -> None:
    metrics.append(TelemetryMetric(
        time=timestamp,
        device_id=device_id,
        site_id=site_id,
        metric_name=name,
        metric_value=float(value),
        metric_value_str=value_str,
        quality="good",
        unit=unit,
        source="telemetry",
        tags={"category": category},
    ))


def _emit_piws_flags(
    metrics: List[TelemetryMetric],
    piws: str,
    timestamp: datetime,
    device_id: UUID,
    site_id: UUID,
) -> None:
    """Emit one boolean metric per QPIWS bit position."""
    if len(piws) < 30:
        return
    for bit_idx, flag_name in _PIWS_FLAGS:
        if bit_idx < len(piws):
            _build_metric(
                metrics, timestamp, device_id, site_id,
                flag_name,
                1.0 if piws[bit_idx] == "1" else 0.0,
                "bool", "fault",
            )


class VoltronicPI30Parser(TelemetryParser):
    """
    Parser for Voltronic PI30-family inverters.

    Axpert / PIP / MKS / HS / MSX / REVO / PI41 / PI30MAX series.
    QPIGS returns 21 space-separated fields; shorter variants (17 fields) are
    handled gracefully — missing high-index fields are silently ignored.
    Battery convention: positive_discharging (positive W = discharging).
    Adapter computes battery_power_w from charging/discharge amps.
    """

    METRIC_MAPPINGS: List[tuple] = [
        # Grid
        ("grid_voltage_v",              ("grid_voltage_v",              "V",   "grid")),
        ("grid_frequency_hz",           ("grid_frequency_hz",           "Hz",  "grid")),
        # AC output (load side)
        ("ac_output_voltage_v",         ("ac_output_voltage_v",         "V",   "output")),
        ("ac_output_frequency_hz",      ("ac_output_frequency_hz",      "Hz",  "output")),
        ("ac_output_apparent_va",       ("ac_output_apparent_va",       "VA",  "output")),
        ("ac_output_active_w",          ("load_power_w",                "W",   "power")),
        ("output_load_pct",             ("output_load_pct",             "%",   "output")),
        # Bus
        ("bus_voltage_v",               ("bus_voltage_v",               "V",   "power")),
        # Battery
        ("battery_voltage_v",           ("battery_voltage_v",           "V",   "battery")),
        ("battery_charging_current_a",  ("battery_charging_current_a",  "A",   "battery")),
        ("battery_capacity_pct",        ("battery_soc_pct",             "%",   "battery")),
        ("battery_discharge_current_a", ("battery_discharge_current_a", "A",   "battery")),
        ("battery_power_w",             ("battery_w",                   "W",   "power")),
        # Temperatures
        ("heatsink_temp_c",             ("inverter_temp_c",             "C",   "temperature")),
        # PV (single MPPT string on PI30)
        ("pv_input_current_a",          ("pv1_current_a",               "A",   "pv")),
        ("pv_input_voltage_v",          ("pv1_voltage_v",               "V",   "pv")),
        ("pv_input_power_w",            ("pv1_power_w",                 "W",   "power")),
        # Grid power (computed by adapter from energy balance)
        ("grid_power_w",                ("grid_power_w",                "W",   "power")),
        # QPIRI settings (polled every ~5 min; absent on telemetry-only polls)
        ("battery_bulk_voltage_v",      ("cfg_battery_bulk_v",          "V",   "config")),
        ("battery_float_voltage_v",     ("cfg_battery_float_v",         "V",   "config")),
        ("battery_under_voltage_v",     ("cfg_battery_under_v",         "V",   "config")),
        ("battery_recharge_voltage_v",  ("cfg_battery_recharge_v",      "V",   "config")),
        ("charging_current_a",          ("cfg_max_charging_a",          "A",   "config")),
        ("ac_charging_current_a",       ("cfg_max_ac_charging_a",       "A",   "config")),
        ("output_source_priority",      ("cfg_output_priority",         "",    "config")),
        ("charger_source_priority",     ("cfg_charger_priority",        "",    "config")),
        ("battery_type_code",           ("cfg_battery_type",            "",    "config")),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        metrics: List[TelemetryMetric] = []

        def _m(name: str, value: float, unit: str, category: str,
               value_str: Optional[str] = None) -> None:
            _build_metric(metrics, timestamp, device_id, site_id,
                          name, value, unit, category, value_str)

        # Numeric metrics
        for key, (metric_name, unit, category) in self.METRIC_MAPPINGS:
            raw = telemetry_data.get(key)
            if raw is None:
                continue
            try:
                _m(metric_name, raw, unit, category)
            except (ValueError, TypeError):
                logger.warning(
                    "VoltronicPI30: cannot convert %s=%r to float, skipping", key, raw
                )

        # Working mode (QMOD single char → numeric + string)
        mode_raw = telemetry_data.get("working_mode_raw", "")
        if mode_raw:
            mode_str = _PI30_MODES.get(mode_raw[:1].upper(), "unknown")
            _m("working_mode_raw", 0.0, "", "status", value_str=mode_str)

        # Warning / fault flags (QPIWS 32-char bit string)
        _emit_piws_flags(metrics, telemetry_data.get("warning_status_raw", ""),
                         timestamp, device_id, site_id)

        logger.debug(
            "VoltronicPI30: %d metrics parsed for device %s", len(metrics), device_id
        )
        return metrics


class VoltronicPI18Parser(TelemetryParser):
    """
    Parser for Voltronic PI18-family inverters (Axpert MAX / InfiniSolar MAX).

    GS query returns 28 space-separated fields with integer×10 encoding for
    all V/Hz values.  Dual MPPT strings with separate temperatures.
    Status fields 20-26 are discrete option codes, not bit flags.
    Battery direction: field 24 (0=idle, 1=charging, 2=discharging).
    Battery convention: positive_discharging.
    """

    METRIC_MAPPINGS: List[tuple] = [
        # Grid
        ("grid_voltage_v",              ("grid_voltage_v",              "V",   "grid")),
        ("grid_frequency_hz",           ("grid_frequency_hz",           "Hz",  "grid")),
        # AC output
        ("ac_output_voltage_v",         ("ac_output_voltage_v",         "V",   "output")),
        ("ac_output_frequency_hz",      ("ac_output_frequency_hz",      "Hz",  "output")),
        ("ac_output_apparent_va",       ("ac_output_apparent_va",       "VA",  "output")),
        ("ac_output_active_w",          ("load_power_w",                "W",   "power")),
        ("output_load_pct",             ("output_load_pct",             "%",   "output")),
        # Battery
        ("battery_voltage_v",           ("battery_voltage_v",           "V",   "battery")),
        ("battery_capacity_pct",        ("battery_soc_pct",             "%",   "battery")),
        ("battery_charging_current_a",  ("battery_charging_current_a",  "A",   "battery")),
        ("battery_discharge_current_a", ("battery_discharge_current_a", "A",   "battery")),
        ("battery_power_w",             ("battery_w",                   "W",   "power")),
        # Temperatures (PI18 has separate MPPT temps)
        ("heatsink_temp_c",             ("inverter_temp_c",             "C",   "temperature")),
        ("mppt1_temp_c",                ("mppt1_temp_c",                "C",   "temperature")),
        ("mppt2_temp_c",                ("mppt2_temp_c",                "C",   "temperature")),
        # PV (dual MPPT)
        ("pv1_input_power_w",           ("pv1_power_w",                 "W",   "power")),
        ("pv2_input_power_w",           ("pv2_power_w",                 "W",   "power")),
        ("pv1_input_voltage_v",         ("pv1_voltage_v",               "V",   "pv")),
        ("pv2_input_voltage_v",         ("pv2_voltage_v",               "V",   "pv")),
        # Grid power (computed)
        ("grid_power_w",                ("grid_power_w",                "W",   "power")),
        # QPIRI settings (polled every ~5 min)
        ("battery_bulk_voltage_v",      ("cfg_battery_bulk_v",          "V",   "config")),
        ("battery_float_voltage_v",     ("cfg_battery_float_v",         "V",   "config")),
        ("battery_under_voltage_v",     ("cfg_battery_under_v",         "V",   "config")),
        ("battery_recharge_voltage_v",  ("cfg_battery_recharge_v",      "V",   "config")),
        ("charging_current_a",          ("cfg_max_charging_a",          "A",   "config")),
        ("ac_charging_current_a",       ("cfg_max_ac_charging_a",       "A",   "config")),
        ("output_source_priority",      ("cfg_output_priority",         "",    "config")),
        ("charger_source_priority",     ("cfg_charger_priority",        "",    "config")),
        ("battery_type_code",           ("cfg_battery_type",            "",    "config")),
        ("battery_recharge_when_soc",   ("cfg_recharge_when_soc_pct",   "%",   "config")),
        ("battery_recharge_to_soc",     ("cfg_recharge_to_soc_pct",     "%",   "config")),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        metrics: List[TelemetryMetric] = []

        def _m(name: str, value: float, unit: str, category: str,
               value_str: Optional[str] = None) -> None:
            _build_metric(metrics, timestamp, device_id, site_id,
                          name, value, unit, category, value_str)

        # Numeric metrics
        for key, (metric_name, unit, category) in self.METRIC_MAPPINGS:
            raw = telemetry_data.get(key)
            if raw is None:
                continue
            try:
                _m(metric_name, raw, unit, category)
            except (ValueError, TypeError):
                logger.warning(
                    "VoltronicPI18: cannot convert %s=%r to float, skipping", key, raw
                )

        # Total PV (sum of dual MPPT)
        pv1 = telemetry_data.get("pv1_input_power_w")
        pv2 = telemetry_data.get("pv2_input_power_w")
        if pv1 is not None or pv2 is not None:
            _m("pv_total_w", (pv1 or 0.0) + (pv2 or 0.0), "W", "power")

        # Battery direction flag (0=idle, 1=charging, 2=discharging)
        bat_dir = telemetry_data.get("battery_power_direction")
        if bat_dir is not None:
            _m("battery_direction_raw", float(bat_dir), "", "status")

        # Working mode
        mode_raw = telemetry_data.get("working_mode_raw", "")
        if mode_raw:
            mode_str = mode_raw[:1].upper()
            label = _PI30_MODES.get(mode_str, mode_raw)
            _m("working_mode_raw", 0.0, "", "status", value_str=label)

        # Warning / fault flags
        _emit_piws_flags(metrics, telemetry_data.get("warning_status_raw", ""),
                         timestamp, device_id, site_id)

        logger.debug(
            "VoltronicPI18: %d metrics parsed for device %s", len(metrics), device_id
        )
        return metrics


class VoltronicPI16Parser(TelemetryParser):
    """
    Parser for Voltronic PI16/PI15 SUNNY-family inverters.

    QPIGS returns 22 space-separated fields.  Key differences from PI30:
    - Field 1 is total output power (W) directly, not VA
    - Up to 3 MPPT strings (PV1/PV2/PV3 power and voltage)
    - PBUS and SBUS voltage instead of single bus voltage
    - No separate battery charge/discharge current; direction comes from status bits
    - 9-bit status string (V + WWWWWWWWW)

    Battery convention: positive_discharging.
    grid_power_w is computed from load - PV_total - battery_net.
    For SUNNY devices that are grid-tie, battery may always read 0.
    """

    # Fields with "---.-" or "-----" placeholder are emitted as None by adapter
    METRIC_MAPPINGS: List[tuple] = [
        # Grid
        ("grid_voltage_v",          ("grid_voltage_v",          "V",    "grid")),
        ("grid_frequency_hz",       ("grid_frequency_hz",       "Hz",   "grid")),
        # AC output
        ("ac_output_active_w",      ("load_power_w",            "W",    "power")),
        ("ac_output_current_a",     ("ac_output_current_a",     "A",    "output")),
        ("ac_output_voltage_v",     ("ac_output_voltage_v",     "V",    "output")),
        ("ac_output_frequency_hz",  ("ac_output_frequency_hz",  "Hz",   "output")),
        ("output_load_pct",         ("output_load_pct",         "%",    "output")),
        # Bus
        ("pbus_voltage_v",          ("pbus_voltage_v",          "V",    "power")),
        ("sbus_voltage_v",          ("sbus_voltage_v",          "V",    "power")),
        # Battery (no current — only voltage, SoC, derived power)
        ("battery_voltage_v",       ("battery_voltage_v",       "V",    "battery")),
        ("battery_capacity_pct",    ("battery_soc_pct",         "%",    "battery")),
        ("battery_power_w",         ("battery_w",               "W",    "power")),
        # PV strings (up to 3)
        ("pv1_input_power_w",       ("pv1_power_w",             "W",    "power")),
        ("pv2_input_power_w",       ("pv2_power_w",             "W",    "power")),
        ("pv3_input_power_w",       ("pv3_power_w",             "W",    "power")),
        ("pv1_input_voltage_v",     ("pv1_voltage_v",           "V",    "pv")),
        ("pv2_input_voltage_v",     ("pv2_voltage_v",           "V",    "pv")),
        ("pv3_input_voltage_v",     ("pv3_voltage_v",           "V",    "pv")),
        # Temperature
        ("max_temp_c",              ("inverter_temp_c",         "C",    "temperature")),
        # Derived
        ("grid_power_w",            ("grid_power_w",            "W",    "power")),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        metrics: List[TelemetryMetric] = []

        def _m(name: str, value: float, unit: str, category: str,
               value_str: Optional[str] = None) -> None:
            _build_metric(metrics, timestamp, device_id, site_id,
                          name, value, unit, category, value_str)

        # Numeric metrics
        for key, (metric_name, unit, category) in self.METRIC_MAPPINGS:
            raw = telemetry_data.get(key)
            if raw is None:
                continue
            try:
                _m(metric_name, raw, unit, category)
            except (ValueError, TypeError):
                logger.warning(
                    "VoltronicPI16: cannot convert %s=%r to float, skipping", key, raw
                )

        # Total PV power (sum of up to 3 strings)
        pv_total = sum(
            telemetry_data.get(k) or 0.0
            for k in ("pv1_input_power_w", "pv2_input_power_w", "pv3_input_power_w")
        )
        if pv_total > 0:
            _m("pv_total_w", pv_total, "W", "power")

        # Battery direction from status bits (bits 4-3):
        #   00 = not connected, 01 = charging, 10 = discharging
        status_raw = telemetry_data.get("device_status_raw", "")
        if len(status_raw) >= 5:
            bat_bits = status_raw[4:6]  # chars at index 4 and 5 (0-indexed from V at 0)
            # The status string is: VWWWWWWWWW where V=unknown, W=9 status bits
            # Position 0=unknown, then bit8..bit0 of status
            # Bits 4-3 (0-indexed from left of the 9 status bits = positions 5 and 6 in full string)
            bat_dir_bits = status_raw[5:7] if len(status_raw) >= 7 else ""
            if bat_dir_bits == "01":
                _m("battery_direction_raw", 1.0, "", "status", value_str="charging")
            elif bat_dir_bits == "10":
                _m("battery_direction_raw", 2.0, "", "status", value_str="discharging")

        # Working mode
        mode_raw = telemetry_data.get("working_mode_raw", "")
        if mode_raw:
            mode_str = _PI30_MODES.get(mode_raw[:1].upper(), "unknown")
            _m("working_mode_raw", 0.0, "", "status", value_str=mode_str)

        # PI16 uses a longer QPIWS string but same bit semantics for common bits
        _emit_piws_flags(metrics, telemetry_data.get("warning_status_raw", ""),
                         timestamp, device_id, site_id)

        logger.debug(
            "VoltronicPI16: %d metrics parsed for device %s", len(metrics), device_id
        )
        return metrics


class VoltronicPI17Parser(TelemetryParser):
    """
    Parser for Voltronic PI17 InfiniSolar 5KW.

    Uses SEC frame format: responses are ^DnnnFIELD,...<CRC><cr> with
    comma-separated values.  The adapter stores parsed fields as a flat dict
    before this parser runs (same as other parsers).

    Field encoding: solar voltages/currents in 0.1-unit steps; battery current
    signed (positive = charging).
    Battery convention: positive_charging (opposite of PI30!).
    """

    METRIC_MAPPINGS: List[tuple] = [
        # PV strings (dual MPPT; fields in 0.1V and 0.1A units, pre-divided by adapter)
        ("pv1_input_voltage_v",         ("pv1_voltage_v",               "V",   "pv")),
        ("pv1_input_current_a",         ("pv1_current_a",               "A",   "pv")),
        ("pv1_input_power_w",           ("pv1_power_w",                 "W",   "power")),
        ("pv2_input_voltage_v",         ("pv2_voltage_v",               "V",   "pv")),
        ("pv2_input_current_a",         ("pv2_current_a",               "A",   "pv")),
        ("pv2_input_power_w",           ("pv2_power_w",                 "W",   "power")),
        # Battery (0.01V units pre-divided; current signed: +charging, −discharging)
        ("battery_voltage_v",           ("battery_voltage_v",           "V",   "battery")),
        ("battery_current_a",           ("battery_current_a",           "A",   "battery")),
        ("battery_capacity_pct",        ("battery_soc_pct",             "%",   "battery")),
        ("battery_power_w",             ("battery_w",                   "W",   "power")),
        # AC output
        ("ac_output_voltage_v",         ("ac_output_voltage_v",         "V",   "output")),
        ("ac_output_frequency_hz",      ("ac_output_frequency_hz",      "Hz",  "output")),
        ("ac_output_current_a",         ("ac_output_current_a",         "A",   "output")),
        ("ac_output_apparent_va",       ("ac_output_apparent_va",       "VA",  "output")),
        ("ac_output_active_w",          ("load_power_w",                "W",   "power")),
        ("output_load_pct",             ("output_load_pct",             "%",   "output")),
        # Temperatures
        ("heatsink_temp_c",             ("inverter_temp_c",             "C",   "temperature")),
        ("battery_temp_c",              ("battery_temp_c",              "C",   "temperature")),
        # Grid power (computed)
        ("grid_power_w",                ("grid_power_w",                "W",   "power")),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        metrics: List[TelemetryMetric] = []

        def _m(name: str, value: float, unit: str, category: str,
               value_str: Optional[str] = None) -> None:
            _build_metric(metrics, timestamp, device_id, site_id,
                          name, value, unit, category, value_str)

        for key, (metric_name, unit, category) in self.METRIC_MAPPINGS:
            raw = telemetry_data.get(key)
            if raw is None:
                continue
            try:
                _m(metric_name, raw, unit, category)
            except (ValueError, TypeError):
                logger.warning(
                    "VoltronicPI17: cannot convert %s=%r to float, skipping", key, raw
                )

        # Total PV power
        pv_total = (telemetry_data.get("pv1_input_power_w") or 0.0) + \
                   (telemetry_data.get("pv2_input_power_w") or 0.0)
        if pv_total > 0:
            _m("pv_total_w", pv_total, "W", "power")

        # Working mode
        mode_raw = telemetry_data.get("working_mode_raw", "")
        if mode_raw:
            mode_str = _PI30_MODES.get(mode_raw[:1].upper(), "unknown")
            _m("working_mode_raw", 0.0, "", "status", value_str=mode_str)

        _emit_piws_flags(metrics, telemetry_data.get("warning_status_raw", ""),
                         timestamp, device_id, site_id)

        logger.debug(
            "VoltronicPI17: %d metrics parsed for device %s", len(metrics), device_id
        )
        return metrics


class VoltronicPI34Parser(TelemetryParser):
    """
    Parser for Voltronic PI34 MPPT-3000 solar charge controller.

    This is NOT a hybrid inverter — it is a standalone MPPT solar charge
    controller with no AC grid input or AC load output.  Device type: charger.

    QPIGS returns 11 space-separated fields:
    (PV_V  BAT_V  CHG_A_total  CHG_A1  CHG_A2  CHG_W  TEMP  RBAT_V  RBAT_T  RSV  STATUS

    Temperatures and battery currents may be signed integers.
    """

    METRIC_MAPPINGS: List[tuple] = [
        ("pv_input_voltage_v",          ("pv1_voltage_v",                   "V",    "pv")),
        ("battery_voltage_v",           ("battery_voltage_v",               "V",    "battery")),
        ("charging_current_a",          ("battery_charging_current_a",      "A",    "battery")),
        ("charging_current1_a",         ("battery_charging_current1_a",     "A",    "battery")),
        ("charging_current2_a",         ("battery_charging_current2_a",     "A",    "battery")),
        ("charging_power_w",            ("battery_charging_power_w",        "W",    "power")),
        ("unit_temp_c",                 ("inverter_temp_c",                 "C",    "temperature")),
        ("remote_battery_voltage_v",    ("remote_battery_voltage_v",        "V",    "battery")),
        ("remote_battery_temp_c",       ("remote_battery_temp_c",           "C",    "temperature")),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        metrics: List[TelemetryMetric] = []

        def _m(name: str, value: float, unit: str, category: str,
               value_str: Optional[str] = None) -> None:
            _build_metric(metrics, timestamp, device_id, site_id,
                          name, value, unit, category, value_str)

        for key, (metric_name, unit, category) in self.METRIC_MAPPINGS:
            raw = telemetry_data.get(key)
            if raw is None:
                continue
            try:
                _m(metric_name, raw, unit, category)
            except (ValueError, TypeError):
                logger.warning(
                    "VoltronicPI34: cannot convert %s=%r to float, skipping", key, raw
                )

        # Charging efficiency proxy: if we have both PV voltage and charging power
        pv_v = telemetry_data.get("pv_input_voltage_v")
        chg_w = telemetry_data.get("charging_power_w")
        if pv_v and chg_w:
            # Derive PV current from P=VI
            bat_v = telemetry_data.get("battery_voltage_v", 0)
            if bat_v > 0:
                _m("pv1_power_w", float(chg_w), "W", "power")

        # Warning / fault status
        _emit_piws_flags(metrics, telemetry_data.get("warning_status_raw", ""),
                         timestamp, device_id, site_id)

        logger.debug(
            "VoltronicPI34: %d metrics parsed for device %s", len(metrics), device_id
        )
        return metrics
