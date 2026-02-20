"""
Admin portal - Electricity provider management endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..dependencies import (
    get_unit_of_work,
    require_ops_admin,
    require_portal_admin,
)
from ..schemas.admin_schemas import (
    ProviderCreate,
    ProviderListResponse,
    ProviderResponse,
    ProviderUpdate,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.admin import AdminAuditLog, ElectricityProvider, ProviderStatus
from ...domain.entities.user import User

router = APIRouter(prefix="/admin/providers", tags=["Admin - Providers"])


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _provider_to_response(p: ElectricityProvider) -> ProviderResponse:
    return ProviderResponse(
        id=p.id,
        name=p.name,
        short_name=p.short_name,
        region=p.region,
        status=p.status,
        tariff_count=p.tariff_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=ProviderListResponse)
async def list_providers(
    status_filter: Optional[ProviderStatus] = Query(None, alias="status"),
    region: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_portal_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProviderListResponse:
    """List all electricity providers. Accessible by all portal admin roles."""
    providers = await uow.electricity_providers.list_all(
        status=status_filter, region=region, limit=limit, offset=offset
    )
    total = await uow.electricity_providers.count(status=status_filter, region=region)
    return ProviderListResponse(
        items=[_provider_to_response(p) for p in providers],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: UUID,
    current_user: User = Depends(require_portal_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProviderResponse:
    """Get a single electricity provider by ID."""
    provider = await uow.electricity_providers.get_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return _provider_to_response(provider)


@router.post("", response_model=ProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    request: Request,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProviderResponse:
    """Create a new electricity provider. Requires ops_admin or super_admin."""
    provider = ElectricityProvider.create(
        name=payload.name,
        short_name=payload.short_name,
        region=payload.region,
        created_by=current_user.id,
    )
    saved = await uow.electricity_providers.add(provider)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="create",
        resource_type="provider",
        resource_id=str(saved.id),
        new_values={"name": saved.name, "short_name": saved.short_name, "region": saved.region},
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()

    return _provider_to_response(saved)


@router.put("/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: UUID,
    payload: ProviderUpdate,
    request: Request,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProviderResponse:
    """Update an electricity provider. Requires ops_admin or super_admin."""
    provider = await uow.electricity_providers.get_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    old_values = {
        "name": provider.name,
        "short_name": provider.short_name,
        "region": provider.region,
        "status": provider.status.value,
    }

    name = payload.name if payload.name is not None else provider.name
    short_name = payload.short_name if payload.short_name is not None else provider.short_name
    region = payload.region if payload.region is not None else provider.region
    provider.update(name=name, short_name=short_name, region=region)

    if payload.status is not None:
        if payload.status == ProviderStatus.ACTIVE:
            provider.activate()
        else:
            provider.deactivate()

    updated = await uow.electricity_providers.update(provider)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="update",
        resource_type="provider",
        resource_id=str(provider_id),
        old_values=old_values,
        new_values={
            "name": updated.name, "short_name": updated.short_name,
            "region": updated.region, "status": updated.status.value,
        },
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()

    return _provider_to_response(updated)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: UUID,
    request: Request,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> None:
    """Delete a provider and its tariffs (CASCADE). Requires ops_admin or super_admin."""
    provider = await uow.electricity_providers.get_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    old_values = {"name": provider.name, "short_name": provider.short_name}
    await uow.electricity_providers.delete(provider_id)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="delete",
        resource_type="provider",
        resource_id=str(provider_id),
        old_values=old_values,
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()
