"""
Organization management API endpoints.
"""
import re
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
    require_admin,
)
from ..schemas.organization_schemas import (
    InviteMemberRequest,
    OrganizationCreate,
    OrganizationDetailResponse,
    OrganizationListResponse,
    OrganizationMemberResponse,
    OrganizationResponse,
    OrganizationSettingsSchema,
    OrganizationUpdate,
    TransferOwnershipRequest,
    UpdateMemberRoleRequest,
)
from ..schemas.auth_schemas import MessageResponse, ErrorResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User, UserRole
from ...domain.entities.organization import (
    Organization,
    OrganizationMember,
    OrganizationSettings,
    OrganizationStatus,
    MembershipStatus,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from name."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def user_can_manage_org(user: User, org: Organization) -> bool:
    """Check if user can manage organization."""
    if user.id == org.owner_id:
        return True
    member = org.get_member(user.id)
    if member and member.role in [UserRole.ADMIN, UserRole.MANAGER]:
        return True
    return False


def user_is_org_admin(user: User, org: Organization) -> bool:
    """Check if user is organization admin or owner."""
    if user.id == org.owner_id:
        return True
    member = org.get_member(user.id)
    if member and member.role == UserRole.ADMIN:
        return True
    return False


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def create_organization(
    request: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Create a new organization."""
    # Generate slug if not provided
    slug = request.slug or generate_slug(request.name)

    # Check if slug exists
    if await uow.organizations.slug_exists(slug):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization with this slug already exists",
        )

    # Create settings
    settings = OrganizationSettings()
    if request.settings:
        settings.max_sites = request.settings.max_sites
        settings.max_users = request.settings.max_users
        settings.alert_email_enabled = request.settings.alert_email_enabled
        settings.alert_sms_enabled = request.settings.alert_sms_enabled
        settings.report_frequency = request.settings.report_frequency
        settings.default_dashboard = request.settings.default_dashboard

    # Create organization
    org = Organization(
        name=request.name,
        slug=slug,
        description=request.description,
        owner_id=current_user.id,
        settings=settings,
    )

    # Add owner as admin member
    owner_member = OrganizationMember(
        user_id=current_user.id,
        organization_id=org.id,
        role=UserRole.OWNER,
        status=MembershipStatus.ACTIVE,
        invited_by=current_user.id,
    )
    owner_member.accept()
    org.members.append(owner_member)

    saved_org = await uow.organizations.add(org)
    await uow.commit()

    return OrganizationResponse(
        id=saved_org.id,
        name=saved_org.name,
        slug=saved_org.slug,
        description=saved_org.description,
        owner_id=saved_org.owner_id,
        status=saved_org.status.value,
        settings=OrganizationSettingsSchema(
            max_sites=saved_org.settings.max_sites,
            max_users=saved_org.settings.max_users,
            alert_email_enabled=saved_org.settings.alert_email_enabled,
            alert_sms_enabled=saved_org.settings.alert_sms_enabled,
            report_frequency=saved_org.settings.report_frequency,
            default_dashboard=saved_org.settings.default_dashboard,
        ),
        created_at=saved_org.created_at,
        updated_at=saved_org.updated_at,
    )


@router.get(
    "",
    response_model=OrganizationListResponse,
)
async def list_my_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List organizations the current user belongs to."""
    # Get organizations where user is a member
    orgs = await uow.organizations.get_by_member_id(current_user.id)

    # Manual pagination since we're filtering in memory
    total = len(orgs)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_orgs = orgs[start:end]
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return OrganizationListResponse(
        items=[
            OrganizationResponse(
                id=o.id,
                name=o.name,
                slug=o.slug,
                description=o.description,
                owner_id=o.owner_id,
                status=o.status.value,
                settings=OrganizationSettingsSchema(
                    max_sites=o.settings.max_sites,
                    max_users=o.settings.max_users,
                    alert_email_enabled=o.settings.alert_email_enabled,
                    alert_sms_enabled=o.settings.alert_sms_enabled,
                    report_frequency=o.settings.report_frequency,
                    default_dashboard=o.settings.default_dashboard,
                ),
                created_at=o.created_at,
                updated_at=o.updated_at,
            )
            for o in paginated_orgs
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{org_id}",
    response_model=OrganizationDetailResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def get_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get organization details."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check membership
    if not org.is_member(current_user.id) and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization",
        )

    # Get counts
    site_count = await uow.sites.count_by_organization_id(org_id)
    device_count = await uow.devices.count_by_organization_id(org_id)

    # Build member responses with user details
    member_responses = []
    for m in org.members:
        user = await uow.users.get_by_id(m.user_id)
        member_responses.append(OrganizationMemberResponse(
            id=m.id,
            user_id=m.user_id,
            organization_id=m.organization_id,
            role=m.role.value,
            status=m.status.value,
            invited_by=m.invited_by,
            invited_at=m.invited_at,
            accepted_at=m.accepted_at,
            email=user.email if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
        ))

    return OrganizationDetailResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        owner_id=org.owner_id,
        status=org.status.value,
        settings=OrganizationSettingsSchema(
            max_sites=org.settings.max_sites,
            max_users=org.settings.max_users,
            alert_email_enabled=org.settings.alert_email_enabled,
            alert_sms_enabled=org.settings.alert_sms_enabled,
            report_frequency=org.settings.report_frequency,
            default_dashboard=org.settings.default_dashboard,
        ),
        created_at=org.created_at,
        updated_at=org.updated_at,
        members=member_responses,
        site_count=site_count,
        device_count=device_count,
    )


@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def update_organization(
    org_id: UUID,
    request: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update organization details."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check permission
    if not user_can_manage_org(current_user, org):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this organization",
        )

    # Update fields
    if request.name is not None:
        org.name = request.name
    if request.description is not None:
        org.description = request.description
    if request.settings is not None:
        org.settings.max_sites = request.settings.max_sites
        org.settings.max_users = request.settings.max_users
        org.settings.alert_email_enabled = request.settings.alert_email_enabled
        org.settings.alert_sms_enabled = request.settings.alert_sms_enabled
        org.settings.report_frequency = request.settings.report_frequency
        org.settings.default_dashboard = request.settings.default_dashboard

    org.mark_updated()
    updated_org = await uow.organizations.update(org)
    await uow.commit()

    return OrganizationResponse(
        id=updated_org.id,
        name=updated_org.name,
        slug=updated_org.slug,
        description=updated_org.description,
        owner_id=updated_org.owner_id,
        status=updated_org.status.value,
        settings=OrganizationSettingsSchema(
            max_sites=updated_org.settings.max_sites,
            max_users=updated_org.settings.max_users,
            alert_email_enabled=updated_org.settings.alert_email_enabled,
            alert_sms_enabled=updated_org.settings.alert_sms_enabled,
            report_frequency=updated_org.settings.report_frequency,
            default_dashboard=updated_org.settings.default_dashboard,
        ),
        created_at=updated_org.created_at,
        updated_at=updated_org.updated_at,
    )


@router.delete(
    "/{org_id}",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def delete_organization(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Delete an organization (owner only)."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Only owner can delete
    if org.owner_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the organization owner can delete it",
        )

    # Check for existing sites
    site_count = await uow.sites.count_by_organization_id(org_id)
    if site_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete organization with {site_count} active sites. Delete sites first.",
        )

    await uow.organizations.delete(org_id)
    await uow.commit()

    return MessageResponse(
        message="Organization deleted successfully",
        success=True,
    )


# Member management endpoints

@router.get(
    "/{org_id}/members",
    response_model=list[OrganizationMemberResponse],
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def list_organization_members(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List organization members."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check membership
    if not org.is_member(current_user.id) and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization",
        )

    member_responses = []
    for m in org.members:
        user = await uow.users.get_by_id(m.user_id)
        member_responses.append(OrganizationMemberResponse(
            id=m.id,
            user_id=m.user_id,
            organization_id=m.organization_id,
            role=m.role.value,
            status=m.status.value,
            invited_by=m.invited_by,
            invited_at=m.invited_at,
            accepted_at=m.accepted_at,
            email=user.email if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None,
        ))

    return member_responses


@router.post(
    "/{org_id}/invite",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def invite_member(
    org_id: UUID,
    request: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Invite a user to the organization."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check permission
    if not user_is_org_admin(current_user, org):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to invite members",
        )

    # Check member limit
    active_members = len([m for m in org.members if m.status == MembershipStatus.ACTIVE])
    if active_members >= org.settings.max_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization has reached maximum member limit ({org.settings.max_users})",
        )

    # Find user by email
    user = await uow.users.get_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found",
        )

    # Check if already a member
    if org.is_member(user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization",
        )

    # Map role string to enum
    role_map = {
        'viewer': UserRole.VIEWER,
        'installer': UserRole.INSTALLER,
        'manager': UserRole.MANAGER,
        'admin': UserRole.ADMIN,
    }
    role = role_map.get(request.role, UserRole.VIEWER)

    # Add member
    org.add_member(
        user_id=user.id,
        role=role,
        invited_by=current_user.id,
    )

    await uow.organizations.update(org)
    await uow.commit()

    # Get the newly added member
    new_member = org.get_member(user.id)

    return OrganizationMemberResponse(
        id=new_member.id,
        user_id=new_member.user_id,
        organization_id=new_member.organization_id,
        role=new_member.role.value,
        status=new_member.status.value,
        invited_by=new_member.invited_by,
        invited_at=new_member.invited_at,
        accepted_at=new_member.accepted_at,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
    )


@router.post(
    "/{org_id}/members/{member_id}/accept",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def accept_invitation(
    org_id: UUID,
    member_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Accept an organization invitation."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    member = next((m for m in org.members if m.id == member_id), None)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Only the invited user can accept
    if member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only accept your own invitations",
        )

    if member.status == MembershipStatus.ACTIVE:
        return MessageResponse(
            message="Invitation already accepted",
            success=True,
        )

    org.accept_invitation(current_user.id)
    await uow.organizations.update(org)
    await uow.commit()

    return MessageResponse(
        message="Invitation accepted successfully",
        success=True,
    )


@router.put(
    "/{org_id}/members/{user_id}/role",
    response_model=OrganizationMemberResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    request: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update a member's role in the organization."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check permission - only owner or admin can change roles
    if not user_is_org_admin(current_user, org):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to change member roles",
        )

    member = org.get_member(user_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # Cannot change owner's role
    if member.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change the owner's role. Use transfer ownership instead.",
        )

    # Map role string to enum
    role_map = {
        'viewer': UserRole.VIEWER,
        'installer': UserRole.INSTALLER,
        'manager': UserRole.MANAGER,
        'admin': UserRole.ADMIN,
    }
    new_role = role_map.get(request.role, UserRole.VIEWER)

    member.role = new_role
    member.mark_updated()

    await uow.organizations.update(org)
    await uow.commit()

    user = await uow.users.get_by_id(user_id)

    return OrganizationMemberResponse(
        id=member.id,
        user_id=member.user_id,
        organization_id=member.organization_id,
        role=member.role.value,
        status=member.status.value,
        invited_by=member.invited_by,
        invited_at=member.invited_at,
        accepted_at=member.accepted_at,
        email=user.email if user else None,
        first_name=user.first_name if user else None,
        last_name=user.last_name if user else None,
    )


@router.delete(
    "/{org_id}/members/{user_id}",
    response_model=MessageResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Remove a member from the organization."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    member = org.get_member(user_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    # Users can remove themselves
    is_self = user_id == current_user.id

    # Or admins can remove others
    if not is_self and not user_is_org_admin(current_user, org):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to remove members",
        )

    # Cannot remove owner
    if member.role == UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the organization owner",
        )

    org.remove_member(user_id)
    await uow.organizations.update(org)
    await uow.commit()

    return MessageResponse(
        message="Member removed successfully",
        success=True,
    )


@router.post(
    "/{org_id}/transfer-ownership",
    response_model=OrganizationResponse,
    responses={404: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def transfer_ownership(
    org_id: UUID,
    request: TransferOwnershipRequest,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Transfer organization ownership to another member."""
    org = await uow.organizations.get_by_id(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Only owner can transfer ownership
    if org.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can transfer ownership",
        )

    # New owner must be an existing member
    if not org.is_member(request.new_owner_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New owner must be an existing member of the organization",
        )

    org.transfer_ownership(request.new_owner_id)
    await uow.organizations.update(org)
    await uow.commit()

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        owner_id=org.owner_id,
        status=org.status.value,
        settings=OrganizationSettingsSchema(
            max_sites=org.settings.max_sites,
            max_users=org.settings.max_users,
            alert_email_enabled=org.settings.alert_email_enabled,
            alert_sms_enabled=org.settings.alert_sms_enabled,
            report_frequency=org.settings.report_frequency,
            default_dashboard=org.settings.default_dashboard,
        ),
        created_at=org.created_at,
        updated_at=org.updated_at,
    )
