#!/usr/bin/env python3
"""
Backfill script to parse historical telemetry from device_telemetry into telemetry_raw.

This script:
1. Reads historical JSON telemetry from device_telemetry table
2. Parses each record using DeyeHybridParser
3. Writes normalized metrics to telemetry_raw table
4. Processes in batches to avoid memory issues
5. Refreshes continuous aggregates after completion

Usage:
    python3 backfill_telemetry.py [--limit N] [--batch-size N] [--dry-run]

Options:
    --limit N         Process only N records (for testing)
    --batch-size N    Process N records per batch (default: 1000)
    --dry-run         Show what would be done without writing to database
"""

import asyncio
import argparse
import logging
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelemetryMetric:
    """Normalized telemetry metric (same as in the app)."""

    def __init__(
        self,
        time: datetime,
        device_id: UUID,
        site_id: UUID,
        metric_name: str,
        metric_value: Optional[float] = None,
        metric_value_str: Optional[str] = None,
        quality: str = "good",
        unit: Optional[str] = None,
        source: str = "telemetry",
        tags: Optional[Dict[str, str]] = None,
    ):
        self.time = time
        self.device_id = device_id
        self.site_id = site_id
        self.metric_name = metric_name
        self.metric_value = metric_value
        self.metric_value_str = metric_value_str
        self.quality = quality
        self.unit = unit
        self.source = source
        self.tags = tags or {}

    def to_db_tuple(self):
        """Convert to database tuple for executemany."""
        return (
            self.time,
            self.device_id,
            self.metric_name,
            self.site_id,
            self.metric_value,
            self.metric_value_str,
            self.quality,
            self.unit,
            self.source,
            json.dumps(self.tags) if self.tags else None
        )


class PowdriveParser:
    """
    Simplified Powdrive inverter parser for backfilling.
    (Mirrors the parser in device_server/telemetry/powdrive_parser.py)
    """

    # Metric mappings: json_field -> (metric_name, unit, category)
    METRIC_MAPPINGS = [
        # PV Power Metrics
        ('pv1_power_w', ('pv1_power_w', 'W', 'power')),
        ('pv2_power_w', ('pv2_power_w', 'W', 'power')),
        ('pv3_power_w', ('pv3_power_w', 'W', 'power')),
        ('pv4_power_w', ('pv4_power_w', 'W', 'power')),

        # Power Metrics
        ('grid_power_w', ('grid_w', 'W', 'power')),
        ('load_power_w', ('load_w', 'W', 'power')),
        ('battery_power_w', ('battery_w', 'W', 'power')),

        # Battery Metrics
        ('battery_soc_pct', ('battery_soc_pct', '%', 'battery')),
        ('battery_voltage_v', ('battery_voltage_v', 'V', 'battery')),
        ('battery_current_a', ('battery_current_a', 'A', 'battery')),

        # Energy Metrics
        ('pv_energy_today_kwh', ('pv_energy_today_kwh', 'kWh', 'energy')),
        ('load_energy_today_kwh', ('load_energy_today_kwh', 'kWh', 'energy')),
        ('grid_export_energy_today_kwh', ('grid_export_energy_today_kwh', 'kWh', 'energy')),
        ('grid_import_energy_today_kwh', ('grid_import_energy_today_kwh', 'kWh', 'energy')),
        ('battery_charge_energy_today_kwh', ('battery_charge_energy_today_kwh', 'kWh', 'energy')),
        ('battery_discharge_energy_today_kwh', ('battery_discharge_energy_today_kwh', 'kWh', 'energy')),

        # Temperature Metrics
        ('inverter_temp_c', ('inverter_temp_c', 'C', 'temperature')),
        ('battery_temp_c', ('battery_temp_c', 'C', 'temperature')),
        ('heat_sink_temp_c', ('heat_sink_temp_c', 'C', 'temperature')),

        # Grid Metrics
        ('grid_voltage_v', ('grid_voltage_v', 'V', 'grid')),
        ('grid_frequency_hz', ('grid_frequency_hz', 'Hz', 'grid')),
        ('grid_l1_voltage_v', ('grid_l1_voltage_v', 'V', 'grid')),
        ('grid_l2_voltage_v', ('grid_l2_voltage_v', 'V', 'grid')),
        ('grid_l3_voltage_v', ('grid_l3_voltage_v', 'V', 'grid')),
        ('grid_l1_current_a', ('grid_l1_current_a', 'A', 'grid')),
        ('grid_l2_current_a', ('grid_l2_current_a', 'A', 'grid')),
        ('grid_l3_current_a', ('grid_l3_current_a', 'A', 'grid')),
        ('grid_l1_power_w', ('grid_l1_power_w', 'W', 'grid')),
        ('grid_l2_power_w', ('grid_l2_power_w', 'W', 'grid')),
        ('grid_l3_power_w', ('grid_l3_power_w', 'W', 'grid')),

        # Load Metrics
        ('load_l1_power_w', ('load_l1_power_w', 'W', 'load')),
        ('load_l2_power_w', ('load_l2_power_w', 'W', 'load')),
        ('load_l3_power_w', ('load_l3_power_w', 'W', 'load')),

        # PV String Details
        ('pv1_voltage_v', ('pv1_voltage_v', 'V', 'pv')),
        ('pv1_current_a', ('pv1_current_a', 'A', 'pv')),
        ('pv2_voltage_v', ('pv2_voltage_v', 'V', 'pv')),
        ('pv2_current_a', ('pv2_current_a', 'A', 'pv')),
        ('pv3_voltage_v', ('pv3_voltage_v', 'V', 'pv')),
        ('pv3_current_a', ('pv3_current_a', 'A', 'pv')),
        ('pv4_voltage_v', ('pv4_voltage_v', 'V', 'pv')),
        ('pv4_current_a', ('pv4_current_a', 'A', 'pv')),

        # Grid CT Metrics
        ('grid_ct_power_w', ('grid_ct_power_w', 'W', 'grid')),

        # Status Metrics
        ('grid_status_raw', ('grid_status_raw', 'enum', 'status')),
        ('working_mode_raw', ('working_mode_raw', 'enum', 'status')),
        ('power_on_off_status', ('power_on_off_status', 'bool', 'status')),

        # Configuration
        ('battery_capacity_ah', ('battery_capacity_ah', 'Ah', 'config')),
        ('battery_type', ('battery_type', 'enum', 'config')),
        ('inverter_type', ('inverter_type', 'enum', 'config')),
    ]

    def parse(
        self,
        telemetry_data: Dict[str, Any],
        device_id: UUID,
        site_id: UUID,
        timestamp: datetime
    ) -> List[TelemetryMetric]:
        """Parse Powdrive telemetry JSON into normalized metrics."""
        metrics = []

        for json_field, (metric_name, unit, _category) in self.METRIC_MAPPINGS:
            value = telemetry_data.get(json_field)

            if value is None:
                continue

            # Handle boolean values
            if unit == 'bool':
                metric = TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name=metric_name,
                    metric_value=1.0 if value else 0.0,
                    metric_value_str=str(value),
                    quality='good',
                    unit=unit,
                    source='telemetry'
                )
                metrics.append(metric)

            # Handle enum values
            elif unit == 'enum':
                try:
                    numeric_value = float(value)
                    metric = TelemetryMetric(
                        time=timestamp,
                        device_id=device_id,
                        site_id=site_id,
                        metric_name=metric_name,
                        metric_value=numeric_value,
                        metric_value_str=str(value),
                        quality='good',
                        unit=unit,
                        source='telemetry'
                    )
                    metrics.append(metric)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert enum {metric_name}={value} to float"
                    )

            # Handle numeric values
            else:
                try:
                    numeric_value = float(value)
                    metric = TelemetryMetric(
                        time=timestamp,
                        device_id=device_id,
                        site_id=site_id,
                        metric_name=metric_name,
                        metric_value=numeric_value,
                        quality='good',
                        unit=unit,
                        source='telemetry'
                    )
                    metrics.append(metric)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert {metric_name}={value} to float, skipping"
                    )
                    continue

        # Calculate total PV power if not already present
        pv_total_w = sum(
            telemetry_data.get(f'pv{i}_power_w', 0)
            for i in range(1, 5)
        )
        if pv_total_w > 0:
            metrics.append(
                TelemetryMetric(
                    time=timestamp,
                    device_id=device_id,
                    site_id=site_id,
                    metric_name='pv_total_w',
                    metric_value=float(pv_total_w),
                    quality='good',
                    unit='W',
                    source='telemetry'
                )
            )

        return metrics


async def backfill_telemetry(
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    limit: Optional[int] = None,
    batch_size: int = 1000,
    dry_run: bool = False
):
    """Backfill historical telemetry data."""

    logger.info("=" * 70)
    logger.info("TELEMETRY BACKFILL SCRIPT")
    logger.info("=" * 70)
    logger.info(f"Database: {db_host}:{db_port}/{db_name}")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Limit: {limit if limit else 'ALL'}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("=" * 70)

    # Connect to database
    logger.info("Connecting to database...")
    conn = await asyncpg.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )

    try:
        # Get device-to-site mapping
        logger.info("Loading device-to-site mapping...")
        device_site_rows = await conn.fetch(
            "SELECT device_id, site_id FROM device_registry"
        )
        device_site_map = {row['device_id']: row['site_id'] for row in device_site_rows}
        logger.info(f"Found {len(device_site_map)} devices")

        # Count total records to process
        count_query = "SELECT COUNT(*) FROM device_telemetry"
        if limit:
            count_query = f"SELECT COUNT(*) FROM (SELECT 1 FROM device_telemetry LIMIT {limit}) AS limited"

        total_count = await conn.fetchval(count_query)
        logger.info(f"Total records to process: {total_count}")

        # Initialize parser
        parser = PowdriveParser()

        # Process in batches
        offset = 0
        total_parsed_metrics = 0
        total_errors = 0

        while True:
            # Fetch batch
            fetch_limit = min(batch_size, limit - offset) if limit else batch_size

            if fetch_limit <= 0:
                break

            logger.info(f"Fetching batch: offset={offset}, limit={fetch_limit}")

            batch_query = """
                SELECT
                    time,
                    device_id,
                    serial_number,
                    device_type,
                    data
                FROM device_telemetry
                ORDER BY time ASC
                OFFSET $1
                LIMIT $2
            """

            batch = await conn.fetch(batch_query, offset, fetch_limit)

            if not batch:
                logger.info("No more records to process")
                break

            logger.info(f"Processing {len(batch)} records...")

            # Log first record for debugging
            if batch:
                first_record = batch[0]
                logger.debug(f"First record: time={first_record['time']}, device_id={first_record['device_id']}, data type={type(first_record['data'])}")
                if first_record['data']:
                    sample_keys = list(first_record['data'].keys())[:5] if isinstance(first_record['data'], dict) else []
                    logger.debug(f"Sample data keys: {sample_keys}")

            # Parse each record
            all_metrics = []
            for idx, record in enumerate(batch):
                device_id = record['device_id']
                site_id = device_site_map.get(device_id)

                if not site_id:
                    logger.warning(f"No site_id for device {device_id}, skipping")
                    total_errors += 1
                    continue

                try:
                    # Parse telemetry JSON
                    telemetry_data = json.loads(record['data']) if isinstance(record['data'], str) else record['data']

                    metrics = parser.parse(
                        telemetry_data=telemetry_data,
                        device_id=device_id,
                        site_id=site_id,
                        timestamp=record['time']
                    )

                    if idx == 0:  # Log first record's parsing result
                        logger.info(f"First record parsed: {len(metrics)} metrics extracted")

                    all_metrics.extend(metrics)

                except Exception as e:
                    logger.error(f"Error parsing record {record['time']} for device {device_id}: {e}")
                    total_errors += 1
                    continue

            # Insert metrics into telemetry_raw
            if all_metrics and not dry_run:
                logger.info(f"Inserting {len(all_metrics)} metrics into telemetry_raw...")

                await conn.executemany(
                    """
                    INSERT INTO telemetry_raw
                    (time, device_id, metric_name, site_id, metric_value,
                     metric_value_str, quality, unit, source, tags)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (time, device_id, metric_name) DO UPDATE SET
                        metric_value = EXCLUDED.metric_value,
                        quality = EXCLUDED.quality
                    """,
                    [m.to_db_tuple() for m in all_metrics]
                )

                total_parsed_metrics += len(all_metrics)
            elif dry_run:
                logger.info(f"[DRY RUN] Would insert {len(all_metrics)} metrics")
                total_parsed_metrics += len(all_metrics)

            offset += len(batch)

            logger.info(
                f"Progress: {offset}/{total_count} records "
                f"({offset * 100 / total_count:.1f}%), "
                f"{total_parsed_metrics} metrics parsed"
            )

        logger.info("=" * 70)
        logger.info("BACKFILL COMPLETE")
        logger.info(f"Total records processed: {offset}")
        logger.info(f"Total metrics parsed: {total_parsed_metrics}")
        logger.info(f"Total errors: {total_errors}")
        logger.info("=" * 70)

        # Refresh continuous aggregates
        if not dry_run and total_parsed_metrics > 0:
            logger.info("Refreshing continuous aggregates...")

            try:
                # Refresh hourly
                logger.info("  - Refreshing telemetry_hourly...")
                await conn.execute(
                    "CALL refresh_continuous_aggregate('telemetry_hourly', NULL, NULL)"
                )

                # Refresh daily
                logger.info("  - Refreshing telemetry_daily...")
                await conn.execute(
                    "CALL refresh_continuous_aggregate('telemetry_daily', NULL, NULL)"
                )

                # Refresh monthly
                logger.info("  - Refreshing telemetry_monthly...")
                await conn.execute(
                    "CALL refresh_continuous_aggregate('telemetry_monthly', NULL, NULL)"
                )

                # Refresh yearly
                logger.info("  - Refreshing telemetry_yearly...")
                await conn.execute(
                    "CALL refresh_continuous_aggregate('telemetry_yearly', NULL, NULL)"
                )

                logger.info("✓ Continuous aggregates refreshed successfully")

            except Exception as e:
                logger.error(f"Error refreshing continuous aggregates: {e}")
                logger.warning("You may need to manually refresh them later")

    finally:
        await conn.close()
        logger.info("Database connection closed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill historical telemetry from device_telemetry to telemetry_raw"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only N records (for testing)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Process N records per batch (default: 1000)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing to database"
    )
    parser.add_argument(
        "--db-host",
        default="localhost",
        help="Database host (default: localhost)"
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=5432,
        help="Database port (default: 5432)"
    )
    parser.add_argument(
        "--db-name",
        default="solarhub_db",
        help="Database name (default: solarhub_db)"
    )
    parser.add_argument(
        "--db-user",
        default="solarhub",
        help="Database user (default: solarhub)"
    )
    parser.add_argument(
        "--db-password",
        default="solarhub_dev_2024",
        help="Database password"
    )

    args = parser.parse_args()

    # Run backfill
    asyncio.run(backfill_telemetry(
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run
    ))


if __name__ == "__main__":
    main()
