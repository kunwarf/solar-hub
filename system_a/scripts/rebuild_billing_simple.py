"""
Simple billing rebuild script using API calls.

This script recalculates billing for historical periods by calling
the billing API endpoints.

Usage:
    # Rebuild billing for specific month
    python rebuild_billing_simple.py --site-id <uuid> --year 2026 --month 1

    # Rebuild billing for date range
    python rebuild_billing_simple.py --site-id <uuid> --start-date 2025-12-01 --end-date 2026-02-28

    # Dry run (show what would be done)
    python rebuild_billing_simple.py --site-id <uuid> --year 2026 --month 1 --dry-run
"""
import os
import sys
import argparse
import requests
from datetime import datetime, date, timedelta
from typing import Optional
from uuid import UUID
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


def delete_billing_for_period(
    api_url: str,
    site_id: UUID,
    period_start: date,
    period_end: date,
    dry_run: bool = False
) -> int:
    """Delete existing billing records for a period via API."""
    if dry_run:
        logger.info(f"[DRY RUN] Would delete billing for {period_start} to {period_end}")
        return 0

    try:
        response = requests.delete(
            f"{api_url}/billing/simulations",
            params={
                "site_id": str(site_id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat()
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            deleted = result.get("deleted_count", 0)
            logger.info(f"Deleted {deleted} billing record(s) for {period_start} to {period_end}")
            return deleted
        elif response.status_code == 404:
            logger.info(f"No billing records found for {period_start} to {period_end}")
            return 0
        else:
            logger.error(f"Failed to delete billing: HTTP {response.status_code}")
            return 0
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return 0


def recalculate_billing_for_period(
    api_url: str,
    site_id: UUID,
    period_start: date,
    period_end: date,
    dry_run: bool = False
) -> dict:
    """Recalculate billing for a period via API."""
    if dry_run:
        logger.info(f"[DRY RUN] Would recalculate billing for {period_start} to {period_end}")
        return {"dry_run": True}

    try:
        response = requests.post(
            f"{api_url}/billing/compute",
            json={
                "site_id": str(site_id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat()
            },
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"✓ Billing recalculated for {period_start} to {period_end}")
            logger.info(f"  Total bill: PKR {result.get('estimated_bill_pkr', 0)}")
            return result
        else:
            logger.error(f"Failed to recalculate billing: HTTP {response.status_code}")
            logger.error(f"Response: {response.text}")
            return {}
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild billing data using timezone-aware calculations",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--site-id", type=UUID, required=True, help="Site UUID")
    parser.add_argument("--year", type=int, help="Year (use with --month)")
    parser.add_argument("--month", type=int, help="Month (1-12, use with --year)")
    parser.add_argument("--start-date", type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
                       help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=lambda s: datetime.strptime(s, '%Y-%m-%d').date(),
                       help="End date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action='store_true',
                       help="Show what would be done without making changes")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000/api/v1",
                       help="API base URL (default: http://localhost:8000/api/v1)")

    args = parser.parse_args()

    # Validate arguments
    if args.year and args.month:
        start_date = date(args.year, args.month, 1)
        if args.month == 12:
            end_date = date(args.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(args.year, args.month + 1, 1) - timedelta(days=1)
        periods = [(start_date, end_date)]
    elif args.start_date and args.end_date:
        # Generate monthly periods
        periods = []
        current = date(args.start_date.year, args.start_date.month, 1)
        end = date(args.end_date.year, args.end_date.month, 1)

        while current <= end:
            if current.month == 12:
                next_month = date(current.year + 1, 1, 1)
            else:
                next_month = date(current.year, current.month + 1, 1)
            month_end = next_month - timedelta(days=1)
            periods.append((current, month_end))
            current = next_month
    else:
        parser.error("Must specify --year/--month or --start-date/--end-date")

    logger.info("=" * 80)
    logger.info("BILLING DATA REBUILD (API Method)")
    logger.info("=" * 80)
    logger.info(f"Site ID: {args.site_id}")
    logger.info(f"API URL: {args.api_url}")
    logger.info(f"Periods to rebuild: {len(periods)}")
    for period_start, period_end in periods:
        logger.info(f"  - {period_start} to {period_end}")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
    logger.info("=" * 80)

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
        deleted = delete_billing_for_period(
            args.api_url, args.site_id, period_start, period_end, dry_run=False
        )
        total_deleted += deleted

        # Recalculate billing
        result = recalculate_billing_for_period(
            args.api_url, args.site_id, period_start, period_end, dry_run=False
        )
        if result:
            total_recalculated += 1

    logger.info("=" * 80)
    logger.info(f"✓ Rebuild complete!")
    logger.info(f"  - Deleted: {total_deleted} old billing record(s)")
    logger.info(f"  - Recalculated: {total_recalculated} period(s)")
    logger.info("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nCancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Rebuild failed: {e}")
        sys.exit(1)
