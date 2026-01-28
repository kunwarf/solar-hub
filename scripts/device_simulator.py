"""
Device Simulator for Solar Hub.

Simulates ESP32 devices sending telemetry to System B's ingest endpoint.
Generates realistic solar data patterns including:
- PV power following a bell curve (peaks at solar noon)
- Variable load with evening peaks
- Battery charge/discharge based on PV surplus
- Grid import/export to balance the system

Usage:
    python scripts/device_simulator.py --devices 2 --interval 30 --system-b-url http://localhost:8001
    python scripts/device_simulator.py --site-id <UUID> --device-ids <UUID1>,<UUID2> --interval 10
"""
import argparse
import asyncio
import logging
import math
import random
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("simulator")


# ============================================================================
# Solar Data Generation
# ============================================================================

def solar_power_w(hour: float, capacity_w: float = 5000.0) -> float:
    """
    Generate realistic PV power output based on time of day.

    Uses a shifted sine curve to model solar irradiance:
    - Sunrise ~6:00, sunset ~18:00 (Pakistan latitude)
    - Peak at solar noon (~12:30)
    - Random cloud variation (+/- 15%)
    """
    if hour < 6.0 or hour > 18.5:
        return 0.0

    # Bell curve centered at 12.5 (solar noon in Pakistan)
    intensity = max(0.0, math.sin((hour - 6.0) * math.pi / 12.5))
    # Cloud variation
    cloud_factor = 1.0 + random.uniform(-0.15, 0.10)
    # Temperature derating above 25C (panels lose efficiency in heat)
    temp_factor = 1.0 - max(0, (hour - 12) * 0.5) * 0.002

    return round(capacity_w * intensity * cloud_factor * temp_factor, 1)


def load_power_w(hour: float, base_load_w: float = 1500.0) -> float:
    """
    Generate realistic household load profile.

    Higher consumption in:
    - Morning (6-9): breakfast, getting ready
    - Evening (18-23): cooking, AC, TV, lights
    - Midday (12-14): AC during peak heat
    """
    time_factor = 1.0

    if 6.0 <= hour < 9.0:
        time_factor = 1.3 + random.uniform(-0.1, 0.1)
    elif 12.0 <= hour < 14.0:
        time_factor = 1.5 + random.uniform(-0.1, 0.2)  # AC during peak heat
    elif 18.0 <= hour < 22.0:
        time_factor = 1.8 + random.uniform(-0.1, 0.2)  # Evening peak
    elif 22.0 <= hour < 24.0:
        time_factor = 1.0 + random.uniform(-0.1, 0.1)
    elif 0.0 <= hour < 6.0:
        time_factor = 0.5 + random.uniform(-0.05, 0.05)  # Nighttime base
    else:
        time_factor = 1.0 + random.uniform(-0.1, 0.1)

    return round(base_load_w * time_factor, 1)


def battery_state(
    pv_w: float,
    load_w: float,
    current_soc: float,
    capacity_wh: float = 10000.0,
    max_charge_w: float = 3000.0,
    max_discharge_w: float = 3000.0,
) -> tuple[float, float, float]:
    """
    Calculate battery power and new state of charge.

    Logic:
    - If PV surplus: charge battery (positive power = charging)
    - If PV deficit and SOC > 20%: discharge battery (negative power)
    - Clamp to max charge/discharge rates and SOC limits (10%-95%)

    Returns (battery_power_w, new_soc_pct, grid_power_w).
    """
    surplus = pv_w - load_w

    if surplus > 0:
        # PV surplus - try to charge battery
        if current_soc < 95.0:
            charge_w = min(surplus, max_charge_w)
            # Calculate energy added in 1 minute (simplified)
            energy_wh = charge_w / 60.0  # per minute
            new_soc = min(95.0, current_soc + (energy_wh / capacity_wh) * 100.0)
            # Remaining surplus goes to grid (export = negative grid)
            grid_w = -(surplus - charge_w)
            return round(charge_w, 1), round(new_soc, 2), round(grid_w, 1)
        else:
            # Battery full - export everything to grid
            return 0.0, current_soc, round(-surplus, 1)
    else:
        # PV deficit - try to discharge battery
        deficit = abs(surplus)
        if current_soc > 20.0:
            discharge_w = min(deficit, max_discharge_w)
            energy_wh = discharge_w / 60.0
            new_soc = max(10.0, current_soc - (energy_wh / capacity_wh) * 100.0)
            # Remaining deficit comes from grid (import = positive grid)
            grid_w = max(0, deficit - discharge_w)
            return round(-discharge_w, 1), round(new_soc, 2), round(grid_w, 1)
        else:
            # Battery depleted - import everything from grid
            return 0.0, current_soc, round(deficit, 1)


def grid_metrics() -> dict:
    """Generate realistic grid voltage and frequency readings."""
    return {
        "grid_voltage_v": round(220.0 + random.uniform(-10, 10), 1),
        "grid_frequency_hz": round(50.0 + random.uniform(-0.3, 0.3), 2),
    }


def ambient_temperature(hour: float) -> float:
    """Generate ambient temperature based on time of day (Pakistan summer)."""
    # Base 28C, peaks at 14:00 at ~42C, drops to ~25C at night
    base = 28.0
    variation = 14.0 * max(0, math.sin((hour - 6) * math.pi / 16))
    noise = random.uniform(-1.5, 1.5)
    return round(base + variation + noise, 1)


# ============================================================================
# Device State
# ============================================================================

class SimulatedDevice:
    """State for a simulated ESP32 device."""

    def __init__(
        self,
        device_id: UUID,
        site_id: UUID,
        serial_number: str,
        pv_capacity_w: float = 5000.0,
        base_load_w: float = 1500.0,
        battery_capacity_wh: float = 10000.0,
    ):
        self.device_id = device_id
        self.site_id = site_id
        self.serial_number = serial_number
        self.pv_capacity_w = pv_capacity_w
        self.base_load_w = base_load_w
        self.battery_capacity_wh = battery_capacity_wh
        self.battery_soc = 50.0 + random.uniform(-10, 10)  # Start ~50%

    def generate_telemetry(self) -> dict:
        """Generate a telemetry reading for the current time."""
        now = datetime.now(timezone.utc)
        # Use local time for solar calculations (UTC+5 for Pakistan)
        local_hour = (now.hour + 5) % 24 + now.minute / 60.0

        pv_w = solar_power_w(local_hour, self.pv_capacity_w)
        load_w = load_power_w(local_hour, self.base_load_w)
        bat_w, self.battery_soc, grid_w = battery_state(
            pv_w, load_w, self.battery_soc, self.battery_capacity_wh,
        )
        grid = grid_metrics()
        temp = ambient_temperature(local_hour)

        return {
            "device_id": str(self.device_id),
            "site_id": str(self.site_id),
            "timestamp": now.isoformat(),
            "source": "simulator",
            "metrics": {
                "pv_power_w": pv_w,
                "load_power_w": load_w,
                "battery_power_w": bat_w,
                "grid_power_w": grid_w,
                "battery_soc_pct": round(self.battery_soc, 1),
                "grid_voltage_v": grid["grid_voltage_v"],
                "grid_frequency_hz": grid["grid_frequency_hz"],
                "temperature_ambient": temp,
            },
        }


# ============================================================================
# HTTP Client
# ============================================================================

async def send_telemetry(
    client: httpx.AsyncClient,
    base_url: str,
    points: list[dict],
) -> bool:
    """Send a batch of telemetry points to System B."""
    url = f"{base_url}/api/v1/telemetry/ingest"
    try:
        response = await client.post(url, json={"points": points})
        if response.status_code in (200, 201):
            data = response.json()
            logger.info(
                "Sent %d points → inserted=%d, failed=%d",
                len(points),
                data.get("inserted", 0),
                data.get("failed", 0),
            )
            return True
        else:
            logger.error("Ingest failed: HTTP %d - %s", response.status_code, response.text[:200])
            return False
    except httpx.ConnectError:
        logger.error("Connection refused: Is System B running at %s?", base_url)
        return False
    except Exception as e:
        logger.error("Send error: %s", e)
        return False


# ============================================================================
# Main Loop
# ============================================================================

async def run_simulator(
    system_b_url: str,
    devices: list[SimulatedDevice],
    interval_seconds: int,
    duration_seconds: int,
) -> None:
    """Run the simulation loop."""
    logger.info("=" * 60)
    logger.info("Solar Hub Device Simulator")
    logger.info("=" * 60)
    logger.info("System B URL: %s", system_b_url)
    logger.info("Devices: %d", len(devices))
    logger.info("Interval: %ds", interval_seconds)
    logger.info("Duration: %s", f"{duration_seconds}s" if duration_seconds > 0 else "unlimited")
    logger.info("-" * 60)

    for dev in devices:
        logger.info("  Device %s (site=%s)", dev.serial_number, dev.site_id)

    logger.info("=" * 60)

    elapsed = 0
    async with httpx.AsyncClient(timeout=10.0) as client:
        while duration_seconds == 0 or elapsed < duration_seconds:
            # Generate telemetry for all devices
            points = [dev.generate_telemetry() for dev in devices]

            # Log a sample
            sample = points[0]["metrics"]
            logger.info(
                "[%s] PV=%.0fW Load=%.0fW Bat=%.0fW(%.0f%%) Grid=%.0fW Temp=%.1f°C",
                points[0]["timestamp"][:19],
                sample["pv_power_w"],
                sample["load_power_w"],
                sample["battery_power_w"],
                sample["battery_soc_pct"],
                sample["grid_power_w"],
                sample["temperature_ambient"],
            )

            await send_telemetry(client, system_b_url, points)

            await asyncio.sleep(interval_seconds)
            elapsed += interval_seconds

    logger.info("Simulation complete.")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Simulate ESP32 devices sending telemetry to System B",
    )
    parser.add_argument(
        "--devices", type=int, default=1,
        help="Number of devices to simulate (default: 1)",
    )
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Seconds between telemetry readings (default: 30)",
    )
    parser.add_argument(
        "--duration", type=int, default=0,
        help="Total duration in seconds (0 = run forever, default: 0)",
    )
    parser.add_argument(
        "--system-b-url", type=str, default="http://localhost:8001",
        help="System B base URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--site-id", type=str, default=None,
        help="Site UUID (auto-generated if not provided)",
    )
    parser.add_argument(
        "--device-ids", type=str, default=None,
        help="Comma-separated device UUIDs (auto-generated if not provided)",
    )
    parser.add_argument(
        "--pv-capacity", type=float, default=5000.0,
        help="PV capacity per device in watts (default: 5000)",
    )
    parser.add_argument(
        "--base-load", type=float, default=1500.0,
        help="Base load per device in watts (default: 1500)",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point."""
    args = parse_args()

    site_id = UUID(args.site_id) if args.site_id else uuid4()

    if args.device_ids:
        device_uuids = [UUID(d.strip()) for d in args.device_ids.split(",")]
    else:
        device_uuids = [uuid4() for _ in range(args.devices)]

    devices = []
    for i, dev_id in enumerate(device_uuids):
        serial = f"SIM{i+1:02d}-0000-0000-00{i:02d}"
        devices.append(SimulatedDevice(
            device_id=dev_id,
            site_id=site_id,
            serial_number=serial,
            pv_capacity_w=args.pv_capacity,
            base_load_w=args.base_load,
        ))

    try:
        asyncio.run(run_simulator(
            system_b_url=args.system_b_url,
            devices=devices,
            interval_seconds=args.interval,
            duration_seconds=args.duration,
        ))
    except KeyboardInterrupt:
        logger.info("Simulator stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
