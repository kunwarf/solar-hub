"""
Simulator manager for coordinating multiple device simulators.

Provides centralized management of virtual devices for testing.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .base_simulator import BaseSimulator
from .inverter_simulator import PowdriveSimulator
from .meter_simulator import IAMMeterSimulator
from .battery_simulator import PytesBatterySimulator

logger = logging.getLogger(__name__)


@dataclass
class SimulatorInfo:
    """Information about a registered simulator."""
    simulator: BaseSimulator
    port: int
    host: str = "127.0.0.1"
    auto_start: bool = True
    started_at: Optional[datetime] = None


class SimulatorManager:
    """
    Manages multiple device simulators.

    Provides:
    - Centralized lifecycle management
    - Port allocation
    - Simulation tick coordination
    - Health monitoring
    """

    def __init__(
        self,
        base_port: int = 8500,
        host: str = "127.0.0.1",
    ):
        """
        Initialize simulator manager.

        Args:
            base_port: Starting port for auto-allocation.
            host: Default host to bind simulators to.
        """
        self.base_port = base_port
        self.host = host

        self._simulators: Dict[str, SimulatorInfo] = {}
        self._next_port = base_port
        self._running = False
        self._tick_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running

    @property
    def simulator_count(self) -> int:
        """Get number of registered simulators."""
        return len(self._simulators)

    def add_inverter(
        self,
        name: str,
        serial_number: str,
        port: Optional[int] = None,
        rated_power_w: int = 12000,
        battery_soc: float = 75.0,
        auto_start: bool = True,
    ) -> PowdriveSimulator:
        """
        Add a Powdrive inverter simulator.

        Args:
            name: Unique name for the simulator.
            serial_number: Device serial number.
            port: Port to use (auto-allocated if None).
            rated_power_w: Rated power in watts.
            battery_soc: Initial battery SOC.
            auto_start: Start automatically with manager.

        Returns:
            The created simulator.
        """
        if port is None:
            port = self._allocate_port()

        simulator = PowdriveSimulator(
            serial_number=serial_number,
            rated_power_w=rated_power_w,
            battery_capacity_pct=battery_soc,
        )

        self._simulators[name] = SimulatorInfo(
            simulator=simulator,
            port=port,
            host=self.host,
            auto_start=auto_start,
        )

        logger.info(f"Added inverter simulator '{name}' ({serial_number}) on port {port}")
        return simulator

    def add_meter(
        self,
        name: str,
        serial_number: str,
        port: Optional[int] = None,
        auto_start: bool = True,
    ) -> IAMMeterSimulator:
        """
        Add an IAMMeter simulator.

        Args:
            name: Unique name for the simulator.
            serial_number: Device serial number.
            port: Port to use (auto-allocated if None).
            auto_start: Start automatically with manager.

        Returns:
            The created simulator.
        """
        if port is None:
            port = self._allocate_port()

        simulator = IAMMeterSimulator(
            serial_number=serial_number,
        )

        self._simulators[name] = SimulatorInfo(
            simulator=simulator,
            port=port,
            host=self.host,
            auto_start=auto_start,
        )

        logger.info(f"Added meter simulator '{name}' ({serial_number}) on port {port}")
        return simulator

    def add_battery(
        self,
        name: str,
        serial_number: str,
        port: Optional[int] = None,
        capacity_wh: int = 5120,
        initial_soc: float = 75.0,
        auto_start: bool = True,
    ) -> PytesBatterySimulator:
        """
        Add a Pytes battery simulator.

        Args:
            name: Unique name for the simulator.
            serial_number: Device serial number.
            port: Port to use (auto-allocated if None).
            capacity_wh: Battery capacity in Wh.
            initial_soc: Initial state of charge.
            auto_start: Start automatically with manager.

        Returns:
            The created simulator.
        """
        if port is None:
            port = self._allocate_port()

        simulator = PytesBatterySimulator(
            serial_number=serial_number,
            capacity_wh=capacity_wh,
            initial_soc=initial_soc,
        )

        self._simulators[name] = SimulatorInfo(
            simulator=simulator,
            port=port,
            host=self.host,
            auto_start=auto_start,
        )

        logger.info(f"Added battery simulator '{name}' ({serial_number}) on port {port}")
        return simulator

    def add_simulator(
        self,
        name: str,
        simulator: BaseSimulator,
        port: Optional[int] = None,
        auto_start: bool = True,
    ) -> None:
        """
        Add a custom simulator.

        Args:
            name: Unique name for the simulator.
            simulator: Simulator instance.
            port: Port to use (auto-allocated if None).
            auto_start: Start automatically with manager.
        """
        if port is None:
            port = self._allocate_port()

        self._simulators[name] = SimulatorInfo(
            simulator=simulator,
            port=port,
            host=self.host,
            auto_start=auto_start,
        )

        logger.info(f"Added custom simulator '{name}' on port {port}")

    def get_simulator(self, name: str) -> Optional[BaseSimulator]:
        """
        Get a simulator by name.

        Args:
            name: Simulator name.

        Returns:
            Simulator instance or None.
        """
        info = self._simulators.get(name)
        return info.simulator if info else None

    def get_port(self, name: str) -> Optional[int]:
        """
        Get the port for a simulator.

        Args:
            name: Simulator name.

        Returns:
            Port number or None.
        """
        info = self._simulators.get(name)
        return info.port if info else None

    def _allocate_port(self) -> int:
        """Allocate the next available port."""
        port = self._next_port
        self._next_port += 1
        return port

    async def start_all(self) -> None:
        """Start all auto-start simulators."""
        if self._running:
            logger.warning("SimulatorManager already running")
            return

        self._running = True

        # Start all auto-start simulators
        start_tasks = []
        for name, info in self._simulators.items():
            if info.auto_start and not info.simulator.is_running:
                start_tasks.append(self._start_simulator(name, info))

        if start_tasks:
            await asyncio.gather(*start_tasks)

        # Start coordinated tick loop
        self._tick_task = asyncio.create_task(
            self._tick_loop(),
            name="simulator_manager_tick"
        )

        logger.info(f"SimulatorManager started with {len(self._simulators)} simulators")

    async def _start_simulator(self, name: str, info: SimulatorInfo) -> None:
        """Start a single simulator."""
        try:
            actual_port = await info.simulator.start(info.host, info.port)
            info.port = actual_port
            info.started_at = datetime.now()
            logger.debug(f"Started simulator '{name}' on {info.host}:{actual_port}")
        except Exception as e:
            logger.error(f"Failed to start simulator '{name}': {e}")

    async def stop_all(self) -> None:
        """Stop all simulators."""
        if not self._running:
            return

        self._running = False

        # Cancel tick task
        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass
            self._tick_task = None

        # Stop all simulators
        stop_tasks = []
        for name, info in self._simulators.items():
            if info.simulator.is_running:
                stop_tasks.append(info.simulator.stop())

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        logger.info("SimulatorManager stopped")

    async def start_simulator(self, name: str) -> bool:
        """
        Start a specific simulator.

        Args:
            name: Simulator name.

        Returns:
            True if started successfully.
        """
        info = self._simulators.get(name)
        if not info:
            logger.error(f"Simulator '{name}' not found")
            return False

        if info.simulator.is_running:
            return True

        await self._start_simulator(name, info)
        return info.simulator.is_running

    async def stop_simulator(self, name: str) -> bool:
        """
        Stop a specific simulator.

        Args:
            name: Simulator name.

        Returns:
            True if stopped successfully.
        """
        info = self._simulators.get(name)
        if not info:
            return False

        if info.simulator.is_running:
            await info.simulator.stop()

        return True

    async def _tick_loop(self, interval: float = 1.0) -> None:
        """
        Coordinated tick loop for all simulators.

        This ensures all simulators update together.
        """
        last_tick = datetime.now()

        while self._running:
            try:
                await asyncio.sleep(interval)

                now = datetime.now()
                dt = (now - last_tick).total_seconds()
                last_tick = now

                # Tick all running simulators
                for name, info in self._simulators.items():
                    if info.simulator.is_running:
                        try:
                            info.simulator.simulate_tick(dt)
                        except Exception as e:
                            logger.error(f"Error in tick for '{name}': {e}")

            except asyncio.CancelledError:
                break

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all simulators."""
        stats = {
            "running": self._running,
            "simulator_count": len(self._simulators),
            "simulators": {},
        }

        for name, info in self._simulators.items():
            sim_stats = info.simulator.get_stats()
            sim_stats["port"] = info.port
            sim_stats["started_at"] = info.started_at.isoformat() if info.started_at else None
            stats["simulators"][name] = sim_stats

        return stats

    def list_simulators(self) -> List[Dict[str, Any]]:
        """List all registered simulators."""
        result = []
        for name, info in self._simulators.items():
            result.append({
                "name": name,
                "type": type(info.simulator).__name__,
                "serial_number": info.simulator.serial_number,
                "port": info.port,
                "running": info.simulator.is_running,
            })
        return result


# Convenience function for creating a standard test setup
def create_standard_site(
    manager: SimulatorManager,
    site_prefix: str = "SITE1",
    inverter_count: int = 1,
    meter_count: int = 1,
    battery_count: int = 1,
) -> Dict[str, BaseSimulator]:
    """
    Create a standard solar site configuration.

    Args:
        manager: SimulatorManager to add devices to.
        site_prefix: Prefix for serial numbers.
        inverter_count: Number of inverters.
        meter_count: Number of meters.
        battery_count: Number of batteries.

    Returns:
        Dictionary of name -> simulator.
    """
    devices = {}

    for i in range(inverter_count):
        name = f"{site_prefix}_inverter_{i+1}"
        serial = f"PD12K{site_prefix}{i+1:03d}"
        devices[name] = manager.add_inverter(name, serial)

    for i in range(meter_count):
        name = f"{site_prefix}_meter_{i+1}"
        serial = f"IAM{site_prefix}{i+1:04d}"
        devices[name] = manager.add_meter(name, serial)

    for i in range(battery_count):
        name = f"{site_prefix}_battery_{i+1}"
        serial = f"PYTES{site_prefix}{i+1:03d}"
        devices[name] = manager.add_battery(name, serial)

    return devices
