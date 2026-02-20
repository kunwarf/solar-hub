"""
Public read-only endpoints for electricity providers and tariffs.

These endpoints are accessible by authenticated end-users so they can
select their DISCO and tariff plan in the settings UI.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_current_active_user, get_unit_of_work
from ..schemas.admin_schemas import PublicProviderResponse, PublicTariffResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.admin import ProviderStatus, TariffStatus
from ...domain.entities.user import User

router = APIRouter(prefix="/providers", tags=["Providers (Public)"])


@router.get("", response_model=list[PublicProviderResponse])
async def list_active_providers(
    region: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> list[PublicProviderResponse]:
    """
    List active electricity providers.

    Returns only active providers. Used by end-users to select their DISCO.
    """
    providers = await uow.electricity_providers.list_all(
        status=ProviderStatus.ACTIVE,
        region=region,
        limit=200,
        offset=0,
    )
    return [
        PublicProviderResponse(
            id=p.id,
            name=p.name,
            short_name=p.short_name,
            region=p.region,
        )
        for p in providers
    ]


@router.get("/{provider_id}/tariffs", response_model=list[PublicTariffResponse])
async def list_active_tariffs_for_provider(
    provider_id: UUID,
    current_user: User = Depends(get_current_active_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> list[PublicTariffResponse]:
    """
    List active tariff plans for a provider.

    Used by end-users to select their tariff plan for billing calculations.
    """
    provider = await uow.electricity_providers.get_by_id(provider_id)
    if not provider or provider.status != ProviderStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    tariffs = await uow.electricity_tariffs.list_by_provider(
        provider_id=provider_id,
        status=TariffStatus.ACTIVE,
        limit=200,
        offset=0,
    )
    return [
        PublicTariffResponse(
            id=t.id,
            provider_id=t.provider_id,
            name=t.name,
            category=t.category,
            type=t.type,
            rates=t.rates,
            fixed_charges=t.fixed_charges,
            effective_from=t.effective_from,
            effective_to=t.effective_to,
        )
        for t in tariffs
    ]
