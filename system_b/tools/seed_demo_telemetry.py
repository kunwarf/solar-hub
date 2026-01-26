"""
Seed demo telemetry data to Redis for development/testing.

This script writes simulated telemetry data to Redis for a specified device,
allowing the dashboard to display realistic data without a real device connected.

Usage:
    python -m system_b.tools.seed_demo_telemetry --serial SH01IN9A423V4CU0

    # Run continuously (updates every 5 seconds):
    python -m system_b.tools.seed_demo_telemetry --serial SH01IN9A423V4CU0 --continuous
"""
import argparse
import asyncio
import json
import logging
import math
import random
import sys
import time
from datetime import datetime, timezone

import redis.asyncio as redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Redis key patterns (must match System B's TelemetryCacheWriter)
KEY_TELEMETRY = "device:{serial}:telemetry"
KEY_STATUS = "device:{serial}:status"
KEY_LAST_SEEN = "device:{serial}:last_seen"

# TTL settings
TELEMETRY_TTL = 300  # 5 minutes
STATUS_TTL = 600  # 10 minutes


def generate_demo_telemetry(serial_number: str) -> dict:
    """Generate realistic demo telemetry data based on time of day."""
    now = datetime.now(timezone.utc)
    hour = now.hour + (now.minute / 60)  # Fractional hour

    # Solar power follows sun pattern (bell curve, peak at noon)
    # Assuming UTC, adjust for local timezone in production
    is_daytime = 6 <= hour <= 18
    if is_daytime:
        # Bell curve peaking at noon
        solar_factor = math.sin((hour - 6) * math.pi / 12)
        pv_power = max(0, 4500 * solar_factor + random.uniform(-200, 200))
    else:
        pv_power = 0

    # Base load with some variation
    base_load = 1200 + random.uniform(-100, 200)

    # Morning and evening peaks
    if 7 <= hour <= 9:
        base_load += 800  # Morning peak
    elif 18 <= hour <= 22:
        base_load += 1200  # Evening peak

    load_power = base_load

    # Battery behavior
    battery_soc = 50 + random.uniform(-5, 5)
    if pv_power > load_power:
        # Charging
        battery_power = min((pv_power - load_power) * 0.8, 2500)  # Max 2.5kW charge
        battery_soc += battery_power / 13500 * 100  # 13.5kWh battery
        battery_charging = True
    else:
        # Discharging
        battery_power = -min((load_power - pv_power) * 0.5, 2000)  # Max 2kW discharge
        battery_charging = False

    battery_soc = max(10, min(95, battery_soc))  # Clamp between 10-95%

    # Grid power (import positive, export negative)
    grid_power = load_power - pv_power - (-battery_power if battery_power < 0 else battery_power)

    # Voltages and frequencies
    grid_voltage = 220 + random.uniform(-5, 5)
    grid_frequency = 50 + random.uniform(-0.1, 0.1)
    pv_voltage = 380 + random.uniform(-10, 10) if pv_power > 0 else 0

    # Temperature
    ambient_temp = 25 + random.uniform(-3, 3)
    inverter_temp = ambient_temp + 15 + (pv_power / 4500 * 10)

    # Energy today (accumulates based on time of day)
    hours_since_sunrise = max(0, hour - 6)
    energy_today_kwh = pv_power / 1000 * hours_since_sunrise * 0.6

    timestamp = now.isoformat()

    return {
        "serial_number": serial_number,
        "timestamp": timestamp,
        "power": {
            "pv_total_w": round(pv_power, 1),
            "pv1_w": round(pv_power * 0.6, 1),
            "pv2_w": round(pv_power * 0.4, 1),
            "grid_w": round(grid_power, 1),
            "load_w": round(load_power, 1),
            "battery_w": round(battery_power, 1),
        },
        "battery": {
            "soc_pct": round(battery_soc, 1),
            "voltage_v": round(48 + (battery_soc / 100 * 6), 2),
            "current_a": round(battery_power / 48, 2),
            "charging": battery_charging,
        },
        "energy_today": {
            "pv_kwh": round(energy_today_kwh, 2),
            "load_kwh": round(load_power / 1000 * hours_since_sunrise * 0.8, 2),
            "grid_import_kwh": round(max(0, grid_power / 1000) * hours_since_sunrise * 0.3, 2),
            "grid_export_kwh": round(max(0, -grid_power / 1000) * hours_since_sunrise * 0.3, 2),
            "battery_charge_kwh": round(max(0, battery_power / 1000) * hours_since_sunrise * 0.5, 2),
            "battery_discharge_kwh": round(max(0, -battery_power / 1000) * hours_since_sunrise * 0.5, 2),
        },
        "temperatures": {
            "inverter_c": round(inverter_temp, 1),
            "ambient_c": round(ambient_temp, 1),
        },
        "grid": {
            "voltage_v": round(grid_voltage, 1),
            "frequency_hz": round(grid_frequency, 2),
        },
        "status": {
            "grid_connected": True,
            "faults": [],
            "warnings": [],
            "working_mode": 1,
            "working_mode_name": "Auto",
        },
        "raw": {
            "pv_power": round(pv_power, 1),
            "grid_power": round(grid_power, 1),
            "load_power": round(load_power, 1),
            "battery_power": round(battery_power, 1),
            "battery_soc": round(battery_soc, 1),
            "grid_voltage": round(grid_voltage, 1),
            "grid_frequency": round(grid_frequency, 2),
        },
    }


async def seed_telemetry(
    redis_host: str,
    redis_port: int,
    redis_db: int,
    serial_number: str,
    continuous: bool = False,
    interval: int = 5,
) -> None:
    """Seed demo telemetry data to Redis."""
    logger.info(f"Connecting to Redis at {redis_host}:{redis_port}/{redis_db}")

    client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        decode_responses=True,
    )

    try:
        await client.ping()
        logger.info("Connected to Redis")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return

    try:
        while True:
            # Generate demo telemetry
            telemetry = generate_demo_telemetry(serial_number)
            now = int(time.time())

            # Write to Redis
            key_telemetry = KEY_TELEMETRY.format(serial=serial_number)
            key_status = KEY_STATUS.format(serial=serial_number)
            key_last_seen = KEY_LAST_SEEN.format(serial=serial_number)

            async with client.pipeline() as pipe:
                pipe.setex(key_telemetry, TELEMETRY_TTL, json.dumps(telemetry, default=str))
                pipe.setex(key_status, STATUS_TTL, "online")
                pipe.setex(key_last_seen, STATUS_TTL, str(now))
                await pipe.execute()

            logger.info(
                f"Seeded telemetry for {serial_number}: "
                f"PV={telemetry['power']['pv_total_w']:.0f}W, "
                f"Grid={telemetry['power']['grid_w']:.0f}W, "
                f"Battery={telemetry['power']['battery_w']:.0f}W, "
                f"SOC={telemetry['battery']['soc_pct']:.0f}%"
            )

            if not continuous:
                logger.info("Single seed completed. Use --continuous to keep updating.")
                break

            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        await client.close()
        logger.info("Disconnected from Redis")


def main():
    parser = argparse.ArgumentParser(
        description="Seed demo telemetry data to Redis for development/testing"
    )
    parser.add_argument(
        "--serial",
        required=True,
        help="Device serial number (e.g., SH01IN9A423V4CU0)",
    )
    parser.add_argument(
        "--redis-host",
        default="localhost",
        help="Redis host (default: localhost)",
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=6379,
        help="Redis port (default: 6379)",
    )
    parser.add_argument(
        "--redis-db",
        type=int,
        default=0,
        help="Redis database (default: 0)",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Continuously update telemetry every few seconds",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Update interval in seconds for continuous mode (default: 5)",
    )

    args = parser.parse_args()

    asyncio.run(
        seed_telemetry(
            redis_host=args.redis_host,
            redis_port=args.redis_port,
            redis_db=args.redis_db,
            serial_number=args.serial,
            continuous=args.continuous,
            interval=args.interval,
        )
    )


if __name__ == "__main__":
    main()
