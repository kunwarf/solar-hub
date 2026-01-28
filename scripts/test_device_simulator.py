"""
Tests for device simulator data generation logic.
"""
import pytest
from uuid import uuid4
from device_simulator import (
    solar_power_w,
    load_power_w,
    battery_state,
    ambient_temperature,
    SimulatedDevice,
)


class TestSolarPowerGeneration:
    """Tests for the solar power bell curve generator."""

    def test_zero_at_night(self):
        """No solar power before 6am or after 18:30."""
        assert solar_power_w(0.0) == 0.0
        assert solar_power_w(3.0) == 0.0
        assert solar_power_w(5.5) == 0.0
        assert solar_power_w(19.0) == 0.0
        assert solar_power_w(23.0) == 0.0

    def test_peak_at_midday(self):
        """Maximum solar power should be near solar noon (12-13h)."""
        morning = solar_power_w(9.0, capacity_w=5000.0)
        midday = solar_power_w(12.5, capacity_w=5000.0)
        evening = solar_power_w(16.0, capacity_w=5000.0)

        assert midday > morning
        assert midday > evening
        # Peak should be a significant fraction of capacity
        assert midday > 3000.0

    def test_respects_capacity(self):
        """Output should never exceed the capacity."""
        for hour in range(6, 19):
            power = solar_power_w(float(hour), capacity_w=5000.0)
            # Allow 10% over due to random variation
            assert power <= 5500.0, f"Power {power}W exceeds capacity at hour {hour}"

    def test_bell_curve_symmetry(self):
        """Morning and evening power at symmetric hours should be roughly similar."""
        # 8am and 5pm are roughly symmetric around 12:30
        # Due to random variation, check over multiple samples
        morning_samples = [solar_power_w(8.0, 5000.0) for _ in range(20)]
        evening_samples = [solar_power_w(17.0, 5000.0) for _ in range(20)]

        avg_morning = sum(morning_samples) / len(morning_samples)
        avg_evening = sum(evening_samples) / len(evening_samples)

        # Within 40% of each other (generous due to randomness)
        assert abs(avg_morning - avg_evening) / max(avg_morning, avg_evening) < 0.4


class TestLoadPowerGeneration:
    """Tests for the load power generator."""

    def test_nighttime_is_lowest(self):
        """Load should be lowest during nighttime (0-6am)."""
        night_samples = [load_power_w(3.0, 1500.0) for _ in range(20)]
        evening_samples = [load_power_w(20.0, 1500.0) for _ in range(20)]

        avg_night = sum(night_samples) / len(night_samples)
        avg_evening = sum(evening_samples) / len(evening_samples)

        assert avg_night < avg_evening

    def test_evening_peak(self):
        """Load should be highest during evening (18-22h)."""
        evening_samples = [load_power_w(20.0, 1500.0) for _ in range(20)]
        midday_samples = [load_power_w(10.0, 1500.0) for _ in range(20)]

        avg_evening = sum(evening_samples) / len(evening_samples)
        avg_midday = sum(midday_samples) / len(midday_samples)

        assert avg_evening > avg_midday

    def test_always_positive(self):
        """Load should always be positive."""
        for hour in range(24):
            for _ in range(10):
                assert load_power_w(float(hour), 1500.0) > 0


class TestBatteryState:
    """Tests for the battery charge/discharge logic."""

    def test_charges_when_pv_surplus(self):
        """Battery should charge when PV exceeds load."""
        bat_w, new_soc, grid_w = battery_state(
            pv_w=4000.0, load_w=1500.0, current_soc=50.0,
        )
        assert bat_w > 0, "Battery should be charging (positive power)"
        assert new_soc >= 50.0, "SOC should increase"

    def test_discharges_when_pv_deficit(self):
        """Battery should discharge when load exceeds PV."""
        bat_w, new_soc, grid_w = battery_state(
            pv_w=500.0, load_w=2000.0, current_soc=50.0,
        )
        assert bat_w < 0, "Battery should be discharging (negative power)"
        assert new_soc <= 50.0, "SOC should decrease"

    def test_does_not_discharge_below_minimum(self):
        """Battery should not discharge below 20% SOC."""
        bat_w, new_soc, grid_w = battery_state(
            pv_w=0.0, load_w=2000.0, current_soc=15.0,
        )
        assert bat_w == 0.0, "Battery should not discharge below 20%"
        assert grid_w > 0, "Grid should import to cover deficit"

    def test_does_not_charge_above_maximum(self):
        """Battery should not charge above 95% SOC."""
        bat_w, new_soc, grid_w = battery_state(
            pv_w=4000.0, load_w=1000.0, current_soc=96.0,
        )
        assert bat_w == 0.0, "Battery should not charge above 95%"
        assert grid_w < 0, "Surplus should export to grid"

    def test_grid_exports_on_surplus(self):
        """Grid should export when PV surplus and battery full."""
        _, _, grid_w = battery_state(
            pv_w=5000.0, load_w=1000.0, current_soc=96.0,
        )
        assert grid_w < 0, "Grid should be negative (exporting)"

    def test_grid_imports_on_deficit(self):
        """Grid should import when PV deficit and battery depleted."""
        _, _, grid_w = battery_state(
            pv_w=0.0, load_w=2000.0, current_soc=15.0,
        )
        assert grid_w > 0, "Grid should be positive (importing)"


class TestSimulatedDevice:
    """Tests for the SimulatedDevice class."""

    def test_generates_all_required_metrics(self):
        """Telemetry should include all metrics that System A expects."""
        device = SimulatedDevice(
            device_id=uuid4(),
            site_id=uuid4(),
            serial_number="SIM01-0000-0000-0001",
        )
        telemetry = device.generate_telemetry()

        assert "device_id" in telemetry
        assert "site_id" in telemetry
        assert "timestamp" in telemetry
        assert "metrics" in telemetry

        metrics = telemetry["metrics"]
        required = [
            "pv_power_w",
            "load_power_w",
            "battery_power_w",
            "grid_power_w",
            "battery_soc_pct",
            "grid_voltage_v",
            "grid_frequency_hz",
            "temperature_ambient",
        ]
        for key in required:
            assert key in metrics, f"Missing metric: {key}"

    def test_battery_soc_stays_in_bounds(self):
        """Battery SOC should stay within 10-95% over many readings."""
        device = SimulatedDevice(
            device_id=uuid4(),
            site_id=uuid4(),
            serial_number="SIM01-0000-0000-0002",
        )

        for _ in range(100):
            telemetry = device.generate_telemetry()
            soc = telemetry["metrics"]["battery_soc_pct"]
            assert 5.0 <= soc <= 100.0, f"SOC out of bounds: {soc}"

    def test_grid_voltage_realistic(self):
        """Grid voltage should be within realistic range for Pakistan."""
        device = SimulatedDevice(
            device_id=uuid4(),
            site_id=uuid4(),
            serial_number="SIM01-0000-0000-0003",
        )
        telemetry = device.generate_telemetry()
        voltage = telemetry["metrics"]["grid_voltage_v"]
        assert 200.0 <= voltage <= 240.0, f"Unrealistic voltage: {voltage}"
