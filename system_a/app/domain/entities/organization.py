"""
Organization domain entity and related value objects.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from .base import AggregateRoot, Entity, utc_now
from .user import UserRole
from ..exceptions import ValidationException, BusinessRuleViolationException, EntityNotFoundException


class OrganizationStatus(str, Enum):
    """Organization status."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class MembershipStatus(str, Enum):
    """Organization membership status."""
    PENDING = "pending"    # Invitation sent
    ACTIVE = "active"      # Member accepted
    REMOVED = "removed"    # Member removed


@dataclass(frozen=True)
class OrganizationSettings:
    """Organization-level settings (value object)."""
    default_timezone: str = "Asia/Karachi"
    default_currency: str = "PKR"
    default_language: str = "en"
    billing_email: Optional[str] = None
    support_email: Optional[str] = None
    max_sites: int = 100
    max_users: int = 50
    max_devices_per_site: int = 100
    alert_notifications_enabled: bool = True
    daily_report_enabled: bool = True
    weekly_report_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'default_timezone': self.default_timezone,
            'default_currency': self.default_currency,
            'default_language': self.default_language,
            'billing_email': self.billing_email,
            'support_email': self.support_email,
            'max_sites': self.max_sites,
            'max_users': self.max_users,
            'max_devices_per_site': self.max_devices_per_site,
            'alert_notifications_enabled': self.alert_notifications_enabled,
            'daily_report_enabled': self.daily_report_enabled,
            'weekly_report_enabled': self.weekly_report_enabled
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrganizationSettings':
        """Create from dictionary."""
        return cls(
            default_timezone=data.get('default_timezone', 'Asia/Karachi'),
            default_currency=data.get('default_currency', 'PKR'),
            default_language=data.get('default_language', 'en'),
            billing_email=data.get('billing_email'),
            support_email=data.get('support_email'),
            max_sites=data.get('max_sites', 100),
            max_users=data.get('max_users', 50),
            max_devices_per_site=data.get('max_devices_per_site', 100),
            alert_notifications_enabled=data.get('alert_notifications_enabled', True),
            daily_report_enabled=data.get('daily_report_enabled', True),
            weekly_report_enabled=data.get('weekly_report_enabled', True)
        )


@dataclass(kw_only=True)
class OrganizationMember(Entity):
    """
    Represents a user's membership in an organization.

    This is an entity within the Organization aggregate.
    """
    organization_id: UUID
    user_id: UUID
    role: UserRole
    status: MembershipStatus = MembershipStatus.PENDING
    invited_by: Optional[UUID] = None
    invited_at: datetime = field(default_factory=utc_now)
    accepted_at: Optional[datetime] = None

    def accept(self) -> None:
        """Accept membership invitation."""
        if self.status != MembershipStatus.PENDING:
            raise BusinessRuleViolationException(
                message="Cannot accept - membership is not pending",
                rule="membership_acceptance"
            )
        self.status = MembershipStatus.ACTIVE
        self.accepted_at = utc_now()
        self.mark_updated()

    def remove(self) -> None:
        """Remove member from organization."""
        if self.status == MembershipStatus.REMOVED:
            raise BusinessRuleViolationException(
                message="Member already removed",
                rule="membership_removal"
            )
        self.status = MembershipStatus.REMOVED
        self.mark_updated()

    def change_role(self, new_role: UserRole) -> None:
        """Change member's role in organization."""
        self.role = new_role
        self.mark_updated()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'user_id': str(self.user_id),
            'role': self.role.value,
            'status': self.status.value,
            'invited_by': str(self.invited_by) if self.invited_by else None,
            'invited_at': self.invited_at.isoformat(),
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'created_at': self.created_at.isoformat()
        }


@dataclass(kw_only=True)
class Organization(AggregateRoot):
    """
    Organization aggregate root.

    An organization is the top-level entity that owns sites, devices,
    and has members (users).
    """
    name: str
    owner_id: UUID
    slug: str = ""
    description: Optional[str] = None
    status: OrganizationStatus = OrganizationStatus.ACTIVE
    settings: OrganizationSettings = field(default_factory=OrganizationSettings)
    members: List[OrganizationMember] = field(default_factory=list)
    site_count: int = 0

    def __post_init__(self) -> None:
        """Validate and initialize organization."""
        self._validate()
        if not self.slug:
            self.slug = self._generate_slug(self.name)

    def _validate(self) -> None:
        """Validate organization data."""
        errors = {}

        if not self.name or len(self.name.strip()) < 2:
            errors['name'] = ['Organization name must be at least 2 characters']

        if len(self.name) > 200:
            errors['name'] = ['Organization name cannot exceed 200 characters']

        if self.description and len(self.description) > 1000:
            errors['description'] = ['Description cannot exceed 1000 characters']

        if errors:
            raise ValidationException(
                message="Invalid organization data",
                errors=errors
            )

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        import re
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug[:100]

    @property
    def is_active(self) -> bool:
        """Check if organization is active."""
        return self.status == OrganizationStatus.ACTIVE

    @property
    def active_members(self) -> List[OrganizationMember]:
        """Get list of active members."""
        return [m for m in self.members if m.status == MembershipStatus.ACTIVE]

    @property
    def member_count(self) -> int:
        """Get count of active members."""
        return len(self.active_members)

    def get_member(self, user_id: UUID) -> Optional[OrganizationMember]:
        """Get member by user ID."""
        for member in self.members:
            if member.user_id == user_id and member.status != MembershipStatus.REMOVED:
                return member
        return None

    def is_member(self, user_id: UUID) -> bool:
        """Check if user is an active member."""
        member = self.get_member(user_id)
        return member is not None and member.status == MembershipStatus.ACTIVE

    def is_owner(self, user_id: UUID) -> bool:
        """Check if user is the organization owner."""
        return self.owner_id == user_id

    def can_manage(self, user_id: UUID) -> bool:
        """Check if user can manage organization (owner or admin)."""
        if self.is_owner(user_id):
            return True
        member = self.get_member(user_id)
        if member and member.status == MembershipStatus.ACTIVE:
            return member.role in (UserRole.OWNER, UserRole.ADMIN)
        return False

    def add_member(
        self,
        user_id: UUID,
        role: UserRole,
        invited_by: UUID
    ) -> OrganizationMember:
        """
        Add a new member to the organization.

        Args:
            user_id: User ID to add
            role: Role for the new member
            invited_by: User ID who invited this member

        Returns:
            Created OrganizationMember

        Raises:
            BusinessRuleViolationException: If user is already a member or limits exceeded
        """
        # Check if already a member
        existing = self.get_member(user_id)
        if existing and existing.status != MembershipStatus.REMOVED:
            raise BusinessRuleViolationException(
                message="User is already a member of this organization",
                rule="duplicate_member"
            )

        # Check member limit
        if len(self.active_members) >= self.settings.max_users:
            raise BusinessRuleViolationException(
                message=f"Organization member limit ({self.settings.max_users}) reached",
                rule="member_limit"
            )

        member = OrganizationMember(
            organization_id=self.id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
            status=MembershipStatus.PENDING
        )
        self.members.append(member)
        self.mark_updated()

        from ..events.organization_events import MemberInvited
        self.add_domain_event(MemberInvited(
            organization_id=self.id,
            user_id=user_id,
            role=role.value,
            invited_by=invited_by
        ))

        return member

    def accept_invitation(self, user_id: UUID) -> None:
        """Accept membership invitation."""
        member = self.get_member(user_id)
        if not member:
            raise EntityNotFoundException(
                entity_type="OrganizationMember",
                entity_id=user_id
            )

        member.accept()
        self.mark_updated()

        from ..events.organization_events import MemberAccepted
        self.add_domain_event(MemberAccepted(
            organization_id=self.id,
            user_id=user_id
        ))

    def remove_member(self, user_id: UUID, removed_by: UUID) -> None:
        """Remove member from organization."""
        if user_id == self.owner_id:
            raise BusinessRuleViolationException(
                message="Cannot remove organization owner",
                rule="owner_removal"
            )

        member = self.get_member(user_id)
        if not member:
            raise EntityNotFoundException(
                entity_type="OrganizationMember",
                entity_id=user_id
            )

        member.remove()
        self.mark_updated()

        from ..events.organization_events import MemberRemoved
        self.add_domain_event(MemberRemoved(
            organization_id=self.id,
            user_id=user_id,
            removed_by=removed_by
        ))

    def change_member_role(
        self,
        user_id: UUID,
        new_role: UserRole,
        changed_by: UUID
    ) -> None:
        """Change a member's role."""
        member = self.get_member(user_id)
        if not member:
            raise EntityNotFoundException(
                entity_type="OrganizationMember",
                entity_id=user_id
            )

        old_role = member.role
        member.change_role(new_role)
        self.mark_updated()

        from ..events.organization_events import MemberRoleChanged
        self.add_domain_event(MemberRoleChanged(
            organization_id=self.id,
            user_id=user_id,
            old_role=old_role.value,
            new_role=new_role.value,
            changed_by=changed_by
        ))

    def update_details(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """Update organization details."""
        if name is not None:
            self.name = name
            self.slug = self._generate_slug(name)
        if description is not None:
            self.description = description

        self._validate()
        self.mark_updated()

        from ..events.organization_events import OrganizationUpdated
        self.add_domain_event(OrganizationUpdated(organization_id=self.id))

    def update_settings(self, settings: OrganizationSettings) -> None:
        """Update organization settings."""
        self.settings = settings
        self.mark_updated()

    def transfer_ownership(self, new_owner_id: UUID, transferred_by: UUID) -> None:
        """Transfer organization ownership to another member."""
        # Verify new owner is a member
        member = self.get_member(new_owner_id)
        if not member or member.status != MembershipStatus.ACTIVE:
            raise BusinessRuleViolationException(
                message="New owner must be an active member",
                rule="ownership_transfer"
            )

        old_owner_id = self.owner_id
        self.owner_id = new_owner_id

        # Update roles
        member.change_role(UserRole.OWNER)

        self.mark_updated()

        from ..events.organization_events import OwnershipTransferred
        self.add_domain_event(OwnershipTransferred(
            organization_id=self.id,
            old_owner_id=old_owner_id,
            new_owner_id=new_owner_id,
            transferred_by=transferred_by
        ))

    def suspend(self, reason: str, suspended_by: UUID) -> None:
        """Suspend organization."""
        if self.status == OrganizationStatus.SUSPENDED:
            raise BusinessRuleViolationException(
                message="Organization is already suspended",
                rule="organization_suspension"
            )

        self.status = OrganizationStatus.SUSPENDED
        self.mark_updated()

        from ..events.organization_events import OrganizationSuspended
        self.add_domain_event(OrganizationSuspended(
            organization_id=self.id,
            reason=reason,
            suspended_by=suspended_by
        ))

    def reactivate(self, reactivated_by: UUID) -> None:
        """Reactivate suspended organization."""
        if self.status != OrganizationStatus.SUSPENDED:
            raise BusinessRuleViolationException(
                message="Organization is not suspended",
                rule="organization_reactivation"
            )

        self.status = OrganizationStatus.ACTIVE
        self.mark_updated()

        from ..events.organization_events import OrganizationReactivated
        self.add_domain_event(OrganizationReactivated(
            organization_id=self.id,
            reactivated_by=reactivated_by
        ))

    def increment_site_count(self) -> None:
        """Increment site count (called when site is added)."""
        if self.site_count >= self.settings.max_sites:
            raise BusinessRuleViolationException(
                message=f"Organization site limit ({self.settings.max_sites}) reached",
                rule="site_limit"
            )
        self.site_count += 1
        self.mark_updated()

    def decrement_site_count(self) -> None:
        """Decrement site count (called when site is removed)."""
        if self.site_count > 0:
            self.site_count -= 1
            self.mark_updated()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize organization to dictionary."""
        return {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'description': self.description,
            'owner_id': str(self.owner_id),
            'status': self.status.value,
            'settings': self.settings.to_dict(),
            'member_count': self.member_count,
            'site_count': self.site_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def create(
        cls,
        name: str,
        owner_id: UUID,
        description: Optional[str] = None
    ) -> 'Organization':
        """
        Factory method to create a new organization.

        Args:
            name: Organization name
            owner_id: User ID of the organization owner
            description: Optional description

        Returns:
            New Organization instance with OrganizationCreated event
        """
        org = cls(
            name=name.strip(),
            owner_id=owner_id,
            description=description
        )

        # Add owner as first member
        owner_member = OrganizationMember(
            organization_id=org.id,
            user_id=owner_id,
            role=UserRole.OWNER,
            status=MembershipStatus.ACTIVE,
            accepted_at=utc_now()
        )
        org.members.append(owner_member)

        from ..events.organization_events import OrganizationCreated
        org.add_domain_event(OrganizationCreated(
            organization_id=org.id,
            name=org.name,
            owner_id=owner_id
        ))

        return org
