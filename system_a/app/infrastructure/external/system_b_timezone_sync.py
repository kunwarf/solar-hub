"""
Service for syncing site timezone metadata to System B (TimescaleDB).

This ensures the timezone-aware continuous aggregates in System B have
access to site timezone information.
"""
import logging
from typing import Optional
from uuid import UUID
import os

import asyncpg

logger = logging.getLogger(__name__)


class SystemBTimezoneSyncService:
    """
    Service to sync site timezone information to System B's sites_metadata table.

    This is required because System B's timezone-aware continuous aggregates
    need to join telemetry_raw with site timezone information, but the sites
    table lives in System A.
    """

    def __init__(self):
        """Initialize the sync service."""
        self._pool: Optional[asyncpg.Pool] = None
        self._enabled = os.getenv("USE_TIMESCALEDB", "false").lower() == "true"

    async def _get_connection_string(self) -> str:
        """Build System B connection string from environment."""
        host = os.getenv("TIMESCALE_HOST", "127.0.0.1")
        port = os.getenv("TIMESCALE_PORT", "5432")
        user = os.getenv("TIMESCALE_USER", "solarhub_telemetry")
        password = os.getenv("TIMESCALE_PASSWORD", "")
        database = os.getenv("TIMESCALE_DATABASE", "solar_hub_telemetry")

        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool to System B."""
        if self._pool is None:
            conn_string = await self._get_connection_string()
            self._pool = await asyncpg.create_pool(
                conn_string,
                min_size=1,
                max_size=5,
                command_timeout=10,
            )
        return self._pool

    async def sync_site_timezone(self, site_id: UUID, timezone: str) -> bool:
        """
        Sync site timezone to System B's sites_metadata table.

        Args:
            site_id: Site UUID
            timezone: Timezone string (e.g., "Asia/Karachi")

        Returns:
            True if sync succeeded, False otherwise
        """
        if not self._enabled:
            logger.debug("TimescaleDB sync disabled (USE_TIMESCALEDB=false)")
            return True  # Return True to not break the flow

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                # Upsert into sites_metadata
                await conn.execute(
                    """
                    INSERT INTO sites_metadata (id, timezone, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (id) DO UPDATE
                    SET timezone = EXCLUDED.timezone,
                        updated_at = NOW()
                    """,
                    site_id,
                    timezone,
                )

            logger.info(f"Synced site timezone to System B: site_id={site_id}, timezone={timezone}")
            return True

        except Exception as e:
            logger.error(f"Failed to sync site timezone to System B: {e}", exc_info=True)
            # Don't fail the main operation if sync fails
            return False

    async def sync_site_deletion(self, site_id: UUID) -> bool:
        """
        Remove site from System B's sites_metadata table.

        Args:
            site_id: Site UUID to remove

        Returns:
            True if sync succeeded, False otherwise
        """
        if not self._enabled:
            return True

        try:
            pool = await self._get_pool()

            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM sites_metadata WHERE id = $1",
                    site_id,
                )

            logger.info(f"Removed site from System B: site_id={site_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove site from System B: {e}", exc_info=True)
            return False

    async def bulk_sync_sites(self, sites: list[tuple[UUID, str]]) -> dict:
        """
        Bulk sync multiple sites to System B.

        Args:
            sites: List of (site_id, timezone) tuples

        Returns:
            Dictionary with sync statistics
        """
        if not self._enabled:
            return {"synced": 0, "failed": 0, "total": 0}

        synced = 0
        failed = 0

        for site_id, timezone in sites:
            if await self.sync_site_timezone(site_id, timezone):
                synced += 1
            else:
                failed += 1

        logger.info(f"Bulk sync complete: {synced} synced, {failed} failed out of {len(sites)} total")

        return {
            "synced": synced,
            "failed": failed,
            "total": len(sites),
        }

    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None


# Global instance
_sync_service: Optional[SystemBTimezoneSyncService] = None


def get_timezone_sync_service() -> SystemBTimezoneSyncService:
    """Get or create the global timezone sync service instance."""
    global _sync_service
    if _sync_service is None:
        _sync_service = SystemBTimezoneSyncService()
    return _sync_service
