"""
Device API endpoints for System B.

Handles device registration, status, and management.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db_session, get_device_service, get_auth_service
from ..schemas import (
    DeviceRegisterRequest,
    DeviceSelfRegisterRequest,
    DeviceSelfRegisterResponse,
    DeviceClaimRequest,
    DeviceClaimResponse,
    DeviceFullResponse,
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
    # Serial number schemas
    SerialNumberGenerateRequest,
    SerialNumberGenerateResponse,
    SerialNumberValidateRequest,
    SerialNumberValidateResponse,
    SerialNumberBatchValidateRequest,
    SerialNumberBatchValidateResponse,
)
from ...application.services import DeviceService, DeviceAuthService
from ...application.services.serial_number_service import get_serial_number_service, SerialNumberService
from ...infrastructure.database.repositories import DeviceRegistryRepository
from ...domain.entities.telemetry import ConnectionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["Devices"])


def device_to_response(device, newly_registered: bool = True) -> DeviceResponse:
    """Convert DeviceRegistry entity to DeviceResponse schema."""
    # Extract fields from metadata
    metadata = device.metadata or {}
    firmware_version = metadata.get("firmware_version")
    hardware_version = metadata.get("hardware_version")
    capabilities = metadata.get("capabilities")
    device_metadata = metadata.get("device_metadata") or metadata

    return DeviceResponse(
        id=device.id,
        site_id=device.site_id,
        device_type=device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
        serial_number=device.serial_number,
        protocol_id=device.protocol,
        firmware_version=firmware_version,
        hardware_version=hardware_version,
        connection_status=device.connection_status.value if hasattr(device.connection_status, 'value') else str(device.connection_status),
        last_seen=device.last_connected_at,
        capabilities=capabilities,
        device_metadata=device_metadata,
        is_active=device.connection_status != ConnectionStatus.DISCONNECTED,
        created_at=device.created_at,
        newly_registered=newly_registered,
    )


@router.post(
    "/register",
    response_model=DeviceResponse,
    summary="Register or reconnect a device",
    description="Register a new device or reconnect an existing device. "
                "If a device with the same serial number already exists, "
                "returns the existing device with newly_registered=false.",
)
async def register_device(
    request: DeviceRegisterRequest,
    response: "Response",
    session: AsyncSession = Depends(get_db_session),
) -> DeviceResponse:
    """
    Register a new device or reconnect an existing one.

    This endpoint supports both initial registration and reconnection:
    - If the serial_number is new: creates a new device, returns 201 Created
    - If the serial_number exists: returns existing device, returns 200 OK

    The response includes `newly_registered` field to indicate which case occurred.
    """
    from fastapi import Response
    from uuid import uuid4

    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    try:
        # Convert device_type string to DeviceType enum
        from ...domain.entities.telemetry import DeviceType
        try:
            device_type_enum = DeviceType(request.device_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid device_type: {request.device_type}",
            )

        # Check if device with this serial number already exists
        existing_device = await device_repo.get_by_serial_number(request.serial_number)

        if existing_device:
            # Device already registered - update connection status and return
            logger.info(f"Device {request.serial_number} already registered (id: {existing_device.id}), reconnecting")

            # Update last_connected_at and connection status
            await device_repo.update_connection_status(
                device_id=existing_device.id,
                status=ConnectionStatus.CONNECTED,
            )

            # Refresh device data after update
            existing_device = await device_repo.get_by_id(existing_device.id)

            # Return 200 OK for existing device
            response.status_code = status.HTTP_200_OK
            return device_to_response(existing_device, newly_registered=False)

        # New device - proceed with registration
        device_id = uuid4()

        # For now, we'll use the site_id as organization_id placeholder
        # In production, you'd fetch organization_id from the site
        # TODO: Get organization_id from site_id via System A or local cache
        organization_id = request.site_id  # Temporary: use site_id as org_id

        # Build connection config from request
        connection_config = request.connection_config or {}
        if request.protocol_id:
            connection_config["protocol_id"] = request.protocol_id

        # Build metadata from request
        metadata = request.device_metadata or {}
        if request.firmware_version:
            metadata["firmware_version"] = request.firmware_version
        if request.hardware_version:
            metadata["hardware_version"] = request.hardware_version
        if request.capabilities:
            metadata["capabilities"] = request.capabilities

        device = await service.register_device(
            device_id=device_id,
            site_id=request.site_id,
            organization_id=organization_id,
            device_type=device_type_enum,
            serial_number=request.serial_number,
            protocol=request.protocol_id,
            connection_config=connection_config if connection_config else None,
            metadata=metadata if metadata else None,
        )

        logger.info(f"New device registered: {request.serial_number} (id: {device.id})")

        # Return 201 Created for new device
        response.status_code = status.HTTP_201_CREATED
        return device_to_response(device, newly_registered=True)

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error registering device: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Failed to register device: {e}\n{error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Device registration failed: {str(e)}",
        )


def device_to_full_response(device) -> DeviceFullResponse:
    """Convert DeviceRegistry entity to DeviceFullResponse schema."""
    return DeviceFullResponse(
        id=device.device_id,
        serial_number=device.serial_number,
        device_type=device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
        manufacturer=device.manufacturer,
        model=device.model,
        firmware_version=device.firmware_version,
        protocol=device.protocol,
        status=device.status,
        owner_id=device.owner_id,
        site_id=device.site_id,
        organization_id=device.organization_id,
        connection_status=device.connection_status.value if hasattr(device.connection_status, 'value') else str(device.connection_status),
        last_connected_at=device.last_connected_at,
        last_telemetry_at=device.last_telemetry_at,
        capabilities=device.capabilities,
        polling_interval_seconds=device.polling_interval_seconds,
        created_at=device.created_at,
    )


@router.post(
    "/self-register",
    response_model=DeviceSelfRegisterResponse,
    summary="Device self-registration (ESP)",
    description="Register an orphan device. Called by ESP logger on power-up. "
                "Device starts in 'orphan' state until claimed by a user.",
)
async def self_register_device(
    request: DeviceSelfRegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceSelfRegisterResponse:
    """
    Device self-registration endpoint for ESP loggers.

    This is called when an ESP device powers on and connects to System B.
    The device registers with its serial number and starts polling immediately.
    Device is in 'orphan' state until claimed by a user during registration.

    Serial numbers must be valid SolarHub format with correct check digits.
    """
    from ...domain.entities.telemetry import DeviceType

    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    try:
        # Validate serial number format and check digits
        serial_service = get_serial_number_service()
        is_valid, error = serial_service.validate(request.serial_number)

        if not is_valid:
            logger.warning(f"Invalid serial number: {request.serial_number} - {error}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid serial number: {error}",
            )

        # Get normalized serial number
        normalized_serial = request.serial_number.upper().replace("-", "").replace(" ", "")

        # Convert device_type string to DeviceType enum
        try:
            device_type_enum = DeviceType(request.device_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid device_type: {request.device_type}. Must be one of: inverter, battery, meter",
            )

        # Register orphan device (or reconnect existing)
        device = await service.register_orphan_device(
            serial_number=normalized_serial,
            device_type=device_type_enum,
            firmware_version=request.firmware_version,
            manufacturer=request.manufacturer,
            protocol=request.protocol,
            capabilities=request.capabilities,
            model=request.model,
        )

        # Determine if this was a new registration or reconnection
        is_reconnect = device.reconnect_count > 1
        message = "Device reconnected" if is_reconnect else "Device registered successfully"

        logger.info(f"Device self-registered: {request.serial_number} (id: {device.device_id}, reconnect: {is_reconnect})")

        return DeviceSelfRegisterResponse(
            status="success",
            device_id=device.device_id,
            message=message,
            polling_interval_ms=device.polling_interval_seconds * 1000,
            is_claimed=device.is_claimed(),
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Failed to self-register device: {e}\n{error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Device self-registration failed: {str(e)}",
        )


@router.get(
    "/serial/{serial_number}",
    response_model=DeviceFullResponse,
    summary="Get device by serial number",
    description="Get device details by serial number.",
)
async def get_device_by_serial(
    serial_number: str,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceFullResponse:
    """
    Get device by serial number.

    Used by System A to check device status before claiming.
    """
    device_repo = DeviceRegistryRepository(session)
    device = await device_repo.get_by_serial_number(serial_number)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found. Please ensure your device is powered on and connected.",
        )

    return device_to_full_response(device)


@router.put(
    "/{device_id}/claim",
    response_model=DeviceClaimResponse,
    summary="Claim an orphan device",
    description="Claim an orphan device for a user. Called by System A during user registration or device claim.",
)
async def claim_device(
    device_id: UUID,
    request: DeviceClaimRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceClaimResponse:
    """
    Claim an orphan device for a user.

    This is called by System A when:
    1. A user registers with a device serial number
    2. A user claims a device after registration
    """
    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    try:
        device = await service.claim_device(
            device_id=device_id,
            owner_id=request.owner_id,
            site_id=request.site_id,
            organization_id=request.organization_id,
        )

        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found",
            )

        logger.info(f"Device {device_id} claimed by user {request.owner_id}")

        return DeviceClaimResponse(
            success=True,
            message="Device claimed successfully",
            device=device_to_full_response(device),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to claim device: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Device claim failed: {str(e)}",
        )


@router.put(
    "/{device_id}/release",
    response_model=DeviceClaimResponse,
    summary="Release a claimed device",
    description="Release a claimed device (make it orphan again).",
)
async def release_device(
    device_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceClaimResponse:
    """
    Release a claimed device (make it orphan again).

    This removes the device from the user's account.
    """
    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    device = await service.release_device(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    logger.info(f"Device {device_id} released")

    return DeviceClaimResponse(
        success=True,
        message="Device released successfully",
        device=device_to_full_response(device),
    )


@router.get(
    "/orphan",
    response_model=List[DeviceFullResponse],
    summary="Get all orphan devices",
    description="Get all orphan devices (not yet claimed by any user).",
)
async def get_orphan_devices(
    session: AsyncSession = Depends(get_db_session),
) -> List[DeviceFullResponse]:
    """
    Get all orphan devices.

    Used for admin purposes to see devices that haven't been claimed.
    """
    device_repo = DeviceRegistryRepository(session)
    service = DeviceService(device_repo, None)

    devices = await service.get_orphan_devices()

    return [device_to_full_response(d) for d in devices]


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

    # Extract fields from metadata
    metadata = device.metadata or {}
    firmware_version = metadata.get("firmware_version")
    hardware_version = metadata.get("hardware_version")
    capabilities = metadata.get("capabilities")
    device_metadata = metadata.get("device_metadata") or metadata
    
    return DeviceResponse(
        id=device.id,
        site_id=device.site_id,
        device_type=device.device_type.value if hasattr(device.device_type, 'value') else str(device.device_type),
        serial_number=device.serial_number,
        protocol_id=device.protocol,
        firmware_version=firmware_version,
        hardware_version=hardware_version,
        connection_status=device.connection_status.value if hasattr(device.connection_status, 'value') else str(device.connection_status),
        last_seen=device.last_connected_at,
        capabilities=capabilities,
        device_metadata=device_metadata,
        is_active=device.connection_status != ConnectionStatus.DISCONNECTED,
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

    return device_to_response(device)


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

    return device_to_response(device)


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


# ============================================================================
# Serial Number API Endpoints
# ============================================================================


@router.post(
    "/serial/generate",
    response_model=SerialNumberGenerateResponse,
    summary="Generate serial numbers",
    description="Generate new serial numbers with check digits for devices.",
)
async def generate_serial_numbers(
    request: SerialNumberGenerateRequest,
) -> SerialNumberGenerateResponse:
    """
    Generate serial numbers for new devices.

    Serial number format: MMHH-TTNN-NNNN-NNCC (16 characters)
    - MM: Manufacturer code (SH for SolarHub)
    - HH: Hardware revision (01, 02, etc.)
    - TT: Device type code (IN=inverter, BT=battery, MT=meter, GW=gateway)
    - NNNNNNNN: Random alphanumeric (8 chars)
    - CC: Check digits (2 chars)
    """
    serial_service = get_serial_number_service()

    serial_numbers = serial_service.generate(
        device_type=request.device_type,
        hardware_revision=request.hardware_revision,
        count=request.count,
    )

    formatted = [serial_service.format_display(sn) for sn in serial_numbers]

    # Get the device type code for the response
    from ...application.services.serial_number_service import DEVICE_TYPE_TO_CODE, DeviceTypeCode
    device_type_code = DEVICE_TYPE_TO_CODE.get(
        request.device_type.lower(),
        DeviceTypeCode.OTHER
    ).value

    return SerialNumberGenerateResponse(
        serial_numbers=serial_numbers,
        formatted=formatted,
        count=len(serial_numbers),
        device_type=device_type_code,
    )


@router.post(
    "/serial/validate",
    response_model=SerialNumberValidateResponse,
    summary="Validate a serial number",
    description="Validate a serial number and extract its components.",
)
async def validate_serial_number(
    request: SerialNumberValidateRequest,
) -> SerialNumberValidateResponse:
    """
    Validate a serial number.

    Returns validation result and parsed components if valid.
    """
    serial_service = get_serial_number_service()

    is_valid, error = serial_service.validate(request.serial_number)

    if is_valid:
        info = serial_service.parse(request.serial_number)
        return SerialNumberValidateResponse(
            serial_number=info.serial_number,
            is_valid=True,
            error=None,
            formatted=serial_service.format_display(info.serial_number),
            manufacturer_code=info.manufacturer_code,
            hardware_revision=info.hardware_revision,
            device_type_code=info.device_type_code,
            device_type=info.device_type,
        )
    else:
        # Normalize serial for response
        normalized = request.serial_number.upper().replace("-", "").replace(" ", "")
        return SerialNumberValidateResponse(
            serial_number=normalized,
            is_valid=False,
            error=error,
            formatted=None,
            manufacturer_code=None,
            hardware_revision=None,
            device_type_code=None,
            device_type=None,
        )


@router.post(
    "/serial/validate/batch",
    response_model=SerialNumberBatchValidateResponse,
    summary="Validate multiple serial numbers",
    description="Validate a batch of serial numbers.",
)
async def validate_serial_numbers_batch(
    request: SerialNumberBatchValidateRequest,
) -> SerialNumberBatchValidateResponse:
    """
    Validate multiple serial numbers in a single request.
    """
    serial_service = get_serial_number_service()

    results = []
    valid_count = 0
    invalid_count = 0

    for serial in request.serial_numbers:
        is_valid, error = serial_service.validate(serial)

        if is_valid:
            info = serial_service.parse(serial)
            results.append(SerialNumberValidateResponse(
                serial_number=info.serial_number,
                is_valid=True,
                error=None,
                formatted=serial_service.format_display(info.serial_number),
                manufacturer_code=info.manufacturer_code,
                hardware_revision=info.hardware_revision,
                device_type_code=info.device_type_code,
                device_type=info.device_type,
            ))
            valid_count += 1
        else:
            normalized = serial.upper().replace("-", "").replace(" ", "")
            results.append(SerialNumberValidateResponse(
                serial_number=normalized,
                is_valid=False,
                error=error,
                formatted=None,
                manufacturer_code=None,
                hardware_revision=None,
                device_type_code=None,
                device_type=None,
            ))
            invalid_count += 1

    return SerialNumberBatchValidateResponse(
        results=results,
        valid_count=valid_count,
        invalid_count=invalid_count,
    )
