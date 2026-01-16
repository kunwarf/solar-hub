"""
Device API endpoints for System B.

Handles device registration, status, and management.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db_session, get_device_service, get_auth_service
from ..schemas import (
    DeviceRegisterRequest,
    DeviceSyncRequest,
    DeviceUpdateRequest,
    DeviceResponse,
    DeviceSessionResponse,
    DeviceSummaryResponse,
    DeviceListResponse,
    ConnectionStatsResponse,
    DeviceAuthRequest,
    DeviceAuthResponse,
    DeviceTokenResponse,
)
from ...application.services import DeviceService, DeviceAuthService
from ...infrastructure.database.repositories import DeviceRegistryRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.post(
    "/register",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new device",
    description="Register a new device in the system.",
)
async def register_device(
    request: DeviceRegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceResponse:
    """
    Register a new device.
    """
    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    try:
        device = await service.register_device(
            site_id=request.site_id,
            device_type=request.device_type,
            serial_number=request.serial_number,
            protocol_id=request.protocol_id,
            firmware_version=request.firmware_version,
            hardware_version=request.hardware_version,
            connection_config=request.connection_config,
            capabilities=request.capabilities,
            device_metadata=request.device_metadata,
        )

        return DeviceResponse(
            id=device.id,
            site_id=device.site_id,
            device_type=device.device_type,
            serial_number=device.serial_number,
            protocol_id=device.protocol_id,
            firmware_version=device.firmware_version,
            hardware_version=device.hardware_version,
            connection_status=device.connection_status,
            last_seen=device.last_seen,
            capabilities=device.capabilities,
            device_metadata=device.device_metadata,
            is_active=device.is_active,
            created_at=device.created_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to register device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Device registration failed",
        )


@router.post(
    "/sync",
    response_model=DeviceResponse,
    summary="Sync device state",
    description="Upsert device information during connection sync.",
)
async def sync_device(
    request: DeviceSyncRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceResponse:
    """
    Sync device state - create or update device record.
    """
    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    device = await service.sync_device(
        site_id=request.site_id,
        device_type=request.device_type,
        serial_number=request.serial_number,
        protocol_id=request.protocol_id,
        firmware_version=request.firmware_version,
        hardware_version=request.hardware_version,
        connection_config=request.connection_config,
        capabilities=request.capabilities,
        device_metadata=request.device_metadata,
    )

    return DeviceResponse(
        id=device.id,
        site_id=device.site_id,
        device_type=device.device_type,
        serial_number=device.serial_number,
        protocol_id=device.protocol_id,
        firmware_version=device.firmware_version,
        hardware_version=device.hardware_version,
        connection_status=device.connection_status,
        last_seen=device.last_seen,
        capabilities=device.capabilities,
        device_metadata=device.device_metadata,
        is_active=device.is_active,
        created_at=device.created_at,
    )


@router.get(
    "/{device_id}",
    response_model=DeviceResponse,
    summary="Get device by ID",
    description="Get device details by ID.",
)
async def get_device(
    device_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceResponse:
    """
    Get device details.
    """
    device_repo = DeviceRegistryRepository(session)
    device = await device_repo.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    return DeviceResponse(
        id=device.id,
        site_id=device.site_id,
        device_type=device.device_type,
        serial_number=device.serial_number,
        protocol_id=device.protocol_id,
        firmware_version=device.firmware_version,
        hardware_version=device.hardware_version,
        connection_status=device.connection_status,
        last_seen=device.last_seen,
        capabilities=device.capabilities,
        device_metadata=device.device_metadata,
        is_active=device.is_active,
        created_at=device.created_at,
    )


@router.patch(
    "/{device_id}",
    response_model=DeviceResponse,
    summary="Update device",
    description="Update device information.",
)
async def update_device(
    device_id: UUID,
    request: DeviceUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceResponse:
    """
    Update device information.
    """
    device_repo = DeviceRegistryRepository(session)

    device = await device_repo.get_by_id(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    updates = request.model_dump(exclude_unset=True)
    device = await device_repo.update(device_id, **updates)

    return DeviceResponse(
        id=device.id,
        site_id=device.site_id,
        device_type=device.device_type,
        serial_number=device.serial_number,
        protocol_id=device.protocol_id,
        firmware_version=device.firmware_version,
        hardware_version=device.hardware_version,
        connection_status=device.connection_status,
        last_seen=device.last_seen,
        capabilities=device.capabilities,
        device_metadata=device.device_metadata,
        is_active=device.is_active,
        created_at=device.created_at,
    )


@router.get(
    "/site/{site_id}",
    response_model=DeviceListResponse,
    summary="Get devices by site",
    description="Get all devices for a site.",
)
async def get_site_devices(
    site_id: UUID,
    device_type: Optional[str] = None,
    connection_status: Optional[str] = None,
    is_active: bool = True,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> DeviceListResponse:
    """
    Get devices for a site.
    """
    device_repo = DeviceRegistryRepository(session)

    devices = await device_repo.get_by_site(
        site_id=site_id,
        device_type=device_type,
        connection_status=connection_status,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    total = await device_repo.count_by_site(site_id, is_active=is_active)

    return DeviceListResponse(
        devices=[
            DeviceSummaryResponse(
                id=d.id,
                site_id=d.site_id,
                device_type=d.device_type,
                serial_number=d.serial_number,
                connection_status=d.connection_status,
                last_seen=d.last_seen,
                is_active=d.is_active,
            )
            for d in devices
        ],
        total=total,
    )


@router.post(
    "/{device_id}/connect",
    response_model=DeviceSessionResponse,
    summary="Handle device connect",
    description="Record device connection event.",
)
async def device_connect(
    device_id: UUID,
    ip_address: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceSessionResponse:
    """
    Handle device connection.
    """
    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    session_info = await service.handle_device_connect(
        device_id=device_id,
        ip_address=ip_address,
    )

    return DeviceSessionResponse(
        device_id=device_id,
        session_id=session_info.get("session_id"),
        connected_at=session_info.get("connected_at"),
        ip_address=ip_address,
    )


@router.post(
    "/{device_id}/disconnect",
    summary="Handle device disconnect",
    description="Record device disconnection event.",
)
async def device_disconnect(
    device_id: UUID,
    reason: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Handle device disconnection.
    """
    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    await service.handle_device_disconnect(
        device_id=device_id,
        reason=reason,
    )

    return {"success": True, "device_id": str(device_id)}


@router.post(
    "/{device_id}/heartbeat",
    summary="Update device heartbeat",
    description="Update last_seen timestamp for a device.",
)
async def device_heartbeat(
    device_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Update device heartbeat.
    """
    device_repo = DeviceRegistryRepository(session)

    await device_repo.update_last_seen(device_id)

    return {"success": True, "device_id": str(device_id), "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get(
    "/stats/connection",
    response_model=ConnectionStatsResponse,
    summary="Get connection statistics",
    description="Get connection statistics for all devices or a site.",
)
async def get_connection_stats(
    site_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_db_session),
) -> ConnectionStatsResponse:
    """
    Get connection statistics.
    """
    device_repo = DeviceRegistryRepository(session)

    stats = await device_repo.get_connection_stats(site_id)

    return ConnectionStatsResponse(
        total_devices=stats["total"],
        online=stats["online"],
        offline=stats["offline"],
        error=stats.get("error", 0),
        never_connected=stats.get("never_connected", 0),
    )


@router.get(
    "/polling/list",
    response_model=List[DeviceSummaryResponse],
    summary="Get devices for polling",
    description="Get list of devices that should be polled.",
)
async def get_devices_for_polling(
    site_id: Optional[UUID] = None,
    session: AsyncSession = Depends(get_db_session),
) -> List[DeviceSummaryResponse]:
    """
    Get devices that should be polled.
    """
    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    devices = await service.get_devices_for_polling(site_id)

    return [
        DeviceSummaryResponse(
            id=d.id,
            site_id=d.site_id,
            device_type=d.device_type,
            serial_number=d.serial_number,
            connection_status=d.connection_status,
            last_seen=d.last_seen,
            is_active=d.is_active,
        )
        for d in devices
    ]


# Authentication endpoints

@router.post(
    "/auth/token",
    response_model=DeviceAuthResponse,
    summary="Authenticate by token",
    description="Authenticate a device using its auth token.",
)
async def authenticate_by_token(
    request: DeviceAuthRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceAuthResponse:
    """
    Authenticate device by token.
    """
    device_repo = DeviceRegistryRepository(session)
    auth_service = DeviceAuthService(device_repo)

    result = await auth_service.authenticate_by_token(
        device_id=request.device_id,
        token=request.token,
    )

    if not result["authenticated"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.get("reason", "Authentication failed"),
        )

    return DeviceAuthResponse(
        authenticated=True,
        device_id=request.device_id,
        session_token=result.get("session_token"),
        expires_at=result.get("expires_at"),
    )


@router.post(
    "/{device_id}/generate-token",
    response_model=DeviceTokenResponse,
    summary="Generate device token",
    description="Generate a new authentication token for a device.",
)
async def generate_device_token(
    device_id: UUID,
    expires_in_days: int = Query(default=365, ge=1, le=3650),
    session: AsyncSession = Depends(get_db_session),
) -> DeviceTokenResponse:
    """
    Generate new auth token for device.
    """
    device_repo = DeviceRegistryRepository(session)

    device = await device_repo.get_by_id(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    token = await device_repo.generate_auth_token(device_id, expires_in_days)

    return DeviceTokenResponse(
        device_id=device_id,
        token=token,
        expires_in_days=expires_in_days,
    )
