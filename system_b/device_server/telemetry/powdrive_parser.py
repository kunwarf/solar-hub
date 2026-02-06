"""
Powdrive Inverter telemetry parser.

Extracts normalized metrics from Powdrive inverter telemetry JSON.
Unlike Deye format, Powdrive has a flat JSON structure with all fields at root level.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple
from uuid import UUID

from .parser import TelemetryParser, TelemetryMetric

logger = logging.getLogger(__name__)


class PowdriveParser(TelemetryParser):
    """
    Parser for Powdrive inverter telemetry.

    Extracts power, energy, battery, grid, and temperature metrics
    from the flat JSON telemetry format into normalized rows.

    NOTE: Powdrive uses negative values for battery charging.
    Standard convention: positive = charging, negative = discharging.
    Battery power values are inverted during parsing to match standard convention.
    """

    # Metric mappings: json_field -> (metric_name, unit, category)
    METRIC_MAPPINGS: List[Tuple[str, Tuple[str, str, str]]] = [
        # ===== PV Power Metrics (Instantaneous W) =====
        ('pv1_power_w', ('pv1_power_w', 'W', 'power')),
        ('pv2_power_w', ('pv2_power_w', 'W', 'power')),
        ('pv3_power_w', ('pv3_power_w', 'W', 'power')),
        ('pv4_power_w', ('pv4_power_w', 'W', 'power')),

        # ===== Power Metrics =====
        ('grid_power_w', ('grid_w', 'W', 'power')),
        ('load_power_w', ('load_w', 'W', 'power')),
        ('battery_power_w', ('battery_w', 'W', 'power')),

        # ===== Battery Metrics =====
        ('battery_soc_pct', ('battery_soc_pct', '%', 'battery')),
        ('battery_voltage_v', ('battery_voltage_v', 'V', 'battery')),
        ('battery_current_a', ('battery_current_a', 'A', 'battery')),

        # ===== Energy Metrics (Daily kWh) =====
        ('pv_energy_today_kwh', ('pv_energy_today_kwh', 'kWh', 'energy')),
        ('load_energy_today_kwh', ('load_energy_today_kwh', 'kWh', 'energy')),
        ('day_gen_energy_kwh', ('day_gen_energy_kwh', 'kWh', 'energy')),
        ('grid_export_energy_today_kwh', ('grid_export_energy_today_kwh', 'kWh', 'energy')),
        ('grid_import_energy_today_kwh', ('grid_import_energy_today_kwh', 'kWh', 'energy')),
        ('battery_charge_energy_today_kwh', ('battery_charge_energy_today_kwh', 'kWh', 'energy')),
        ('battery_discharge_energy_today_kwh', ('battery_discharge_energy_today_kwh', 'kWh', 'energy')),

        # ===== Energy Totals (Total kWh) =====
        ('pv_energy_total_kwh', ('pv_energy_total_kwh', 'kWh', 'energy_total')),
        ('load_energy_total_kwh', ('load_energy_total_kwh', 'kWh', 'energy_total')),
        ('export_energy_total_kwh', ('export_energy_total_kwh', 'kWh', 'energy_total')),
        ('import_energy_total_kwh', ('import_energy_total_kwh', 'kWh', 'energy_total')),
        ('battery_charge_energy_total_kwh', ('battery_charge_energy_total_kwh', 'kWh', 'energy_total')),
        ('battery_discharge_energy_total_kwh', ('battery_discharge_energy_total_kwh', 'kWh', 'energy_total')),

        # ===== Temperature Metrics =====
        ('inverter_temp_c', ('inverter_temp_c', 'C', 'temperature')),
        ('battery_temp_c', ('battery_temp_c', 'C', 'temperature')),
        ('heat_sink_temp_c', ('heat_sink_temp_c', 'C', 'temperature')),

        # ===== Grid Metrics =====
        ('grid_voltage_v', ('grid_voltage_v', 'V', 'grid')),
        ('grid_frequency_hz', ('grid_frequency_hz', 'Hz', 'grid')),
        ('grid_l1_voltage_v', ('grid_l1_voltage_v', 'V', 'grid')),
        ('grid_l2_voltage_v', ('grid_l2_voltage_v', 'V', 'grid')),
        ('grid_l3_voltage_v', ('grid_l3_voltage_v', 'V', 'grid')),
        ('grid_l1_current_a', ('grid_l1_current_a', 'A', 'grid')),
        ('grid_l2_current_a', ('grid_l2_current_a', 'A', 'grid')),
        ('grid_l3_current_a', ('grid_l3_current_a', 'A', 'grid')),
        ('grid_l1_power_w', ('grid_l1_power_w', 'W', 'grid')),
        ('grid_l2_power_w', ('grid_l2_power_w', 'W', 'grid')),
        ('grid_l3_power_w', ('grid_l3_power_w', 'W', 'grid')),

        # ===== Load Metrics =====
        ('load_l1_power_w', ('load_l1_power_w', 'W', 'load')),
        ('load_l2_power_w', ('load_l2_power_w', 'W', 'load')),
        ('load_l3_power_w', ('load_l3_power_w', 'W', 'load')),
        ('load_l1_voltage_v', ('load_l1_voltage_v', 'V', 'load')),
        ('load_l2_voltage_v', ('load_l2_voltage_v', 'V', 'load')),
        ('load_l3_voltage_v', ('load_l3_voltage_v', 'V', 'load')),

        # ===== PV String Details =====
        ('pv1_voltage_v', ('pv1_voltage_v', 'V', 'pv')),
        ('pv1_current_a', ('pv1_current_a', 'A', 'pv')),
        ('pv2_voltage_v', ('pv2_voltage_v', 'V', 'pv')),
        ('pv2_current_a', ('pv2_current_a', 'A', 'pv')),
        ('pv3_voltage_v', ('pv3_voltage_v', 'V', 'pv')),
        ('pv3_current_a', ('pv3_current_a', 'A', 'pv')),
        ('pv4_voltage_v', ('pv4_voltage_v', 'V', 'pv')),
        ('pv4_current_a', ('pv4_current_a', 'A', 'pv')),

        # ===== Grid CT Metrics =====
        ('grid_ct_power_w', ('grid_ct_power_w', 'W', 'grid')),
        ('grid_ct_l1_power_w', ('grid_ct_l1_power_w', 'W', 'grid')),
        ('grid_ct_l2_power_w', ('grid_ct_l2_power_w', 'W', 'grid')),
        ('grid_ct_l3_power_w', ('grid_ct_l3_power_w', 'W', 'grid')),

        # ===== Status Metrics =====
        ('grid_status_raw', ('grid_status_raw', 'enum', 'status')),
        ('working_mode_raw', ('working_mode_raw', 'enum', 'status')),
        ('power_on_off_status', ('power_on_off_status', 'bool', 'status')),

        # ===== Configuration/Settings (for reference) =====
        ('battery_capacity_ah', ('battery_capacity_ah', 'Ah', 'config')),
        ('battery_type', ('battery_type', 'enum', 'config')),
        ('inverter_type', ('inverter_type', 'enum', 'config')),
    ]

    # Metrics that need sign inversion (Powdrive uses negative = charging)
    INVERT_SIGN_METRICS = {
        'battery_power_w',  # Powdrive: negative = charging, we want positive = charging
        'battery_current_a',  # Powdrive: negative = charging current
    }

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        """
        Parse Powdrive telemetry JSON into normalized metrics.

        Args:
            telemetry_data: Raw JSON telemetry (flat structure)
            device_id: Device UUID
            site_id: Site UUID
            timestamp: Telemetry timestamp

        Returns:
            List of TelemetryMetric objects
        """
        metrics = []

        for json_field, (metric_name, unit, category) in self.METRIC_MAPPINGS:
            value = telemetry_data.get(json_field)

            if value is None:
                continue

            # Handle boolean values
            if unit == 'bool':
                metric = TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name=metric_name,
                    metric_value=1.0 if value else 0.0,
                    metric_value_str=str(value),
                    quality='good',
                    unit=unit,
                    source='telemetry',
                    tags={'category': category}
                )
                metrics.append(metric)

            # Handle enum values (store as both numeric and string)
            elif unit == 'enum':
                try:
                    numeric_value = float(value)
                    metric = TelemetryMetric(
                        time=timestamp,
                        device_id=device_id,
                        site_id=site_id,
                        metric_name=metric_name,
                        metric_value=numeric_value,
                        metric_value_str=str(value),
                        quality='good',
                        unit=unit,
                        source='telemetry',
                        tags={'category': category}
                    )
                    metrics.append(metric)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert enum {metric_name}={value} to float"
                    )

            # Handle numeric values
            else:
                try:
                    numeric_value = float(value)

                    # Invert sign for Powdrive battery metrics
                    # Powdrive uses negative values for charging, we use positive = charging
                    if json_field in self.INVERT_SIGN_METRICS:
                        numeric_value = -numeric_value
                        logger.debug(
                            f"Inverted {json_field}: {value} -> {numeric_value} "
                            f"(Powdrive convention: negative = charging)"
                        )

                    metric = TelemetryMetric(
                        time=timestamp,
                        device_id=device_id,
                        site_id=site_id,
                        metric_name=metric_name,
                        metric_value=numeric_value,
                        quality='good',
                        unit=unit,
                        source='telemetry',
                        tags={'category': category}
                    )
                    metrics.append(metric)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert {metric_name}={value} to float, skipping"
                    )
                    continue

        # Calculate total PV power if not already present
        pv_total_w = sum(
            telemetry_data.get(f'pv{i}_power_w', 0)
            for i in range(1, 5)
        )
        if pv_total_w > 0:
            metrics.append(
                TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name='pv_total_w',
                    metric_value=float(pv_total_w),
                    quality='good',
                    unit='W',
                    source='telemetry',
                    tags={'category': 'power', 'calculated': 'true'}
                )
            )

        logger.debug(
            f"Parsed {len(metrics)} metrics from Powdrive telemetry "
            f"(device {device_id})"
        )

        return metrics
