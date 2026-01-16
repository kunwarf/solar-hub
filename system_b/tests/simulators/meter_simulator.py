"""
IAMMeter simulator.

Simulates a 3-phase energy meter with realistic power measurements.
"""
import random
from datetime import datetime
from typing import Dict, Any

from .modbus_simulator import ModbusTCPSimulator


class IAMMeterSimulator(ModbusTCPSimulator):
    """
    Simulates an IAMMeter 3-phase energy meter.

    Provides power, voltage, current, and energy readings
    via Modbus TCP.
    """

    # Register addresses (based on IAMMeter WEM3080T protocol)
    REG_VOLTAGE_A = 0x0000  # V * 100
    REG_CURRENT_A = 0x0008  # A * 100
    REG_ACTIVE_POWER_A = 0x0010  # W
    REG_REACTIVE_POWER_A = 0x0018  # VAR
    REG_APPARENT_POWER_A = 0x0020  # VA
    REG_POWER_FACTOR_A = 0x002A  # * 1000
    REG_FREQUENCY = 0x0036  # Hz * 100

    REG_IMPORT_ENERGY = 0x0100  # kWh * 100 (U32)
    REG_EXPORT_ENERGY = 0x0108  # kWh * 100 (U32)

    REG_TOTAL_ACTIVE_POWER = 0x0034  # W (S32)

    # Serial number location
    REG_SERIAL = 0x8000  # 8 registers

    def __init__(
        self,
        serial_number: str = "IAM3080001",
        unit_id: int = 1,
        ct_ratio: int = 1,  # CT ratio for current scaling
    ):
        """
        Initialize IAMMeter simulator.

        Args:
            serial_number: Device serial number.
            unit_id: Modbus unit ID.
            ct_ratio: Current transformer ratio.
        """
        super().__init__(
            register_map={},
            unit_id=unit_id,
            serial_number=serial_number,
            name=f"IAMMeter({serial_number})",
        )

        self.ct_ratio = ct_ratio

        # Per-phase state
        self.voltage = [230.0, 230.0, 230.0]  # V
        self.current = [5.0, 5.0, 5.0]  # A
        self.active_power = [1000.0, 1000.0, 1000.0]  # W
        self.power_factor = [0.95, 0.95, 0.95]
        self.frequency = 50.0  # Hz

        # Energy counters
        self.import_energy_kwh = 1000.0
        self.export_energy_kwh = 500.0

        # Simulation mode
        self.grid_tie_mode = True  # True = can export to grid

        # Initialize registers
        self._init_registers()

    def _init_registers(self) -> None:
        """Initialize register map."""
        # Set serial number
        self.set_serial_number_registers(
            self.REG_SERIAL,
            self.serial_number,
            num_registers=8
        )

        self._update_registers()

    def _update_registers(self) -> None:
        """Update registers from state."""
        for phase in range(3):
            offset = phase * 2  # Registers are in pairs (high, low for 32-bit)

            # Voltage (V * 100)
            self.set_register(self.REG_VOLTAGE_A + phase, int(self.voltage[phase] * 100))

            # Current (A * 100)
            self.set_register(self.REG_CURRENT_A + phase, int(self.current[phase] * 100))

            # Active power (W) - signed 32-bit
            power = int(self.active_power[phase])
            self.set_register(self.REG_ACTIVE_POWER_A + offset, (power >> 16) & 0xFFFF)
            self.set_register(self.REG_ACTIVE_POWER_A + offset + 1, power & 0xFFFF)

            # Reactive power (VAR)
            reactive = int(self.active_power[phase] * 0.1)  # Approximate
            self.set_register(self.REG_REACTIVE_POWER_A + offset, (reactive >> 16) & 0xFFFF)
            self.set_register(self.REG_REACTIVE_POWER_A + offset + 1, reactive & 0xFFFF)

            # Apparent power (VA)
            apparent = int(self.active_power[phase] / self.power_factor[phase])
            self.set_register(self.REG_APPARENT_POWER_A + offset, (apparent >> 16) & 0xFFFF)
            self.set_register(self.REG_APPARENT_POWER_A + offset + 1, apparent & 0xFFFF)

            # Power factor (* 1000)
            pf = int(self.power_factor[phase] * 1000)
            self.set_register(self.REG_POWER_FACTOR_A + phase, pf)

        # Frequency (Hz * 100)
        self.set_register(self.REG_FREQUENCY, int(self.frequency * 100))

        # Total active power (S32)
        total_power = int(sum(self.active_power))
        self.set_register(self.REG_TOTAL_ACTIVE_POWER, (total_power >> 16) & 0xFFFF)
        self.set_register(self.REG_TOTAL_ACTIVE_POWER + 1, total_power & 0xFFFF)

        # Energy counters (kWh * 100, U32)
        import_val = int(self.import_energy_kwh * 100)
        self.set_register(self.REG_IMPORT_ENERGY, (import_val >> 16) & 0xFFFF)
        self.set_register(self.REG_IMPORT_ENERGY + 1, import_val & 0xFFFF)

        export_val = int(self.export_energy_kwh * 100)
        self.set_register(self.REG_EXPORT_ENERGY, (export_val >> 16) & 0xFFFF)
        self.set_register(self.REG_EXPORT_ENERGY + 1, export_val & 0xFFFF)

    def simulate_tick(self, dt: float) -> None:
        """
        Update simulation state.

        Args:
            dt: Time delta in seconds.
        """
        now = datetime.now()
        hour = now.hour + now.minute / 60.0

        # Simulate load pattern
        base_power_per_phase = 1000

        if 7 <= hour <= 9:  # Morning peak
            load_factor = 2.0
        elif 18 <= hour <= 22:  # Evening peak
            load_factor = 3.0
        elif 0 <= hour <= 6:  # Night
            load_factor = 0.3
        else:  # Day
            load_factor = 1.0

        # Add some imbalance between phases
        phase_factors = [1.0, 0.9, 1.1]

        for phase in range(3):
            self.active_power[phase] = (
                base_power_per_phase *
                load_factor *
                phase_factors[phase] *
                (1 + random.uniform(-0.1, 0.1))
            )

            # Update voltage with small variations
            self.voltage[phase] = 230.0 + random.uniform(-3, 3)

            # Calculate current from power and voltage
            if self.voltage[phase] > 0:
                self.current[phase] = abs(self.active_power[phase]) / self.voltage[phase]

            # Power factor varies slightly
            self.power_factor[phase] = 0.95 + random.uniform(-0.03, 0.03)

        # Frequency variation
        self.frequency = 50.0 + random.uniform(-0.05, 0.05)

        # Update energy counters
        total_power = sum(self.active_power)
        energy_delta = (abs(total_power) / 1000) * (dt / 3600)  # kWh

        if total_power > 0:
            self.import_energy_kwh += energy_delta
        else:
            self.export_energy_kwh += energy_delta

        self._update_registers()

    def set_grid_power(self, power_w: float) -> None:
        """
        Set the grid power for testing.

        Positive = import from grid, Negative = export to grid.

        Args:
            power_w: Total grid power in watts.
        """
        power_per_phase = power_w / 3
        for phase in range(3):
            self.active_power[phase] = power_per_phase * (0.9 + phase * 0.1)

        self._update_registers()

    def get_state(self) -> Dict[str, Any]:
        """Get current simulator state."""
        return {
            "serial_number": self.serial_number,
            "total_power_w": sum(self.active_power),
            "voltage_avg_v": sum(self.voltage) / 3,
            "current_total_a": sum(self.current),
            "frequency_hz": self.frequency,
            "power_factor_avg": sum(self.power_factor) / 3,
            "import_energy_kwh": self.import_energy_kwh,
            "export_energy_kwh": self.export_energy_kwh,
        }
