#!/usr/bin/env python3
"""
Sync sites metadata from System A to System B.

This script copies site ID and timezone information from the main database
(System A) to the telemetry database (System B) for use by timezone-aware
continuous aggregates.

Usage:
    python sync_sites_metadata.py
"""
import asyncio
import asyncpg
from dotenv import load_dotenv
import os
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


async def sync_sites():
    """Sync sites from System A to System B."""

    # Build connection strings
    # System A (main database)
    system_a_url = os.getenv("DATABASE_URL")

    # If DATABASE_URL not set, try to build from individual components
    if not system_a_url:
        logger.info("DATABASE_URL not set, trying to build from components...")
        db_host = os.getenv("DB_HOST", "127.0.0.1")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER", "solarhub")
        db_password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "solar_hub")

        system_a_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        logger.info(f"Built System A URL: {db_user}@{db_host}:{db_port}/{db_name}")

    # System B (telemetry database)
    timescale_host = os.getenv("TIMESCALE_HOST", "127.0.0.1")
    timescale_port = os.getenv("TIMESCALE_PORT", "5432")
    timescale_user = os.getenv("TIMESCALE_USER", "solarhub_telemetry")
    timescale_password = os.getenv("TIMESCALE_PASSWORD", "")
    timescale_db = os.getenv("TIMESCALE_DATABASE", "solar_hub_telemetry")

    system_b_url = f"postgresql://{timescale_user}:{timescale_password}@{timescale_host}:{timescale_port}/{timescale_db}"

    logger.info("Connecting to databases...")

    # Connect to both databases
    conn_a = None
    conn_b = None

    try:
        conn_a = await asyncpg.connect(system_a_url)
        conn_b = await asyncpg.connect(system_b_url)

        logger.info("✓ Connected to both databases")

        # Check if sites_metadata table exists
        table_exists = await conn_b.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'sites_metadata'
            )
        """)

        if not table_exists:
            logger.error("sites_metadata table does not exist in System B")
            logger.error("Please run migration 0007 first: alembic upgrade head")
            sys.exit(1)

        # Get all sites from System A
        logger.info("Fetching sites from System A...")
        sites = await conn_a.fetch("SELECT id, timezone FROM sites ORDER BY created_at")

        if not sites:
            logger.warning("No sites found in System A")
            return

        logger.info(f"Found {len(sites)} sites to sync")

        # Sync to System B
        synced = 0
        failed = 0

        for site in sites:
            try:
                await conn_b.execute(
                    """
                    INSERT INTO sites_metadata (id, timezone, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET timezone = EXCLUDED.timezone,
                        updated_at = NOW()
                    """,
                    site['id'],
                    site['timezone']
                )
                synced += 1

                if synced % 10 == 0:
                    logger.info(f"Progress: {synced}/{len(sites)} sites synced")

            except Exception as e:
                logger.error(f"Failed to sync site {site['id']}: {e}")
                failed += 1

        # Summary
        logger.info("="*60)
        logger.info("Sync Summary:")
        logger.info(f"  Total sites: {len(sites)}")
        logger.info(f"  ✓ Synced: {synced}")
        if failed > 0:
            logger.warning(f"  ✗ Failed: {failed}")
        logger.info("="*60)

        # Verify counts
        system_a_count = await conn_a.fetchval("SELECT COUNT(*) FROM sites")
        system_b_count = await conn_b.fetchval("SELECT COUNT(*) FROM sites_metadata")

        logger.info("\nVerification:")
        logger.info(f"  System A sites: {system_a_count}")
        logger.info(f"  System B sites_metadata: {system_b_count}")

        if system_a_count == system_b_count:
            logger.info("✓ Counts match - sync successful!")
        else:
            logger.warning(f"⚠️  Count mismatch: {system_a_count} vs {system_b_count}")

        # Show sample data
        logger.info("\nSample sites_metadata (first 5):")
        samples = await conn_b.fetch("""
            SELECT id, timezone, updated_at
            FROM sites_metadata
            ORDER BY updated_at DESC
            LIMIT 5
        """)

        for sample in samples:
            logger.info(f"  - {sample['id']} | {sample['timezone']} | {sample['updated_at']}")

    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)

    finally:
        if conn_a:
            await conn_a.close()
        if conn_b:
            await conn_b.close()


if __name__ == "__main__":
    try:
        asyncio.run(sync_sites())
        logger.info("\n✓ Sync complete!")
    except KeyboardInterrupt:
        logger.info("\nSync interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
