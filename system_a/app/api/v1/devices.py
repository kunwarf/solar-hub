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
    get_telemetry_cache,
    get_system_b_client_instance,
)
from ...infrastructure.cache.telemetry_cache import TelemetryCacheReader
from ..schemas.device_schemas import (
    ConnectionConfigSchema,
    DeviceCommandRequest,
    DeviceCommandResponse,
    DeviceCreate,
    DeviceDetailResponse,
    DeviceListResponse,
    DeviceMetricsSchema,
    DeviceResponse,
    DeviceSnapshotUpdate,
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
from ...infrastructure.external.system_b_client import SystemBClient, SystemBClientError

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
    # Get protocol from connection_config if available, otherwise default
    protocol = "modbus_tcp"
    if device.connection_config:
        protocol = device.connection_config.protocol.value

    return DeviceResponse(
        id=device.id,
        site_id=device.site_id,
        organization_id=device.organization_id,
        device_type=device.device_type.value,
        manufacturer=device.manufacturer,
        model=device.model,
        serial_number=device.serial_number,
        name=device.name,
        description=None,  # Device entity doesn't have description
        status=device.status.value,
        protocol=protocol,
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

    # Handle optional connection_config
    connection_config_schema = None
    if device.connection_config:
        connection_config_schema = ConnectionConfigSchema(
            protocol=device.connection_config.protocol.value,
            host=device.connection_config.host,
            port=device.connection_config.port,
            slave_id=device.connection_config.slave_id,
            mqtt_topic=device.connection_config.mqtt_topic,
            api_endpoint=device.connection_config.api_endpoint,
            auth_token=None,  # Don't expose auth token
            polling_interval_seconds=device.connection_config.polling_interval_seconds,
            timeout_seconds=device.connection_config.timeout_seconds,
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
        description=None,  # Device entity doesn't have description field
        status=device.status.value,
        protocol=device.connection_config.protocol.value if device.connection_config else "mqtt",
        firmware_version=device.firmware_version,
        last_seen_at=device.last_seen_at,
        created_at=device.created_at,
        updated_at=device.updated_at,
        connection_config=connection_config_schema,
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


@router.patch(
    "/{device_id}/snapshot",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def update_device_snapshot(
    device_id: UUID,
    request: DeviceSnapshotUpdate,
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Update device telemetry snapshot from System B.

    This endpoint is called by System B to push latest device telemetry.
    It does not require authentication as it uses API key authentication
    via the System A client in System B.
    """
    import logging
    logger = logging.getLogger("system_a")

    device = await uow.devices.get_by_id(device_id)

    # If not found by ID, try to find by serial number from snapshot
    if not device:
        serial_number = request.snapshot.get('device_serial_number')
        if serial_number:
            device = await uow.devices.get_by_serial_number(str(serial_number))
            if device:
                logger.info(f"Device found by serial number {serial_number} (ID mismatch: {device_id})")

    if not device:
        serial_number = request.snapshot.get('device_serial_number', 'unknown')
        logger.warning(
            f"Device not found in System A. "
            f"ID: {device_id}, Serial: {serial_number}. "
            f"User needs to register and claim this device first."
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device not found. Serial: {serial_number}. Please register and claim this device first.",
        )

    # Parse timestamp if provided
    recorded_at = datetime.now(timezone.utc)
    if request.timestamp:
        try:
            recorded_at = datetime.fromisoformat(request.timestamp.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass

    snapshot = request.snapshot
    
    # Map snapshot data to DeviceMetrics
    # Handle various metric name formats from System B
    metrics_data = {}
    
    # Power metrics (convert W to kW where needed)
    if 'power_output_w' in snapshot or 'power_output' in snapshot:
        metrics_data['power_output_w'] = snapshot.get('power_output_w') or snapshot.get('power_output', 0)
    if 'pv_power_w' in snapshot or 'pv1_power_w' in snapshot:
        pv1 = snapshot.get('pv1_power_w', 0) or 0
        pv2 = snapshot.get('pv2_power_w', 0) or 0
        metrics_data['pv_power_w'] = pv1 + pv2
    if 'grid_power_w' in snapshot:
        metrics_data['grid_power_w'] = snapshot.get('grid_power_w')
    if 'load_power_w' in snapshot:
        metrics_data['load_power_w'] = snapshot.get('load_power_w')
    if 'battery_power_w' in snapshot:
        metrics_data['battery_power_w'] = snapshot.get('battery_power_w')
    
    # Energy metrics
    if 'energy_today_kwh' in snapshot:
        metrics_data['energy_today_kwh'] = snapshot.get('energy_today_kwh')
    if 'energy_total_kwh' in snapshot:
        metrics_data['energy_total_kwh'] = snapshot.get('energy_total_kwh')
    
    # Electrical metrics
    if 'voltage_v' in snapshot:
        metrics_data['voltage_v'] = snapshot.get('voltage_v')
    if 'current_a' in snapshot:
        metrics_data['current_a'] = snapshot.get('current_a')
    if 'frequency_hz' in snapshot:
        metrics_data['frequency_hz'] = snapshot.get('frequency_hz')
    
    # Temperature
    if 'temperature_c' in snapshot or 'inverter_temp_c' in snapshot:
        metrics_data['temperature_c'] = snapshot.get('temperature_c') or snapshot.get('inverter_temp_c')
    
    # Battery metrics
    if 'battery_soc_percent' in snapshot or 'battery_soc_pct' in snapshot:
        metrics_data['battery_soc_percent'] = snapshot.get('battery_soc_percent') or snapshot.get('battery_soc_pct')
    
    # Create DeviceMetrics object
    device_metrics = DeviceMetrics(
        power_output_w=metrics_data.get('power_output_w'),
        energy_today_kwh=metrics_data.get('energy_today_kwh'),
        energy_total_kwh=metrics_data.get('energy_total_kwh'),
        voltage_v=metrics_data.get('voltage_v'),
        current_a=metrics_data.get('current_a'),
        frequency_hz=metrics_data.get('frequency_hz'),
        temperature_c=metrics_data.get('temperature_c'),
        battery_soc_percent=metrics_data.get('battery_soc_percent'),
        battery_power_w=metrics_data.get('battery_power_w'),
        grid_power_w=metrics_data.get('grid_power_w'),
        load_power_w=metrics_data.get('load_power_w'),
        recorded_at=recorded_at,
    )

    # Update device metrics
    device.update_metrics(device_metrics)
    await uow.devices.update(device)
    await uow.commit()

    return MessageResponse(
        message="Device snapshot updated successfully",
        success=True,
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
    # Note: description field removed from Device entity
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
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """Send a command to a device via System B."""
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

    try:
        result = await system_b_client.send_command(
            device_id=device_id,
            site_id=device.site_id,
            command_type=request.command,
            command_params=request.parameters,
        )

        return DeviceCommandResponse(
            command_id=UUID(result["id"]) if "id" in result else uuid4(),
            device_id=device_id,
            command=request.command,
            status=result.get("status", "pending"),
            sent_at=datetime.now(timezone.utc),
            response=result,
            error=None,
        )
    except SystemBClientError as e:
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send command to device: {str(e)}",
        )


@router.get(
    "/{device_id}/commands/{command_id}",
    response_model=DeviceCommandResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_command_status(
    device_id: UUID,
    command_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """Get the status of a command sent to a device."""
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow)

    try:
        result = await system_b_client.get_command_status(command_id)

        return DeviceCommandResponse(
            command_id=command_id,
            device_id=device_id,
            command=result.get("command_type", "unknown"),
            status=result.get("status", "unknown"),
            sent_at=datetime.fromisoformat(result["created_at"]) if "created_at" in result else datetime.now(timezone.utc),
            response=result,
            error=result.get("error"),
        )
    except SystemBClientError as e:
        if e.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Command not found",
            )
        raise HTTPException(
            status_code=e.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to get command status: {str(e)}",
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


@router.get(
    "/{device_id}/telemetry/realtime",
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_device_realtime_telemetry(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    cache: TelemetryCacheReader = Depends(get_telemetry_cache),
):
    """
    Get real-time telemetry from Redis cache.

    System B writes telemetry to Redis, this endpoint reads it.
    Returns the latest cached telemetry data for the device.
    """
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow)

    # Get telemetry from Redis cache using device serial number
    telemetry = await cache.get_telemetry(device.serial_number)
    device_status = await cache.get_status(device.serial_number)
    last_seen = await cache.get_last_seen(device.serial_number)

    return {
        "device_id": str(device.id),
        "serial_number": device.serial_number,
        "status": device_status or "unknown",
        "last_seen": last_seen,
        "telemetry": telemetry,
    }


@router.get(
    "/serial/{serial_number}/telemetry/realtime",
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_device_realtime_telemetry_by_serial(
    serial_number: str,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    cache: TelemetryCacheReader = Depends(get_telemetry_cache),
):
    """
    Get real-time telemetry by serial number from Redis cache.

    System B writes telemetry to Redis, this endpoint reads it.
    """
    # Find device by serial number
    device = await uow.devices.get_by_serial_number(serial_number)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow)

    # Get telemetry from Redis cache
    telemetry = await cache.get_telemetry(serial_number)
    device_status = await cache.get_status(serial_number)
    last_seen = await cache.get_last_seen(serial_number)

    return {
        "device_id": str(device.id),
        "serial_number": serial_number,
        "status": device_status or "unknown",
        "last_seen": last_seen,
        "telemetry": telemetry,
    }
