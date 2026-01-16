"""
Discovery API endpoints for network scanning and device identification.
"""
import asyncio
import logging
from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks

from ..dependencies import get_current_user, require_admin
from ..schemas.discovery_schemas import (
    ScanNetworkRequest,
    ScanHostRequest,
    DiscoveryResultResponse,
    DiscoveredDeviceResponse,
    ScanProgressResponse,
    ScanStatusResponse,
    StartScanResponse,
    DiscoverySummaryResponse,
)
from ..schemas.auth_schemas import MessageResponse
from ...domain.entities.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discovery", tags=["Discovery"])

# In-memory storage for scan results (in production, use Redis or database)
_active_scans: Dict[UUID, dict] = {}
_scan_results: Dict[UUID, dict] = {}


def _get_discovery_service():
    """
    Get discovery service instance.

    Note: In production, this should be properly initialized with the
    protocol registry from system_b. For now, we provide a mock/stub
    that demonstrates the API structure.
    """
    # Import here to avoid circular imports and handle missing module gracefully
    try:
        from system_b.device_server.discovery import DiscoveryService
        from system_b.device_server.protocols.registry import ProtocolRegistry
        from system_b.device_server.protocols.loader import load_protocols

        # Load protocols from yaml
        protocols = load_protocols()
        registry = ProtocolRegistry(protocols)
        return DiscoveryService(registry)
    except ImportError as e:
        logger.warning(f"Could not import discovery service: {e}")
        return None


@router.post(
    "/scan-network",
    response_model=DiscoveryResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan network for devices",
    description="Scan a network range for solar devices. Returns discovered and identified devices.",
)
async def scan_network(
    request: ScanNetworkRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
) -> DiscoveryResultResponse:
    """
    Scan a network range for solar devices.

    Scans all IP addresses in the specified network for responsive
    hosts on the given ports, then attempts to identify them using
    registered device protocols.

    Requires admin role.
    """
    service = _get_discovery_service()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery service not available",
        )

    if request.run_in_background:
        # Start background scan and return immediately
        scan_id = await service.scan_network_async(
            network=request.network,
            ports=request.ports,
            site_id=request.site_id,
            max_concurrent=request.max_concurrent,
            connect_timeout=request.connect_timeout,
            identify_timeout=request.identify_timeout,
        )

        # Return minimal response with scan ID
        result = service.get_scan_status(scan_id)
        if result:
            return DiscoveryResultResponse(
                scan_id=result.scan_id,
                network=result.network,
                ports=result.ports,
                site_id=result.site_id,
                devices=[],
                progress=ScanProgressResponse(
                    **result.progress.to_dict()
                ),
                summary={
                    "total_devices": 0,
                    "identified_devices": 0,
                    "unidentified_hosts": 0,
                },
            )

    # Run synchronous scan
    logger.info(f"Starting network scan: {request.network}")

    result = await service.scan_network(
        network=request.network,
        ports=request.ports,
        site_id=request.site_id,
        max_concurrent=request.max_concurrent,
        connect_timeout=request.connect_timeout,
        identify_timeout=request.identify_timeout,
    )

    # Convert to response
    return DiscoveryResultResponse(
        scan_id=result.scan_id,
        network=result.network,
        ports=result.ports,
        site_id=result.site_id,
        devices=[
            DiscoveredDeviceResponse(
                ip_address=d.ip_address,
                port=d.port,
                protocol_id=d.protocol_id,
                serial_number=d.serial_number,
                device_type=d.device_type,
                model=d.model,
                manufacturer=d.manufacturer,
                firmware_version=d.firmware_version,
                is_identified=d.is_identified,
                response_time_ms=d.response_time_ms,
                extra_data=d.extra_data,
                discovered_at=d.discovered_at,
            )
            for d in result.devices
        ],
        progress=ScanProgressResponse(
            **result.progress.to_dict()
        ),
        summary={
            "total_devices": len(result.devices),
            "identified_devices": len(result.identified_devices),
            "unidentified_hosts": len(result.unidentified_hosts),
        },
    )


@router.post(
    "/scan-host",
    response_model=DiscoveryResultResponse,
    summary="Scan a single host",
    description="Scan a specific IP address for devices.",
)
async def scan_host(
    request: ScanHostRequest,
    current_user: User = Depends(require_admin),
) -> DiscoveryResultResponse:
    """
    Scan a single host for devices.

    Attempts to identify a device at the specified IP address
    on the given ports.

    Requires admin role.
    """
    service = _get_discovery_service()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery service not available",
        )

    # Scan single host by using /32 network
    result = await service.scan_network(
        network=f"{request.ip_address}/32",
        ports=request.ports,
        site_id=request.site_id,
        max_concurrent=1,
    )

    return DiscoveryResultResponse(
        scan_id=result.scan_id,
        network=f"{request.ip_address}/32",
        ports=result.ports,
        site_id=result.site_id,
        devices=[
            DiscoveredDeviceResponse(
                ip_address=d.ip_address,
                port=d.port,
                protocol_id=d.protocol_id,
                serial_number=d.serial_number,
                device_type=d.device_type,
                model=d.model,
                manufacturer=d.manufacturer,
                firmware_version=d.firmware_version,
                is_identified=d.is_identified,
                response_time_ms=d.response_time_ms,
                extra_data=d.extra_data,
                discovered_at=d.discovered_at,
            )
            for d in result.devices
        ],
        progress=ScanProgressResponse(
            **result.progress.to_dict()
        ),
        summary={
            "total_devices": len(result.devices),
            "identified_devices": len(result.identified_devices),
            "unidentified_hosts": len(result.unidentified_hosts),
        },
    )


@router.get(
    "/status/{scan_id}",
    response_model=ScanStatusResponse,
    summary="Get scan status",
    description="Get the status and progress of a running or completed scan.",
)
async def get_scan_status(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
) -> ScanStatusResponse:
    """
    Get status of a discovery scan.

    Returns progress information for background scans.
    """
    service = _get_discovery_service()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery service not available",
        )

    result = service.get_scan_status(scan_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id} not found",
        )

    return ScanStatusResponse(
        scan_id=result.scan_id,
        is_running=result.progress.is_running,
        is_complete=result.progress.is_complete,
        progress=ScanProgressResponse(
            **result.progress.to_dict()
        ),
        device_count=len(result.devices),
    )


@router.get(
    "/results/{scan_id}",
    response_model=DiscoveryResultResponse,
    summary="Get scan results",
    description="Get full results of a completed scan.",
)
async def get_scan_results(
    scan_id: UUID,
    current_user: User = Depends(get_current_user),
) -> DiscoveryResultResponse:
    """
    Get full results of a discovery scan.

    Returns all discovered devices and identification results.
    """
    service = _get_discovery_service()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery service not available",
        )

    result = service.get_scan_status(scan_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id} not found",
        )

    return DiscoveryResultResponse(
        scan_id=result.scan_id,
        network=result.network,
        ports=result.ports,
        site_id=result.site_id,
        devices=[
            DiscoveredDeviceResponse(
                ip_address=d.ip_address,
                port=d.port,
                protocol_id=d.protocol_id,
                serial_number=d.serial_number,
                device_type=d.device_type,
                model=d.model,
                manufacturer=d.manufacturer,
                firmware_version=d.firmware_version,
                is_identified=d.is_identified,
                response_time_ms=d.response_time_ms,
                extra_data=d.extra_data,
                discovered_at=d.discovered_at,
            )
            for d in result.devices
        ],
        progress=ScanProgressResponse(
            **result.progress.to_dict()
        ),
        summary={
            "total_devices": len(result.devices),
            "identified_devices": len(result.identified_devices),
            "unidentified_hosts": len(result.unidentified_hosts),
        },
    )


@router.post(
    "/cancel/{scan_id}",
    response_model=MessageResponse,
    summary="Cancel scan",
    description="Cancel a running discovery scan.",
)
async def cancel_scan(
    scan_id: UUID,
    current_user: User = Depends(require_admin),
) -> MessageResponse:
    """
    Cancel a running discovery scan.

    Requires admin role.
    """
    service = _get_discovery_service()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery service not available",
        )

    cancelled = await service.cancel_scan(scan_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan {scan_id} not found or already completed",
        )

    return MessageResponse(message=f"Scan {scan_id} cancelled")


@router.get(
    "/active",
    response_model=DiscoverySummaryResponse,
    summary="List active scans",
    description="Get summary of all active and recent discovery scans.",
)
async def list_active_scans(
    current_user: User = Depends(get_current_user),
) -> DiscoverySummaryResponse:
    """
    Get summary of active discovery scans.
    """
    service = _get_discovery_service()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery service not available",
        )

    scans = service.get_active_scans()
    active_count = sum(1 for s in scans if s.progress.is_running)
    total_devices = sum(len(s.devices) for s in scans)

    return DiscoverySummaryResponse(
        active_scans=active_count,
        total_devices_found=total_devices,
        scans=[
            ScanStatusResponse(
                scan_id=s.scan_id,
                is_running=s.progress.is_running,
                is_complete=s.progress.is_complete,
                progress=ScanProgressResponse(
                    **s.progress.to_dict()
                ),
                device_count=len(s.devices),
            )
            for s in scans
        ],
    )


@router.post(
    "/clear-cache",
    response_model=MessageResponse,
    summary="Clear discovery cache",
    description="Clear the known devices cache to allow re-discovery.",
)
async def clear_discovery_cache(
    current_user: User = Depends(require_admin),
) -> MessageResponse:
    """
    Clear the discovery cache.

    Clears the list of known serial numbers to allow devices
    to be discovered again.

    Requires admin role.
    """
    service = _get_discovery_service()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discovery service not available",
        )

    service.clear_known_devices()
    return MessageResponse(message="Discovery cache cleared")
