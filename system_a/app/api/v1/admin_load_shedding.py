"""
Admin portal - Load shedding schedule management endpoints.
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
    LoadSheddingCreate,
    LoadSheddingListResponse,
    LoadSheddingResponse,
    LoadSheddingUpdate,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.admin import AdminAuditLog, LoadSheddingSchedule
from ...domain.entities.user import User

router = APIRouter(prefix="/admin/load-shedding", tags=["Admin - Load Shedding"])


def _get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _sched_to_response(s: LoadSheddingSchedule) -> LoadSheddingResponse:
    return LoadSheddingResponse(
        id=s.id,
        area_name=s.area_name,
        region=s.region,
        feeder_code=s.feeder_code,
        schedule=s.schedule,
        is_active=s.is_active,
        effective_from=s.effective_from,
        effective_to=s.effective_to,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.get("", response_model=LoadSheddingListResponse)
async def list_schedules(
    region: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_portal_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> LoadSheddingListResponse:
    """List load shedding schedules."""
    schedules = await uow.load_shedding_schedules.list_all(
        region=region, is_active=is_active, limit=limit, offset=offset
    )
    total = await uow.load_shedding_schedules.count(region=region, is_active=is_active)
    return LoadSheddingListResponse(
        items=[_sched_to_response(s) for s in schedules],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{schedule_id}", response_model=LoadSheddingResponse)
async def get_schedule(
    schedule_id: UUID,
    current_user: User = Depends(require_portal_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> LoadSheddingResponse:
    """Get a load shedding schedule by ID."""
    sched = await uow.load_shedding_schedules.get_by_id(schedule_id)
    if not sched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return _sched_to_response(sched)


@router.post("", response_model=LoadSheddingResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: LoadSheddingCreate,
    request: Request,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> LoadSheddingResponse:
    """Create a load shedding schedule. Requires ops_admin or super_admin."""
    sched = LoadSheddingSchedule.create(
        area_name=payload.area_name,
        region=payload.region,
        schedule=payload.schedule,
        feeder_code=payload.feeder_code,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    saved = await uow.load_shedding_schedules.add(sched)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="create",
        resource_type="load_shedding",
        resource_id=str(saved.id),
        new_values={"area_name": saved.area_name, "region": saved.region,
                    "feeder_code": saved.feeder_code},
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()

    return _sched_to_response(saved)


@router.put("/{schedule_id}", response_model=LoadSheddingResponse)
async def update_schedule(
    schedule_id: UUID,
    payload: LoadSheddingUpdate,
    request: Request,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> LoadSheddingResponse:
    """Update a load shedding schedule. Requires ops_admin or super_admin."""
    sched = await uow.load_shedding_schedules.get_by_id(schedule_id)
    if not sched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    old_values = {"area_name": sched.area_name, "region": sched.region,
                  "is_active": sched.is_active}

    if payload.is_active is not None:
        if payload.is_active:
            sched.activate()
        else:
            sched.deactivate()

    sched.update(
        area_name=payload.area_name if payload.area_name is not None else sched.area_name,
        region=payload.region if payload.region is not None else sched.region,
        schedule=payload.schedule if payload.schedule is not None else sched.schedule,
        feeder_code=payload.feeder_code if payload.feeder_code is not None else sched.feeder_code,
        effective_from=payload.effective_from if payload.effective_from is not None else sched.effective_from,
        effective_to=payload.effective_to if payload.effective_to is not None else sched.effective_to,
    )

    updated = await uow.load_shedding_schedules.update(sched)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="update",
        resource_type="load_shedding",
        resource_id=str(schedule_id),
        old_values=old_values,
        new_values={"area_name": updated.area_name, "region": updated.region,
                    "is_active": updated.is_active},
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()

    return _sched_to_response(updated)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    request: Request,
    current_user: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> None:
    """Delete a load shedding schedule. Requires ops_admin or super_admin."""
    sched = await uow.load_shedding_schedules.get_by_id(schedule_id)
    if not sched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    old_values = {"area_name": sched.area_name, "region": sched.region}
    await uow.load_shedding_schedules.delete(schedule_id)

    audit = AdminAuditLog.record(
        admin_user_id=current_user.id,
        admin_email=str(current_user.email),
        action="delete",
        resource_type="load_shedding",
        resource_id=str(schedule_id),
        old_values=old_values,
        ip_address=_get_client_ip(request),
    )
    await uow.admin_audit_logs.add(audit)
    await uow.commit()
