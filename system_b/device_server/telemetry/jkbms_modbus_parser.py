"""
JK BMS Modbus RTU telemetry parser.

Parses the flat register dict produced by TCPModbusAdapter.poll()
for the jkbms_modbus protocol into normalized TelemetryMetric objects.

The dict keys match the 'id' fields in jkbms_modbus_registers.json.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from .parser import TelemetryParser, TelemetryMetric

logger = logging.getLogger(__name__)


class JKBMSModbusParser(TelemetryParser):
    """
    Parser for JK BMS telemetry received via Modbus RTU (passive slave mode).

    Converts the flat register dict from TCPModbusAdapter.poll() into
    normalized TelemetryMetric objects.  Cell voltages are emitted as
    individual per-cell metrics matching the same naming convention used
    by JKBMSParser (serial bridge path) so the frontend BatteryCellGrid
    component works identically for both connection methods.
    """

    # Scalar metrics: register_id -> (metric_name, unit, category)
    SCALAR_METRICS: List[tuple] = [
        ("battery_soc_pct",      ("battery_soc_pct",      "%",   "battery")),
        ("battery_soh_pct",      ("battery_soh_pct",      "%",   "battery")),
        ("battery_voltage_v",    ("battery_voltage_v",    "V",   "battery")),
        ("battery_current_a",    ("battery_current_a",    "A",   "battery")),
        ("battery_temp_c",       ("battery_temp_c",       "C",   "temperature")),
        ("battery_temp2_c",      ("battery_temp2_c",      "C",   "temperature")),
        ("battery_mos_temp_c",   ("battery_mos_temp_c",   "C",   "temperature")),
        ("battery_remaining_ah", ("battery_remaining_ah", "Ah",  "battery")),
        ("battery_total_ah",     ("battery_total_ah",     "Ah",  "battery")),
        ("battery_cycle_count",  ("battery_cycle_count",  "",    "battery")),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        metrics: List[TelemetryMetric] = []

        # --- Scalar metrics ---
        for reg_id, (metric_name, unit, category) in self.SCALAR_METRICS:
            value = telemetry_data.get(reg_id)
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

        # --- Derived battery power ---
        voltage = telemetry_data.get("battery_voltage_v")
        current = telemetry_data.get("battery_current_a")
        if voltage is not None and current is not None:
            try:
                power_w = float(voltage) * float(current)
                metrics.append(TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name="battery_w",
                    metric_value=power_w,
                    quality="good",
                    unit="W",
                    source="telemetry",
                    tags={"category": "power"},
                ))
            except (ValueError, TypeError):
                pass

        # --- Per-cell voltage metrics ---
        for cell_num in range(1, 33):
            key = f"battery_cell_{cell_num}_voltage_v"
            value = telemetry_data.get(key)
            if value is None:
                continue
            try:
                metrics.append(TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name=key,
                    metric_value=float(value),
                    quality="good",
                    unit="V",
                    source="telemetry",
                    tags={"category": "battery_cell", "cell": cell_num},
                ))
            except (ValueError, TypeError):
                logger.warning(f"Could not convert cell {cell_num} voltage={value} to float")

        logger.debug(
            f"Parsed {len(metrics)} metrics from JK BMS Modbus telemetry (device {device_id})"
        )
        return metrics
