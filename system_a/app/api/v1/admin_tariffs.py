"""
Admin portal - Electricity tariff management endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..dependencies import (
    get_unit_of_work,
    require_billing_or_ops_admin,
    require_portal_admin,
)
from ..schemas.admin_schemas import (
    TariffCreate,
    TariffListResponse,
    TariffResponse,
    TariffUpdate,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.admin import (
    AdminAuditLog,
    ElectricityTariff,
    TariffStatus,
)
from ...domain.entities.user import User

router = APIRouter(prefix="/admin/tariffs", tags=["Admin - Tariffs"])


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _tariff_to_response(t: ElectricityTariff) -> TariffResponse:
    return TariffResponse(
        id=t.id,
        provider_id=t.provider_id,
        name=t.name,
        category=t.category,
        type=t.type,
        rates=t.rates,
        fixed_charges=t.fixed_charges,
        effective_from=t.effective_from,
        effective_to=t.effective_to,
        status=t.status,
        description=t.description,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("", response_model=TariffListResponse)
async def list_tariffs(
    provider_id: Optional[UUID] = Query(None),
    status_filter: Optional[TariffStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_portal_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> TariffListResponse:
    """List tariffs, optionally filtered by provider or status."""
    tariffs = await uow.electricity_tariffs.list_all(
        provider_id=provider_id, status=status_filter, limit=limit, offset=offset
    )
    # Use a simple count approach
    total = len(tariffs)  # For pagination accuracy, re-count
    if limit < 200 or offset > 0:
        # Do an accurate count query when paginating
        all_tariffs = await uow.electricity_tariffs.list_all(
            provider_id=provider_id, status=status_filter, limit=10000, offset=0
        )
        total = len(all_tariffs)
    return TariffListResponse(
        items=[_tariff_to_response(t) for t in tariffs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{tariff_id}", response_model=TariffResponse)
async def get_tariff(
    tariff_id: UUID,
    current_user: User = Depends(require_portal_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> TariffResponse:
    """Get a single tariff by ID."""
    tariff = await uow.electricity_tariffs.get_by_id(tariff_id)
    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")
    return _tariff_to_response(tariff)


@router.post("", response_model=TariffResponse, status_code=status.HTTP_201_CREATED)
async def create_tariff(
    payload: TariffCreate,
    request: Request,
    current_user: User = Depends(require_billing_or_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> TariffResponse:
    """Create a new tariff. Requires billing_admin, ops_admin, or super_admin."""
    # Verify provider exists
    provider = await uow.electricity_providers.get_by_id(payload.provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {payload.provider_id} not found",
        )

    tariff = ElectricityTariff.create(
        provider_id=payload.provider_id,
        name=payload.name,
        category=payload.category,
        type=payload.type,
        rates=payload.rates,
        fixed_charges=payload.fixed_charges,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        description=payload.description,
    )
    saved = await uow.electricity_tariffs.add(tariff)

    # Update denormalised count on provider
    await uow.electricity_providers.update_tariff_count(payload.provider_id)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="create",
        resource_type="tariff",
        resource_id=str(saved.id),
        new_values={"name": saved.name, "category": saved.category.value,
                    "type": saved.type.value, "provider_id": str(saved.provider_id)},
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()

    return _tariff_to_response(saved)


@router.put("/{tariff_id}", response_model=TariffResponse)
async def update_tariff(
    tariff_id: UUID,
    payload: TariffUpdate,
    request: Request,
    current_user: User = Depends(require_billing_or_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> TariffResponse:
    """Update a tariff. Requires billing_admin, ops_admin, or super_admin."""
    tariff = await uow.electricity_tariffs.get_by_id(tariff_id)
    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")

    old_values = {
        "name": tariff.name, "category": tariff.category.value,
        "status": tariff.status.value,
    }

    tariff.update(
        name=payload.name if payload.name is not None else tariff.name,
        category=payload.category if payload.category is not None else tariff.category,
        type=payload.type if payload.type is not None else tariff.type,
        rates=payload.rates if payload.rates is not None else tariff.rates,
        fixed_charges=payload.fixed_charges if payload.fixed_charges is not None else tariff.fixed_charges,
        effective_from=payload.effective_from if payload.effective_from is not None else tariff.effective_from,
        effective_to=payload.effective_to if payload.effective_to is not None else tariff.effective_to,
        description=payload.description if payload.description is not None else tariff.description,
    )
    if payload.status is not None:
        if payload.status == TariffStatus.ACTIVE:
            tariff.activate()
        else:
            tariff.deactivate()

    updated = await uow.electricity_tariffs.update(tariff)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="update",
        resource_type="tariff",
        resource_id=str(tariff_id),
        old_values=old_values,
        new_values={"name": updated.name, "category": updated.category.value,
                    "status": updated.status.value},
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()

    return _tariff_to_response(updated)


@router.delete("/{tariff_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tariff(
    tariff_id: UUID,
    request: Request,
    current_user: User = Depends(require_billing_or_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> None:
    """Delete a tariff. Requires billing_admin, ops_admin, or super_admin."""
    tariff = await uow.electricity_tariffs.get_by_id(tariff_id)
    if not tariff:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff not found")

    provider_id = tariff.provider_id
    old_values = {"name": tariff.name, "provider_id": str(provider_id)}

    await uow.electricity_tariffs.delete(tariff_id)
    await uow.electricity_providers.update_tariff_count(provider_id)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="delete",
        resource_type="tariff",
        resource_id=str(tariff_id),
        old_values=old_values,
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()
