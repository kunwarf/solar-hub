"""
Test script to query System B directly for hourly energy data for a specific date.

Run from project root:
  python scratchpad/test_system_b_hourly_data.py
"""
import asyncio
import sys
import logging
from datetime import date, datetime, time, timezone
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


async def test_system_b_hourly_data():
    """Test System B hourly data for specific dates."""
    from system_a.app.infrastructure.external.system_b_client import SystemBClient
    from system_a.app.config import get_settings

    settings = get_settings()

    # Test dates - check a few recent days
    test_dates = [
        date(2026, 2, 2),  # Feb 2
        date(2026, 2, 1),  # Feb 1
        date(2026, 1, 31),  # Jan 31
        date(2026, 1, 30),  # Jan 30
    ]

    logger.info("=" * 80)
    logger.info("SYSTEM B HOURLY DATA TEST")
    logger.info("=" * 80)
    logger.info(f"Site ID: {SITE_ID}")
    logger.info(f"System B URL: {settings.system_b_url}")
    logger.info("=" * 80)

    try:
        # Create System B client
        system_b_client = SystemBClient(
            base_url=settings.system_b_url,
            api_key=settings.system_b_api_key,
        )
        logger.info("✓ Created System B client")

        for test_date in test_dates:
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"DATE: {test_date}")
            logger.info("=" * 80)

            # Get hourly data for this date
            start_time = datetime.combine(test_date, time.min, tzinfo=timezone.utc)
            end_time = datetime.combine(test_date, time.max, tzinfo=timezone.utc)

            logger.info(f"Fetching hourly data from {start_time} to {end_time}")

            try:
                hourly_data = await system_b_client.get_hourly_energy_summary(
                    site_id=SITE_ID,
                    start_time=start_time,
                    end_time=end_time
                )

                logger.info(f"Received {len(hourly_data)} hourly data points")

                if len(hourly_data) == 0:
                    logger.warning("✗ NO DATA RETURNED!")
                    continue

                # Aggregate the hourly data
                total_pv = sum(h.get("pv_kwh", 0) for h in hourly_data)
                total_load = sum(h.get("load_kwh", 0) for h in hourly_data)
                total_import = sum(h.get("grid_import_kwh", 0) for h in hourly_data)
                total_export = sum(h.get("grid_export_kwh", 0) for h in hourly_data)

                logger.info("")
                logger.info("DAILY TOTALS (sum of all hours):")
                logger.info(f"  PV Generation:  {total_pv:>10.2f} kWh")
                logger.info(f"  Load:           {total_load:>10.2f} kWh")
                logger.info(f"  Grid Import:    {total_import:>10.2f} kWh")
                logger.info(f"  Grid Export:    {total_export:>10.2f} kWh")

                # Check for negative values
                negative_pv = [h for h in hourly_data if h.get("pv_kwh", 0) < 0]
                negative_load = [h for h in hourly_data if h.get("load_kwh", 0) < 0]
                negative_import = [h for h in hourly_data if h.get("grid_import_kwh", 0) < 0]
                negative_export = [h for h in hourly_data if h.get("grid_export_kwh", 0) < 0]

                if negative_pv or negative_load or negative_import or negative_export:
                    logger.warning("")
                    logger.warning("⚠ NEGATIVE VALUES DETECTED:")
                    if negative_pv:
                        logger.warning(f"  PV: {len(negative_pv)} hours with negative values")
                    if negative_load:
                        logger.warning(f"  Load: {len(negative_load)} hours with negative values")
                    if negative_import:
                        logger.warning(f"  Import: {len(negative_import)} hours with negative values")
                        # Show the negative import hours
                        for h in negative_import[:3]:
                            logger.warning(f"    {h['timestamp']}: grid_import_kwh = {h['grid_import_kwh']}")
                    if negative_export:
                        logger.warning(f"  Export: {len(negative_export)} hours with negative values")

                # Show sample of hourly data (first 5 hours)
                logger.info("")
                logger.info("SAMPLE HOURLY DATA (first 5 hours):")
                for i, h in enumerate(hourly_data[:5]):
                    logger.info(
                        f"  {h['timestamp']}: "
                        f"PV={h.get('pv_kwh', 0):>6.2f}, "
                        f"Load={h.get('load_kwh', 0):>6.2f}, "
                        f"Import={h.get('grid_import_kwh', 0):>6.2f}, "
                        f"Export={h.get('grid_export_kwh', 0):>6.2f}"
                    )

            except Exception as e:
                logger.error(f"Failed to fetch data for {test_date}: {e}", exc_info=True)

        await system_b_client.close()
        logger.info("")
        logger.info("=" * 80)
        logger.info("TEST COMPLETE")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(test_system_b_hourly_data())
