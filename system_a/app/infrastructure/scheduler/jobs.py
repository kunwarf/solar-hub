"""
Scheduled jobs.

DEPRECATED: Telemetry sync jobs are disabled - System A now queries System B directly.
Only billing jobs remain active.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all scheduled jobs with the scheduler."""
    # DEPRECATED: Telemetry sync jobs disabled - we now query System B directly
    # No longer syncing data to System A summary tables
    # scheduler.add_job(
    #     sync_hourly_job,
    #     CronTrigger(minute=5),
    #     id="sync_hourly",
    #     name="Hourly telemetry sync",
    #     replace_existing=True,
    # )
    # scheduler.add_job(
    #     sync_daily_job,
    #     CronTrigger(hour=0, minute=15),
    #     id="sync_daily",
    #     name="Daily telemetry rollup",
    #     replace_existing=True,
    # )
    # scheduler.add_job(
    #     sync_monthly_job,
    #     CronTrigger(day=1, hour=1, minute=0),
    #     id="sync_monthly",
    #     name="Monthly telemetry rollup",
    #     replace_existing=True,
    # )
    logger.info("Telemetry sync jobs disabled (querying System B directly)")

    # Billing jobs (still active)
    from .billing_jobs import register_billing_jobs
    register_billing_jobs(scheduler)

    # AI jobs: outage detection + future insight prefetch
    from .ai_jobs import register_ai_jobs
    register_ai_jobs(scheduler)


async def sync_hourly_job() -> None:
    """
    Sync hourly telemetry from System B for all sites.

    Runs every hour at :05 past the hour.
    Pulls the last 2 hours of aggregate data.
    """
    logger.info("Starting hourly telemetry sync job")

    try:
        from ...infrastructure.database.connection import get_unit_of_work
        from ...infrastructure.external.system_b_client import get_system_b_client
        from ...infrastructure.database.repositories.telemetry_repository import (
            SQLAlchemyTelemetryRepository,
        )
        from ...application.services.telemetry_sync_service import TelemetrySyncService

        uow = await get_unit_of_work()
        async with uow:
            sync_service = TelemetrySyncService(
                system_b_client=get_system_b_client(),
                telemetry_repository=SQLAlchemyTelemetryRepository(uow._session),
                site_repository=uow.sites,
                device_repository=uow.devices,
            )

            # Get all site IDs from all orgs
            all_orgs = await uow.organizations.list_all(limit=100)
            site_ids = []
            for org in all_orgs:
                sites = await uow.sites.get_by_organization_id(org.id)
                site_ids.extend([s.id for s in sites])

            if site_ids:
                results = await sync_service.sync_all_sites(site_ids=site_ids)
                await uow.commit()

                total_records = sum(r.records_upserted for r in results.values())
                total_errors = sum(len(r.errors) for r in results.values())
                logger.info(
                    "Hourly sync completed: %d sites, %d records, %d errors",
                    len(results), total_records, total_errors,
                )
            else:
                logger.info("No sites found for hourly sync")

    except Exception as e:
        logger.error("Hourly sync job failed: %s", e, exc_info=True)


async def sync_daily_job() -> None:
    """
    Roll up hourly summaries into daily summaries.

    Runs daily at 00:15 Asia/Karachi.
    Aggregates yesterday's hourly data into daily rows.
    """
    logger.info("Starting daily telemetry rollup job")

    try:
        from ...infrastructure.database.connection import get_unit_of_work
        from ...infrastructure.external.system_b_client import get_system_b_client
        from ...infrastructure.database.repositories.telemetry_repository import (
            SQLAlchemyTelemetryRepository,
        )
        from ...application.services.telemetry_sync_service import TelemetrySyncService

        uow = await get_unit_of_work()
        async with uow:
            sync_service = TelemetrySyncService(
                system_b_client=get_system_b_client(),
                telemetry_repository=SQLAlchemyTelemetryRepository(uow._session),
                site_repository=uow.sites,
                device_repository=uow.devices,
            )

            all_orgs = await uow.organizations.list_all(limit=100)
            total_records = 0
            total_errors = 0

            for org in all_orgs:
                sites = await uow.sites.get_by_organization_id(org.id)
                for site in sites:
                    result = await sync_service.sync_daily_for_site(site.id, days_back=1)
                    total_records += result.records_upserted
                    total_errors += len(result.errors)

            await uow.commit()
            logger.info(
                "Daily rollup completed: %d records, %d errors",
                total_records, total_errors,
            )

    except Exception as e:
        logger.error("Daily rollup job failed: %s", e, exc_info=True)


async def sync_monthly_job() -> None:
    """
    Roll up daily summaries into monthly summaries.

    Runs on the 1st of each month at 01:00 Asia/Karachi.
    """
    logger.info("Starting monthly telemetry rollup job")

    try:
        from ...infrastructure.database.connection import get_unit_of_work
        from ...infrastructure.external.system_b_client import get_system_b_client
        from ...infrastructure.database.repositories.telemetry_repository import (
            SQLAlchemyTelemetryRepository,
        )
        from ...application.services.telemetry_sync_service import TelemetrySyncService

        uow = await get_unit_of_work()
        async with uow:
            sync_service = TelemetrySyncService(
                system_b_client=get_system_b_client(),
                telemetry_repository=SQLAlchemyTelemetryRepository(uow._session),
                site_repository=uow.sites,
                device_repository=uow.devices,
            )

            all_orgs = await uow.organizations.list_all(limit=100)
            total_records = 0
            total_errors = 0

            for org in all_orgs:
                sites = await uow.sites.get_by_organization_id(org.id)
                for site in sites:
                    result = await sync_service.sync_monthly_for_site(site.id, months_back=1)
                    total_records += result.records_upserted
                    total_errors += len(result.errors)

            await uow.commit()
            logger.info(
                "Monthly rollup completed: %d records, %d errors",
                total_records, total_errors,
            )

    except Exception as e:
        logger.error("Monthly rollup job failed: %s", e, exc_info=True)
