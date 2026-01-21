"""
Device Simulator for System B.

Simulates a solar device (inverter, battery, meter) that:
1. Registers with the server
2. Sends periodic telemetry data
3. Handles reconnection scenarios

Usage:
    python -m tools.device_simulator --server-url http://localhost:8000 --device-type inverter

    # Or as a module
    from tools.device_simulator import DeviceSimulator
    simulator = DeviceSimulator(server_url="http://localhost:8000", device_type="inverter")
    await simulator.run()
"""
import asyncio
import logging
import random
import signal
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DeviceSimulator:
    """
    Simulates a solar energy device sending telemetry to System B.

    Supports different device types with appropriate metrics:
    - inverter: PV power, AC power, efficiency, temperature
    - battery: SOC, voltage, current, temperature, power
    - meter: grid power, import/export energy, voltage, current
    """

    # Metric definitions for each device type
    DEVICE_METRICS = {
        "inverter": {
            "pv_power_w": {"min": 0, "max": 12000, "unit": "W"},
            "pv_voltage_v": {"min": 0, "max": 600, "unit": "V"},
            "pv_current_a": {"min": 0, "max": 30, "unit": "A"},
            "ac_power_w": {"min": 0, "max": 12000, "unit": "W"},
            "ac_voltage_v": {"min": 210, "max": 250, "unit": "V"},
            "ac_current_a": {"min": 0, "max": 60, "unit": "A"},
            "ac_frequency_hz": {"min": 49.5, "max": 50.5, "unit": "Hz"},
            "efficiency_pct": {"min": 90, "max": 99, "unit": "%"},
            "temperature_c": {"min": 20, "max": 65, "unit": "C"},
            "energy_today_kwh": {"min": 0, "max": 100, "unit": "kWh", "cumulative": True},
            "energy_total_kwh": {"min": 0, "max": 100000, "unit": "kWh", "cumulative": True},
        },
        "battery": {
            "soc_pct": {"min": 10, "max": 100, "unit": "%"},
            "soh_pct": {"min": 80, "max": 100, "unit": "%"},
            "voltage_v": {"min": 45, "max": 58, "unit": "V"},
            "current_a": {"min": -100, "max": 100, "unit": "A"},
            "power_w": {"min": -5000, "max": 5000, "unit": "W"},
            "temperature_c": {"min": 15, "max": 45, "unit": "C"},
            "charge_energy_kwh": {"min": 0, "max": 10000, "unit": "kWh", "cumulative": True},
            "discharge_energy_kwh": {"min": 0, "max": 10000, "unit": "kWh", "cumulative": True},
            "cycles": {"min": 0, "max": 6000, "unit": "cycles", "cumulative": True},
        },
        "meter": {
            "grid_power_w": {"min": -10000, "max": 10000, "unit": "W"},
            "grid_voltage_v": {"min": 210, "max": 250, "unit": "V"},
            "grid_current_a": {"min": 0, "max": 60, "unit": "A"},
            "grid_frequency_hz": {"min": 49.5, "max": 50.5, "unit": "Hz"},
            "import_energy_kwh": {"min": 0, "max": 100000, "unit": "kWh", "cumulative": True},
            "export_energy_kwh": {"min": 0, "max": 100000, "unit": "kWh", "cumulative": True},
            "power_factor": {"min": 0.8, "max": 1.0, "unit": ""},
        },
    }

    def __init__(
        self,
        server_url: str,
        site_id: Optional[UUID] = None,
        device_type: str = "inverter",
        serial_number: Optional[str] = None,
        telemetry_interval: int = 10,
        reconnect_interval: int = 30,
        simulate_disconnects: bool = False,
        disconnect_probability: float = 0.01,
    ):
        """
        Initialize the device simulator.

        Args:
            server_url: Base URL of the System B server (e.g., http://localhost:8000)
            site_id: Site UUID (generated if not provided)
            device_type: Type of device to simulate (inverter, battery, meter)
            serial_number: Device serial number (generated if not provided)
            telemetry_interval: Seconds between telemetry sends
            reconnect_interval: Seconds to wait before reconnecting after disconnect
            simulate_disconnects: Whether to randomly simulate disconnections
            disconnect_probability: Probability of disconnect per telemetry cycle (0.0-1.0)
        """
        self.server_url = server_url.rstrip("/")
        self.site_id = site_id or uuid4()
        self.device_type = device_type.lower()
        self.serial_number = serial_number or self._generate_serial_number()
        self.telemetry_interval = telemetry_interval
        self.reconnect_interval = reconnect_interval
        self.simulate_disconnects = simulate_disconnects
        self.disconnect_probability = disconnect_probability

        # Device state
        self.device_id: Optional[UUID] = None
        self.is_registered = False
        self.is_connected = False
        self._running = False
        self._client: Optional[httpx.AsyncClient] = None

        # Metric state (for cumulative values and realistic simulation)
        self._metric_state: Dict[str, float] = {}
        self._init_metric_state()

        # Validate device type
        if self.device_type not in self.DEVICE_METRICS:
            raise ValueError(
                f"Invalid device type: {device_type}. "
                f"Supported types: {list(self.DEVICE_METRICS.keys())}"
            )

    def _generate_serial_number(self) -> str:
        """Generate a realistic serial number."""
        prefix_map = {
            "inverter": "INV",
            "battery": "BAT",
            "meter": "MTR",
        }
        prefix = prefix_map.get(self.device_type, "DEV")
        random_part = "".join(random.choices("0123456789ABCDEF", k=8))
        return f"{prefix}-{random_part}"

    def _init_metric_state(self) -> None:
        """Initialize metric state with starting values."""
        metrics = self.DEVICE_METRICS.get(self.device_type, {})
        for name, config in metrics.items():
            if config.get("cumulative"):
                # Cumulative metrics start at a realistic value
                self._metric_state[name] = random.uniform(
                    config["min"], config["max"] * 0.5
                )
            else:
                # Regular metrics start at mid-range
                self._metric_state[name] = (config["min"] + config["max"]) / 2

    def _generate_telemetry(self) -> Dict[str, Any]:
        """Generate realistic telemetry values."""
        metrics = self.DEVICE_METRICS.get(self.device_type, {})
        telemetry = {}

        # Time-based factors for realistic simulation
        hour = datetime.now().hour
        is_daytime = 6 <= hour <= 18
        solar_factor = max(0, 1 - abs(hour - 12) / 6) if is_daytime else 0

        for name, config in metrics.items():
            min_val = config["min"]
            max_val = config["max"]

            if config.get("cumulative"):
                # Cumulative metrics only increase
                increment = random.uniform(0, (max_val - min_val) / 1000)
                self._metric_state[name] += increment
                telemetry[name] = round(self._metric_state[name], 2)
            else:
                # Apply time-based variations for solar metrics
                if "pv" in name or "solar" in name:
                    # PV metrics depend on time of day
                    effective_max = max_val * solar_factor
                    value = random.uniform(min_val, max(min_val, effective_max))
                elif "power" in name and self.device_type == "inverter":
                    # AC power follows PV power
                    value = random.uniform(min_val, max_val * solar_factor * 0.95)
                elif "temperature" in name:
                    # Temperature varies slowly
                    current = self._metric_state.get(name, (min_val + max_val) / 2)
                    change = random.uniform(-0.5, 0.5)
                    value = max(min_val, min(max_val, current + change))
                    self._metric_state[name] = value
                elif "soc" in name:
                    # Battery SOC changes based on power flow
                    current = self._metric_state.get(name, 50)
                    # Charge during day, discharge at night
                    change = random.uniform(-0.5, 1.0) if is_daytime else random.uniform(-1.0, 0.2)
                    value = max(min_val, min(max_val, current + change))
                    self._metric_state[name] = value
                elif "grid_power" in name:
                    # Grid power is negative when exporting
                    if is_daytime and solar_factor > 0.3:
                        value = random.uniform(min_val, 0)  # Exporting
                    else:
                        value = random.uniform(0, max_val * 0.5)  # Importing
                else:
                    # Other metrics vary randomly within range
                    current = self._metric_state.get(name, (min_val + max_val) / 2)
                    change = random.uniform(-0.1, 0.1) * (max_val - min_val)
                    value = max(min_val, min(max_val, current + change))
                    self._metric_state[name] = value

                telemetry[name] = round(value, 2)

        return telemetry

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def register(self) -> bool:
        """
        Register the device with the server.

        Returns:
            True if registration successful, False otherwise.
        """
        client = await self._get_client()

        payload = {
            "site_id": str(self.site_id),
            "device_type": self.device_type,
            "serial_number": self.serial_number,
            "firmware_version": "1.0.0",
            "hardware_version": "1.0",
            "device_metadata": {
                "manufacturer": "SolarHub Simulator",
                "model": f"SIM-{self.device_type.upper()}-1000",
                "simulator": True,
            },
        }

        try:
            response = await client.post(
                f"{self.server_url}/api/v1/devices/register",
                json=payload,
            )

            if response.status_code in (200, 201):
                data = response.json()
                self.device_id = UUID(data["id"])
                self.is_registered = True
                self.is_connected = True

                newly_registered = data.get("newly_registered", True)
                if newly_registered:
                    logger.info(
                        f"Device registered successfully: {self.serial_number} "
                        f"(id: {self.device_id})"
                    )
                else:
                    logger.info(
                        f"Device reconnected: {self.serial_number} "
                        f"(id: {self.device_id})"
                    )
                return True
            else:
                logger.error(
                    f"Registration failed: {response.status_code} - {response.text}"
                )
                return False

        except httpx.RequestError as e:
            logger.error(f"Registration request failed: {e}")
            return False

    async def send_telemetry(self) -> bool:
        """
        Send telemetry data to the server.

        Returns:
            True if telemetry sent successfully, False otherwise.
        """
        if not self.device_id:
            logger.warning("Cannot send telemetry: device not registered")
            return False

        client = await self._get_client()
        telemetry = self._generate_telemetry()

        payload = {
            "points": [
                {
                    "device_id": str(self.device_id),
                    "site_id": str(self.site_id),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source": "simulator",
                    "metrics": telemetry,
                }
            ]
        }

        try:
            response = await client.post(
                f"{self.server_url}/api/v1/telemetry/ingest",
                json=payload,
            )

            if response.status_code == 201:
                data = response.json()
                logger.debug(
                    f"Telemetry sent: {data['inserted']} metrics "
                    f"for device {self.serial_number}"
                )
                return True
            else:
                logger.warning(
                    f"Telemetry send failed: {response.status_code} - {response.text}"
                )
                return False

        except httpx.RequestError as e:
            logger.error(f"Telemetry request failed: {e}")
            self.is_connected = False
            return False

    async def disconnect(self, reason: str = "Simulated disconnect") -> None:
        """Notify server of disconnection."""
        if not self.device_id:
            return

        client = await self._get_client()

        try:
            await client.post(
                f"{self.server_url}/api/v1/devices/{self.device_id}/disconnect",
                params={"reason": reason},
            )
            logger.info(f"Device disconnected: {self.serial_number} - {reason}")
        except httpx.RequestError as e:
            logger.warning(f"Disconnect notification failed: {e}")

        self.is_connected = False

    async def run(self) -> None:
        """
        Run the simulator main loop.

        Continuously:
        1. Register/reconnect if needed
        2. Send telemetry at configured interval
        3. Handle disconnections and reconnections
        """
        self._running = True
        logger.info(
            f"Starting device simulator: {self.device_type} - {self.serial_number}"
        )
        logger.info(f"Server: {self.server_url}")
        logger.info(f"Site ID: {self.site_id}")
        logger.info(f"Telemetry interval: {self.telemetry_interval}s")

        while self._running:
            try:
                # Register/reconnect if needed
                if not self.is_connected:
                    logger.info("Attempting to register/reconnect...")
                    success = await self.register()
                    if not success:
                        logger.warning(
                            f"Registration failed, retrying in {self.reconnect_interval}s"
                        )
                        await asyncio.sleep(self.reconnect_interval)
                        continue

                # Send telemetry
                await self.send_telemetry()

                # Simulate random disconnects
                if self.simulate_disconnects and random.random() < self.disconnect_probability:
                    await self.disconnect("Random disconnect simulation")
                    await asyncio.sleep(self.reconnect_interval)
                    continue

                # Wait for next telemetry cycle
                await asyncio.sleep(self.telemetry_interval)

            except asyncio.CancelledError:
                logger.info("Simulator cancelled")
                break
            except Exception as e:
                logger.error(f"Error in simulator loop: {e}")
                await asyncio.sleep(self.reconnect_interval)

        # Cleanup
        await self.stop()

    async def stop(self) -> None:
        """Stop the simulator and cleanup."""
        self._running = False

        if self.is_connected:
            await self.disconnect("Simulator stopped")

        if self._client and not self._client.is_closed:
            await self._client.aclose()

        logger.info(f"Simulator stopped: {self.serial_number}")


class MultiDeviceSimulator:
    """
    Simulate multiple devices simultaneously.
    """

    def __init__(
        self,
        server_url: str,
        site_id: Optional[UUID] = None,
        devices: Optional[List[Dict[str, Any]]] = None,
        telemetry_interval: int = 10,
    ):
        """
        Initialize multi-device simulator.

        Args:
            server_url: Base URL of the System B server
            site_id: Site UUID (all devices belong to same site)
            devices: List of device configurations, each with:
                     - device_type: inverter, battery, meter
                     - serial_number: optional serial number
                     - count: number of devices of this type (default 1)
            telemetry_interval: Seconds between telemetry sends
        """
        self.server_url = server_url
        self.site_id = site_id or uuid4()
        self.telemetry_interval = telemetry_interval
        self.simulators: List[DeviceSimulator] = []

        # Default device configuration if none provided
        if devices is None:
            devices = [
                {"device_type": "inverter", "count": 1},
                {"device_type": "battery", "count": 1},
                {"device_type": "meter", "count": 1},
            ]

        # Create simulators
        for device_config in devices:
            count = device_config.get("count", 1)
            for i in range(count):
                simulator = DeviceSimulator(
                    server_url=self.server_url,
                    site_id=self.site_id,
                    device_type=device_config["device_type"],
                    serial_number=device_config.get("serial_number"),
                    telemetry_interval=self.telemetry_interval,
                )
                self.simulators.append(simulator)

    async def run(self) -> None:
        """Run all device simulators concurrently."""
        logger.info(f"Starting {len(self.simulators)} device simulators")
        logger.info(f"Site ID: {self.site_id}")

        tasks = [asyncio.create_task(sim.run()) for sim in self.simulators]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stop all simulators."""
        for simulator in self.simulators:
            await simulator.stop()


async def main():
    """Main entry point for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Device Simulator for System B")
    parser.add_argument(
        "--server-url",
        default="http://localhost:8000",
        help="System B server URL",
    )
    parser.add_argument(
        "--site-id",
        type=str,
        default=None,
        help="Site UUID (generated if not provided)",
    )
    parser.add_argument(
        "--device-type",
        choices=["inverter", "battery", "meter"],
        default="inverter",
        help="Type of device to simulate",
    )
    parser.add_argument(
        "--serial-number",
        type=str,
        default=None,
        help="Device serial number (generated if not provided)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Telemetry interval in seconds",
    )
    parser.add_argument(
        "--multi",
        action="store_true",
        help="Simulate multiple devices (1 inverter, 1 battery, 1 meter)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (debug) logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    site_id = UUID(args.site_id) if args.site_id else None

    # Setup graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received")
        shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            signal.signal(sig, lambda s, f: signal_handler())

    if args.multi:
        # Multi-device simulation
        simulator = MultiDeviceSimulator(
            server_url=args.server_url,
            site_id=site_id,
            telemetry_interval=args.interval,
        )
    else:
        # Single device simulation
        simulator = DeviceSimulator(
            server_url=args.server_url,
            site_id=site_id,
            device_type=args.device_type,
            serial_number=args.serial_number,
            telemetry_interval=args.interval,
        )

    # Run simulator
    try:
        run_task = asyncio.create_task(simulator.run())
        shutdown_task = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [run_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await simulator.stop()

    except Exception as e:
        logger.error(f"Simulator error: {e}")
        await simulator.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
