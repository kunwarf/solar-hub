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
    MPPTChannelSchema,
    MPPTChannelsResponse,
    ExtendedInverterMetrics,
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
    "/{device_id}/unclaim",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def unclaim_device(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """
    Unclaim a device — removes it from this site and releases it in System B.

    The device remains registered in System B as an orphan and will be
    available to claim again. Use this when a device needs to be moved
    to a different site or re-paired after a hardware replacement.
    """
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow, require_manage=True)

    # Release in System B (clears site_id/org_id/owner + inverter_serial metadata)
    try:
        await system_b_client.release_device(device_id)
    except SystemBClientError as e:
        # Log but don't block — System A cleanup should still proceed
        import logging
        logging.getLogger("system_a").warning(
            f"System B release failed for {device_id}: {e} — proceeding with System A removal"
        )

    # Remove from System A
    await uow.devices.delete(device_id)
    await uow.commit()

    return MessageResponse(
        message="Device unclaimed successfully",
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
    "/{device_id}/battery/bank",
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_device_battery_bank(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    cache: TelemetryCacheReader = Depends(get_telemetry_cache),
):
    """
    Get detailed battery bank telemetry (Pylontech/Pytes).

    Returns per-unit and per-cell data written by System B from the
    Pylontech serial command protocol. Falls back to bank-level data
    from the generic battery section when no cell data is available.
    """
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    await check_site_access(device.site_id, current_user, uow)

    telemetry = await cache.get_telemetry(device.serial_number)

    if not telemetry:
        return {
            "device_id": str(device_id),
            "serial_number": device.serial_number,
            "available": False,
            "battery_bank": None,
        }

    battery_bank = telemetry.get("battery_bank")
    battery = telemetry.get("battery", {})

    return {
        "device_id": str(device_id),
        "serial_number": device.serial_number,
        "available": battery_bank is not None,
        "timestamp": telemetry.get("timestamp"),
        # Bank-level summary (always present for battery devices)
        "bank": {
            "soc_pct": battery.get("soc_pct"),
            "voltage_v": battery.get("voltage_v"),
            "current_a": battery.get("current_a"),
            "charging": battery.get("charging"),
            "power_w": telemetry.get("raw", {}).get("battery_power_w"),
            "temp_c": telemetry.get("temperatures", {}).get("battery_c"),
            "soh_pct": battery_bank.get("soh_pct") if battery_bank else None,
            "cycle_count": battery_bank.get("cycle_count") if battery_bank else None,
            "units_count": battery_bank.get("units_count") if battery_bank else None,
            "has_alarm": battery_bank.get("has_alarm") if battery_bank else None,
            "alarms": battery_bank.get("alarms") if battery_bank else [],
        },
        # Per-unit detail (Pylontech only)
        "units": battery_bank.get("units", []) if battery_bank else [],
        # Per-cell detail (Pylontech only)
        "cells": battery_bank.get("cells", []) if battery_bank else [],
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


@router.get(
    "/{device_id}/mppt-channels",
    response_model=MPPTChannelsResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_mppt_channels(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    cache: TelemetryCacheReader = Depends(get_telemetry_cache),
):
    """
    Get MPPT (Maximum Power Point Tracking) channel data for the device.

    This endpoint returns detailed information about each PV string/channel
    connected to the inverter, including voltage, current, power, and status.
    """
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow)

    # Only inverters have MPPT channels
    if device.device_type != DeviceType.INVERTER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MPPT channel data is only available for inverter devices",
        )

    # Get telemetry from Redis cache
    telemetry = await cache.get_telemetry(device.serial_number)

    if not telemetry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No telemetry data available for this device",
        )

    # Extract MPPT channel data from telemetry
    # System B writes MPPT data in format: pv1_voltage_v, pv1_current_a, pv1_power_w, etc.
    channels = []
    total_power_w = 0.0

    # Check for up to 4 MPPT channels (common in hybrid inverters)
    for i in range(1, 5):
        voltage_key = f"pv{i}_voltage_v"
        current_key = f"pv{i}_current_a"
        power_key = f"pv{i}_power_w"

        if voltage_key in telemetry or power_key in telemetry:
            voltage = telemetry.get(voltage_key, 0.0) or 0.0
            current = telemetry.get(current_key, 0.0) or 0.0
            power = telemetry.get(power_key, 0.0) or 0.0

            # Determine status based on power output
            if power >= 50:  # Producing significant power
                if voltage > 0 and current > 0:
                    # Check if efficiency is reasonable
                    expected_power = voltage * current
                    actual_efficiency = (power / expected_power * 100) if expected_power > 0 else 0
                    if actual_efficiency > 85:
                        channel_status = "optimal"
                    elif actual_efficiency > 60:
                        channel_status = "shaded"
                    else:
                        channel_status = "low"
                else:
                    channel_status = "low"
            elif power > 0:
                channel_status = "low"
            else:
                channel_status = "offline"

            # Calculate efficiency
            efficiency_pct = None
            if voltage > 0 and current > 0:
                expected_power = voltage * current
                if expected_power > 0:
                    efficiency_pct = round((power / expected_power) * 100, 1)

            channels.append(MPPTChannelSchema(
                channel_id=i,
                name=f"String {i}",
                power_w=round(power, 2),
                voltage_v=round(voltage, 2),
                current_a=round(current, 2),
                status=channel_status,
                panel_count=telemetry.get(f"pv{i}_panel_count"),
                efficiency_pct=efficiency_pct,
            ))

            total_power_w += power

    if not channels:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No MPPT channel data found in telemetry",
        )

    return MPPTChannelsResponse(
        device_id=device.id,
        serial_number=device.serial_number,
        channels=channels,
        total_power_w=round(total_power_w, 2),
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/{device_id}/telemetry/extended",
    response_model=ExtendedInverterMetrics,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_extended_telemetry(
    device_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    cache: TelemetryCacheReader = Depends(get_telemetry_cache),
):
    """
    Get extended inverter telemetry with detailed electrical metrics.

    This endpoint returns comprehensive inverter metrics including DC input,
    AC output, efficiency, temperature, battery, grid, and load information.
    """
    device = await uow.devices.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    # Check access
    await check_site_access(device.site_id, current_user, uow)

    # Get telemetry from Redis cache
    telemetry = await cache.get_telemetry(device.serial_number)
    device_status = await cache.get_status(device.serial_number)

    if not telemetry:
        # Return empty metrics if no data available
        return ExtendedInverterMetrics(
            timestamp=datetime.now(timezone.utc),
            online=False,
        )

    # Extract comprehensive metrics from telemetry
    # DC Metrics
    dc_voltage_v = telemetry.get("dc_voltage_v") or telemetry.get("voltage_v")
    dc_current_a = telemetry.get("dc_current_a") or telemetry.get("current_a")
    dc_power_w = telemetry.get("dc_power_w")

    # AC Metrics
    ac_voltage_v = telemetry.get("ac_voltage_v") or telemetry.get("grid_voltage_v")
    ac_current_a = telemetry.get("ac_current_a")
    ac_power_w = telemetry.get("ac_power_w") or telemetry.get("power_output_w")
    ac_frequency_hz = telemetry.get("frequency_hz") or telemetry.get("grid_frequency_hz")

    # Efficiency and Temperature
    efficiency_pct = telemetry.get("efficiency_pct") or telemetry.get("efficiency_percent")
    temperature_c = telemetry.get("temperature_c") or telemetry.get("inverter_temp_c")

    # Battery Metrics
    battery_voltage_v = telemetry.get("battery_voltage_v")
    battery_current_a = telemetry.get("battery_current_a")
    battery_power_w = telemetry.get("battery_power_w")
    battery_soc_pct = telemetry.get("battery_soc_pct") or telemetry.get("battery_soc_percent")

    # Power Flow
    grid_power_w = telemetry.get("grid_power_w")
    load_power_w = telemetry.get("load_power_w")

    # PV Power (sum of all MPPT channels)
    pv_power_w = telemetry.get("pv_power_w")
    if not pv_power_w:
        # Calculate from individual strings
        pv1 = telemetry.get("pv1_power_w", 0) or 0
        pv2 = telemetry.get("pv2_power_w", 0) or 0
        pv3 = telemetry.get("pv3_power_w", 0) or 0
        pv4 = telemetry.get("pv4_power_w", 0) or 0
        pv_power_w = pv1 + pv2 + pv3 + pv4

    return ExtendedInverterMetrics(
        dc_voltage_v=dc_voltage_v,
        dc_current_a=dc_current_a,
        dc_power_w=dc_power_w,
        ac_voltage_v=ac_voltage_v,
        ac_current_a=ac_current_a,
        ac_power_w=ac_power_w,
        ac_frequency_hz=ac_frequency_hz,
        efficiency_pct=efficiency_pct,
        temperature_c=temperature_c,
        battery_voltage_v=battery_voltage_v,
        battery_current_a=battery_current_a,
        battery_power_w=battery_power_w,
        battery_soc_pct=battery_soc_pct,
        grid_power_w=grid_power_w,
        load_power_w=load_power_w,
        pv_power_w=pv_power_w,
        online=(device_status == "online"),
        timestamp=datetime.now(timezone.utc),
    )
