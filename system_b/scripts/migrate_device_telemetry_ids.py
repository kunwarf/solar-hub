#!/usr/bin/env python3
"""
Migrate historical device_telemetry records to use data logger device_id.

This script updates all device_telemetry records that were written with
transient inverter device_ids to use the stable data logger device_id instead.

This is necessary before running backfill_telemetry.py, because the backfill
script looks up site_id by device_id, and only the data logger device has
a site_id in device_registry.

Usage:
    python3 migrate_device_telemetry_ids.py [--dry-run]
"""

import asyncio
import argparse
import logging
from typing import Optional
import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_device_ids(
    db_host: str,
    db_port: int,
    db_name: str,
    db_user: str,
    db_password: str,
    dry_run: bool = False
):
    """
    Migrate device_telemetry records to use data logger device_id.

    Strategy:
    1. Find the data logger device_id from device_registry (serial: SH01IN9A423V4CU0)
    2. Find the inverter serial number from device_registry metadata
    3. Update all device_telemetry records with matching serial_number to use data logger device_id
    """

    logger.info("=" * 70)
    logger.info("DEVICE_TELEMETRY ID MIGRATION SCRIPT")
    logger.info("=" * 70)
    logger.info(f"Database: {db_host}:{db_port}/{db_name}")
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
        # Step 1: Get data logger info from device_registry
        logger.info("Looking up data logger in device_registry...")
        data_logger = await conn.fetchrow(
            """
            SELECT device_id, serial_number, metadata
            FROM device_registry
            WHERE device_type = 'inverter'
              AND serial_number LIKE 'SH%'  -- Data logger serials start with SH
            LIMIT 1
            """
        )

        if not data_logger:
            logger.error("Data logger not found in device_registry!")
            logger.error("Expected a device with serial_number starting with 'SH'")
            return

        data_logger_id = data_logger['device_id']
        data_logger_serial = data_logger['serial_number']
        metadata = data_logger['metadata']

        logger.info(f"Found data logger:")
        logger.info(f"  Device ID: {data_logger_id}")
        logger.info(f"  Serial: {data_logger_serial}")

        # Extract inverter serial from metadata if available
        inverter_serial = None
        if metadata:
            # Metadata can be a dict or an array of dicts
            if isinstance(metadata, dict) and 'inverter_serial' in metadata:
                inverter_serial = metadata['inverter_serial']
            elif isinstance(metadata, list):
                # Find first non-null element with inverter_serial
                for item in metadata:
                    if item and isinstance(item, dict) and 'inverter_serial' in item:
                        inverter_serial = item['inverter_serial']
                        break

        if inverter_serial:
            logger.info(f"  Inverter Serial (from metadata): {inverter_serial}")

        # Step 2: Check current state of device_telemetry
        logger.info("\nAnalyzing device_telemetry table...")

        # Count records by device_id
        device_counts = await conn.fetch(
            """
            SELECT device_id, serial_number, COUNT(*) as record_count
            FROM device_telemetry
            GROUP BY device_id, serial_number
            ORDER BY record_count DESC
            """
        )

        logger.info(f"Found {len(device_counts)} unique device_id values in device_telemetry:")
        total_records = 0
        records_to_migrate = 0

        for row in device_counts:
            device_id = row['device_id']
            serial = row['serial_number']
            count = row['record_count']
            total_records += count

            is_data_logger = (device_id == data_logger_id)
            needs_migration = not is_data_logger

            if needs_migration:
                records_to_migrate += count

            status = "✓ OK (data logger)" if is_data_logger else "✗ NEEDS MIGRATION"
            logger.info(f"  {status}: device_id={device_id}, serial={serial}, records={count}")

        logger.info(f"\nTotal records: {total_records}")
        logger.info(f"Records already using data logger ID: {total_records - records_to_migrate}")
        logger.info(f"Records needing migration: {records_to_migrate}")

        if records_to_migrate == 0:
            logger.info("\n✓ All records already use the data logger device_id!")
            logger.info("No migration needed.")
            return

        # Step 3: Perform migration
        if dry_run:
            logger.info("\n[DRY RUN] Would update device_telemetry records:")
            logger.info(f"  SET device_id = '{data_logger_id}'")
            logger.info(f"  WHERE device_id != '{data_logger_id}'")
            logger.info(f"  (Affects {records_to_migrate} records)")
        else:
            logger.info(f"\nMigrating {records_to_migrate} records...")
            logger.info(f"  Setting device_id to: {data_logger_id}")

            # Update all records that don't have the data logger device_id
            result = await conn.execute(
                """
                UPDATE device_telemetry
                SET device_id = $1
                WHERE device_id != $1
                """,
                data_logger_id
            )

            # Parse the result (format: "UPDATE N")
            updated_count = int(result.split()[-1])
            logger.info(f"✓ Updated {updated_count} records")

            # Verify the update
            remaining = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM device_telemetry
                WHERE device_id != $1
                """,
                data_logger_id
            )

            if remaining == 0:
                logger.info("✓ Verification passed: All records now use data logger device_id")
            else:
                logger.warning(f"⚠ Warning: {remaining} records still have different device_id")

        logger.info("=" * 70)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Data logger device_id: {data_logger_id}")
        logger.info(f"Data logger serial: {data_logger_serial}")
        logger.info(f"Total records: {total_records}")
        logger.info(f"Records migrated: {records_to_migrate}")

        if not dry_run and records_to_migrate > 0:
            logger.info("\n✓ Migration complete!")
            logger.info("\nNext steps:")
            logger.info("1. Run backfill script to parse historical telemetry:")
            logger.info("   python3 backfill_telemetry.py --limit 100  # Test first")
            logger.info("   python3 backfill_telemetry.py --batch-size 1000  # Full backfill")
        elif dry_run:
            logger.info("\n[DRY RUN] No changes made. Run without --dry-run to apply changes.")

        logger.info("=" * 70)

    finally:
        await conn.close()
        logger.info("Database connection closed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate device_telemetry records to use data logger device_id"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--db-host",
        default="127.0.0.1",
        help="Database host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=5432,
        help="Database port (default: 5432)"
    )
    parser.add_argument(
        "--db-name",
        default="solar_hub_telemetry",
        help="Database name (default: solar_hub_telemetry)"
    )
    parser.add_argument(
        "--db-user",
        default="solarhub_telemetry",
        help="Database user (default: solarhub_telemetry)"
    )
    parser.add_argument(
        "--db-password",
        help="Database password (required)"
    )

    args = parser.parse_args()

    if not args.db_password:
        parser.error("--db-password is required")

    # Run migration
    asyncio.run(migrate_device_ids(
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        dry_run=args.dry_run
    ))


if __name__ == "__main__":
    main()
