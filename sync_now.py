"""
Quick sync script to populate System A summary tables from System B telemetry.
Run from project root: python sync_now.py
"""
import asyncio
import sys
import logging
from pathlib import Path

# Add system_a to path
sys.path.insert(0, str(Path(__file__).parent / "system_a"))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
)
logger = logging.getLogger(__name__)


async def main():
    """Run manual sync."""
    from system_a.app.infrastructure.database.connection import get_unit_of_work
    from system_a.app.infrastructure.external.system_b_client import get_system_b_client
    from system_a.app.infrastructure.database.repositories.telemetry_repository import SQLAlchemyTelemetryRepository
    from system_a.app.application.services.telemetry_sync_service import TelemetrySyncService

    logger.info("=" * 60)
    logger.info("MANUAL TELEMETRY SYNC")
    logger.info("=" * 60)

    try:
        uow = get_unit_of_work()
        async with uow:
            sync_service = TelemetrySyncService(
                system_b_client=get_system_b_client(),
                telemetry_repository=SQLAlchemyTelemetryRepository(uow._session),
                site_repository=uow.sites,
                device_repository=uow.devices,
            )

            # Get all sites
            logger.info("Finding sites...")
            all_orgs = await uow.organizations.list_all(limit=100)
            site_ids = []
            for org in all_orgs:
                sites = await uow.sites.get_by_organization_id(org.id)
                site_ids.extend([s.id for s in sites])

            logger.info(f"Found {len(site_ids)} sites: {site_ids}")

            if not site_ids:
                logger.error("No sites found! Create a site first.")
                return

            # Sync hourly data (last 24 hours)
            logger.info("Syncing hourly data (last 24 hours)...")
            hourly_results = await sync_service.sync_all_sites(site_ids=site_ids)

            total_hourly = sum(r.records_upserted for r in hourly_results.values())
            total_errors = sum(len(r.errors) for r in hourly_results.values())

            logger.info(f"Hourly sync: {total_hourly} records, {total_errors} errors")

            if total_errors > 0:
                for site_id, result in hourly_results.items():
                    if result.errors:
                        logger.error(f"Site {site_id} errors:")
                        for error in result.errors[:3]:  # Show first 3 errors
                            logger.error(f"  - {error}")

            # Roll up to daily (last 7 days)
            logger.info("Rolling up to daily summaries (last 7 days)...")
            daily_records = 0
            for site_id in site_ids:
                result = await sync_service.sync_daily_for_site(site_id, days_back=7)
                daily_records += result.records_upserted
                if result.errors:
                    logger.warning(f"Site {site_id} daily errors: {result.errors[:2]}")

            logger.info(f"Daily rollup: {daily_records} records")

            # Commit everything
            await uow.commit()

            logger.info("=" * 60)
            logger.info("✅ SYNC COMPLETED!")
            logger.info(f"   Hourly records: {total_hourly}")
            logger.info(f"   Daily records: {daily_records}")
            logger.info(f"   Total errors: {total_errors}")
            logger.info("=" * 60)

            if total_hourly > 0:
                logger.info("✅ Charts should now show data! Refresh your browser.")
            else:
                logger.warning("⚠️  No records synced. Check System B has telemetry data.")

    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
