"""
Rebuild billing data using timezone-aware calculations.

This script recalculates billing for historical periods using the new
timezone-aware telemetry data from System B.

Usage:
    # Rebuild billing for specific month
    python rebuild_billing_data.py --site-id <uuid> --year 2026 --month 1

    # Rebuild billing for date range
    python rebuild_billing_data.py --site-id <uuid> --start-date 2025-12-01 --end-date 2026-02-28

    # Rebuild all billing data for a site
    python rebuild_billing_data.py --site-id <uuid> --all

    # Dry run (show what would be done)
    python rebuild_billing_data.py --site-id <uuid> --year 2026 --month 1 --dry-run
"""
import os
import sys
import argparse
import asyncio
from datetime import datetime, date, timedelta
from typing import Optional
from uuid import UUID
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


async def get_billing_periods_to_rebuild(
    session: AsyncSession,
    site_id: UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    all_periods: bool = False
) -> list[tuple[date, date]]:
    """
    Get list of billing periods that need to be rebuilt.

    Returns list of (period_start, period_end) tuples.
    """
    from sqlalchemy import select, text

    if all_periods:
        # Get all billing cycles for this site
        query = text("""
            SELECT DISTINCT
                DATE_TRUNC('month', period_start)::date as month_start,
                (DATE_TRUNC('month', period_start) + INTERVAL '1 month' - INTERVAL '1 day')::date as month_end
            FROM billing_simulations
            WHERE site_id = :site_id
            ORDER BY month_start
        """)
        result = await session.execute(query, {"site_id": str(site_id)})
        return [(row[0], row[1]) for row in result]

    elif start_date and end_date:
        # Generate monthly periods for the date range
        periods = []
        current = date(start_date.year, start_date.month, 1)
        end = date(end_date.year, end_date.month, 1)

        while current <= end:
            # Last day of the month
            if current.month == 12:
                next_month = date(current.year + 1, 1, 1)
            else:
                next_month = date(current.year, current.month + 1, 1)
            month_end = next_month - timedelta(days=1)

            periods.append((current, month_end))
            current = next_month

        return periods

    else:
        return []


async def delete_billing_for_period(
    session: AsyncSession,
    site_id: UUID,
    period_start: date,
    period_end: date,
    dry_run: bool = False
) -> int:
    """Delete existing billing records for a period."""
    from sqlalchemy import text

    if dry_run:
        # Count what would be deleted
        query = text("""
            SELECT COUNT(*)
            FROM billing_simulations
            WHERE site_id = :site_id
              AND period_start >= :start
              AND period_end <= :end
        """)
        result = await session.execute(query, {
            "site_id": str(site_id),
            "start": period_start,
            "end": period_end
        })
        count = result.scalar()
        logger.info(f"[DRY RUN] Would delete {count} billing record(s) for {period_start} to {period_end}")
        return count

    # Delete billing cycles
    query = text("""
        DELETE FROM billing_simulations
        WHERE site_id = :site_id
          AND period_start >= :start
          AND period_end <= :end
    """)
    result = await session.execute(query, {
        "site_id": str(site_id),
        "start": period_start,
        "end": period_end
    })
    deleted = result.rowcount
    await session.commit()

    logger.info(f"Deleted {deleted} billing record(s) for {period_start} to {period_end}")
    return deleted


async def recalculate_billing_for_period(
    session: AsyncSession,
    site_id: UUID,
    period_start: date,
    period_end: date,
    dry_run: bool = False
) -> dict:
    """
    Recalculate billing for a specific period using timezone-aware data.

    This will:
    1. Fetch hourly energy data from System B (timezone-aware)
    2. Classify hours into TOU periods using LOCAL time
    3. Calculate billing amounts using correct TOU rates
    4. Create new billing cycle record
    """
    # Import System A services
    from app.domain.services.billing_service import BillingService
    from app.infrastructure.external.system_b_client import SystemBClient
    from app.infrastructure.database.repositories.site_repository import SiteRepository
    from app.infrastructure.database.repositories.billing_repository import BillingRepository

    if dry_run:
        logger.info(f"[DRY RUN] Would recalculate billing for {period_start} to {period_end}")
        return {"dry_run": True, "period_start": period_start, "period_end": period_end}

    # Initialize services
    site_repo = SiteRepository(session)
    billing_repo = BillingRepository(session)
    system_b_client = SystemBClient()
    billing_service = BillingService(billing_repo, site_repo, system_b_client)

    # Trigger billing computation
    logger.info(f"Recalculating billing for {period_start} to {period_end}...")

    # The billing service will fetch data from System B using timezone-aware API
    result = await billing_service.compute_daily_billing(site_id, period_start)

    logger.info(f"✓ Billing recalculated for {period_start}")
    return result


async def main():
    parser = argparse.ArgumentParser(
        description="Rebuild billing data with timezone-aware calculations",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--site-id", type=UUID, required=True, help="Site UUID")
    parser.add_argument("--year", type=int, help="Year (use with --month)")
    parser.add_argument("--month", type=int, help="Month (1-12, use with --year)")
    parser.add_argument("--start-date", type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
                       help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
                       help="End date (YYYY-MM-DD)")
    parser.add_argument("--all", action='store_true',
                       help="Rebuild all billing data for the site")
    parser.add_argument("--dry-run", action='store_true',
                       help="Show what would be done without making changes")

    args = parser.parse_args()

    # Validate arguments
    if args.year and args.month:
        start_date = date(args.year, args.month, 1)
        if args.month == 12:
            end_date = date(args.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(args.year, args.month + 1, 1) - timedelta(days=1)
    elif args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    elif args.all:
        start_date = None
        end_date = None
    else:
        parser.error("Must specify --year/--month, --start-date/--end-date, or --all")

    logger.info("=" * 80)
    logger.info("BILLING DATA REBUILD")
    logger.info("=" * 80)
    logger.info(f"Site ID: {args.site_id}")
    if args.all:
        logger.info("Mode: Rebuild ALL billing data")
    else:
        logger.info(f"Period: {start_date} to {end_date}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    logger.info("=" * 80)

    # Create database connection
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        # Build from components
        db_host = os.getenv("DB_HOST", "127.0.0.1")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER", "solarhub")
        db_password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "solar_hub")
        db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get periods to rebuild
        periods = await get_billing_periods_to_rebuild(
            session, args.site_id, start_date, end_date, args.all
        )

        if not periods:
            logger.warning("No billing periods found to rebuild")
            return

        logger.info(f"Found {len(periods)} period(s) to rebuild:")
        for period_start, period_end in periods:
            logger.info(f"  - {period_start} to {period_end}")

        if args.dry_run:
            logger.info("\n[DRY RUN] Exiting without making changes")
            return

        # Confirm before proceeding
        response = input("\nProceed with rebuilding? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Cancelled by user")
            return

        # Rebuild each period
        total_deleted = 0
        total_recalculated = 0

        for period_start, period_end in periods:
            logger.info(f"\nProcessing {period_start} to {period_end}...")

            # Delete old billing data
            deleted = await delete_billing_for_period(
                session, args.site_id, period_start, period_end, dry_run=False
            )
            total_deleted += deleted

            # Recalculate billing
            result = await recalculate_billing_for_period(
                session, args.site_id, period_start, period_end, dry_run=False
            )
            total_recalculated += 1

        logger.info("=" * 80)
        logger.info(f"✓ Rebuild complete!")
        logger.info(f"  - Deleted: {total_deleted} old billing record(s)")
        logger.info(f"  - Recalculated: {total_recalculated} period(s)")
        logger.info("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nCancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Rebuild failed: {e}")
        sys.exit(1)
