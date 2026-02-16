"""
Verify billing calculation accuracy by comparing database values with System B raw data.

Run from project root:
  python scratchpad/verify_billing_accuracy.py
"""
import asyncio
import sys
import logging
from datetime import date, datetime, time, timezone, timedelta
from uuid import UUID
from pathlib import Path

# Add system_a to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "system_a"))
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

SITE_ID = UUID('271edc3f-f8e8-4aac-acae-78ffd8bf4643')


async def verify_billing_accuracy():
    """Verify billing calculation accuracy."""
    from system_a.app.infrastructure.database.connection import get_unit_of_work
    from system_a.app.infrastructure.database.repositories.net_metering_repository import SQLAlchemyNetMeteringRepository
    from system_a.app.infrastructure.external.system_b_client import SystemBClient
    from system_a.app.config import get_settings
    from sqlalchemy import text

    settings = get_settings()

    # Check last 3 days
    end_date = date.today()
    start_date = end_date - timedelta(days=3)

    logger.info("=" * 80)
    logger.info("BILLING ACCURACY VERIFICATION")
    logger.info("=" * 80)
    logger.info(f"Site ID: {SITE_ID}")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info("=" * 80)

    try:
        # Create System B client
        system_b_client = None
        if settings.use_system_b_for_billing:
            system_b_client = SystemBClient(
                base_url=settings.system_b_url,
                api_key=settings.system_b_api_key,
            )
            logger.info(f"✓ Created System B client: {settings.system_b_url}")

        # Get Unit of Work
        uow = get_unit_of_work()

        async with uow:
            nm_repo = SQLAlchemyNetMeteringRepository(uow._session)

            # Query billing_daily snapshots
            logger.info("")
            logger.info("=" * 80)
            logger.info("BILLING SNAPSHOTS FROM DATABASE")
            logger.info("=" * 80)

            query = text("""
                SELECT
                    date,
                    import_off_kwh,
                    import_peak_kwh,
                    export_off_kwh,
                    export_peak_kwh,
                    solar_generation_kwh,
                    load_consumption_kwh,
                    bill_final_rs_to_date,
                    surplus_deficit_flag
                FROM billing_daily
                WHERE site_id = :site_id
                    AND date >= :start_date
                    AND date <= :end_date
                ORDER BY date
            """)

            result = await uow._session.execute(
                query,
                {"site_id": str(SITE_ID), "start_date": start_date, "end_date": end_date}
            )

            snapshots = result.fetchall()

            if not snapshots:
                logger.warning("✗ No billing snapshots found in database!")
                return

            logger.info(f"Found {len(snapshots)} billing snapshots")
            logger.info("")

            for snapshot in snapshots:
                logger.info(f"Date: {snapshot.date}")
                logger.info(f"  Import Off-Peak:  {snapshot.import_off_kwh:>8.2f} kWh")
                logger.info(f"  Import Peak:      {snapshot.import_peak_kwh:>8.2f} kWh")
                logger.info(f"  Export Off-Peak:  {snapshot.export_off_kwh:>8.2f} kWh")
                logger.info(f"  Export Peak:      {snapshot.export_peak_kwh:>8.2f} kWh")
                logger.info(f"  Solar Generation: {snapshot.solar_generation_kwh:>8.2f} kWh")
                logger.info(f"  Load Consumption: {snapshot.load_consumption_kwh:>8.2f} kWh")
                logger.info(f"  Bill To Date:     {snapshot.bill_final_rs_to_date:>8.2f} PKR")
                logger.info(f"  Surplus/Deficit:  {snapshot.surplus_deficit_flag}")
                logger.info("")

        # Now fetch raw System B data for comparison
        if system_b_client:
            logger.info("=" * 80)
            logger.info("RAW SYSTEM B DATA FOR COMPARISON")
            logger.info("=" * 80)

            for snapshot in snapshots:
                target_date = snapshot.date

                # Get hourly data for this date
                start_time = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
                end_time = datetime.combine(target_date, time.max, tzinfo=timezone.utc)

                logger.info(f"Date: {target_date}")
                logger.info(f"  Fetching hourly data from {start_time} to {end_time}")

                try:
                    hourly_data = await system_b_client.get_hourly_energy_summary(
                        site_id=SITE_ID,
                        start_time=start_time,
                        end_time=end_time
                    )

                    # Aggregate the hourly data
                    total_pv = sum(h.get("pv_kwh", 0) for h in hourly_data)
                    total_load = sum(h.get("load_kwh", 0) for h in hourly_data)
                    total_import = sum(h.get("grid_import_kwh", 0) for h in hourly_data)
                    total_export = sum(h.get("grid_export_kwh", 0) for h in hourly_data)

                    logger.info(f"  System B Totals (24 hours):")
                    logger.info(f"    PV Generation: {total_pv:>8.2f} kWh")
                    logger.info(f"    Load:          {total_load:>8.2f} kWh")
                    logger.info(f"    Grid Import:   {total_import:>8.2f} kWh")
                    logger.info(f"    Grid Export:   {total_export:>8.2f} kWh")
                    logger.info(f"    Hours fetched: {len(hourly_data)}")

                    # Compare with database snapshot
                    db_total_import = float(snapshot.import_off_kwh + snapshot.import_peak_kwh)
                    db_total_export = float(snapshot.export_off_kwh + snapshot.export_peak_kwh)

                    import_diff = abs(total_import - db_total_import)
                    export_diff = abs(total_export - db_total_export)
                    pv_diff = abs(total_pv - float(snapshot.solar_generation_kwh))
                    load_diff = abs(total_load - float(snapshot.load_consumption_kwh))

                    logger.info(f"  Comparison (System B vs Database):")
                    logger.info(f"    Import diff:   {import_diff:>8.2f} kWh {'✓' if import_diff < 0.1 else '✗ MISMATCH'}")
                    logger.info(f"    Export diff:   {export_diff:>8.2f} kWh {'✓' if export_diff < 0.1 else '✗ MISMATCH'}")
                    logger.info(f"    PV diff:       {pv_diff:>8.2f} kWh {'✓' if pv_diff < 0.1 else '✗ MISMATCH'}")
                    logger.info(f"    Load diff:     {load_diff:>8.2f} kWh {'✓' if load_diff < 0.1 else '✗ MISMATCH'}")

                    # Show peak vs off-peak breakdown
                    logger.info(f"  Peak/Off-Peak Classification:")
                    peak_hours = [19, 20, 21, 22, 23]  # 7 PM to midnight

                    peak_import = sum(
                        h.get("grid_import_kwh", 0)
                        for h in hourly_data
                        if datetime.fromisoformat(h["timestamp"].replace("Z", "+00:00")).hour in peak_hours
                    )
                    off_peak_import = total_import - peak_import

                    peak_export = sum(
                        h.get("grid_export_kwh", 0)
                        for h in hourly_data
                        if datetime.fromisoformat(h["timestamp"].replace("Z", "+00:00")).hour in peak_hours
                    )
                    off_peak_export = total_export - peak_export

                    logger.info(f"    Calculated Peak Import:     {peak_import:>8.2f} kWh (DB: {snapshot.import_peak_kwh:>8.2f})")
                    logger.info(f"    Calculated Off-Peak Import: {off_peak_import:>8.2f} kWh (DB: {snapshot.import_off_kwh:>8.2f})")
                    logger.info(f"    Calculated Peak Export:     {peak_export:>8.2f} kWh (DB: {snapshot.export_peak_kwh:>8.2f})")
                    logger.info(f"    Calculated Off-Peak Export: {off_peak_export:>8.2f} kWh (DB: {snapshot.export_off_kwh:>8.2f})")

                    logger.info("")

                except Exception as e:
                    logger.error(f"  Failed to fetch System B data: {e}")
                    logger.info("")

            await system_b_client.close()

        logger.info("=" * 80)
        logger.info("VERIFICATION COMPLETE")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(verify_billing_accuracy())
