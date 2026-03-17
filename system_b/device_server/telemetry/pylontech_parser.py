"""
Pylontech / Pytes battery telemetry parser.

Extracts normalized metrics from Pylontech/Pytes battery telemetry.
The flat telemetry dict contains bank-level scalars plus JSON-encoded
per-unit and per-cell arrays produced by the PytesBatteryAdapter.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from .parser import TelemetryParser, TelemetryMetric

logger = logging.getLogger(__name__)


class PylontechParser(TelemetryParser):
    """
    Parser for Pylontech / Pytes battery telemetry.

    Handles bank-level metrics (SOC, voltage, current, power, temp, SOH, cycles)
    and per-unit metrics from the battery_units list.
    Cell-level data is stored as a JSON tag on the bank metric row.
    """

    # Bank-level scalar metric mappings: telemetry_key -> (metric_name, unit, category)
    BANK_METRIC_MAPPINGS: List[tuple] = [
        ("battery_soc_pct",      ("battery_soc_pct",      "%",  "battery")),
        ("battery_voltage_v",    ("battery_voltage_v",    "V",  "battery")),
        ("battery_current_a",    ("battery_current_a",    "A",  "battery")),
        ("battery_power_w",      ("battery_w",            "W",  "power")),
        ("battery_temp_c",       ("battery_temp_c",       "C",  "temperature")),
        ("battery_soh_pct",      ("battery_soh_pct",      "%",  "battery")),
        ("battery_cycle_count",  ("battery_cycle_count",  "",   "battery")),
        ("battery_units_count",  ("battery_units_count",  "",   "battery")),
    ]

    # Per-unit metric mappings: unit_dict_key -> (metric_name_template, unit, category)
    # metric_name_template uses {unit} as placeholder for unit number (1-indexed)
    UNIT_METRIC_MAPPINGS: List[tuple] = [
        ("voltage_v",   ("battery_unit_{unit}_voltage_v",  "V", "battery_unit")),
        ("current_a",   ("battery_unit_{unit}_current_a",  "A", "battery_unit")),
        ("power_w",     ("battery_unit_{unit}_power_w",    "W", "battery_unit")),
        ("soc_pct",     ("battery_unit_{unit}_soc_pct",    "%", "battery_unit")),
        ("temp_c",      ("battery_unit_{unit}_temp_c",     "C", "battery_unit")),
        ("soh_pct",     ("battery_unit_{unit}_soh_pct",    "%", "battery_unit")),
        ("cycle_count", ("battery_unit_{unit}_cycles",     "",  "battery_unit")),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        """
        Parse Pylontech battery telemetry into normalized metrics.

        Args:
            telemetry_data: Flat telemetry dict from Pylontech adapter.
            device_id: Device UUID.
            site_id: Site UUID.
            timestamp: Telemetry timestamp.

        Returns:
            List of TelemetryMetric objects.
        """
        metrics: List[TelemetryMetric] = []

        # --- Bank-level scalars ---
        for telemetry_key, (metric_name, unit, category) in self.BANK_METRIC_MAPPINGS:
            value = telemetry_data.get(telemetry_key)
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

        # --- Per-unit metrics ---
        units: List[Dict[str, Any]] = telemetry_data.get("battery_units", [])
        for unit_data in units:
            unit_num = unit_data.get("unit", 0)
            for dict_key, (name_tpl, unit_str, category) in self.UNIT_METRIC_MAPPINGS:
                value = unit_data.get(dict_key)
                if value is None:
                    continue
                try:
                    metrics.append(TelemetryMetric(
                        time=timestamp,
                        device_id=device_id,
                        site_id=site_id,
                        metric_name=name_tpl.format(unit=unit_num),
                        metric_value=float(value),
                        quality="good",
                        unit=unit_str,
                        source="telemetry",
                        tags={"category": category, "unit": unit_num},
                    ))
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert unit {unit_num} {dict_key}={value} to float"
                    )

            # Store alarm/fault flags as 0/1 metrics
            for flag_key, metric_suffix in [
                ("has_alarm", "alarm"),
                ("has_fault", "fault"),
            ]:
                flag_val = unit_data.get(flag_key)
                if flag_val is not None:
                    metrics.append(TelemetryMetric(
                        time=timestamp,
                        device_id=device_id,
                        site_id=site_id,
                        metric_name=f"battery_unit_{unit_num}_{metric_suffix}",
                        metric_value=1.0 if flag_val else 0.0,
                        metric_value_str=str(flag_val),
                        quality="good",
                        unit="bool",
                        source="telemetry",
                        tags={"category": "battery_unit", "unit": unit_num},
                    ))

        # --- Per-cell voltages (from 'bat N' commands) ---
        # Supports stacks of up to 10 modules with 15 or 16 cells each.
        cells: List[Dict[str, Any]] = telemetry_data.get("battery_cells", [])
        for cell_data in cells:
            module_num = cell_data.get("module")
            cell_num   = cell_data.get("cell")
            value      = cell_data.get("voltage_v")
            if module_num is None or cell_num is None or value is None:
                continue
            try:
                metrics.append(TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name=f"battery_unit_{module_num}_cell_{cell_num}_voltage_v",
                    metric_value=float(value),
                    quality="good",
                    unit="V",
                    source="telemetry",
                    tags={
                        "category": "battery_cell",
                        "unit": module_num,
                        "cell": cell_num,
                    },
                ))
            except (ValueError, TypeError):
                pass

        logger.debug(
            f"Parsed {len(metrics)} metrics from Pylontech telemetry "
            f"(device {device_id}, {len(units)} units, {len(cells)} cells)"
        )
        return metrics
