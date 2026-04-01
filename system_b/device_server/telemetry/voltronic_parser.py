"""
Voltronic inverter telemetry parser.

Two families, two classes — do NOT unify them.  PI30 and PI18 have different
field counts, different value encodings (PI18 uses integer×10 for V/Hz), and
different battery-direction semantics.  The adapter stores 'voltronic_protocol_id'
('PI30' or 'PI18') in the telemetry dict; timescale_writer selects the right parser.

Protocol family reference:
  PI30 — Axpert / PIP / MKS series (21-field QPIGS, separate charge/discharge amps)
  PI18 — Axpert Max / InfiniSolar  (28-field GS, dual-MPPT, battery direction flags)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from .parser import TelemetryParser, TelemetryMetric

logger = logging.getLogger(__name__)

# QPIWS warning/fault bit positions (0-indexed from left, same for both families).
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
}


class VoltronicPI30Parser(TelemetryParser):
    """
    Parser for Voltronic PI30-family inverters.

    Axpert / PIP / MKS series.  QPIGS returns 21 space-separated fields.
    Battery convention: positive_discharging (positive W = discharging).
    Adapter computes battery_power_w from charging/discharge amps.
    """

    # Flat telemetry key → (metric_name, unit, category)
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

        # --- Numeric metrics ---
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

        # --- Working mode (QMOD single char → numeric + string) ---
        mode_raw = telemetry_data.get("working_mode_raw", "")
        if mode_raw:
            mode_str = _PI30_MODES.get(mode_raw[:1].upper(), "unknown")
            _m("working_mode_raw", 0.0, "", "status", value_str=mode_str)

        # --- Warning / fault flags (QPIWS 32-char bit string) ---
        piws = telemetry_data.get("warning_status_raw", "")
        if len(piws) >= 30:
            for bit_idx, flag_name in _PIWS_FLAGS:
                if bit_idx < len(piws):
                    _m(flag_name, 1.0 if piws[bit_idx] == "1" else 0.0, "bool", "fault")

        logger.debug(
            "VoltronicPI30: %d metrics parsed for device %s", len(metrics), device_id
        )
        return metrics


class VoltronicPI18Parser(TelemetryParser):
    """
    Parser for Voltronic PI18-family inverters.

    Axpert Max / InfiniSolar series.  GS query returns 28 fields.
    PI18 has dual MPPT, separate MPPT temperatures, and integer×10 encoding
    for all V/Hz fields.  Status fields 20-26 are discrete option codes.
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

        # --- Numeric metrics ---
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

        # --- Total PV (sum of dual MPPT) ---
        pv1 = telemetry_data.get("pv1_input_power_w")
        pv2 = telemetry_data.get("pv2_input_power_w")
        if pv1 is not None or pv2 is not None:
            _m("pv_total_w", (pv1 or 0.0) + (pv2 or 0.0), "W", "power")

        # --- Battery direction flag (field 24: 0=idle, 1=charging, 2=discharging) ---
        bat_dir = telemetry_data.get("battery_power_direction")
        if bat_dir is not None:
            _m("battery_direction_raw", float(bat_dir), "", "status")

        # --- Working mode ---
        mode_raw = telemetry_data.get("working_mode_raw", "")
        if mode_raw:
            # PI18 MOD returns text like "Battery mode" — store first char for consistency
            mode_str = mode_raw[:1].upper()
            label = _PI30_MODES.get(mode_str, mode_raw)
            _m("working_mode_raw", 0.0, "", "status", value_str=label)

        # --- Warning / fault flags ---
        piws = telemetry_data.get("warning_status_raw", "")
        if len(piws) >= 30:
            for bit_idx, flag_name in _PIWS_FLAGS:
                if bit_idx < len(piws):
                    _m(flag_name, 1.0 if piws[bit_idx] == "1" else 0.0, "bool", "fault")

        logger.debug(
            "VoltronicPI18: %d metrics parsed for device %s", len(metrics), device_id
        )
        return metrics
