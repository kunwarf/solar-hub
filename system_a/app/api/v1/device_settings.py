"""
Device Settings API endpoints.

Provides endpoints for managing device-specific configuration settings.
Settings vary by device type (inverter, battery, meter) and manufacturer.
"""
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_unit_of_work
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User
from ...infrastructure.database.models.device_settings_model import (
    DeviceSettings,
    get_default_settings,
)


router = APIRouter(prefix="/devices", tags=["Device Settings"])


# ============== Request/Response Schemas ==============


class DeviceSettingsResponse(BaseModel):
    """Device settings response schema"""

    id: str
    device_id: str
    device_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    settings: Dict[str, Any]
    is_default: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class DeviceSettingsUpdate(BaseModel):
    """Device settings update schema"""

    settings: Dict[str, Any] = Field(..., description="Device configuration settings")


class DeviceSettingsResetResponse(BaseModel):
    """Response after resetting settings"""

    message: str
    settings: Dict[str, Any]


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


@router.get(
    "/{device_id}/settings",
    response_model=DeviceSettingsResponse,
    summary="Get device settings",
    description="Retrieve configuration settings for a specific device. Returns defaults if no custom settings exist.",
)
async def get_device_settings(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> DeviceSettingsResponse:
    """Get device settings."""
    # This endpoint is deprecated. Settings are now read directly from devices via commands.
    # Use POST /devices/{device_id}/commands/query-settings instead.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "This endpoint is deprecated. Device settings are now read directly from physical devices. "
            "Use POST /devices/{device_id}/commands/query-settings to query current settings from the device. "
            "Settings are cached in the frontend localStorage."
        ),
    )


@router.put(
    "/{device_id}/settings",
    response_model=DeviceSettingsResponse,
    summary="Update device settings",
    description="Update configuration settings for a device. Creates new settings record if none exists.",
)
async def update_device_settings(
    device_id: UUID,
    settings_update: DeviceSettingsUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> DeviceSettingsResponse:
    """Update device settings."""
    # This endpoint is deprecated. Settings are now written directly to devices via commands.
    # Use POST /devices/{device_id}/commands/update-settings instead.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "This endpoint is deprecated. Device settings are now written directly to physical devices. "
            "Use POST /devices/{device_id}/commands/update-settings to update settings on the device."
        ),
    )


@router.post(
    "/{device_id}/settings/reset",
    response_model=DeviceSettingsResetResponse,
    summary="Reset device settings to defaults",
    description="Reset device configuration settings to manufacturer/type defaults.",
)
async def reset_device_settings(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> DeviceSettingsResetResponse:
    """Reset device settings to defaults."""
    # This endpoint is deprecated. Settings are managed directly on devices via commands.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "This endpoint is deprecated. Device settings are managed directly on physical devices. "
            "Use POST /devices/{device_id}/commands/update-settings to write default settings to the device."
        ),
    )


@router.delete(
    "/{device_id}/settings",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete device settings",
    description="Delete custom device settings. Device will revert to defaults.",
)
async def delete_device_settings(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> None:
    """Delete device settings."""
    # This endpoint is deprecated. Settings are managed directly on devices via commands.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "This endpoint is deprecated. Device settings are managed directly on physical devices. "
            "There is no database storage to delete."
        ),
    )
