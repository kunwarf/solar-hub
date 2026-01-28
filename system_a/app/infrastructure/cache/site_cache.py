"""
Site cache service for System A.

Caches site/user/device relationships in Redis to avoid database queries
on every dashboard refresh. Cache is invalidated when entities change.
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from .redis_cache import RedisManager

logger = logging.getLogger(__name__)


@dataclass
class CachedSiteInfo:
    """Cached site information."""
    site_id: UUID
    organization_id: UUID
    site_name: str
    device_serials: List[str]
    import_rate_pkr: float = 30.0  # Default PKR/kWh grid import rate
    export_rate_pkr: float = 15.0  # Default PKR/kWh grid export rate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": str(self.site_id),
            "organization_id": str(self.organization_id),
            "site_name": self.site_name,
            "device_serials": self.device_serials,
            "import_rate_pkr": self.import_rate_pkr,
            "export_rate_pkr": self.export_rate_pkr,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CachedSiteInfo":
        return cls(
            site_id=UUID(data["site_id"]),
            organization_id=UUID(data["organization_id"]),
            site_name=data["site_name"],
            device_serials=data.get("device_serials", []),
            import_rate_pkr=data.get("import_rate_pkr", 30.0),
            export_rate_pkr=data.get("export_rate_pkr", 15.0),
        )


class SiteCacheService:
    """
    Caches site-related data in Redis for fast dashboard access.

    Key patterns:
    - site:{site_id}:info - Site metadata (org_id, name, device serials)
    - user:{user_id}:default_site - User's default site ID
    - user:{user_id}:sites - List of site IDs accessible to user

    TTL: 5 minutes (300 seconds) - short enough to pick up changes quickly
    """

    KEY_SITE_INFO = "site:{site_id}:info"
    KEY_USER_DEFAULT_SITE = "user:{user_id}:default_site"
    KEY_USER_SITES = "user:{user_id}:sites"

    CACHE_TTL = 300  # 5 minutes

    async def get_site_info(
        self,
        site_id: UUID,
    ) -> Optional[CachedSiteInfo]:
        """
        Get cached site info including device serials.

        Args:
            site_id: Site UUID.

        Returns:
            CachedSiteInfo or None if not cached.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_SITE_INFO.format(site_id=str(site_id))
            value = await client.get(key)

            if value:
                data = json.loads(value)
                return CachedSiteInfo.from_dict(data)
            return None

        except Exception as e:
            logger.error(f"Failed to get site info from cache: {e}")
            return None

    async def set_site_info(
        self,
        site_info: CachedSiteInfo,
    ) -> bool:
        """
        Cache site info.

        Args:
            site_info: Site information to cache.

        Returns:
            True if cached successfully.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_SITE_INFO.format(site_id=str(site_info.site_id))
            value = json.dumps(site_info.to_dict())
            await client.setex(key, self.CACHE_TTL, value)
            return True

        except Exception as e:
            logger.error(f"Failed to cache site info: {e}")
            return False

    async def get_user_default_site(
        self,
        user_id: UUID,
    ) -> Optional[UUID]:
        """
        Get user's default site ID from cache.

        Args:
            user_id: User UUID.

        Returns:
            Site UUID or None if not cached.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_USER_DEFAULT_SITE.format(user_id=str(user_id))
            value = await client.get(key)

            if value:
                return UUID(value)
            return None

        except Exception as e:
            logger.error(f"Failed to get user default site from cache: {e}")
            return None

    async def set_user_default_site(
        self,
        user_id: UUID,
        site_id: UUID,
    ) -> bool:
        """
        Cache user's default site ID.

        Args:
            user_id: User UUID.
            site_id: Default site UUID.

        Returns:
            True if cached successfully.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_USER_DEFAULT_SITE.format(user_id=str(user_id))
            await client.setex(key, self.CACHE_TTL, str(site_id))
            return True

        except Exception as e:
            logger.error(f"Failed to cache user default site: {e}")
            return False

    async def get_user_sites(
        self,
        user_id: UUID,
    ) -> Optional[List[UUID]]:
        """
        Get list of site IDs accessible to user from cache.

        Args:
            user_id: User UUID.

        Returns:
            List of site UUIDs or None if not cached.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_USER_SITES.format(user_id=str(user_id))
            value = await client.get(key)

            if value:
                site_ids = json.loads(value)
                return [UUID(sid) for sid in site_ids]
            return None

        except Exception as e:
            logger.error(f"Failed to get user sites from cache: {e}")
            return None

    async def set_user_sites(
        self,
        user_id: UUID,
        site_ids: List[UUID],
    ) -> bool:
        """
        Cache list of site IDs accessible to user.

        Args:
            user_id: User UUID.
            site_ids: List of site UUIDs.

        Returns:
            True if cached successfully.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_USER_SITES.format(user_id=str(user_id))
            value = json.dumps([str(sid) for sid in site_ids])
            await client.setex(key, self.CACHE_TTL, value)
            return True

        except Exception as e:
            logger.error(f"Failed to cache user sites: {e}")
            return False

    async def invalidate_site(
        self,
        site_id: UUID,
    ) -> bool:
        """
        Invalidate site cache when site is modified.

        Args:
            site_id: Site UUID to invalidate.

        Returns:
            True if invalidated successfully.
        """
        try:
            client = await RedisManager.get_client()
            key = self.KEY_SITE_INFO.format(site_id=str(site_id))
            await client.delete(key)
            return True

        except Exception as e:
            logger.error(f"Failed to invalidate site cache: {e}")
            return False

    async def invalidate_user(
        self,
        user_id: UUID,
    ) -> bool:
        """
        Invalidate user's site cache when user/org membership changes.

        Args:
            user_id: User UUID to invalidate.

        Returns:
            True if invalidated successfully.
        """
        try:
            client = await RedisManager.get_client()
            pipeline = client.pipeline()
            pipeline.delete(self.KEY_USER_DEFAULT_SITE.format(user_id=str(user_id)))
            pipeline.delete(self.KEY_USER_SITES.format(user_id=str(user_id)))
            await pipeline.execute()
            return True

        except Exception as e:
            logger.error(f"Failed to invalidate user cache: {e}")
            return False


# Singleton instance
site_cache = SiteCacheService()
