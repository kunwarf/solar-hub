"""
Admin portal - Provider Billing Schedule management endpoints.

Admins define billing rates (prices, TOU windows) per DISCO + tariff category.
When a user's site has matching disco_provider + tariff_category, the billing engine
automatically applies these admin-defined rates instead of per-site configuration.
"""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_unit_of_work,
    require_ops_admin,
)
from ..schemas.admin_schemas import (
    BillingScheduleCreate,
    BillingScheduleListResponse,
    BillingScheduleResponse,
    BillingScheduleUpdate,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.admin import BillingScheduleStatus, ProviderBillingSchedule
from ...domain.entities.user import User

router = APIRouter(prefix="/admin/billing-schedules", tags=["Admin - Billing Schedules"])


def _schedule_to_response(s: ProviderBillingSchedule) -> BillingScheduleResponse:
    return BillingScheduleResponse(
        id=s.id,
        provider_id=s.provider_id,
        tariff_category=s.tariff_category,
        price_offpeak_import=float(s.price_offpeak_import),
        price_peak_import=float(s.price_peak_import),
        price_offpeak_settlement=float(s.price_offpeak_settlement),
        price_peak_settlement=float(s.price_peak_settlement),
        fixed_charge=float(s.fixed_charge),
        tou_windows=s.tou_windows,
        default_anchor_day=s.default_anchor_day,
        currency=s.currency,
        net_metering_enabled=s.net_metering_enabled,
        status=s.status,
        effective_from=s.effective_from,
        effective_to=s.effective_to,
        description=s.description,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=BillingScheduleListResponse)
async def list_billing_schedules(
    provider_id: Optional[UUID] = Query(None),
    category: Optional[str] = Query(None),
    schedule_status: Optional[BillingScheduleStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> BillingScheduleListResponse:
    """List all provider billing schedules with optional filters."""
    schedules = await uow.provider_billing_schedules.list_all(
        provider_id=provider_id,
        category=category,
        status=schedule_status,
        limit=limit,
        offset=offset,
    )
    total = await uow.provider_billing_schedules.count(
        provider_id=provider_id,
        category=category,
        status=schedule_status,
    )
    return BillingScheduleListResponse(
        items=[_schedule_to_response(s) for s in schedules],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{schedule_id}", response_model=BillingScheduleResponse)
async def get_billing_schedule(
    schedule_id: UUID,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> BillingScheduleResponse:
    """Get a single billing schedule by ID."""
    schedule = await uow.provider_billing_schedules.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing schedule not found")
    return _schedule_to_response(schedule)


@router.post("", response_model=BillingScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_billing_schedule(
    body: BillingScheduleCreate,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> BillingScheduleResponse:
    """
    Create a new provider billing schedule.

    Only one active schedule is allowed per provider + tariff_category combination
    (enforced by the idx_pbs_active_unique partial index).
    """
    # Validate provider exists
    provider = await uow.electricity_providers.get_by_id(body.provider_id)
    if not provider:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

    # Check for existing active schedule
    if body.status == BillingScheduleStatus.ACTIVE:
        existing = await uow.provider_billing_schedules.get_active_for_provider_category(
            body.provider_id, body.tariff_category
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An active schedule already exists for this provider + category. "
                       f"Deactivate schedule {existing.id} first.",
            )

    schedule = ProviderBillingSchedule.create(
        provider_id=body.provider_id,
        tariff_category=body.tariff_category,
        price_offpeak_import=body.price_offpeak_import,
        price_peak_import=body.price_peak_import,
        price_offpeak_settlement=body.price_offpeak_settlement,
        price_peak_settlement=body.price_peak_settlement,
        fixed_charge=body.fixed_charge,
        tou_windows=body.tou_windows,
        default_anchor_day=body.default_anchor_day,
        currency=body.currency,
        net_metering_enabled=body.net_metering_enabled,
        status=body.status,
        effective_from=body.effective_from or date.today(),
        effective_to=body.effective_to,
        description=body.description,
    )
    created = await uow.provider_billing_schedules.add(schedule)
    await uow.commit()
    return _schedule_to_response(created)


@router.put("/{schedule_id}", response_model=BillingScheduleResponse)
async def update_billing_schedule(
    schedule_id: UUID,
    body: BillingScheduleUpdate,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> BillingScheduleResponse:
    """Update an existing billing schedule (partial update)."""
    schedule = await uow.provider_billing_schedules.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing schedule not found")

    # If activating, check for duplicate active schedule
    new_status = body.status if body.status is not None else schedule.status
    if new_status == BillingScheduleStatus.ACTIVE and schedule.status != BillingScheduleStatus.ACTIVE:
        existing = await uow.provider_billing_schedules.get_active_for_provider_category(
            schedule.provider_id, body.tariff_category or schedule.tariff_category
        )
        if existing and existing.id != schedule_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An active schedule already exists for this provider + category: {existing.id}",
            )

    schedule.update(
        tariff_category=body.tariff_category if body.tariff_category is not None else schedule.tariff_category,
        price_offpeak_import=body.price_offpeak_import if body.price_offpeak_import is not None else schedule.price_offpeak_import,
        price_peak_import=body.price_peak_import if body.price_peak_import is not None else schedule.price_peak_import,
        price_offpeak_settlement=body.price_offpeak_settlement if body.price_offpeak_settlement is not None else schedule.price_offpeak_settlement,
        price_peak_settlement=body.price_peak_settlement if body.price_peak_settlement is not None else schedule.price_peak_settlement,
        fixed_charge=body.fixed_charge if body.fixed_charge is not None else schedule.fixed_charge,
        tou_windows=body.tou_windows if body.tou_windows is not None else schedule.tou_windows,
        default_anchor_day=body.default_anchor_day if body.default_anchor_day is not None else schedule.default_anchor_day,
        currency=body.currency if body.currency is not None else schedule.currency,
        net_metering_enabled=body.net_metering_enabled if body.net_metering_enabled is not None else schedule.net_metering_enabled,
        status=new_status,
        effective_from=body.effective_from if body.effective_from is not None else schedule.effective_from,
        effective_to=body.effective_to if body.effective_to is not None else schedule.effective_to,
        description=body.description if body.description is not None else schedule.description,
    )

    updated = await uow.provider_billing_schedules.update(schedule)
    await uow.commit()
    return _schedule_to_response(updated)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_billing_schedule(
    schedule_id: UUID,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> None:
    """Delete a billing schedule."""
    deleted = await uow.provider_billing_schedules.delete(schedule_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing schedule not found")
    await uow.commit()
