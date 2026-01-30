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
    await check_device_access(device_id, current_user, uow)

    # Get device to determine type/manufacturer
    device = await uow.devices.get_by_id(device_id)

    async with uow:
        # Try to get existing settings
        settings_record = await uow.session.execute(
            "SELECT * FROM device_settings WHERE device_id = :device_id",
            {"device_id": str(device_id)},
        )
        settings_row = settings_record.fetchone()

        if settings_row:
            # Return existing settings
            return DeviceSettingsResponse(
                id=str(settings_row.id),
                device_id=str(settings_row.device_id),
                device_type=settings_row.device_type,
                manufacturer=settings_row.manufacturer,
                model=settings_row.model,
                settings=settings_row.settings,
                is_default=settings_row.is_default,
                created_at=settings_row.created_at.isoformat(),
                updated_at=settings_row.updated_at.isoformat(),
            )
        else:
            # Return default settings
            default_settings = get_default_settings(
                device.device_type.value,
                device.manufacturer,
                device.model,
            )

            return DeviceSettingsResponse(
                id="default",
                device_id=str(device_id),
                device_type=device.device_type.value,
                manufacturer=device.manufacturer,
                model=device.model,
                settings=default_settings,
                is_default=True,
                created_at=device.created_at.isoformat(),
                updated_at=device.updated_at.isoformat(),
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
    await check_device_access(device_id, current_user, uow)

    # Get device to determine type/manufacturer
    device = await uow.devices.get_by_id(device_id)

    async with uow:
        # Check if settings exist
        settings_query = await uow.session.execute(
            "SELECT * FROM device_settings WHERE device_id = :device_id",
            {"device_id": str(device_id)},
        )
        existing = settings_query.fetchone()

        if existing:
            # Update existing settings
            await uow.session.execute(
                """
                UPDATE device_settings
                SET settings = :settings,
                    updated_by = :updated_by,
                    updated_at = NOW(),
                    is_default = false
                WHERE device_id = :device_id
                RETURNING *
                """,
                {
                    "device_id": str(device_id),
                    "settings": settings_update.settings,
                    "updated_by": str(current_user.id),
                },
            )
        else:
            # Create new settings
            await uow.session.execute(
                """
                INSERT INTO device_settings (
                    id, device_id, device_type, manufacturer, model,
                    settings, is_default, created_by, updated_by
                )
                VALUES (
                    gen_random_uuid(), :device_id, :device_type, :manufacturer, :model,
                    :settings, false, :created_by, :updated_by
                )
                """,
                {
                    "device_id": str(device_id),
                    "device_type": device.device_type.value,
                    "manufacturer": device.manufacturer,
                    "model": device.model,
                    "settings": settings_update.settings,
                    "created_by": str(current_user.id),
                    "updated_by": str(current_user.id),
                },
            )

        await uow.commit()

        # Fetch updated settings
        updated_query = await uow.session.execute(
            "SELECT * FROM device_settings WHERE device_id = :device_id",
            {"device_id": str(device_id)},
        )
        updated_row = updated_query.fetchone()

        return DeviceSettingsResponse(
            id=str(updated_row.id),
            device_id=str(updated_row.device_id),
            device_type=updated_row.device_type,
            manufacturer=updated_row.manufacturer,
            model=updated_row.model,
            settings=updated_row.settings,
            is_default=updated_row.is_default,
            created_at=updated_row.created_at.isoformat(),
            updated_at=updated_row.updated_at.isoformat(),
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
    await check_device_access(device_id, current_user, uow)

    # Get device to determine type/manufacturer
    device = await uow.devices.get_by_id(device_id)

    # Get default settings
    default_settings = get_default_settings(
        device.device_type.value,
        device.manufacturer,
        device.model,
    )

    async with uow:
        # Delete existing custom settings
        await uow.session.execute(
            "DELETE FROM device_settings WHERE device_id = :device_id",
            {"device_id": str(device_id)},
        )

        await uow.commit()

    return DeviceSettingsResetResponse(
        message="Device settings reset to defaults",
        settings=default_settings,
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
    await check_device_access(device_id, current_user, uow)

    async with uow:
        await uow.session.execute(
            "DELETE FROM device_settings WHERE device_id = :device_id",
            {"device_id": str(device_id)},
        )
        await uow.commit()
