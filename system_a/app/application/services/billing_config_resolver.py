"""
Billing Config Resolver.

Resolves effective billing configuration for a site:
  1. Checks if site has disco_provider + tariff_category set
  2. Looks up matching active ProviderBillingSchedule
  3. If found: uses admin-defined rates + site's anchor_day
  4. If not found: falls back to per-site billing_config

This allows admins to manage rates centrally per DISCO + tariff category,
while users only control their billing anchor day.
"""
import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from ..interfaces.unit_of_work import UnitOfWork
from ...domain.entities.net_metering import (
    BillingConfig,
    BillingPrices,
    TouConfig,
    FixedProrationMode,
)
from ...infrastructure.database.repositories.net_metering_repository import (
    SQLAlchemyNetMeteringRepository,
)
from ...infrastructure.database.repositories.site_repository import (
    SQLAlchemySiteRepository,
)
from ...infrastructure.database.repositories.admin_repository import (
    SQLAlchemyElectricityProviderRepository,
    SQLAlchemyProviderBillingScheduleRepository,
)

logger = logging.getLogger(__name__)


class BillingConfigResolver:
    """
    Resolves effective billing config: provider schedule → per-site fallback.

    Usage:
        resolver = BillingConfigResolver(nm_repo, site_repo, provider_repo, schedule_repo)
        config = await resolver.resolve(site_id)
        # config is BillingConfig or None if neither source exists
    """

    def __init__(
        self,
        nm_repo: SQLAlchemyNetMeteringRepository,
        site_repo: SQLAlchemySiteRepository,
        provider_repo: SQLAlchemyElectricityProviderRepository,
        schedule_repo: SQLAlchemyProviderBillingScheduleRepository,
    ) -> None:
        self._nm_repo = nm_repo
        self._site_repo = site_repo
        self._provider_repo = provider_repo
        self._schedule_repo = schedule_repo

    async def resolve(self, site_id: UUID) -> Optional[BillingConfig]:
        """
        Resolve effective billing configuration for a site.

        Priority:
          1. Admin-defined ProviderBillingSchedule (if site has disco_provider + tariff_category)
          2. Per-site billing_config (legacy / fallback)

        Returns:
            BillingConfig populated with effective rates, or None if nothing configured.
        """
        # Always get per-site config – needed for anchor_day and as fallback
        site_config = await self._nm_repo.get_billing_config_by_site(site_id)

        # Get site to read disco_provider + tariff_category
        site = await self._site_repo.get_by_id(site_id)
        if not site or not site.configuration:
            return site_config

        disco = site.configuration.disco_provider   # Optional[DiscoProvider enum]
        category = site.configuration.tariff_category  # Optional[str]

        if not disco or not category:
            return site_config

        # Look up provider by short_name (case-insensitive)
        providers = await self._provider_repo.list_all(limit=100)
        provider = next(
            (p for p in providers if p.short_name.upper() == disco.value.upper()),
            None,
        )
        if not provider:
            logger.debug(
                "[BillingResolver] No provider found for disco=%s site=%s",
                disco.value, site_id,
            )
            return site_config

        # Look up active schedule for provider + category (case-insensitive)
        schedule = await self._schedule_repo.get_active_for_provider_category(
            provider.id, category
        )
        if not schedule:
            logger.debug(
                "[BillingResolver] No active schedule for provider=%s category=%s site=%s",
                provider.short_name, category, site_id,
            )
            return site_config

        logger.debug(
            "[BillingResolver] Using provider schedule %s for site %s (provider=%s cat=%s)",
            schedule.id, site_id, provider.short_name, category,
        )

        # Build BillingConfig from schedule, using site's anchor_day if available
        anchor_day = site_config.anchor_day if site_config else schedule.default_anchor_day
        fixed_proration = (
            site_config.fixed_proration_mode
            if site_config
            else FixedProrationMode.NONE
        )

        tou_config = TouConfig.from_dict(schedule.tou_windows)
        prices = BillingPrices(
            price_offpeak_import=Decimal(str(schedule.price_offpeak_import)),
            price_peak_import=Decimal(str(schedule.price_peak_import)),
            price_offpeak_settlement=Decimal(str(schedule.price_offpeak_settlement)),
            price_peak_settlement=Decimal(str(schedule.price_peak_settlement)),
            fixed_charge_per_billing_month=Decimal(str(schedule.fixed_charge)),
        )

        return BillingConfig(
            site_id=site_id,
            anchor_day=anchor_day,
            tou_config=tou_config,
            prices=prices,
            net_metering_enabled=schedule.net_metering_enabled,
            fixed_proration_mode=fixed_proration,
        )

    async def resolve_with_source(self, site_id: UUID):
        """
        Resolve billing config and return alongside its source.

        Returns:
            Tuple of (BillingConfig | None, source: str)
            source is "provider_schedule" | "per_site" | "none"
        """
        site_config = await self._nm_repo.get_billing_config_by_site(site_id)

        site = await self._site_repo.get_by_id(site_id)
        if not site or not site.configuration:
            return site_config, "per_site" if site_config else "none"

        disco = site.configuration.disco_provider
        category = site.configuration.tariff_category

        if not disco or not category:
            return site_config, "per_site" if site_config else "none"

        providers = await self._provider_repo.list_all(limit=100)
        provider = next(
            (p for p in providers if p.short_name.upper() == disco.value.upper()),
            None,
        )
        if not provider:
            return site_config, "per_site" if site_config else "none"

        schedule = await self._schedule_repo.get_active_for_provider_category(
            provider.id, category
        )
        if not schedule:
            return site_config, "per_site" if site_config else "none"

        # Build resolved config from provider schedule
        anchor_day = site_config.anchor_day if site_config else schedule.default_anchor_day
        fixed_proration = (
            site_config.fixed_proration_mode if site_config else FixedProrationMode.NONE
        )
        tou_config = TouConfig.from_dict(schedule.tou_windows)
        prices = BillingPrices(
            price_offpeak_import=Decimal(str(schedule.price_offpeak_import)),
            price_peak_import=Decimal(str(schedule.price_peak_import)),
            price_offpeak_settlement=Decimal(str(schedule.price_offpeak_settlement)),
            price_peak_settlement=Decimal(str(schedule.price_peak_settlement)),
            fixed_charge_per_billing_month=Decimal(str(schedule.fixed_charge)),
        )
        resolved = BillingConfig(
            site_id=site_id,
            anchor_day=anchor_day,
            tou_config=tou_config,
            prices=prices,
            net_metering_enabled=schedule.net_metering_enabled,
            fixed_proration_mode=fixed_proration,
        )
        return resolved, "provider_schedule"
