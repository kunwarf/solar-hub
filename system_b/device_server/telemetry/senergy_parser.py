"""
Senergy Hybrid Inverter telemetry parser.

Extracts normalized metrics from Senergy inverter telemetry.

Key differences from Powdrive:
- battery_current_a is S32 with POSITIVE = charging convention (same as DB).
- battery_power_w is S32 (signed): positive=charging, negative=discharging.
  Used directly — no sign inversion needed.
- Energy field names differ (today_pv_kwh, today_import_kwh, etc.)
- Has a Smart Load / EPS port (smart_load_power_w / phase_r_watt_of_eps)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from .parser import TelemetryParser, TelemetryMetric

logger = logging.getLogger(__name__)


class SenergyParser(TelemetryParser):
    """
    Parser for Senergy hybrid inverter telemetry.

    Senergy uses positive = charging for both battery_power_w and
    battery_current_a — no sign inversion needed (unlike Powdrive).
    """

    # Metric mappings: json_field -> (metric_name, unit, category)
    # Fields that match Powdrive/standard register IDs
    METRIC_MAPPINGS: List[Tuple[str, Tuple[str, str, str]]] = [
        # ===== PV Power =====
        ('pv1_power_w',     ('pv1_power_w',     'W',   'power')),
        ('pv2_power_w',     ('pv2_power_w',     'W',   'power')),

        # ===== Grid =====
        ('grid_power_w',    ('grid_w',           'W',   'power')),
        ('grid_frequency_hz', ('grid_frequency_hz', 'Hz', 'grid')),

        # ===== Load (main port — EPS handled separately below) =====
        ('load_power_w',    ('load_w',           'W',   'power')),

        # ===== Battery (battery_power_w and battery_current_a handled below) =====
        ('battery_soc_pct', ('battery_soc_pct', '%',   'battery')),
        ('battery_voltage_v', ('battery_voltage_v', 'V', 'battery')),
        ('battery_temp_c',  ('battery_temp_c',  'C',   'temperature')),

        # ===== Temperature =====
        ('inverter_temp_c', ('inverter_temp_c', 'C',   'temperature')),

        # ===== Energy today (Senergy-specific field names) =====
        ('today_pv_kwh',    ('pv_energy_today_kwh',             'kWh', 'energy')),
        ('today_load_kwh',  ('load_energy_today_kwh',           'kWh', 'energy')),
        ('today_import_kwh', ('grid_import_energy_today_kwh',   'kWh', 'energy')),
        ('today_export_kwh', ('grid_export_energy_today_kwh',   'kWh', 'energy')),
        ('battery_daily_charge_energy',    ('battery_charge_energy_today_kwh',    'kWh', 'energy')),
        ('battery_daily_discharge_energy', ('battery_discharge_energy_today_kwh', 'kWh', 'energy')),

        # ===== Energy totals =====
        ('total_energy',                   ('pv_energy_total_kwh',                'kWh', 'energy_total')),
        ('accumulated_energy_positive',    ('grid_import_energy_total_kwh',       'kWh', 'energy_total')),
        ('accumulated_energy_negative',    ('grid_export_energy_total_kwh',       'kWh', 'energy_total')),
        ('accumulated_energy_of_load',     ('load_energy_total_kwh',              'kWh', 'energy_total')),
        ('battery_accumulated_charge_energy',    ('battery_charge_energy_total_kwh',    'kWh', 'energy_total')),
        ('battery_accumulated_discharge_energy', ('battery_discharge_energy_total_kwh', 'kWh', 'energy_total')),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime,
    ) -> List[TelemetryMetric]:
        """
        Parse Senergy telemetry into normalized metrics.

        Args:
            telemetry_data: Raw telemetry dict from Modbus polling
            device_id: Device UUID
            site_id: Site UUID
            timestamp: Telemetry timestamp

        Returns:
            List of TelemetryMetric objects
        """
        metrics: List[TelemetryMetric] = []

        def _metric(name: str, value: float, unit: str, category: str) -> TelemetryMetric:
            return TelemetryMetric(
                time=timestamp,
                device_id=device_id,
                site_id=site_id,
                metric_name=name,
                metric_value=value,
                quality='good',
                unit=unit,
                source='telemetry',
                tags={'category': category},
            )

        # Standard field mappings
        for json_field, (metric_name, unit, category) in self.METRIC_MAPPINGS:
            raw = telemetry_data.get(json_field)
            if raw is None:
                continue
            try:
                metrics.append(_metric(metric_name, float(raw), unit, category))
            except (ValueError, TypeError):
                logger.warning(f"SenergyParser: could not convert {json_field}={raw!r} to float")

        # ── Battery current: Senergy positive = charging (same convention as our DB) ──
        for field in ('battery_current_a', 'battery_current'):
            if field in telemetry_data and telemetry_data[field] is not None:
                try:
                    metrics.append(_metric('battery_current_a', float(telemetry_data[field]), 'A', 'battery'))
                    break
                except (ValueError, TypeError):
                    pass

        # ── Battery power: S32, positive=charging, negative=discharging (per register map) ──
        raw_power_w = telemetry_data.get('battery_power_w') or telemetry_data.get('battery_power')
        if raw_power_w is not None:
            try:
                metrics.append(_metric('battery_w', float(raw_power_w), 'W', 'power'))
            except (ValueError, TypeError):
                logger.warning(f"SenergyParser: could not convert battery_power_w={raw_power_w!r}")

        # ── Smart Load / EPS port power ──
        eps_w = telemetry_data.get('smart_load_power_w') or telemetry_data.get('phase_r_watt_of_eps')
        if eps_w is not None:
            try:
                metrics.append(_metric('smart_load_w', float(eps_w), 'W', 'power'))
                # Total load = main port + EPS port
                main_load = telemetry_data.get('load_power_w', 0) or 0
                total_load = float(main_load) + float(eps_w)
                metrics.append(_metric('total_load_w', total_load, 'W', 'power'))
            except (ValueError, TypeError):
                logger.warning(f"SenergyParser: could not convert eps_w={eps_w!r}")

        # ── Computed: PV total ──
        pv1 = telemetry_data.get('pv1_power_w', 0) or 0
        pv2 = telemetry_data.get('pv2_power_w', 0) or 0
        pv_total = float(pv1) + float(pv2)
        if pv_total > 0:
            metrics.append(_metric('pv_total_w', pv_total, 'W', 'power'))

        logger.debug(
            f"Parsed {len(metrics)} metrics from Senergy telemetry "
            f"(device {device_id})"
        )
        return metrics
