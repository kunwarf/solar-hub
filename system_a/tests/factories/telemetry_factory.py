"""
Factory functions for generating test telemetry data.

Creates realistic test data for summary tables.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4


def hourly_summary_data(
    energy_generated_kwh: float = 2.5,
    energy_consumed_kwh: float = 1.5,
    energy_exported_kwh: float = 0.8,
    energy_imported_kwh: float = 0.3,
    peak_power_kw: float = 5.0,
    **overrides: Any,
) -> Dict[str, Any]:
    """Create hourly summary data dict suitable for upsert_hourly_summary()."""
    data = {
        "energy_generated_kwh": energy_generated_kwh,
        "energy_consumed_kwh": energy_consumed_kwh,
        "energy_exported_kwh": energy_exported_kwh,
        "energy_imported_kwh": energy_imported_kwh,
        "energy_stored_kwh": 0.5,
        "energy_discharged_kwh": 0.3,
        "peak_power_kw": peak_power_kw,
        "average_power_kw": energy_generated_kwh,
        "min_power_kw": 0.0,
        "avg_irradiance_w_m2": 800.0,
        "avg_temperature_c": 35.0,
        "max_temperature_c": 42.0,
        "min_temperature_c": 28.0,
        "avg_battery_soc_percent": 65.0,
        "avg_grid_voltage_v": 220.0,
        "avg_grid_frequency_hz": 50.0,
        "avg_power_factor": 0.98,
        "sample_count": 60,
        "data_quality_percent": 100.0,
    }
    data.update(overrides)
    return data


def daily_summary_data(
    energy_generated_kwh: float = 25.0,
    energy_consumed_kwh: float = 18.0,
    energy_exported_kwh: float = 5.0,
    energy_imported_kwh: float = 2.0,
    peak_power_kw: float = 8.0,
    **overrides: Any,
) -> Dict[str, Any]:
    """Create daily summary data dict suitable for upsert_daily_summary()."""
    data = {
        "energy_generated_kwh": energy_generated_kwh,
        "energy_consumed_kwh": energy_consumed_kwh,
        "energy_exported_kwh": energy_exported_kwh,
        "energy_imported_kwh": energy_imported_kwh,
        "energy_stored_kwh": 5.0,
        "energy_discharged_kwh": 3.0,
        "net_energy_kwh": energy_generated_kwh - energy_consumed_kwh,
        "peak_power_kw": peak_power_kw,
        "average_power_kw": energy_generated_kwh / 10,  # ~10 sunshine hours
        "sunshine_hours": 10.0,
        "production_hours": 10.0,
        "grid_outage_minutes": 0,
        "avg_temperature_c": 35.0,
        "max_temperature_c": 42.0,
        "min_temperature_c": 25.0,
        "avg_battery_soc_percent": 60.0,
        "avg_grid_voltage_v": 220.0,
        "avg_power_factor": 0.97,
        "co2_avoided_kg": energy_generated_kwh * 0.475,
        "estimated_savings_pkr": energy_generated_kwh * 25.0,
        "hours_with_data": 24,
        "data_completeness_percent": 100.0,
    }
    data.update(overrides)
    return data


def monthly_summary_data(
    energy_generated_kwh: float = 750.0,
    energy_consumed_kwh: float = 540.0,
    peak_power_kw: float = 9.0,
    days_with_data: int = 30,
    **overrides: Any,
) -> Dict[str, Any]:
    """Create monthly summary data dict suitable for upsert_monthly_summary()."""
    data = {
        "energy_generated_kwh": energy_generated_kwh,
        "energy_consumed_kwh": energy_consumed_kwh,
        "energy_exported_kwh": 150.0,
        "energy_imported_kwh": 60.0,
        "energy_stored_kwh": 150.0,
        "energy_discharged_kwh": 90.0,
        "net_energy_kwh": energy_generated_kwh - energy_consumed_kwh,
        "peak_power_kw": peak_power_kw,
        "average_daily_generation_kwh": energy_generated_kwh / days_with_data,
        "total_sunshine_hours": 300.0,
        "total_production_hours": 300.0,
        "total_grid_outage_minutes": 15,
        "avg_temperature_c": 33.0,
        "co2_avoided_kg": energy_generated_kwh * 0.475,
        "trees_equivalent": (energy_generated_kwh * 0.475) / 1000 * 45,
        "estimated_revenue_pkr": energy_generated_kwh * 25.0,
        "estimated_savings_pkr": energy_generated_kwh * 25.0,
        "days_with_data": days_with_data,
        "data_completeness_percent": (days_with_data / 30) * 100.0,
    }
    data.update(overrides)
    return data


def make_hourly_series(
    site_id: UUID,
    device_id: Optional[UUID],
    start_hour: datetime,
    count: int = 12,
    base_generation_kwh: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    Generate a series of hourly summary data dicts for testing.

    Returns list of (timestamp_hour, data) tuples.
    """
    results = []
    for i in range(count):
        ts = start_hour + timedelta(hours=i)
        # Bell curve for solar
        hour_of_day = ts.hour + ts.minute / 60.0
        intensity = max(0.0, (1.0 - abs(hour_of_day - 12.5) / 6.5))
        gen = base_generation_kwh * intensity

        results.append({
            "timestamp_hour": ts,
            "site_id": site_id,
            "device_id": device_id,
            "data": hourly_summary_data(energy_generated_kwh=round(gen, 2)),
        })
    return results
