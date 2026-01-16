"""
Pytes battery simulator.

Simulates a Pytes battery rack with command-based protocol.
"""
import asyncio
import random
from datetime import datetime
from typing import Dict, Any, Optional

from .base_simulator import BaseSimulator


class PytesBatterySimulator(BaseSimulator):
    """
    Simulates a Pytes battery with command protocol.

    Responds to text-based commands for battery status queries.
    """

    def __init__(
        self,
        serial_number: str = "PYTES00001",
        capacity_wh: int = 5120,
        initial_soc: float = 75.0,
        num_cells: int = 16,
    ):
        """
        Initialize Pytes battery simulator.

        Args:
            serial_number: Battery serial number.
            capacity_wh: Battery capacity in Wh.
            initial_soc: Initial state of charge (%).
            num_cells: Number of cells in battery.
        """
        super().__init__(
            serial_number=serial_number,
            name=f"PytesBattery({serial_number})",
        )

        self.capacity_wh = capacity_wh
        self.num_cells = num_cells

        # Battery state
        self.soc = initial_soc
        self.voltage = 51.2  # V (nominal)
        self.current = 0.0  # A (positive = charging)
        self.power = 0.0  # W

        # Cell data
        self.cell_voltages = [3.2] * num_cells  # V per cell
        self.cell_temps = [25.0] * num_cells  # °C per cell

        # Battery info
        self.cycles = random.randint(50, 200)
        self.firmware_version = "1.5.3"
        self.manufacture_date = "2024-06-15"

        # Status flags
        self.charging = False
        self.discharging = False
        self.balancing = False
        self.fault = False
        self.alarm = False

    async def handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle battery command connection.

        Pytes batteries use a line-based text protocol.
        """
        while self._running:
            try:
                # Read command line
                data = await asyncio.wait_for(reader.readline(), timeout=30.0)
                if not data:
                    break

                command = data.decode('ascii', errors='ignore').strip()
                if not command:
                    continue

                self._total_requests += 1

                # Process command
                response = self._process_command(command)

                # Send response
                writer.write(response.encode('ascii'))
                await writer.drain()

            except asyncio.TimeoutError:
                # Client idle timeout
                break
            except (ConnectionResetError, BrokenPipeError):
                break
            except Exception as e:
                writer.write(f"Error: {e}\r\n".encode())
                await writer.drain()

    def _process_command(self, command: str) -> str:
        """
        Process battery command and return response.

        Args:
            command: Command string.

        Returns:
            Response string.
        """
        cmd = command.lower().strip()

        if cmd.startswith("pwr"):
            return self._format_power_response()
        elif cmd.startswith("bat"):
            return self._format_battery_response()
        elif cmd.startswith("info"):
            return self._format_info_response()
        elif cmd.startswith("stat"):
            return self._format_status_response()
        elif cmd.startswith("cell"):
            return self._format_cell_response()
        elif cmd.startswith("help"):
            return self._format_help_response()
        else:
            return f"Unknown command: {command}\r\nCommand completed\r\n"

    def _format_power_response(self) -> str:
        """Format power status response."""
        return f"""Voltage         :      {int(self.voltage * 1000):>8}
Current         :      {int(self.current * 1000):>8}
Temperature     :      {int(self.cell_temps[0] * 1000):>8}
Coulomb         :      {int(self.soc):>8}

Command completed
"""

    def _format_battery_response(self) -> str:
        """Format battery status response."""
        min_cell = min(self.cell_voltages)
        max_cell = max(self.cell_voltages)
        min_temp = min(self.cell_temps)
        max_temp = max(self.cell_temps)

        status_bits = 0
        if self.charging:
            status_bits |= 0x01
        if self.discharging:
            status_bits |= 0x02
        if self.balancing:
            status_bits |= 0x04
        if self.fault:
            status_bits |= 0x80

        return f"""@ Battery
Voltage              :      {int(self.voltage * 1000):>8} mV
Current              :      {int(self.current * 1000):>8} mA
SOC                  :      {int(self.soc):>8} %
SOH                  :      {100:>8} %
Cycles               :      {self.cycles:>8}
Status               :      0x{status_bits:02X}
Cell Count           :      {self.num_cells:>8}
Cell V Min           :      {int(min_cell * 1000):>8} mV
Cell V Max           :      {int(max_cell * 1000):>8} mV
Cell V Diff          :      {int((max_cell - min_cell) * 1000):>8} mV
Temp Min             :      {int(min_temp * 10):>8} 0.1C
Temp Max             :      {int(max_temp * 10):>8} 0.1C

Command completed
"""

    def _format_info_response(self) -> str:
        """Format device info response."""
        return f"""@ Device Info
Serial               :      {self.serial_number}
Manufacturer         :      Pytes
Model                :      E-Box-48100R
Firmware             :      {self.firmware_version}
Manufacture Date     :      {self.manufacture_date}
Capacity             :      {self.capacity_wh} Wh
Nominal Voltage      :      51.2 V
Cell Count           :      {self.num_cells}

Command completed
"""

    def _format_status_response(self) -> str:
        """Format status response."""
        state = "Idle"
        if self.charging:
            state = "Charging"
        elif self.discharging:
            state = "Discharging"
        elif self.fault:
            state = "Fault"

        return f"""@ Status
State                :      {state}
Charging             :      {"Yes" if self.charging else "No"}
Discharging          :      {"Yes" if self.discharging else "No"}
Balancing            :      {"Yes" if self.balancing else "No"}
Fault                :      {"Yes" if self.fault else "No"}
Alarm                :      {"Yes" if self.alarm else "No"}

Command completed
"""

    def _format_cell_response(self) -> str:
        """Format cell voltages response."""
        lines = ["@ Cell Voltages (mV)"]
        for i, voltage in enumerate(self.cell_voltages):
            lines.append(f"Cell {i+1:02d}             :      {int(voltage * 1000):>8}")

        lines.append("")
        lines.append("@ Cell Temperatures (0.1C)")
        for i, temp in enumerate(self.cell_temps):
            lines.append(f"Temp {i+1:02d}             :      {int(temp * 10):>8}")

        lines.append("")
        lines.append("Command completed")
        return "\r\n".join(lines) + "\r\n"

    def _format_help_response(self) -> str:
        """Format help response."""
        return """Available commands:
  pwr     - Power readings (voltage, current, temp, SOC)
  bat     - Battery status
  info    - Device information
  stat    - Operational status
  cell    - Cell voltages and temperatures
  help    - This help message

Command completed
"""

    def simulate_tick(self, dt: float) -> None:
        """
        Update battery simulation.

        Args:
            dt: Time delta in seconds.
        """
        # Update voltage based on SOC
        # LiFePO4 voltage curve: ~3.0V empty to ~3.4V full per cell
        cell_voltage = 3.0 + (self.soc / 100) * 0.4
        self.voltage = cell_voltage * self.num_cells

        # Update cell voltages with slight imbalance
        for i in range(self.num_cells):
            imbalance = random.uniform(-0.02, 0.02)
            self.cell_voltages[i] = cell_voltage + imbalance

        # Calculate power from current
        self.power = self.voltage * self.current

        # Update SOC based on current
        if self.current != 0:
            energy_wh = self.power * (dt / 3600)
            soc_delta = (energy_wh / self.capacity_wh) * 100
            self.soc = max(0, min(100, self.soc + soc_delta))

        # Determine charging/discharging state
        self.charging = self.current > 0.5
        self.discharging = self.current < -0.5

        # Temperature simulation
        ambient = 25.0
        # Batteries heat up under load
        heat_factor = abs(self.current) / 50.0  # Normalize by max current
        target_temp = ambient + heat_factor * 10

        for i in range(self.num_cells):
            # Slow temperature change
            temp_diff = target_temp - self.cell_temps[i]
            self.cell_temps[i] += temp_diff * 0.01 * dt
            # Add slight variation between cells
            self.cell_temps[i] += random.uniform(-0.1, 0.1)

        # Check for balancing (when SOC high and cell diff > threshold)
        cell_diff = max(self.cell_voltages) - min(self.cell_voltages)
        self.balancing = self.soc > 90 and cell_diff > 0.02

    def set_power(self, power_w: float) -> None:
        """
        Set battery power for simulation.

        Positive = charging, Negative = discharging.

        Args:
            power_w: Power in watts.
        """
        if self.voltage > 0:
            self.current = power_w / self.voltage
            self.power = power_w

    def inject_fault(self, fault_type: str = "overvoltage") -> None:
        """
        Inject a fault for testing.

        Args:
            fault_type: Type of fault to inject.
        """
        self.fault = True
        self.alarm = True

    def clear_fault(self) -> None:
        """Clear all faults."""
        self.fault = False
        self.alarm = False

    def get_state(self) -> Dict[str, Any]:
        """Get current battery state."""
        return {
            "serial_number": self.serial_number,
            "soc": self.soc,
            "voltage": self.voltage,
            "current": self.current,
            "power": self.power,
            "temperature": sum(self.cell_temps) / len(self.cell_temps),
            "charging": self.charging,
            "discharging": self.discharging,
            "fault": self.fault,
            "cycles": self.cycles,
        }
