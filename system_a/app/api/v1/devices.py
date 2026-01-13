"""
Device management API endpoints.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
)
from ..schemas.device_schemas import (
    ConnectionConfigSchema,
    DeviceCommandRequest,
    DeviceCommandResponse,
    DeviceCreate,
    DeviceDetailResponse,
    DeviceListResponse,
    DeviceMetricsSchema,
    DeviceResponse,
    DeviceStatusUpdate,
    DeviceSummaryResponse,
    DeviceUpdate,
)
from ..schemas.auth_schemas import MessageResponse, ErrorResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserRole
from ...domain.entities.device import (
    Device,
    DeviceType,
    DeviceStatus,
    ProtocolType,
    ConnectionConfig,
    DeviceMetrics,
)

router = APIRouter(prefix="/devices", tags=["Devices"])


def map_device_type(device_type: str) -> DeviceType:
    """Map string to DeviceType enum."""
    mapping = {
        'inverter': DeviceType.INVERTER,
        'meter': DeviceType.METER,
        'battery': DeviceType.BATTERY,
        'weather_station': DeviceType.WEATHER_STATION,
        'sensor': DeviceType.SENSOR,
        'gateway': DeviceType.GATEWAY,
        'other': DeviceType.OTHER,
    }
    return mapping.get(device_type, DeviceType.OTHER)


def map_protocol_type(protocol: str) -> ProtocolType:
    """Map string to ProtocolType enum."""
    mapping = {
        'modbus_tcp': ProtocolType.MODBUS_TCP,
        'modbus_rtu': ProtocolType.MODBUS_RTU,
        'mqtt': ProtocolType.MQTT,
        'http': ProtocolType.HTTP,
        'custom': ProtocolType.CUSTOM,
    }
    return mapping.get(protocol, ProtocolType.HTTP)


def map_device_status(status_str: str) -> DeviceStatus:
    """Map string to DeviceStatus enum."""
    mapping = {
        'online': DeviceStatus.ONLINE,
        'offline': DeviceStatus.OFFLINE,
        'maintenance': DeviceStatus.MAINTENANCE,
        'error': DeviceStatus.ERROR,
    }
    return mapping.get(status_str, DeviceStatus.OFFLINE)


async def check_site_access(
    site_id: UUID,
    user: User,
    uow: UnitOfWork,
    require_manage: bool = False,
) -> None:
    """Check if user has access to the site's organization."""
    site = await uow.sites.get_by_id(site_id)

    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    org = await uow.organizations.get_by_id(site.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    if not org.is_member(user.id) and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this site",
        )

    if require_manage:
        member = org.get_member(user.id)
        if member and member.role not in [UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER, UserRole.INSTALLER]:
            if user.role != UserRole.SUPER_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to manage devices",
                )


def device_to_response(device: Device) -> DeviceResponse:
    """Convert Device domain entity to response schema."""
    return DeviceResponse(
        id=device.id,
        site_id=device.site_id,
        organization_id=device.organization_id,
        device_type=device.device_type.value,
        manufacturer=device.manufacturer,
        model=device.model,
        serial_number=device.serial_number,
        name=device.name,
        description=device.description,
        status=device.status.value,
        protocol=device.protocol.value,
        firmware_version=device.firmware_version,
        last_seen_at=device.last_seen_at,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


def device_to_detail_response(device: Device) -> DeviceDetailResponse:
    """Convert Device to detailed response."""
    metrics_schema = None
    if device.latest_metrics:
        metrics_schema = DeviceMetricsSchema(
            power_output_kw=device.latest_metrics.power_output_kw,
            energy_today_kwh=device.latest_metrics.energy_today_kwh,
            energy_total_kwh=device.latest_metrics.energy_total_kwh,
            voltage_v=device.latest_metrics.voltage_v,
            current_a=device.latest_metrics.current_a,
            frequency_hz=device.latest_metrics.frequency_hz,
            temperature_c=device.latest_metrics.temperature_c,
            battery_soc_percent=device.latest_metrics.battery_soc_percent,
            grid_power_kw=device.latest_metrics.grid_power_kw,
            pv_power_kw=device.latest_metrics.pv_power_kw,
            last_updated=device.latest_metrics.last_updated,
        )

    return DeviceDetailResponse(
        id=device.id,
        site_id=device.site_id,
        organization_id=device.organization_id,
        device_type=device.device_type.value,
        manufacturer=device.manufacturer,
        model=device.model,
        serial_number=device.serial_number,
        name=device.name,
        description=device.description,
        status=device.status.value,
        protocol=device.protocol.value,
        firmware_version=device.firmware_version,
        last_seen_at=device.last_seen_at,
        created_at=device.created_at,
        updated_at=device.updated_at,
        connection_config=ConnectionConfigSchema(
            protocol=device.connection_config.protocol.value,
            host=device.connection_config.host,
            port=device.connection_config.port,
            slave_id=device.connection_config.slave_id,
            mqtt_topic=device.connection_config.mqtt_topic,
            api_endpoint=device.connection_config.api_endpoint,
            auth_token=None,  # Don't expose auth token
            polling_interval_seconds=device.connection_config.polling_interval_seconds,
            timeout_seconds=device.connection_config.timeout_seconds,
        ),
        latest_metrics=metrics_schema,
        metadata=device.metadata,
        total_messages_received=device.total_messages_received,
        total_errors=device.total_errors,
        uptime_percentage=device.uptime_percentage,
    )


@router.post(
    "",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def register_device(
    request: DeviceCreate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Register a new device."""
    # Check site access
    await check_site_access(request.site_id, current_user, uow, require_manage=True)

    # Get site for organization_id
    site = await uow.sites.get_by_id(request.site_id)

    # Check if serial number already exists
    if await uow.devices.serial_number_exists(request.serial_number):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Device with this serial number is already registered",
        )

    # Create connection config
    config = ConnectionConfig(
        protocol=map_protocol_type(request.connection_config.protocol),
        host=request.connection_config.host,
        port=request.connection_config.port,
        slave_id=request.connection_config.slave_id,
        mqtt_topic=request.connection_config.mqtt_topic,
        api_endpoint=request.connection_config.api_endpoint,
        auth_token=request.connection_config.auth_token,
        polling_interval_seconds=request.connection_config.polling_interval_seconds,
        timeout_seconds=request.connection_config.timeout_seconds,
    )

    # Create device
    device = Device(
        site_id=request.site_id,
        organization_id=site.organization_id,
        device_type=map_device_type(request.device_type),
        manufacturer=request.manufacturer,
        model=request.model,
        serial_number=request.serial_number,
        name=request.name or f"{request.manufacturer} {request.model}",
        description=request.description,
        protocol=config.protocol,
        connection_config=config,
        metadata=request.metadata,
    )

    saved_device = await uow.devices.add(device)
    await uow.commit()

    return device_to_response(saved_device)


@router.get(
    "",
    response_model=DeviceListResponse,
)
async def list_devices(
    site_id: Optional[UUID] = Query(None, description="Filter by site"),
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List devices the user has access to."""
    offset = (page - 1) * page_size

    if site_id:
        # List devices for specific site
        await check_site_access(site_id, current_user, uow)

        devices = await uow.devices.get_by_site_id(
            site_id=site_id,
            limit=page_size,
            offset=offset,
            status=status_filter,
        )
        total = await uow.devices.count_by_site_id(site_id, status=status_filter)

    elif organization_id:
        # List devices for specific organization
        org = await uow.organizations.get_by_id(organization_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

        if not org.is_member(current_user.id) and current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this organization",
            )

        devices = await uow.devices.get_by_organization_id(
            organization_id=organization_id,
            limit=page_size,
            offset=offset,
            device_type=device_type,
            status=status_filter,
        )
        total = await uow.devices.count_by_organization_id(
            organization_id,
            device_type=device_type,
            status=status_filter,
        )

    else:
        # List devices across all user's organizations
        orgs = await uow.organizations.get_by_member_id(current_user.id)

        all_devices = []
        total = 0

        for org in orgs:
            org_devices = await uow.devices.get_by_organization_id(
                organization_id=org.id,
                limit=1000,
                device_type=device_type,
                status=status_filter,
            )
            all_devices.extend(org_devices)
            total += await uow.devices.count_by_organization_id(
                org.id,
                device_type=device_type,
                status=status_filter,
            )

        # Manual pagination
        devices = all_devices[offset:offset + page_size]

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return DeviceListResponse(
        items=[device_to_response(d) for d in devices],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{device_id}",
    response_model=DeviceDetailResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get device details."""
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow)

    return device_to_detail_response(device)


@router.put(
    "/{device_id}",
    response_model=DeviceResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def update_device(
    device_id: UUID,
    request: DeviceUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update device details."""
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow, require_manage=True)

    # Update fields
    if request.name is not None:
        device.name = request.name
    if request.description is not None:
        device.description = request.description
    if request.metadata is not None:
        device.metadata = request.metadata

    if request.connection_config is not None:
        device.connection_config = ConnectionConfig(
            protocol=map_protocol_type(request.connection_config.protocol),
            host=request.connection_config.host,
            port=request.connection_config.port,
            slave_id=request.connection_config.slave_id,
            mqtt_topic=request.connection_config.mqtt_topic,
            api_endpoint=request.connection_config.api_endpoint,
            auth_token=request.connection_config.auth_token,
            polling_interval_seconds=request.connection_config.polling_interval_seconds,
            timeout_seconds=request.connection_config.timeout_seconds,
        )
        device.protocol = device.connection_config.protocol

    device.mark_updated()
    updated_device = await uow.devices.update(device)
    await uow.commit()

    return device_to_response(updated_device)


@router.put(
    "/{device_id}/status",
    response_model=DeviceResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def update_device_status(
    device_id: UUID,
    request: DeviceStatusUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update device status."""
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow, require_manage=True)

    new_status = map_device_status(request.status)

    if new_status == DeviceStatus.MAINTENANCE:
        device.start_maintenance()
    elif new_status == DeviceStatus.ONLINE:
        if device.status == DeviceStatus.MAINTENANCE:
            device.end_maintenance()
        else:
            device.record_heartbeat()
    elif new_status == DeviceStatus.OFFLINE:
        device.status = DeviceStatus.OFFLINE
        device.mark_updated()
    elif new_status == DeviceStatus.ERROR:
        device.record_error("Manual error state set by user")

    await uow.devices.update(device)
    await uow.commit()

    return device_to_response(device)


@router.delete(
    "/{device_id}",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def delete_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Delete/deregister a device."""
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow, require_manage=True)

    await uow.devices.delete(device_id)
    await uow.commit()

    return MessageResponse(
        message="Device deleted successfully",
        success=True,
    )


@router.post(
    "/{device_id}/command",
    response_model=DeviceCommandResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def send_device_command(
    device_id: UUID,
    request: DeviceCommandRequest,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Send a command to a device."""
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow, require_manage=True)

    # Check if device is online
    if device.status != DeviceStatus.ONLINE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot send command to device in {device.status.value} state",
        )

    # TODO: Actually send command to device via System B
    # For now, return a pending command response
    command_id = uuid4()

    return DeviceCommandResponse(
        command_id=command_id,
        device_id=device_id,
        command=request.command,
        status="pending",
        sent_at=datetime.now(timezone.utc),
        response=None,
        error=None,
    )


@router.get(
    "/{device_id}/metrics",
    response_model=DeviceMetricsSchema,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_device_metrics(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get latest device metrics."""
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow)

    if not device.latest_metrics:
        return DeviceMetricsSchema()

    return DeviceMetricsSchema(
        power_output_kw=device.latest_metrics.power_output_kw,
        energy_today_kwh=device.latest_metrics.energy_today_kwh,
        energy_total_kwh=device.latest_metrics.energy_total_kwh,
        voltage_v=device.latest_metrics.voltage_v,
        current_a=device.latest_metrics.current_a,
        frequency_hz=device.latest_metrics.frequency_hz,
        temperature_c=device.latest_metrics.temperature_c,
        battery_soc_percent=device.latest_metrics.battery_soc_percent,
        grid_power_kw=device.latest_metrics.grid_power_kw,
        pv_power_kw=device.latest_metrics.pv_power_kw,
        last_updated=device.latest_metrics.last_updated,
    )
