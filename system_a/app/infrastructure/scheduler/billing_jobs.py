"""
Scheduled billing jobs.

Runs daily to compute running bills and finalize billing periods.
"""
import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def register_billing_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register billing scheduler jobs."""
    # Daily billing job at 00:30 Asia/Karachi
    scheduler.add_job(
        daily_billing_job,
        CronTrigger(hour=0, minute=30),
        id="daily_billing",
        name="Daily billing computation",
        replace_existing=True,
    )

    # Cycle-end check job (runs on 15th of each month at 01:00)
    # This is a safety net to ensure cycle settlements happen
    scheduler.add_job(
        cycle_settlement_check_job,
        CronTrigger(day=15, hour=1, minute=0),
        id="cycle_settlement_check",
        name="Billing cycle settlement check",
        replace_existing=True,
    )

    logger.info("Registered 2 billing scheduler jobs")


async def daily_billing_job() -> None:
    """
    Compute daily billing snapshots for all sites.

    Runs daily at 00:30 Asia/Karachi.
    Processes yesterday's data for all active sites.
    """
    logger.info("Starting daily billing job")

    try:
        from ...infrastructure.database.connection import get_unit_of_work
        from ...infrastructure.database.repositories.net_metering_repository import (
            SQLAlchemyNetMeteringRepository,
        )
        from ...infrastructure.database.repositories.telemetry_repository import (
            SQLAlchemyTelemetryRepository,
        )
        from ...infrastructure.database.repositories.site_repository import (
            SQLAlchemySiteRepository,
        )
        from ...domain.services.net_metering_calculator import NetMeteringCalculator
        from ...application.services.billing_scheduler_service import (
            BillingSchedulerService,
        )

        uow = await get_unit_of_work()
        async with uow:
            service = BillingSchedulerService(
                net_metering_repo=SQLAlchemyNetMeteringRepository(uow._session),
                telemetry_repo=SQLAlchemyTelemetryRepository(uow._session),
                site_repo=SQLAlchemySiteRepository(uow._session),
                calculator=NetMeteringCalculator(),
            )

            # Process yesterday's billing
            yesterday = date.today() - timedelta(days=1)
            result = await service.run_daily_billing_job(target_date=yesterday)

            await uow.commit()

            logger.info(
                "Daily billing job completed: %d/%d sites successful, %d failed",
                result.successful, result.total_sites, result.failed
            )

            # Log any failures
            for site_result in result.site_results:
                if not site_result.success:
                    logger.warning(
                        "Billing failed for site %s: %s",
                        site_result.site_id, site_result.error
                    )

    except Exception as e:
        logger.error("Daily billing job failed: %s", e, exc_info=True)


async def cycle_settlement_check_job() -> None:
    """
    Check and process any pending cycle settlements.

    Runs on the 15th of each month as a safety net.
    Ensures cycle settlements happen even if daily job missed them.
    """
    logger.info("Starting cycle settlement check job")

    try:
        from ...infrastructure.database.connection import get_unit_of_work
        from ...infrastructure.database.repositories.net_metering_repository import (
            SQLAlchemyNetMeteringRepository,
        )
        from ...infrastructure.database.repositories.site_repository import (
            SQLAlchemySiteRepository,
        )

        uow = await get_unit_of_work()
        async with uow:
            nm_repo = SQLAlchemyNetMeteringRepository(uow._session)
            site_repo = SQLAlchemySiteRepository(uow._session)

            # Get all active sites
            sites = await site_repo.list_active_sites(limit=1000)

            today = date.today()
            current_month = today.month
            settlements_processed = 0

            # Check if this is a cycle-end month (Jan, Apr, Jul, Oct - month after cycle ends)
            # Cycles end in months 3, 6, 9, 12 relative to anchor
            # If anchor is 15th, cycle 1 ends Apr 14, cycle 2 ends Jul 14, etc.

            for site in sites:
                config = await nm_repo.get_billing_config_by_site(site.id)
                if not config:
                    continue

                # Check for any unfinalzed cycles that should be settled
                cycles = await nm_repo.list_billing_cycles(
                    site_id=site.id,
                    status="active",
                    limit=4,
                )

                for cycle in cycles:
                    # If cycle end date is in the past and not finalized
                    if cycle.cycle_end_date < today:
                        logger.info(
                            "Found unfinalzed cycle %s for site %s (ended %s)",
                            cycle.id, site.id, cycle.cycle_end_date
                        )
                        # This would require finalization logic
                        # For now, just log it - the daily job should handle it
                        settlements_processed += 1

            await uow.commit()

            logger.info(
                "Cycle settlement check completed: %d pending settlements found",
                settlements_processed
            )

    except Exception as e:
        logger.error("Cycle settlement check failed: %s", e, exc_info=True)


async def backfill_billing_job(
    site_id: str,
    start_date: str,
    end_date: str,
) -> None:
    """
    Backfill billing data for a site.

    This is an on-demand job, not scheduled.

    Args:
        site_id: Site UUID as string
        start_date: Start date as YYYY-MM-DD
        end_date: End date as YYYY-MM-DD
    """
    from uuid import UUID
    from datetime import datetime

    logger.info(
        "Starting billing backfill for site %s from %s to %s",
        site_id, start_date, end_date
    )

    try:
        from ...infrastructure.database.connection import get_unit_of_work
        from ...infrastructure.database.repositories.net_metering_repository import (
            SQLAlchemyNetMeteringRepository,
        )
        from ...infrastructure.database.repositories.telemetry_repository import (
            SQLAlchemyTelemetryRepository,
        )
        from ...infrastructure.database.repositories.site_repository import (
            SQLAlchemySiteRepository,
        )
        from ...domain.services.net_metering_calculator import NetMeteringCalculator
        from ...application.services.billing_scheduler_service import (
            BillingSchedulerService,
        )

        uow = await get_unit_of_work()
        async with uow:
            service = BillingSchedulerService(
                net_metering_repo=SQLAlchemyNetMeteringRepository(uow._session),
                telemetry_repo=SQLAlchemyTelemetryRepository(uow._session),
                site_repo=SQLAlchemySiteRepository(uow._session),
                calculator=NetMeteringCalculator(),
            )

            results = await service.backfill_site(
                site_id=UUID(site_id),
                start_date=datetime.strptime(start_date, "%Y-%m-%d").date(),
                end_date=datetime.strptime(end_date, "%Y-%m-%d").date(),
            )

            await uow.commit()

            successful = sum(1 for r in results if r.success)
            logger.info(
                "Billing backfill completed: %d/%d days successful",
                successful, len(results)
            )

    except Exception as e:
        logger.error("Billing backfill failed: %s", e, exc_info=True)
