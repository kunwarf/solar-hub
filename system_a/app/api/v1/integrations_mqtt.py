"""
Home Assistant MQTT Integration API.

User-facing endpoints for managing per-user HA MQTT credentials and
device enrollment.  One internal endpoint for System B to fetch the
full enrollment list.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...application.services.mqtt_integration_service import (
    MqttIntegrationService,
    MqttIntegrationResult,
    PasswordRotationResult,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User
from ..dependencies import (
    get_current_active_user,
    get_mqtt_integration_service,
    get_unit_of_work,
    verify_service_api_key,
)

router = APIRouter(prefix="/integrations/mqtt", tags=["Integrations - MQTT"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class MqttIntegrationCreateResponse(BaseModel):
    integration_id: str
    ha_username: str
    password: str
    broker_host: str
    broker_port: int
    publish_interval_seconds: int
    message: str = "Save this password — it will not be shown again."


class MqttIntegrationResponse(BaseModel):
    integration_id: str
    ha_username: str
    broker_host: str
    broker_port: int
    enabled: bool
    publish_interval_seconds: int


class PasswordRotateResponse(BaseModel):
    ha_username: str
    password: str
    message: str = "New password generated — save it now."


class DeviceEnrollRequest(BaseModel):
    enrolled: bool


class DeviceEnrollmentItem(BaseModel):
    device_id: str
    serial_number: str
    name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    enrolled: bool


class EnrolledDeviceItem(BaseModel):
    ha_username: str
    device_id: str
    device_serial: str
    device_name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    publish_interval_seconds: int


# ---------------------------------------------------------------------------
# User-facing endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=MqttIntegrationCreateResponse, status_code=201)
async def create_integration(
    current_user: User = Depends(get_current_active_user),
    service: MqttIntegrationService = Depends(get_mqtt_integration_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Create a Home Assistant MQTT integration for the current user."""
    try:
        result: MqttIntegrationResult = await service.create_integration(
            user_id=current_user.id, uow=uow
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MQTT broker unavailable: {e}",
        )

    return MqttIntegrationCreateResponse(
        integration_id=result.integration_id,
        ha_username=result.ha_username,
        password=result.password,
        broker_host=result.broker_host,
        broker_port=result.broker_port,
        publish_interval_seconds=result.publish_interval_seconds,
    )


@router.get("", response_model=MqttIntegrationResponse)
async def get_integration(
    current_user: User = Depends(get_current_active_user),
    service: MqttIntegrationService = Depends(get_mqtt_integration_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get the current user's MQTT integration details."""
    integration = await service.get_integration(user_id=current_user.id, uow=uow)
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No MQTT integration configured",
        )

    return MqttIntegrationResponse(
        integration_id=str(integration.id),
        ha_username=integration.ha_username,
        broker_host=service._public_host,
        broker_port=service._public_port,
        enabled=integration.enabled,
        publish_interval_seconds=integration.publish_interval_seconds,
    )


@router.delete("", status_code=204)
async def delete_integration(
    current_user: User = Depends(get_current_active_user),
    service: MqttIntegrationService = Depends(get_mqtt_integration_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Delete the current user's MQTT integration and revoke broker credentials."""
    try:
        await service.delete_integration(user_id=current_user.id, uow=uow)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MQTT broker unavailable: {e}",
        )


@router.post("/rotate-password", response_model=PasswordRotateResponse)
async def rotate_password(
    current_user: User = Depends(get_current_active_user),
    service: MqttIntegrationService = Depends(get_mqtt_integration_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Regenerate the MQTT password for the current user."""
    try:
        result: PasswordRotationResult = await service.rotate_password(
            user_id=current_user.id, uow=uow
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MQTT broker unavailable: {e}",
        )

    return PasswordRotateResponse(
        ha_username=result.ha_username,
        password=result.password,
    )


@router.get("/devices", response_model=List[DeviceEnrollmentItem])
async def list_devices(
    current_user: User = Depends(get_current_active_user),
    service: MqttIntegrationService = Depends(get_mqtt_integration_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List all devices owned by the user with their enrollment status."""
    devices = await service.list_devices_with_enrollment(
        user_id=current_user.id, uow=uow
    )
    return [DeviceEnrollmentItem(**d) for d in devices]


@router.put("/devices/{device_id}", response_model=DeviceEnrollmentItem)
async def enroll_or_unenroll_device(
    device_id: UUID,
    body: DeviceEnrollRequest,
    current_user: User = Depends(get_current_active_user),
    service: MqttIntegrationService = Depends(get_mqtt_integration_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Enroll or unenroll a specific device from HA publishing."""
    try:
        if body.enrolled:
            await service.enroll_device(
                user_id=current_user.id, device_id=device_id, uow=uow
            )
        else:
            await service.unenroll_device(
                user_id=current_user.id, device_id=device_id, uow=uow
            )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Re-fetch device list to return current enrollment state
    devices = await service.list_devices_with_enrollment(
        user_id=current_user.id, uow=uow
    )
    device_info = next(
        (d for d in devices if d["device_id"] == str(device_id)), None
    )
    if device_info is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return DeviceEnrollmentItem(**device_info)


# ---------------------------------------------------------------------------
# Internal endpoint — System B only
# ---------------------------------------------------------------------------

@router.get("/enrolled-devices", response_model=List[EnrolledDeviceItem])
async def get_all_enrolled_devices(
    _: bool = Depends(verify_service_api_key),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Return all enabled device enrollments across all users.

    Used by System B's HA publisher to know which devices to publish
    and under which ha_username.  Protected by service API key.
    """
    async with uow:
        enrollments = await uow.mqtt_integration_devices.get_all_enabled_enrollments()

    return [EnrolledDeviceItem(**e) for e in enrollments]
