"""
Command API endpoints for System B.

Handles device command creation, execution, and status.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db_session, get_command_service
from ..schemas import (
    CommandCreateRequest,
    CommandResponse,
    CommandListResponse,
    CommandResultRequest,
    CommandStatsResponse,
)
from ...application.services import CommandService
from ...infrastructure.database.repositories import CommandRepository, EventRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commands", tags=["Commands"])


@router.post(
    "/",
    response_model=CommandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a command",
    description="Create a new command for a device.",
)
async def create_command(
    request: CommandCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CommandResponse:
    """
    Create a new device command.
    """
    command_repo = CommandRepository(session)
    event_repo = EventRepository(session)
    service = CommandService(command_repo, event_repo)

    try:
        command = await service.create_command(
            device_id=request.device_id,
            site_id=request.site_id,
            command_type=request.command_type,
            command_params=request.command_params,
            scheduled_at=request.scheduled_at,
            expires_in_minutes=request.expires_in_minutes,
            priority=request.priority,
        )

        return CommandResponse(
            id=command.id,
            device_id=command.device_id,
            site_id=command.site_id,
            command_type=command.command_type,
            command_params=command.command_params,
            status=command.status,
            scheduled_at=command.scheduled_at,
            sent_at=command.sent_at,
            acknowledged_at=command.acknowledged_at,
            completed_at=command.completed_at,
            expires_at=command.expires_at,
            result=command.result,
            error_message=command.error_message,
            retry_count=command.retry_count,
            priority=command.priority,
            created_at=command.created_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/{command_id}",
    response_model=CommandResponse,
    summary="Get command by ID",
    description="Get command details by ID.",
)
async def get_command(
    command_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CommandResponse:
    """
    Get command details.
    """
    command_repo = CommandRepository(session)
    command = await command_repo.get_by_id(command_id)

    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    return CommandResponse(
        id=command.id,
        device_id=command.device_id,
        site_id=command.site_id,
        command_type=command.command_type,
        command_params=command.command_params,
        status=command.status,
        scheduled_at=command.scheduled_at,
        sent_at=command.sent_at,
        acknowledged_at=command.acknowledged_at,
        completed_at=command.completed_at,
        expires_at=command.expires_at,
        result=command.result,
        error_message=command.error_message,
        retry_count=command.retry_count,
        priority=command.priority,
        created_at=command.created_at,
    )


@router.get(
    "/device/{device_id}",
    response_model=CommandListResponse,
    summary="Get device commands",
    description="Get commands for a device.",
)
async def get_device_commands(
    device_id: UUID,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> CommandListResponse:
    """
    Get commands for a device.
    """
    command_repo = CommandRepository(session)

    commands = await command_repo.get_by_device(
        device_id=device_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    total = await command_repo.count_by_device(device_id, status=status_filter)

    return CommandListResponse(
        commands=[
            CommandResponse(
                id=c.id,
                device_id=c.device_id,
                site_id=c.site_id,
                command_type=c.command_type,
                command_params=c.command_params,
                status=c.status,
                scheduled_at=c.scheduled_at,
                sent_at=c.sent_at,
                acknowledged_at=c.acknowledged_at,
                completed_at=c.completed_at,
                expires_at=c.expires_at,
                result=c.result,
                error_message=c.error_message,
                retry_count=c.retry_count,
                priority=c.priority,
                created_at=c.created_at,
            )
            for c in commands
        ],
        total=total,
    )


@router.get(
    "/site/{site_id}",
    response_model=CommandListResponse,
    summary="Get site commands",
    description="Get commands for all devices at a site.",
)
async def get_site_commands(
    site_id: UUID,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> CommandListResponse:
    """
    Get commands for a site.
    """
    command_repo = CommandRepository(session)

    commands = await command_repo.get_by_site(
        site_id=site_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    total = await command_repo.count_by_site(site_id, status=status_filter)

    return CommandListResponse(
        commands=[
            CommandResponse(
                id=c.id,
                device_id=c.device_id,
                site_id=c.site_id,
                command_type=c.command_type,
                command_params=c.command_params,
                status=c.status,
                scheduled_at=c.scheduled_at,
                sent_at=c.sent_at,
                acknowledged_at=c.acknowledged_at,
                completed_at=c.completed_at,
                expires_at=c.expires_at,
                result=c.result,
                error_message=c.error_message,
                retry_count=c.retry_count,
                priority=c.priority,
                created_at=c.created_at,
            )
            for c in commands
        ],
        total=total,
    )


@router.get(
    "/pending/{device_id}",
    response_model=Optional[CommandResponse],
    summary="Claim pending command",
    description="Claim and return the next pending command for a device.",
)
async def claim_pending_command(
    device_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> Optional[CommandResponse]:
    """
    Claim the next pending command for a device.

    This atomically claims the command so no other process can get it.
    """
    command_repo = CommandRepository(session)

    command = await command_repo.claim_pending_command(device_id)

    if not command:
        return None

    return CommandResponse(
        id=command.id,
        device_id=command.device_id,
        site_id=command.site_id,
        command_type=command.command_type,
        command_params=command.command_params,
        status=command.status,
        scheduled_at=command.scheduled_at,
        sent_at=command.sent_at,
        acknowledged_at=command.acknowledged_at,
        completed_at=command.completed_at,
        expires_at=command.expires_at,
        result=command.result,
        error_message=command.error_message,
        retry_count=command.retry_count,
        priority=command.priority,
        created_at=command.created_at,
    )


@router.post(
    "/{command_id}/acknowledge",
    response_model=CommandResponse,
    summary="Acknowledge command",
    description="Mark a command as acknowledged by the device.",
)
async def acknowledge_command(
    command_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CommandResponse:
    """
    Mark command as acknowledged.
    """
    command_repo = CommandRepository(session)
    event_repo = EventRepository(session)
    service = CommandService(command_repo, event_repo)

    command = await service.acknowledge_command(command_id)

    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    return CommandResponse(
        id=command.id,
        device_id=command.device_id,
        site_id=command.site_id,
        command_type=command.command_type,
        command_params=command.command_params,
        status=command.status,
        scheduled_at=command.scheduled_at,
        sent_at=command.sent_at,
        acknowledged_at=command.acknowledged_at,
        completed_at=command.completed_at,
        expires_at=command.expires_at,
        result=command.result,
        error_message=command.error_message,
        retry_count=command.retry_count,
        priority=command.priority,
        created_at=command.created_at,
    )


@router.post(
    "/{command_id}/result",
    response_model=CommandResponse,
    summary="Report command result",
    description="Report the result of command execution.",
)
async def report_command_result(
    command_id: UUID,
    request: CommandResultRequest,
    session: AsyncSession = Depends(get_db_session),
) -> CommandResponse:
    """
    Report command execution result.
    """
    command_repo = CommandRepository(session)
    event_repo = EventRepository(session)
    service = CommandService(command_repo, event_repo)

    if request.success:
        command = await service.complete_command(
            command_id=command_id,
            result=request.data,
        )
    else:
        command = await service.fail_command(
            command_id=command_id,
            error_message=request.error_message,
            error_code=request.error_code,
        )

    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    return CommandResponse(
        id=command.id,
        device_id=command.device_id,
        site_id=command.site_id,
        command_type=command.command_type,
        command_params=command.command_params,
        status=command.status,
        scheduled_at=command.scheduled_at,
        sent_at=command.sent_at,
        acknowledged_at=command.acknowledged_at,
        completed_at=command.completed_at,
        expires_at=command.expires_at,
        result=command.result,
        error_message=command.error_message,
        retry_count=command.retry_count,
        priority=command.priority,
        created_at=command.created_at,
    )


@router.post(
    "/{command_id}/retry",
    response_model=CommandResponse,
    summary="Retry command",
    description="Retry a failed command.",
)
async def retry_command(
    command_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CommandResponse:
    """
    Retry a failed command.
    """
    command_repo = CommandRepository(session)

    command = await command_repo.get_by_id(command_id)
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    if command.status not in ("failed", "expired"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry command with status: {command.status}",
        )

    command = await command_repo.retry_command(command_id)

    return CommandResponse(
        id=command.id,
        device_id=command.device_id,
        site_id=command.site_id,
        command_type=command.command_type,
        command_params=command.command_params,
        status=command.status,
        scheduled_at=command.scheduled_at,
        sent_at=command.sent_at,
        acknowledged_at=command.acknowledged_at,
        completed_at=command.completed_at,
        expires_at=command.expires_at,
        result=command.result,
        error_message=command.error_message,
        retry_count=command.retry_count,
        priority=command.priority,
        created_at=command.created_at,
    )


@router.post(
    "/{command_id}/cancel",
    response_model=CommandResponse,
    summary="Cancel command",
    description="Cancel a pending command.",
)
async def cancel_command(
    command_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> CommandResponse:
    """
    Cancel a pending command.
    """
    command_repo = CommandRepository(session)
    event_repo = EventRepository(session)
    service = CommandService(command_repo, event_repo)

    command = await command_repo.get_by_id(command_id)
    if not command:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )

    if command.status not in ("pending", "sent"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel command with status: {command.status}",
        )

    command = await service.cancel_command(command_id)

    return CommandResponse(
        id=command.id,
        device_id=command.device_id,
        site_id=command.site_id,
        command_type=command.command_type,
        command_params=command.command_params,
        status=command.status,
        scheduled_at=command.scheduled_at,
        sent_at=command.sent_at,
        acknowledged_at=command.acknowledged_at,
        completed_at=command.completed_at,
        expires_at=command.expires_at,
        result=command.result,
        error_message=command.error_message,
        retry_count=command.retry_count,
        priority=command.priority,
        created_at=command.created_at,
    )


@router.get(
    "/stats/summary",
    response_model=CommandStatsResponse,
    summary="Get command statistics",
    description="Get command statistics.",
)
async def get_command_stats(
    site_id: Optional[UUID] = None,
    hours: int = Query(default=24, ge=1, le=168),
    session: AsyncSession = Depends(get_db_session),
) -> CommandStatsResponse:
    """
    Get command statistics.
    """
    command_repo = CommandRepository(session)

    stats = await command_repo.get_stats(site_id=site_id, hours=hours)

    return CommandStatsResponse(
        by_status=stats.get("by_status", {}),
        total_commands=stats.get("total", 0),
        pending_commands=stats.get("pending", 0),
        success_rate=stats.get("success_rate", 0.0),
        active_waiters=0,  # Would need command service integration
    )


@router.post(
    "/expire-stale",
    summary="Expire stale commands",
    description="Mark expired commands as expired.",
)
async def expire_stale_commands(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Expire commands that have passed their expiration time.
    """
    command_repo = CommandRepository(session)

    count = await command_repo.expire_stale_commands()

    return {"expired_count": count}
