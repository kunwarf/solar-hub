"""
Backfill Billing Script - Recalculate billing using System B telemetry data.

This script re-computes historical billing snapshots using System B's
TimescaleDB continuous aggregates as the data source instead of System A's
PostgreSQL summary tables.

Usage:
    # Backfill single site for last 30 days
    python -m scripts.backfill_billing_from_system_b --site-id <UUID> --days 30

    # Backfill specific date range
    python -m scripts.backfill_billing_from_system_b --site-id <UUID> \\
        --start-date 2026-01-01 --end-date 2026-01-31

    # Backfill all sites for last 7 days (dry run)
    python -m scripts.backfill_billing_from_system_b --all-sites --days 7 --dry-run

    # Backfill with validation (compare with existing billing data)
    python -m scripts.backfill_billing_from_system_b --site-id <UUID> --days 30 --validate
"""
import asyncio
import logging
import sys
from datetime import date, timedelta
from typing import List, Optional
from uuid import UUID

import click
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, str(__file__ + "/../../"))

from app.config import settings
from app.application.services.billing_scheduler_service import BillingSchedulerService
from app.domain.services.net_metering_calculator import NetMeteringCalculator
from app.infrastructure.database.repositories.net_metering_repository import (
    SQLAlchemyNetMeteringRepository,
)
from app.infrastructure.database.repositories.telemetry_repository import (
    SQLAlchemyTelemetryRepository,
)
from app.infrastructure.database.repositories.telemetry_system_b_repository import (
    SystemBTelemetryRepository,
)
from app.infrastructure.database.repositories.site_repository import (
    SQLAlchemySiteRepository,
)
from app.infrastructure.external.system_b_client import SystemBClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackfillStats:
    """Statistics for backfill operation."""

    def __init__(self):
        self.total_sites = 0
        self.total_days = 0
        self.successful = 0
        self.failed = 0
        self.skipped = 0
        self.errors: List[str] = []

    def print_summary(self):
        """Print backfill summary."""
        logger.info("=" * 80)
        logger.info("BACKFILL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total sites processed: {self.total_sites}")
        logger.info(f"Total days processed: {self.total_days}")
        logger.info(f"Successful: {self.successful}")
        logger.info(f"Failed: {self.failed}")
        logger.info(f"Skipped: {self.skipped}")

        if self.errors:
            logger.info("\nErrors encountered:")
            for error in self.errors[:10]:  # Show first 10 errors
                logger.error(f"  - {error}")
            if len(self.errors) > 10:
                logger.info(f"  ... and {len(self.errors) - 10} more errors")
        logger.info("=" * 80)


async def backfill_site(
    billing_service: BillingSchedulerService,
    site_id: UUID,
    start_date: date,
    end_date: date,
    dry_run: bool = False,
    validate: bool = False,
    stats: Optional[BackfillStats] = None,
) -> None:
    """
    Backfill billing for a single site.

    Args:
        billing_service: Billing scheduler service instance
        site_id: Site UUID to backfill
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
        dry_run: If True, don't save changes
        validate: If True, compare with existing billing data
        stats: Statistics tracker
    """
    logger.info(f"Starting backfill for site {site_id}: {start_date} to {end_date}")

    current_date = start_date
    while current_date <= end_date:
        try:
            logger.info(f"Processing {site_id} for {current_date}")

            # Compute billing snapshot
            result = await billing_service.compute_site_daily_snapshot(
                site_id=site_id,
                target_date=current_date,
            )

            if result.success:
                if dry_run:
                    logger.info(
                        f"  DRY RUN: Would save snapshot with "
                        f"snapshot_id={result.snapshot_id}"
                    )
                else:
                    logger.info(
                        f"  ✓ Backfilled {current_date}: "
                        f"snapshot_id={result.snapshot_id}"
                    )

                if stats:
                    stats.successful += 1
            else:
                logger.warning(f"  ✗ Failed {current_date}: {result.error}")
                if stats:
                    stats.failed += 1
                    if result.error:
                        stats.errors.append(f"{site_id} {current_date}: {result.error}")

        except Exception as e:
            logger.error(
                f"  ✗ Exception processing {site_id} for {current_date}: {e}",
                exc_info=True
            )
            if stats:
                stats.failed += 1
                stats.errors.append(f"{site_id} {current_date}: {str(e)}")

        current_date += timedelta(days=1)

    logger.info(f"Completed backfill for site {site_id}")


async def main(
    site_id: Optional[str],
    all_sites: bool,
    start_date: Optional[str],
    end_date: Optional[str],
    days: Optional[int],
    dry_run: bool,
    validate: bool,
):
    """Main backfill execution."""
    logger.info("Initializing backfill script...")
    logger.info(f"Using System B URL: {settings.system_b.url}")

    # Calculate date range
    if start_date and end_date:
        start_date_obj = date.fromisoformat(start_date)
        end_date_obj = date.fromisoformat(end_date)
    elif days:
        end_date_obj = date.today() - timedelta(days=1)  # Yesterday
        start_date_obj = end_date_obj - timedelta(days=days - 1)
    else:
        raise ValueError("Either --start-date and --end-date, or --days must be provided")

    logger.info(f"Backfill date range: {start_date_obj} to {end_date_obj}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Validation: {validate}")

    # Initialize database
    engine = create_async_engine(settings.database.url, echo=False)
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    stats = BackfillStats()

    async with async_session_maker() as session:
        # Initialize repositories
        net_metering_repo = SQLAlchemyNetMeteringRepository(session)
        telemetry_repo = SQLAlchemyTelemetryRepository(session)
        site_repo = SQLAlchemySiteRepository(session)

        # Initialize System B client and repository
        system_b_client = SystemBClient(
            base_url=settings.system_b.url,
            api_key=settings.system_b.api_key,
            timeout=settings.system_b.timeout,
        )
        system_b_telemetry_repo = SystemBTelemetryRepository(system_b_client)

        # Initialize calculator
        calculator = NetMeteringCalculator()

        # Initialize billing service (force use System B)
        billing_service = BillingSchedulerService(
            net_metering_repo=net_metering_repo,
            telemetry_repo=telemetry_repo,
            site_repo=site_repo,
            calculator=calculator,
            system_b_telemetry_repo=system_b_telemetry_repo,
        )

        # Override settings to force System B usage
        original_use_system_b = settings.use_system_b_for_billing
        original_validate = settings.validate_system_b_data
        settings.use_system_b_for_billing = True
        settings.validate_system_b_data = validate

        try:
            # Get list of sites to process
            if all_sites:
                sites = await site_repo.list_active_sites(limit=1000)
                site_ids = [site.id for site in sites]
                logger.info(f"Processing {len(site_ids)} active sites")
            elif site_id:
                site_ids = [UUID(site_id)]
                logger.info(f"Processing single site: {site_id}")
            else:
                raise ValueError("Either --site-id or --all-sites must be provided")

            stats.total_sites = len(site_ids)
            stats.total_days = (end_date_obj - start_date_obj).days + 1

            # Process each site
            for idx, site_id in enumerate(site_ids, 1):
                logger.info(f"\nProcessing site {idx}/{len(site_ids)}: {site_id}")
                await backfill_site(
                    billing_service=billing_service,
                    site_id=site_id,
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    dry_run=dry_run,
                    validate=validate,
                    stats=stats,
                )

                # Commit after each site (unless dry run)
                if not dry_run:
                    await session.commit()
                    logger.info(f"Committed changes for site {site_id}")

        finally:
            # Restore original settings
            settings.use_system_b_for_billing = original_use_system_b
            settings.validate_system_b_data = original_validate

            # Close System B client
            await system_b_client.close()

    # Print summary
    stats.print_summary()

    # Close engine
    await engine.dispose()

    # Exit with error code if there were failures
    if stats.failed > 0:
        sys.exit(1)


@click.command()
@click.option(
    '--site-id',
    type=str,
    help='Site UUID to backfill (mutually exclusive with --all-sites)'
)
@click.option(
    '--all-sites',
    is_flag=True,
    help='Backfill all active sites (mutually exclusive with --site-id)'
)
@click.option(
    '--start-date',
    type=str,
    help='Start date in ISO format (YYYY-MM-DD)'
)
@click.option(
    '--end-date',
    type=str,
    help='End date in ISO format (YYYY-MM-DD)'
)
@click.option(
    '--days',
    type=int,
    help='Number of days to backfill (from yesterday backwards)'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Dry run mode - don\'t save changes to database'
)
@click.option(
    '--validate',
    is_flag=True,
    help='Enable validation against existing System A data'
)
def cli(site_id, all_sites, start_date, end_date, days, dry_run, validate):
    """Backfill billing data using System B telemetry."""
    # Validation
    if not site_id and not all_sites:
        click.echo("Error: Either --site-id or --all-sites must be provided")
        sys.exit(1)

    if site_id and all_sites:
        click.echo("Error: --site-id and --all-sites are mutually exclusive")
        sys.exit(1)

    if not (start_date and end_date) and not days:
        click.echo("Error: Either --start-date and --end-date, or --days must be provided")
        sys.exit(1)

    if (start_date or end_date) and days:
        click.echo("Error: Cannot use both --start-date/--end-date and --days")
        sys.exit(1)

    # Run async main
    asyncio.run(main(site_id, all_sites, start_date, end_date, days, dry_run, validate))


if __name__ == '__main__':
    cli()
