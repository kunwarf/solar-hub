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
    logger.info("=" * 100)
    logger.info("[query-settings] ===== QUERY SETTINGS API CALL START =====")
    logger.info("[query-settings] User: %s", current_user.email)
    logger.info("[query-settings] Device ID: %s", device_id)
    logger.info("[query-settings] Setting keys: %s", request.setting_keys or "ALL")
    logger.info("=" * 100)

    await check_device_access(device_id, current_user, uow)

    # Get device to find site_id
    device = await uow.devices.get_by_id(device_id)
    logger.info("[query-settings] Device found:")
    logger.info("[query-settings]   - Name: %s", device.name)
    logger.info("[query-settings]   - Serial: %s", device.serial_number)
    logger.info("[query-settings]   - Site ID: %s", device.site_id)

    try:
        # Send query command to device via System B
        logger.info("-" * 100)
        logger.info("[query-settings] STEP 1: Sending command to System B")
        logger.info("[query-settings] Endpoint: POST /api/v1/commands/")
        logger.info("[query-settings] Payload:")
        logger.info("[query-settings]   - device_id: %s", device_id)
        logger.info("[query-settings]   - site_id: %s", device.site_id)
        logger.info("[query-settings]   - command_type: query_settings")
        logger.info("[query-settings]   - priority: 7")
        logger.info("[query-settings]   - expires_in: 5 minutes")

        command_response = await system_b_client.send_command(
            device_id=device_id,
            site_id=device.site_id,
            command_type="query_settings",
            command_params={
                "setting_keys": request.setting_keys,
            } if request.setting_keys else None,
            device_serial=device.serial_number,
            priority=7,
            expires_in_minutes=5,
        )

        logger.info("-" * 100)
        logger.info("[query-settings] STEP 2: System B Response Received")
        logger.info("[query-settings] Response type: %s", type(command_response))
        logger.info("[query-settings] Response keys: %s", list(command_response.keys()) if isinstance(command_response, dict) else "N/A")
        logger.info("[query-settings] Command ID: %s", command_response.get("id"))
        logger.info("[query-settings] Status: %s", command_response.get("status"))
        logger.info("[query-settings] Has 'result' key: %s", "result" in command_response)

        if command_response.get("result"):
            logger.info("[query-settings] Result exists:")
            result = command_response.get("result", {})
            logger.info("[query-settings]   - Result type: %s", type(result))
            logger.info("[query-settings]   - Result keys: %s", list(result.keys()) if isinstance(result, dict) else "N/A")
            logger.info("[query-settings]   - Has 'settings': %s", "settings" in result)
            if result.get("settings"):
                logger.info("[query-settings]   - Settings count: %d", len(result.get("settings", {})))
                logger.info("[query-settings]   - First 5 setting keys: %s", list(result.get("settings", {}).keys())[:5])
        else:
            logger.info("[query-settings] Result is None or empty (expected for 'pending' status)")

        logger.info("-" * 100)
        logger.info("[query-settings] STEP 3: Building Response")
        response = QuerySettingsResponse(
            command_id=command_response.get("id", ""),
            status=command_response.get("status", "pending"),
            settings=command_response.get("result", {}).get("settings") if command_response.get("result") else None,
            message="Settings query command sent to device",
        )

        logger.info("[query-settings] Response to frontend:")
        logger.info("[query-settings]   - command_id: %s", response.command_id)
        logger.info("[query-settings]   - status: %s", response.status)
        logger.info("[query-settings]   - has settings: %s", response.settings is not None)
        if response.settings:
            logger.info("[query-settings]   - settings count: %d", len(response.settings))
        logger.info("[query-settings]   - message: %s", response.message)

        logger.info("-" * 100)
        logger.info("[query-settings] IMPORTANT ARCHITECTURAL NOTES:")
        logger.info("[query-settings] 1. System A does NOT store command or result locally")
        logger.info("[query-settings] 2. System B owns the command and its result")
        logger.info("[query-settings] 3. Frontend MUST poll GET /commands/{command_id}/status")
        logger.info("[query-settings] 4. System A will proxy the status request to System B")
        logger.info("=" * 100)
        logger.info("[query-settings] ===== QUERY SETTINGS API CALL END =====")
        logger.info("=" * 100)

        return response

    except SystemBClientError as e:
        logger.error("=" * 100)
        logger.error("[query-settings] ERROR: System B client failure")
        logger.error("[query-settings] Status code: %s", e.status_code)
        logger.error("[query-settings] Error message: %s", str(e))
        logger.error("=" * 100)
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
    logger.info("=" * 100)
    logger.info("[command-status] ===== GET COMMAND STATUS API CALL START =====")
    logger.info("[command-status] User: %s", current_user.email)
    logger.info("[command-status] Device ID: %s", device_id)
    logger.info("[command-status] Command ID: %s", command_id)
    logger.info("=" * 100)

    await check_device_access(device_id, current_user, uow)

    try:
        # Get command status from System B
        logger.info("-" * 100)
        logger.info("[command-status] STEP 1: Querying System B for command status")
        logger.info("[command-status] Endpoint: GET /api/v1/commands/%s", command_id)

        command_status = await system_b_client.get_command_status(command_id)

        logger.info("-" * 100)
        logger.info("[command-status] STEP 2: System B Response Received")
        logger.info("[command-status] Response type: %s", type(command_status))
        logger.info("[command-status] Response keys: %s", list(command_status.keys()) if isinstance(command_status, dict) else "N/A")
        logger.info("[command-status] Status: %s", command_status.get("status"))
        logger.info("[command-status] Progress: %s", command_status.get("progress"))
        logger.info("[command-status] Has error_message: %s", bool(command_status.get("error_message")))
        logger.info("[command-status] Has result: %s", bool(command_status.get("result")))

        if command_status.get("result"):
            result = command_status.get("result", {})
            logger.info("[command-status] Result details:")
            logger.info("[command-status]   - Result type: %s", type(result))
            logger.info("[command-status]   - Result keys: %s", list(result.keys()) if isinstance(result, dict) else "N/A")
            logger.info("[command-status]   - Has 'settings': %s", "settings" in result)
            if result.get("settings"):
                logger.info("[command-status]   - Settings type: %s", type(result.get("settings")))
                logger.info("[command-status]   - Settings count: %d", len(result.get("settings", {})))
                logger.info("[command-status]   - First 5 settings: %s", list(result.get("settings", {}).keys())[:5])
            logger.info("[command-status]   - Has 'success': %s (value: %s)", "success" in result, result.get("success"))
            logger.info("[command-status]   - Has 'error': %s (value: %s)", "error" in result, result.get("error"))
        else:
            logger.info("[command-status] Result is None/empty (command may still be pending)")

        logger.info("-" * 100)
        logger.info("[command-status] STEP 3: Building Response for Frontend")

        response = CommandStatusResponse(
            command_id=str(command_id),
            status=command_status.get("status", "unknown"),
            progress=command_status.get("progress"),
            result=command_status.get("result"),
            error=command_status.get("error_message"),
            created_at=command_status.get("created_at", ""),
            updated_at=command_status.get("updated_at"),
        )

        logger.info("[command-status] Response to frontend:")
        logger.info("[command-status]   - command_id: %s", response.command_id)
        logger.info("[command-status]   - status: %s", response.status)
        logger.info("[command-status]   - progress: %s", response.progress)
        logger.info("[command-status]   - has result: %s", response.result is not None)
        if response.result:
            logger.info("[command-status]   - result type: %s", type(response.result))
            if isinstance(response.result, dict):
                logger.info("[command-status]   - result keys: %s", list(response.result.keys()))
                if response.result.get("settings"):
                    logger.info("[command-status]   - SETTINGS FOUND: %d settings", len(response.result.get("settings", {})))
        logger.info("[command-status]   - has error: %s", response.error is not None)
        logger.info("[command-status]   - created_at: %s", response.created_at)
        logger.info("[command-status]   - updated_at: %s", response.updated_at)

        logger.info("-" * 100)
        logger.info("[command-status] CRITICAL CHECK:")
        if response.status == "completed" and response.result and response.result.get("settings"):
            logger.info("[command-status] ✅ SUCCESS: Command completed with settings data!")
            logger.info("[command-status] Frontend should receive %d settings", len(response.result.get("settings", {})))
        elif response.status == "completed" and not response.result:
            logger.error("[command-status] ⚠️  WARNING: Command completed but result is empty!")
        elif response.status == "pending":
            logger.info("[command-status] ⏳ Command still pending, frontend will poll again")
        elif response.status == "failed":
            logger.error("[command-status] ❌ Command failed: %s", response.error)

        logger.info("=" * 100)
        logger.info("[command-status] ===== GET COMMAND STATUS API CALL END =====")
        logger.info("=" * 100)

        return response

    except SystemBClientError as e:
        logger.error("=" * 100)
        logger.error("[command-status] ERROR: System B client failure")
        logger.error("[command-status] Status code: %s", e.status_code)
        logger.error("[command-status] Error message: %s", str(e))
        logger.error("=" * 100)
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
