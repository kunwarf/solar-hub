"""
Deye Hybrid Inverter telemetry parser.

Extracts ~50 normalized metrics from Deye Hybrid inverter telemetry JSON.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple
from uuid import UUID

from .parser import TelemetryParser, TelemetryMetric

logger = logging.getLogger(__name__)


class DeyeHybridParser(TelemetryParser):
    """
    Parser for Deye Hybrid inverter telemetry.

    Extracts power, energy, battery, grid, and temperature metrics
    from the JSON telemetry format into normalized rows.
    """

    # Metric mappings: (json_section, json_field) -> (metric_name, unit, category)
    METRIC_MAPPINGS: List[Tuple[Tuple[str, str], Tuple[str, str, str]]] = [
        # ===== Power Metrics (Instantaneous W) =====
        (('power', 'pv1_w'), ('pv1_power_w', 'W', 'power')),
        (('power', 'pv2_w'), ('pv2_power_w', 'W', 'power')),
        (('power', 'pv_total_w'), ('pv_total_w', 'W', 'power')),
        (('power', 'grid_w'), ('grid_w', 'W', 'power')),
        (('power', 'load_w'), ('load_w', 'W', 'power')),
        (('power', 'battery_w'), ('battery_w', 'W', 'power')),

        # ===== Battery Metrics =====
        (('battery', 'soc_pct'), ('battery_soc_pct', '%', 'battery')),
        (('battery', 'voltage_v'), ('battery_voltage_v', 'V', 'battery')),
        (('battery', 'current_a'), ('battery_current_a', 'A', 'battery')),
        (('battery', 'charging'), ('battery_charging', 'bool', 'battery')),

        # ===== Energy Metrics (Daily kWh) =====
        (('energy_today', 'pv_kwh'), ('pv_energy_today_kwh', 'kWh', 'energy')),
        (('energy_today', 'load_kwh'), ('load_energy_today_kwh', 'kWh', 'energy')),

        # ===== Temperature Metrics =====
        (('temperatures', 'inverter_c'), ('inverter_temp_c', 'C', 'temperature')),
        (('temperatures', 'battery_c'), ('battery_temp_c', 'C', 'temperature')),

        # ===== Grid Metrics =====
        (('grid', 'voltage_v'), ('grid_voltage_v', 'V', 'grid')),
        (('grid', 'frequency_hz'), ('grid_frequency_hz', 'Hz', 'grid')),
        (('grid', 'l1_voltage_v'), ('grid_l1_voltage_v', 'V', 'grid')),
        (('grid', 'l2_voltage_v'), ('grid_l2_voltage_v', 'V', 'grid')),
        (('grid', 'l3_voltage_v'), ('grid_l3_voltage_v', 'V', 'grid')),

        # ===== Status Metrics =====
        (('status', 'grid_connected'), ('grid_connected', 'bool', 'status')),

        # ===== Raw Metrics (Detailed) =====
        (('raw', 'grid_power_w'), ('grid_power_w', 'W', 'raw')),
        (('raw', 'load_power_w'), ('load_power_w', 'W', 'raw')),
        (('raw', 'load_l1_power_w'), ('load_l1_power_w', 'W', 'raw')),
        (('raw', 'load_l2_power_w'), ('load_l2_power_w', 'W', 'raw')),
        (('raw', 'load_l3_power_w'), ('load_l3_power_w', 'W', 'raw')),

        (('raw', 'battery_voltage_v'), ('battery_voltage_v_raw', 'V', 'raw')),
        (('raw', 'battery_current_a'), ('battery_current_a_raw', 'A', 'raw')),
        (('raw', 'battery_power_w'), ('battery_power_w_raw', 'W', 'raw')),
        (('raw', 'battery_soc_pct'), ('battery_soc_pct_raw', '%', 'raw')),

        (('raw', 'pv1_power_w'), ('pv1_power_w_raw', 'W', 'raw')),
        (('raw', 'pv2_power_w'), ('pv2_power_w_raw', 'W', 'raw')),
        (('raw', 'pv1_voltage_v'), ('pv1_voltage_v', 'V', 'raw')),
        (('raw', 'pv1_current_a'), ('pv1_current_a', 'A', 'raw')),
        (('raw', 'pv2_voltage_v'), ('pv2_voltage_v', 'V', 'raw')),
        (('raw', 'pv2_current_a'), ('pv2_current_a', 'A', 'raw')),

        (('raw', 'grid_import_energy_today_kwh'), ('grid_import_energy_today_kwh', 'kWh', 'raw')),
        (('raw', 'grid_export_energy_today_kwh'), ('grid_export_energy_today_kwh', 'kWh', 'raw')),
        (('raw', 'battery_charge_energy_today_kwh'), ('battery_charge_energy_today_kwh', 'kWh', 'raw')),
        (('raw', 'battery_discharge_energy_today_kwh'), ('battery_discharge_energy_today_kwh', 'kWh', 'raw')),
        (('raw', 'pv_energy_today_kwh'), ('pv_energy_today_kwh_raw', 'kWh', 'raw')),
        (('raw', 'load_energy_today_kwh'), ('load_energy_today_kwh_raw', 'kWh', 'raw')),

        (('raw', 'grid_l1_power_w'), ('grid_l1_power_w', 'W', 'raw')),
        (('raw', 'grid_l2_power_w'), ('grid_l2_power_w', 'W', 'raw')),
        (('raw', 'grid_l3_power_w'), ('grid_l3_power_w', 'W', 'raw')),
        (('raw', 'grid_l1_current_a'), ('grid_l1_current_a', 'A', 'raw')),
        (('raw', 'grid_l2_current_a'), ('grid_l2_current_a', 'A', 'raw')),
        (('raw', 'grid_l3_current_a'), ('grid_l3_current_a', 'A', 'raw')),

        (('raw', 'inverter_temp_c'), ('inverter_temp_c_raw', 'C', 'raw')),
        (('raw', 'battery_temp_c'), ('battery_temp_c_raw', 'C', 'raw')),
        (('raw', 'heat_sink_temp_c'), ('heat_sink_temp_c', 'C', 'raw')),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime
    ) -> List[TelemetryMetric]:
        """
        Parse Deye Hybrid inverter telemetry into normalized metrics.

        Extracts ~50 metrics from the JSON structure.

        Args:
            telemetry_data: Raw telemetry JSON.
            device_id: Device UUID.
            site_id: Site UUID.
            timestamp: Reading timestamp.

        Returns:
            List of TelemetryMetric objects (one per metric).
        """
        metrics = []
        extracted_count = 0
        failed_count = 0

        for (section, field), (metric_name, unit, category) in self.METRIC_MAPPINGS:
            try:
                # Extract value from nested JSON
                value = self._safe_extract_float(telemetry_data, section, field)

                # Skip None values
                if value is None:
                    continue

                # Convert boolean fields
                if unit == 'bool':
                    # Convert to 1.0 or 0.0
                    value = 1.0 if value else 0.0

                # Create metric
                metrics.append(TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name=metric_name,
                    metric_value=value,
                    quality='good',
                    unit=unit,
                    source=category,
                ))
                extracted_count += 1

            except Exception as e:
                failed_count += 1
                logger.debug(
                    f"Could not extract metric {metric_name} "
                    f"from {section}.{field}: {e}"
                )
                continue

        logger.debug(
            f"Parsed {extracted_count} metrics from Deye Hybrid telemetry "
            f"(device {device_id}, {failed_count} failed)"
        )

        return metrics
