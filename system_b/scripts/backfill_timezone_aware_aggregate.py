"""
Backfill script for timezone-aware hourly continuous aggregate.

This script refreshes the telemetry_hourly_local continuous aggregate for a
specified date range. It's used during Phase 1 and Phase 4 of the migration
to timezone-aware aggregates.

Usage:
    # Backfill last 7 days
    python backfill_timezone_aware_aggregate.py --days 7

    # Backfill specific date range
    python backfill_timezone_aware_aggregate.py --start-date 2024-01-01 --end-date 2024-01-31

    # Backfill for specific site
    python backfill_timezone_aware_aggregate.py --site-id <uuid> --days 30

    # Dry run (show what would be done)
    python backfill_timezone_aware_aggregate.py --days 7 --dry-run

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (required)
    USE_TIMESCALEDB: Must be 'true' to run (default: false)

Note:
    - This script uses TimescaleDB's refresh_continuous_aggregate() function
    - Progress is logged every 1000 hours processed
    - The script is idempotent - safe to run multiple times
"""
import os
import sys
import argparse
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional
from uuid import UUID
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import asyncpg
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


async def get_site_timezone(conn: asyncpg.Connection, site_id: UUID) -> str:
    """Get timezone for a specific site."""
    result = await conn.fetchrow(
        "SELECT timezone FROM sites WHERE id = $1",
        site_id
    )
    if not result:
        raise ValueError(f"Site {site_id} not found")
    return result['timezone']


async def get_all_sites(conn: asyncpg.Connection) -> list[tuple[UUID, str]]:
    """Get all sites with their timezones."""
    rows = await conn.fetch("SELECT id, timezone FROM sites ORDER BY created_at")
    return [(row['id'], row['timezone']) for row in rows]


async def get_telemetry_date_range(
    conn: asyncpg.Connection,
    site_id: Optional[UUID] = None
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Get the date range of available telemetry data."""
    if site_id:
        query = """
            SELECT MIN(time) as min_time, MAX(time) as max_time
            FROM telemetry_raw
            WHERE site_id = $1
        """
        result = await conn.fetchrow(query, site_id)
    else:
        query = """
            SELECT MIN(time) as min_time, MAX(time) as max_time
            FROM telemetry_raw
        """
        result = await conn.fetchrow(query)

    return result['min_time'], result['max_time']


async def refresh_aggregate_range(
    conn: asyncpg.Connection,
    start_time: datetime,
    end_time: datetime,
    dry_run: bool = False
) -> None:
    """
    Refresh the continuous aggregate for a specific time range.

    Args:
        conn: Database connection
        start_time: Start of range (inclusive)
        end_time: End of range (inclusive)
        dry_run: If True, only log what would be done
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would refresh aggregate from {start_time} to {end_time}")
        return

    # Call TimescaleDB's refresh function
    # This will recompute all buckets in the range
    await conn.execute(
        """
        CALL refresh_continuous_aggregate(
            'telemetry_hourly_local',
            $1::timestamptz,
            $2::timestamptz
        )
        """,
        start_time,
        end_time
    )

    logger.info(f"✓ Refreshed aggregate from {start_time} to {end_time}")


async def backfill_by_date_chunks(
    conn: asyncpg.Connection,
    start_date: date,
    end_date: date,
    chunk_days: int = 7,
    dry_run: bool = False
) -> None:
    """
    Backfill the aggregate in date chunks to manage memory and show progress.

    Args:
        conn: Database connection
        start_date: Start date (local)
        end_date: End date (local)
        chunk_days: Number of days per chunk
        dry_run: If True, only log what would be done
    """
    current_date = start_date
    total_days = (end_date - start_date).days + 1
    processed_days = 0

    logger.info(f"Starting backfill from {start_date} to {end_date} ({total_days} days)")
    logger.info(f"Processing in {chunk_days}-day chunks")

    while current_date <= end_date:
        # Calculate chunk end date
        chunk_end = min(current_date + timedelta(days=chunk_days - 1), end_date)

        # Convert to datetime at start/end of day (UTC)
        chunk_start_dt = datetime.combine(current_date, datetime.min.time())
        chunk_end_dt = datetime.combine(chunk_end, datetime.max.time())

        # Refresh this chunk
        logger.info(f"Processing chunk: {current_date} to {chunk_end}")
        await refresh_aggregate_range(conn, chunk_start_dt, chunk_end_dt, dry_run)

        # Update progress
        processed_days += (chunk_end - current_date).days + 1
        progress_pct = (processed_days / total_days) * 100
        logger.info(f"Progress: {processed_days}/{total_days} days ({progress_pct:.1f}%)")

        # Move to next chunk
        current_date = chunk_end + timedelta(days=1)

    logger.info(f"✓ Completed backfill of {total_days} days")


async def backfill_site(
    conn: asyncpg.Connection,
    site_id: UUID,
    start_date: date,
    end_date: date,
    dry_run: bool = False
) -> None:
    """
    Backfill aggregate for a specific site.

    Note: Since the aggregate groups by site_id, we still need to refresh
    the entire time range. This function mainly exists for validation purposes.
    """
    timezone = await get_site_timezone(conn, site_id)
    logger.info(f"Backfilling site {site_id} (timezone: {timezone})")

    # Get telemetry range for this site
    min_time, max_time = await get_telemetry_date_range(conn, site_id)

    if not min_time or not max_time:
        logger.warning(f"No telemetry data found for site {site_id}")
        return

    logger.info(f"Site telemetry range: {min_time.date()} to {max_time.date()}")

    # Clamp to requested range
    actual_start = max(start_date, min_time.date())
    actual_end = min(end_date, max_time.date())

    if actual_start > actual_end:
        logger.warning(f"No telemetry data in requested range for site {site_id}")
        return

    # Backfill
    await backfill_by_date_chunks(conn, actual_start, actual_end, dry_run=dry_run)


async def validate_backfill(
    conn: asyncpg.Connection,
    start_date: date,
    end_date: date
) -> dict:
    """
    Validate the backfill by comparing record counts between raw and aggregate.

    Returns:
        Dictionary with validation results
    """
    logger.info("Validating backfill...")

    # Count buckets in aggregate
    aggregate_count = await conn.fetchval(
        """
        SELECT COUNT(*)
        FROM telemetry_hourly_local
        WHERE bucket::date BETWEEN $1 AND $2
        """,
        start_date,
        end_date
    )

    # Count expected buckets (rough estimate: 24 hours * days * sites * devices * metrics)
    raw_count = await conn.fetchval(
        """
        SELECT COUNT(DISTINCT (
            time_bucket('1 hour', time),
            site_id,
            device_id,
            metric_name
        ))
        FROM telemetry_raw
        WHERE time::date BETWEEN $1 AND $2
        """,
        start_date,
        end_date
    )

    # Get sites count
    sites_count = await conn.fetchval("SELECT COUNT(*) FROM sites")

    results = {
        'aggregate_buckets': aggregate_count,
        'raw_unique_combinations': raw_count,
        'sites_count': sites_count,
        'start_date': start_date,
        'end_date': end_date,
    }

    logger.info(f"Validation results:")
    logger.info(f"  - Aggregate buckets: {aggregate_count:,}")
    logger.info(f"  - Raw unique combinations: {raw_count:,}")
    logger.info(f"  - Sites: {sites_count}")

    if aggregate_count == 0:
        logger.warning("⚠️  No data in aggregate - backfill may have failed")
    elif aggregate_count < raw_count * 0.95:  # Allow 5% tolerance
        logger.warning(f"⚠️  Aggregate has significantly fewer records than expected")
    else:
        logger.info("✓ Validation passed")

    return results


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill timezone-aware hourly continuous aggregate",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--days',
        type=int,
        help='Number of days to backfill from today (e.g., 7 for last week)'
    )
    parser.add_argument(
        '--start-date',
        type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end-date',
        type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--site-id',
        type=UUID,
        help='Backfill for specific site only'
    )
    parser.add_argument(
        '--chunk-days',
        type=int,
        default=7,
        help='Number of days per processing chunk (default: 7)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate backfill after completion'
    )

    args = parser.parse_args()

    # Check environment
    use_timescaledb = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"
    if not use_timescaledb:
        logger.error("USE_TIMESCALEDB must be 'true' to run this script")
        sys.exit(1)

    # Build System B connection string
    timescale_host = os.getenv("TIMESCALE_HOST", "127.0.0.1")
    timescale_port = os.getenv("TIMESCALE_PORT", "5432")
    timescale_user = os.getenv("TIMESCALE_USER", "solarhub_telemetry")
    timescale_password = os.getenv("TIMESCALE_PASSWORD", "")
    timescale_db = os.getenv("TIMESCALE_DATABASE", "solar_hub_telemetry")

    database_url = f"postgresql://{timescale_user}:{timescale_password}@{timescale_host}:{timescale_port}/{timescale_db}"

    # Determine date range
    if args.days:
        end_date = date.today()
        start_date = end_date - timedelta(days=args.days)
    elif args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    else:
        parser.error("Either --days or both --start-date and --end-date required")

    if start_date > end_date:
        logger.error(f"Start date {start_date} is after end date {end_date}")
        sys.exit(1)

    logger.info("="*80)
    logger.info("Timezone-Aware Hourly Aggregate Backfill")
    logger.info("="*80)
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Chunk size: {args.chunk_days} days")
    if args.site_id:
        logger.info(f"Site filter: {args.site_id}")
    if args.dry_run:
        logger.info("DRY RUN MODE - no changes will be made")
    logger.info("="*80)

    # Connect to database
    conn = await asyncpg.connect(database_url)
    try:
        # Check if aggregate exists
        aggregate_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'telemetry_hourly_local'
                AND n.nspname = 'public'
            )
            """
        )

        if not aggregate_exists:
            logger.error("telemetry_hourly_local aggregate does not exist")
            logger.error("Run migration 0006 first: alembic upgrade head")
            sys.exit(1)

        # Perform backfill
        if args.site_id:
            await backfill_site(conn, args.site_id, start_date, end_date, args.dry_run)
        else:
            await backfill_by_date_chunks(
                conn, start_date, end_date, args.chunk_days, args.dry_run
            )

        # Validate if requested
        if args.validate and not args.dry_run:
            await validate_backfill(conn, start_date, end_date)

        logger.info("="*80)
        logger.info("✓ Backfill complete")
        logger.info("="*80)

    finally:
        await conn.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nBackfill interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Backfill failed: {e}")
        sys.exit(1)
