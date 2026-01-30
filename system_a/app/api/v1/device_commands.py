"""
Device Commands API endpoints.

Provides endpoints for sending commands to physical devices and querying their current settings.
Settings are NOT stored in database - they are read from and written to actual devices.
Frontend uses localStorage for caching.
"""
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
    get_system_b_client_instance,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User
from ...infrastructure.external.system_b_client import SystemBClient, SystemBClientError


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["Device Commands"])


# ============== Request/Response Schemas ==============


class QuerySettingsRequest(BaseModel):
    """Request to query current settings from device"""

    setting_keys: Optional[list[str]] = Field(
        None,
        description="Specific setting keys to query. If None, query all settings."
    )


class QuerySettingsResponse(BaseModel):
    """Response from device settings query"""

    command_id: str
    status: str = "pending"
    settings: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class UpdateSettingsRequest(BaseModel):
    """Request to update device settings"""

    settings: Dict[str, Any] = Field(..., description="Settings to update on device")
    apply_immediately: bool = Field(True, description="Apply settings immediately or queue for later")


class UpdateSettingsResponse(BaseModel):
    """Response from settings update command"""

    command_id: str
    status: str = "pending"
    message: str


class CommandStatusResponse(BaseModel):
    """Command execution status"""

    command_id: str
    status: str  # pending, sent, acknowledged, completed, failed, timeout
    progress: Optional[int] = None  # 0-100
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


# ============== Helper Functions ==============


async def check_device_access(
    device_id: UUID,
    user: User,
    uow: UnitOfWork,
) -> None:
    """Check if user has access to the device."""
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check organization membership
    org = await uow.organizations.get_by_id(device.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    is_member = await uow.organizations.is_member(org.id, user.id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this device",
        )


# ============== API Endpoints ==============


@router.post(
    "/{device_id}/commands/query-settings",
    response_model=QuerySettingsResponse,
    summary="Query current settings from device",
    description="Sends a command to the physical device to read its current settings. "
                "Settings are returned from the actual device hardware, not from a database.",
)
async def query_device_settings(
    device_id: UUID,
    request: QuerySettingsRequest = QuerySettingsRequest(),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
) -> QuerySettingsResponse:
    """Query current settings from the physical device."""
    logger.info(
        "[query-settings] Request from user=%s, device_id=%s, setting_keys=%s",
        current_user.email,
        device_id,
        request.setting_keys,
    )

    await check_device_access(device_id, current_user, uow)

    # Get device to find site_id
    device = await uow.devices.get_by_id(device_id)
    logger.info(
        "[query-settings] Device found: serial=%s, site_id=%s",
        device.serial_number,
        device.site_id,
    )

    try:
        # Send query command to device via System B
        logger.info("[query-settings] Calling System B send_command API...")
        command_response = await system_b_client.send_command(
            device_id=device_id,
            site_id=device.site_id,
            command_type="query_settings",
            command_params={
                "setting_keys": request.setting_keys,
            } if request.setting_keys else None,
            device_serial=device.serial_number,  # Pass serial for direct lookup in System B
            priority=7,  # Higher priority for settings queries
            expires_in_minutes=5,  # Short expiry for real-time queries
        )
        logger.info(
            "[query-settings] System B response received: command_id=%s, status=%s",
            command_response.get("id"),
            command_response.get("status"),
        )

        response = QuerySettingsResponse(
            command_id=command_response.get("id", ""),
            status=command_response.get("status", "pending"),
            settings=command_response.get("result", {}).get("settings") if command_response.get("result") else None,
            message="Settings query command sent to device",
        )
        logger.info("[query-settings] Returning response to frontend")
        return response

    except SystemBClientError as e:
        logger.error(
            "[query-settings] System B error: status_code=%s, message=%s",
            e.status_code,
            str(e),
        )
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query device settings: {str(e)}",
        )


@router.post(
    "/{device_id}/commands/update-settings",
    response_model=UpdateSettingsResponse,
    summary="Update device settings",
    description="Sends a command to the physical device to update its settings. "
                "Settings are written directly to the device hardware.",
)
async def update_device_settings(
    device_id: UUID,
    request: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
) -> UpdateSettingsResponse:
    """Update settings on the physical device."""
    await check_device_access(device_id, current_user, uow)

    # Get device to find site_id
    device = await uow.devices.get_by_id(device_id)

    try:
        # Send update command to device via System B
        command_response = await system_b_client.send_command(
            device_id=device_id,
            site_id=device.site_id,
            command_type="update_settings",
            command_params={
                "settings": request.settings,
                "apply_immediately": request.apply_immediately,
                "updated_by": str(current_user.id),
                "updated_by_email": current_user.email,
            },
            device_serial=device.serial_number,  # Pass serial for direct lookup in System B
            priority=8,  # High priority for settings updates
            expires_in_minutes=10,
        )

        return UpdateSettingsResponse(
            command_id=command_response.get("id", ""),
            status=command_response.get("status", "pending"),
            message="Settings update command sent to device successfully",
        )

    except SystemBClientError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update device settings: {str(e)}",
        )


@router.get(
    "/{device_id}/commands/{command_id}/status",
    response_model=CommandStatusResponse,
    summary="Get command execution status",
    description="Check the status of a previously sent command to see if it completed successfully.",
)
async def get_command_status(
    device_id: UUID,
    command_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
) -> CommandStatusResponse:
    """Get the status of a command."""
    logger.info(
        "[command-status] Request from user=%s, device_id=%s, command_id=%s",
        current_user.email,
        device_id,
        command_id,
    )

    await check_device_access(device_id, current_user, uow)

    try:
        # Get command status from System B
        logger.info("[command-status] Calling System B get_command_status API...")
        command_status = await system_b_client.get_command_status(command_id)
        logger.info(
            "[command-status] System B response: status=%s, has_result=%s, has_error=%s",
            command_status.get("status"),
            bool(command_status.get("result")),
            bool(command_status.get("error_message")),
        )

        response = CommandStatusResponse(
            command_id=str(command_id),
            status=command_status.get("status", "unknown"),
            progress=command_status.get("progress"),
            result=command_status.get("result"),
            error=command_status.get("error_message"),
            created_at=command_status.get("created_at", ""),
            updated_at=command_status.get("updated_at"),
        )
        logger.info("[command-status] Returning response to frontend")
        return response

    except SystemBClientError as e:
        logger.error(
            "[command-status] System B error: status_code=%s, message=%s",
            e.status_code,
            str(e),
        )
        if e.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Command not found",
            )
        raise HTTPException(
            status_code=e.status_code or status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get command status: {str(e)}",
        )


@router.get(
    "/{device_id}/commands",
    summary="List recent commands for device",
    description="Get a list of recent commands sent to this device.",
)
async def list_device_commands(
    device_id: UUID,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> list[CommandStatusResponse]:
    """List recent commands for a device."""
    await check_device_access(device_id, current_user, uow)

    # TODO: Implement System B endpoint to list commands by device
    # For now, return empty list
    return []
