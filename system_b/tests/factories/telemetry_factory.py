"""
Telemetry-related test data factories.
"""
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from uuid import uuid4

import factory


class TelemetryFactory(factory.Factory):
    """
    Factory for creating telemetry data dictionaries.

    Usage:
        telemetry = TelemetryFactory()
        telemetry = TelemetryFactory(metrics={"battery_soc_pct": 50})
    """

    class Meta:
        model = dict

    device_id = factory.LazyFunction(uuid4)
    site_id = factory.LazyFunction(uuid4)
    timestamp = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    source = "modbus"

    @factory.lazy_attribute
    def metrics(self) -> Dict[str, Any]:
        return {
            "battery_soc_pct": random.uniform(20, 100),
            "pv_power_w": random.randint(0, 5000),
            "battery_power_w": random.randint(-2000, 2000),
            "grid_power_w": random.randint(-3000, 3000),
            "load_power_w": random.randint(500, 5000),
        }


class InverterTelemetryFactory(TelemetryFactory):
    """Factory for inverter telemetry with full metrics."""

    source = "modbus"

    @factory.lazy_attribute
    def metrics(self) -> Dict[str, Any]:
        battery_soc = random.uniform(20, 100)
        pv_power = random.randint(0, 12000)
        load_power = random.randint(500, 8000)
        battery_power = random.randint(-5000, 5000)
        grid_power = load_power - pv_power - battery_power

        return {
            # Battery metrics
            "battery_soc_pct": battery_soc,
            "battery_power_w": battery_power,
            "battery_voltage_v": random.uniform(48.0, 54.0),
            "battery_current_a": battery_power / 50.0,
            "battery_temperature_c": random.uniform(20, 35),

            # PV metrics
            "pv_power_w": pv_power,
            "pv1_power_w": pv_power * 0.6,
            "pv2_power_w": pv_power * 0.4,
            "pv1_voltage_v": random.uniform(300, 400),
            "pv2_voltage_v": random.uniform(300, 400),
            "pv1_current_a": (pv_power * 0.6) / 350,
            "pv2_current_a": (pv_power * 0.4) / 350,

            # Grid metrics
            "grid_power_w": grid_power,
            "grid_voltage_v": random.uniform(228, 242),
            "grid_frequency_hz": random.uniform(49.9, 50.1),

            # Load metrics
            "load_power_w": load_power,

            # Energy counters
            "energy_total_kwh": random.uniform(1000, 50000),
            "energy_today_kwh": random.uniform(0, 50),
        }


class MeterTelemetryFactory(TelemetryFactory):
    """Factory for meter telemetry."""

    source = "modbus"

    @factory.lazy_attribute
    def metrics(self) -> Dict[str, Any]:
        active_power = random.uniform(-5000, 10000)
        voltage = random.uniform(228, 242)
        current = abs(active_power) / voltage

        return {
            "active_power_w": active_power,
            "reactive_power_var": random.uniform(-500, 500),
            "apparent_power_va": abs(active_power) * 1.05,
            "power_factor": random.uniform(0.9, 1.0),
            "voltage_v": voltage,
            "current_a": current,
            "frequency_hz": random.uniform(49.9, 50.1),
            "energy_import_kwh": random.uniform(0, 10000),
            "energy_export_kwh": random.uniform(0, 5000),
        }


class BatteryTelemetryFactory(TelemetryFactory):
    """Factory for battery telemetry."""

    source = "command"

    @factory.lazy_attribute
    def metrics(self) -> Dict[str, Any]:
        soc = random.uniform(20, 100)
        voltage = 48.0 + (soc / 100) * 6.0  # 48-54V range
        current = random.uniform(-50, 50)

        return {
            "soc_pct": soc,
            "voltage_v": voltage,
            "current_a": current,
            "power_w": voltage * current,
            "temperature_c": random.uniform(20, 35),
            "cell_voltage_min_v": voltage / 16 - 0.05,
            "cell_voltage_max_v": voltage / 16 + 0.05,
            "cycles": random.randint(0, 500),
        }


class TelemetryBatchFactory:
    """
    Factory for creating batches of telemetry data.

    Usage:
        batch = TelemetryBatchFactory.create_batch(
            device_id=uuid,
            site_id=uuid,
            count=100,
            interval_seconds=60
        )
    """

    @staticmethod
    def create_batch(
        device_id,
        site_id,
        count: int = 100,
        interval_seconds: int = 60,
        start_time: datetime = None,
        telemetry_factory=TelemetryFactory,
    ) -> List[Dict[str, Any]]:
        """
        Create a batch of telemetry records.

        Args:
            device_id: Device ID for all records.
            site_id: Site ID for all records.
            count: Number of records to create.
            interval_seconds: Time between records.
            start_time: Starting timestamp (defaults to now minus count*interval).
            telemetry_factory: Factory class to use.

        Returns:
            List of telemetry dictionaries.
        """
        if start_time is None:
            start_time = datetime.now(timezone.utc) - timedelta(seconds=count * interval_seconds)

        batch = []
        for i in range(count):
            timestamp = start_time + timedelta(seconds=i * interval_seconds)
            record = telemetry_factory(
                device_id=device_id,
                site_id=site_id,
                timestamp=timestamp,
            )
            batch.append(record)

        return batch

    @staticmethod
    def create_daily_pattern(
        device_id,
        site_id,
        date: datetime = None,
        interval_seconds: int = 300,  # 5-minute intervals
    ) -> List[Dict[str, Any]]:
        """
        Create telemetry following realistic daily pattern.

        PV power follows sun curve, battery charges during day, etc.
        """
        if date is None:
            date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        batch = []
        seconds_per_day = 24 * 60 * 60
        num_records = seconds_per_day // interval_seconds

        for i in range(num_records):
            timestamp = date + timedelta(seconds=i * interval_seconds)
            hour = timestamp.hour + timestamp.minute / 60.0

            # PV power follows sun curve (peak at noon)
            if 6 <= hour <= 18:
                sun_factor = 1 - abs(hour - 12) / 6
                pv_power = int(5000 * sun_factor * random.uniform(0.8, 1.2))
            else:
                pv_power = 0

            # Load varies throughout day
            base_load = 500
            if 7 <= hour <= 9:  # Morning peak
                load_power = int(base_load + 2000 * random.uniform(0.8, 1.2))
            elif 18 <= hour <= 22:  # Evening peak
                load_power = int(base_load + 3000 * random.uniform(0.8, 1.2))
            elif 0 <= hour <= 6:  # Night minimum
                load_power = int(base_load * random.uniform(0.5, 1.0))
            else:
                load_power = int(base_load + 1000 * random.uniform(0.8, 1.2))

            # Battery SOC changes based on net power
            # Simplified simulation
            battery_soc = 50 + 30 * sun_factor  # Higher during day

            record = {
                "device_id": device_id,
                "site_id": site_id,
                "timestamp": timestamp,
                "source": "modbus",
                "metrics": {
                    "battery_soc_pct": battery_soc + random.uniform(-5, 5),
                    "pv_power_w": pv_power,
                    "load_power_w": load_power,
                    "battery_power_w": pv_power - load_power,  # Simplified
                    "grid_power_w": 0,  # Off-grid simulation
                },
            }
            batch.append(record)

        return batch
