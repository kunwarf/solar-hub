"""
Site management API endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
)
from ..schemas.site_schemas import (
    AddressSchema,
    GeoLocationSchema,
    SiteConfigurationSchema,
    SiteCreate,
    SiteDetailResponse,
    SiteListResponse,
    SiteResponse,
    SiteStatusUpdate,
    SiteSummaryResponse,
    SiteUpdate,
)
from ..schemas.auth_schemas import MessageResponse, ErrorResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserRole
from ...domain.entities.site import (
    Site,
    SiteConfiguration,
    SiteStatus,
    SiteType,
    GridConnectionType,
    DiscoProvider,
)
from ...domain.value_objects.address import Address, GeoLocation

router = APIRouter(prefix="/sites", tags=["Sites"])


async def get_org_and_check_access(
    org_id: UUID,
    user: User,
    uow: UnitOfWork,
    require_manage: bool = False,
) -> None:
    """Check if user has access to organization."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    if not org.is_member(user.id) and user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization",
        )

    if require_manage:
        member = org.get_member(user.id)
        if member and member.role not in [UserRole.OWNER, UserRole.ADMIN, UserRole.MANAGER]:
            if user.role != UserRole.SUPER_ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to manage sites",
                )


def map_grid_connection(grid_type: str) -> GridConnectionType:
    """Map string to GridConnectionType enum."""
    mapping = {
        'on_grid': GridConnectionType.ON_GRID,
        'off_grid': GridConnectionType.OFF_GRID,
        'hybrid': GridConnectionType.HYBRID,
    }
    return mapping.get(grid_type, GridConnectionType.ON_GRID)


def map_disco_provider(disco: Optional[str]) -> Optional[DiscoProvider]:
    """Map string to DiscoProvider enum."""
    if disco is None:
        return None
    mapping = {
        'lesco': DiscoProvider.LESCO,
        'fesco': DiscoProvider.FESCO,
        'iesco': DiscoProvider.IESCO,
        'gepco': DiscoProvider.GEPCO,
        'mepco': DiscoProvider.MEPCO,
        'pesco': DiscoProvider.PESCO,
        'hesco': DiscoProvider.HESCO,
        'sepco': DiscoProvider.SEPCO,
        'qesco': DiscoProvider.QESCO,
        'tesco': DiscoProvider.TESCO,
        'kelectric': DiscoProvider.KELECTRIC,
    }
    return mapping.get(disco)


def site_to_response(site: Site) -> SiteResponse:
    """Convert Site domain entity to response schema."""
    return SiteResponse(
        id=site.id,
        organization_id=site.organization_id,
        name=site.name,
        description=site.description,
        address=AddressSchema(
            street=site.address.street,
            city=site.address.city,
            state=site.address.state,
            postal_code=site.address.postal_code,
            country=site.address.country,
        ),
        geo_location=GeoLocationSchema(
            latitude=site.geo_location.latitude,
            longitude=site.geo_location.longitude,
        ),
        timezone=site.timezone,
        status=site.status.value,
        site_type=site.site_type.value,
        configuration=SiteConfigurationSchema(
            system_capacity_kw=site.configuration.system_capacity_kw,
            panel_count=site.configuration.panel_count,
            panel_wattage=site.configuration.panel_wattage,
            inverter_capacity_kw=site.configuration.inverter_capacity_kw,
            inverter_count=site.configuration.inverter_count,
            battery_capacity_kwh=site.configuration.battery_capacity_kwh,
            battery_count=site.configuration.battery_count,
            grid_connection_type=site.configuration.grid_connection_type.value,
            net_metering_enabled=site.configuration.net_metering_enabled,
            disco_provider=site.configuration.disco_provider.value if site.configuration.disco_provider else None,
            tariff_category=site.configuration.tariff_category,
            reference_number=site.configuration.reference_number,
        ),
        commissioned_at=site.commissioned_at,
        created_at=site.created_at,
        updated_at=site.updated_at,
    )


@router.post(
    "",
    response_model=SiteResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_site(
    request: SiteCreate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Create a new solar site."""
    # Check organization access
    org = await uow.organizations.get_by_id(request.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    await get_org_and_check_access(request.organization_id, current_user, uow, require_manage=True)

    # Check site limit
    site_count = await uow.sites.count_by_organization_id(request.organization_id)
    if site_count >= org.settings.max_sites:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization has reached maximum site limit ({org.settings.max_sites})",
        )

    # Create address
    address = Address(
        street=request.address.street,
        city=request.address.city,
        state=request.address.state,
        postal_code=request.address.postal_code,
        country=request.address.country,
    )

    # Create geo location
    geo_location = GeoLocation(
        latitude=request.geo_location.latitude,
        longitude=request.geo_location.longitude,
    )

    # Create configuration
    config = SiteConfiguration(
        system_capacity_kw=request.configuration.system_capacity_kw,
        panel_count=request.configuration.panel_count,
        panel_wattage=request.configuration.panel_wattage,
        inverter_capacity_kw=request.configuration.inverter_capacity_kw,
        inverter_count=request.configuration.inverter_count,
        battery_capacity_kwh=request.configuration.battery_capacity_kwh,
        battery_count=request.configuration.battery_count,
        grid_connection_type=map_grid_connection(request.configuration.grid_connection_type),
        net_metering_enabled=request.configuration.net_metering_enabled,
        disco_provider=map_disco_provider(request.configuration.disco_provider),
        tariff_category=request.configuration.tariff_category,
        reference_number=request.configuration.reference_number,
    )

    # Determine site type based on configuration
    site_type = SiteType.COMMERCIAL
    if config.system_capacity_kw <= 10:
        site_type = SiteType.RESIDENTIAL
    elif config.system_capacity_kw >= 500:
        site_type = SiteType.UTILITY

    # Create site
    site = Site(
        organization_id=request.organization_id,
        name=request.name,
        description=request.description,
        address=address,
        geo_location=geo_location,
        timezone=request.timezone,
        site_type=site_type,
        configuration=config,
    )

    saved_site = await uow.sites.add(site)
    await uow.commit()

    return site_to_response(saved_site)


@router.get(
    "",
    response_model=SiteListResponse,
)
async def list_sites(
    organization_id: Optional[UUID] = Query(None, description="Filter by organization"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List sites the user has access to."""
    offset = (page - 1) * page_size

    if organization_id:
        # List sites for specific organization
        await get_org_and_check_access(organization_id, current_user, uow)

        sites = await uow.sites.get_by_organization_id(
            organization_id=organization_id,
            limit=page_size,
            offset=offset,
            status=status_filter,
        )
        total = await uow.sites.count_by_organization_id(organization_id, status=status_filter)
    else:
        # List sites across all user's organizations
        orgs = await uow.organizations.get_by_member_id(current_user.id)

        all_sites = []
        total = 0

        for org in orgs:
            org_sites = await uow.sites.get_by_organization_id(
                organization_id=org.id,
                limit=1000,  # Get all, we'll paginate later
                status=status_filter,
            )
            all_sites.extend(org_sites)
            total += await uow.sites.count_by_organization_id(org.id, status=status_filter)

        # Manual pagination
        sites = all_sites[offset:offset + page_size]

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return SiteListResponse(
        items=[site_to_response(s) for s in sites],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{site_id}",
    response_model=SiteDetailResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_site(
    site_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get site details."""
    site = await uow.sites.get_by_id(site_id)

    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    # Check access
    await get_org_and_check_access(site.organization_id, current_user, uow)

    # Get device counts
    device_count = await uow.devices.count_by_site_id(site_id)
    online_devices = await uow.devices.get_online_devices(site_id)
    online_device_count = len(online_devices)

    # TODO: Get alert count when alert repository is implemented
    alert_count = 0

    base_response = site_to_response(site)

    return SiteDetailResponse(
        **base_response.model_dump(),
        device_count=device_count,
        online_device_count=online_device_count,
        alert_count=alert_count,
    )


@router.put(
    "/{site_id}",
    response_model=SiteResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def update_site(
    site_id: UUID,
    request: SiteUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update site details."""
    site = await uow.sites.get_by_id(site_id)

    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    # Check access
    await get_org_and_check_access(site.organization_id, current_user, uow, require_manage=True)

    # Update fields
    if request.name is not None:
        site.name = request.name
    if request.description is not None:
        site.description = request.description

    if request.address is not None:
        site.address = Address(
            street=request.address.street,
            city=request.address.city,
            state=request.address.state,
            postal_code=request.address.postal_code,
            country=request.address.country,
        )

    if request.geo_location is not None:
        site.geo_location = GeoLocation(
            latitude=request.geo_location.latitude,
            longitude=request.geo_location.longitude,
        )

    if request.timezone is not None:
        site.timezone = request.timezone

    if request.configuration is not None:
        site.configuration = SiteConfiguration(
            system_capacity_kw=request.configuration.system_capacity_kw,
            panel_count=request.configuration.panel_count,
            panel_wattage=request.configuration.panel_wattage,
            inverter_capacity_kw=request.configuration.inverter_capacity_kw,
            inverter_count=request.configuration.inverter_count,
            battery_capacity_kwh=request.configuration.battery_capacity_kwh,
            battery_count=request.configuration.battery_count,
            grid_connection_type=map_grid_connection(request.configuration.grid_connection_type),
            net_metering_enabled=request.configuration.net_metering_enabled,
            disco_provider=map_disco_provider(request.configuration.disco_provider),
            tariff_category=request.configuration.tariff_category,
            reference_number=request.configuration.reference_number,
        )

    site.mark_updated()
    updated_site = await uow.sites.update(site)
    await uow.commit()

    return site_to_response(updated_site)


@router.put(
    "/{site_id}/status",
    response_model=SiteResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def update_site_status(
    site_id: UUID,
    request: SiteStatusUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update site status."""
    site = await uow.sites.get_by_id(site_id)

    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    # Check access
    await get_org_and_check_access(site.organization_id, current_user, uow, require_manage=True)

    # Map status
    status_map = {
        'active': SiteStatus.ACTIVE,
        'inactive': SiteStatus.INACTIVE,
        'maintenance': SiteStatus.MAINTENANCE,
        'decommissioned': SiteStatus.DECOMMISSIONED,
    }
    new_status = status_map.get(request.status)

    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status",
        )

    # Use domain method for status change
    if new_status == SiteStatus.ACTIVE:
        site.activate()
    elif new_status == SiteStatus.INACTIVE:
        site.deactivate()
    elif new_status == SiteStatus.MAINTENANCE:
        site.set_maintenance()
    elif new_status == SiteStatus.DECOMMISSIONED:
        site.decommission()

    await uow.sites.update(site)
    await uow.commit()

    return site_to_response(site)


@router.delete(
    "/{site_id}",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def delete_site(
    site_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Delete a site."""
    site = await uow.sites.get_by_id(site_id)

    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    # Check access - require admin level
    org = await uow.organizations.get_by_id(site.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    is_owner = org.owner_id == current_user.id
    member = org.get_member(current_user.id)
    is_admin = member and member.role in [UserRole.ADMIN]

    if not is_owner and not is_admin and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner or admin can delete sites",
        )

    # Check for devices
    device_count = await uow.devices.count_by_site_id(site_id)
    if device_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete site with {device_count} registered devices. Remove devices first.",
        )

    await uow.sites.delete(site_id)
    await uow.commit()

    return MessageResponse(
        message="Site deleted successfully",
        success=True,
    )


@router.get(
    "/{site_id}/summary",
    response_model=SiteSummaryResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_site_summary(
    site_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get site summary for dashboard."""
    site = await uow.sites.get_by_id(site_id)

    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    # Check access
    await get_org_and_check_access(site.organization_id, current_user, uow)

    # Get device counts
    device_count = await uow.devices.count_by_site_id(site_id)
    online_devices = await uow.devices.get_online_devices(site_id)

    # TODO: Get actual power and energy from telemetry system
    # For now, return placeholder values
    return SiteSummaryResponse(
        id=site.id,
        name=site.name,
        status=site.status.value,
        device_count=device_count,
        online_devices=len(online_devices),
        current_power_kw=0.0,
        daily_energy_kwh=0.0,
        monthly_energy_kwh=0.0,
    )
