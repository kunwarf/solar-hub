"""
Test script to manually run billing calculation and verify database commit.

Run from project root:
  cd /opt/solarhub/app/solar-hub/system_a
  python ../scratchpad/test_billing_commit.py
"""
import asyncio
import sys
import logging
from datetime import date, timedelta
from uuid import UUID
from pathlib import Path

# Add system_a to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "system_a"))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

SITE_ID = UUID('271edc3f-f8e8-4aac-acae-78ffd8bf4643')


async def test_billing_with_commit():
    """Test billing calculation with explicit commit."""
    from system_a.app.infrastructure.database.connection import get_unit_of_work
    from system_a.app.infrastructure.database.repositories.net_metering_repository import SQLAlchemyNetMeteringRepository
    from system_a.app.infrastructure.database.repositories.telemetry_repository import SQLAlchemyTelemetryRepository
    from system_a.app.infrastructure.database.repositories.site_repository import SQLAlchemySiteRepository
    from system_a.app.infrastructure.database.repositories.telemetry_system_b_repository import SystemBTelemetryRepository
    from system_a.app.infrastructure.external.system_b_client import SystemBClient
    from system_a.app.domain.services.net_metering_calculator import NetMeteringCalculator
    from system_a.app.application.services.billing_scheduler_service import BillingSchedulerService
    from system_a.app.config import get_settings

    settings = get_settings()
    target_date = date.today() - timedelta(days=1)

    logger.info("=" * 80)
    logger.info("BILLING CALCULATION TEST")
    logger.info("=" * 80)
    logger.info(f"Site ID: {SITE_ID}")
    logger.info(f"Target date: {target_date}")
    logger.info(f"USE_SYSTEM_B_FOR_BILLING: {settings.use_system_b_for_billing}")
    logger.info("=" * 80)

    try:
        # Create System B client if needed
        system_b_client = None
        if settings.use_system_b_for_billing:
            system_b_client = SystemBClient(
                base_url=settings.system_b_url,
                api_key=settings.system_b_api_key,
            )
            logger.info(f"Created System B client: {settings.system_b_url}")

        # Get Unit of Work
        uow = await get_unit_of_work()

        async with uow:
            logger.info("Unit of Work context started")

            # Create repositories
            nm_repo = SQLAlchemyNetMeteringRepository(uow._session)
            telemetry_repo = SQLAlchemyTelemetryRepository(uow._session)
            site_repo = SQLAlchemySiteRepository(uow._session)

            # Create System B telemetry repo if enabled
            system_b_telemetry_repo = None
            if system_b_client:
                system_b_telemetry_repo = SystemBTelemetryRepository(system_b_client)

            # Create service
            service = BillingSchedulerService(
                net_metering_repo=nm_repo,
                telemetry_repo=telemetry_repo,
                site_repo=site_repo,
                calculator=NetMeteringCalculator(),
                system_b_telemetry_repo=system_b_telemetry_repo,
            )

            logger.info("Created billing scheduler service")

            # Compute snapshot
            logger.info(f"Computing daily snapshot for {target_date}...")
            result = await service.compute_daily_snapshot(SITE_ID, target_date)

            logger.info("=" * 80)
            logger.info("CALCULATION RESULT")
            logger.info("=" * 80)
            logger.info(f"Success: {result.success}")
            logger.info(f"Error: {result.error}")
            logger.info(f"Snapshot ID: {result.snapshot_id}")
            logger.info(f"Billing Month ID: {result.billing_month_id}")
            logger.info("=" * 80)

            if not result.success:
                logger.error(f"Billing calculation failed: {result.error}")
                return

            # Verify snapshot exists in session BEFORE commit
            logger.info("Checking if snapshot exists in database BEFORE commit...")
            snapshot_before = await nm_repo.get_daily_snapshot(SITE_ID, target_date)
            if snapshot_before:
                logger.info(f"✓ Snapshot found BEFORE commit: bill_to_date={snapshot_before.bill_final_rs_to_date}")
            else:
                logger.warning("✗ Snapshot NOT found in database before commit (this is expected)")

            # COMMIT TRANSACTION
            logger.info("=" * 80)
            logger.info("COMMITTING TRANSACTION...")
            logger.info("=" * 80)
            await uow.commit()
            logger.info("✓ Transaction committed successfully")

        logger.info("Unit of Work context exited")

        # Create new UoW to verify data persisted
        logger.info("=" * 80)
        logger.info("VERIFYING DATA PERSISTENCE")
        logger.info("=" * 80)

        uow2 = await get_unit_of_work()
        async with uow2:
            nm_repo2 = SQLAlchemyNetMeteringRepository(uow2._session)

            # Check if snapshot exists AFTER commit (in new transaction)
            snapshot_after = await nm_repo2.get_daily_snapshot(SITE_ID, target_date)

            if snapshot_after:
                logger.info("=" * 80)
                logger.info("✓✓✓ SUCCESS! Snapshot persisted to database")
                logger.info("=" * 80)
                logger.info(f"Date: {snapshot_after.date}")
                logger.info(f"Bill to date: {snapshot_after.bill_final_rs_to_date} PKR")
                logger.info(f"Import off-peak: {snapshot_after.import_off_kwh} kWh")
                logger.info(f"Import peak: {snapshot_after.import_peak_kwh} kWh")
                logger.info(f"Export off-peak: {snapshot_after.export_off_kwh} kWh")
                logger.info(f"Export peak: {snapshot_after.export_peak_kwh} kWh")
                logger.info(f"Solar generation: {snapshot_after.solar_generation_kwh} kWh")
                logger.info(f"Load consumption: {snapshot_after.load_consumption_kwh} kWh")
                logger.info(f"Surplus/Deficit: {snapshot_after.surplus_deficit_flag.value}")
                logger.info("=" * 80)
            else:
                logger.error("=" * 80)
                logger.error("✗✗✗ FAILURE! Snapshot NOT found in database after commit")
                logger.error("=" * 80)
                logger.error("This indicates a transaction commit issue")

        # Close System B client
        if system_b_client:
            await system_b_client.close()
            logger.info("Closed System B client")

        logger.info("=" * 80)
        logger.info("TEST COMPLETE")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(test_billing_with_commit())
