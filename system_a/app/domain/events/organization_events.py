"""
Organization domain events.
"""
from dataclasses import dataclass
from typing import Any, Dict
from uuid import UUID

from .base import DomainEvent


@dataclass
class OrganizationCreated(DomainEvent):
    """Event raised when a new organization is created."""
    organization_id: UUID
    name: str
    owner_id: UUID

    @property
    def event_type(self) -> str:
        return "organization.created"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id),
            'name': self.name,
            'owner_id': str(self.owner_id)
        }


@dataclass
class OrganizationUpdated(DomainEvent):
    """Event raised when organization details are updated."""
    organization_id: UUID

    @property
    def event_type(self) -> str:
        return "organization.updated"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id)
        }


@dataclass
class OrganizationSuspended(DomainEvent):
    """Event raised when organization is suspended."""
    organization_id: UUID
    reason: str
    suspended_by: UUID

    @property
    def event_type(self) -> str:
        return "organization.suspended"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id),
            'reason': self.reason,
            'suspended_by': str(self.suspended_by)
        }


@dataclass
class OrganizationReactivated(DomainEvent):
    """Event raised when organization is reactivated."""
    organization_id: UUID
    reactivated_by: UUID

    @property
    def event_type(self) -> str:
        return "organization.reactivated"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id),
            'reactivated_by': str(self.reactivated_by)
        }


@dataclass
class OwnershipTransferred(DomainEvent):
    """Event raised when organization ownership is transferred."""
    organization_id: UUID
    old_owner_id: UUID
    new_owner_id: UUID
    transferred_by: UUID

    @property
    def event_type(self) -> str:
        return "organization.ownership_transferred"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id),
            'old_owner_id': str(self.old_owner_id),
            'new_owner_id': str(self.new_owner_id),
            'transferred_by': str(self.transferred_by)
        }


@dataclass
class MemberInvited(DomainEvent):
    """Event raised when a user is invited to organization."""
    organization_id: UUID
    user_id: UUID
    role: str
    invited_by: UUID

    @property
    def event_type(self) -> str:
        return "organization.member_invited"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id),
            'user_id': str(self.user_id),
            'role': self.role,
            'invited_by': str(self.invited_by)
        }


@dataclass
class MemberAccepted(DomainEvent):
    """Event raised when invited member accepts invitation."""
    organization_id: UUID
    user_id: UUID

    @property
    def event_type(self) -> str:
        return "organization.member_accepted"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id),
            'user_id': str(self.user_id)
        }


@dataclass
class MemberRemoved(DomainEvent):
    """Event raised when member is removed from organization."""
    organization_id: UUID
    user_id: UUID
    removed_by: UUID

    @property
    def event_type(self) -> str:
        return "organization.member_removed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id),
            'user_id': str(self.user_id),
            'removed_by': str(self.removed_by)
        }


@dataclass
class MemberRoleChanged(DomainEvent):
    """Event raised when member's role is changed."""
    organization_id: UUID
    user_id: UUID
    old_role: str
    new_role: str
    changed_by: UUID

    @property
    def event_type(self) -> str:
        return "organization.member_role_changed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'organization_id': str(self.organization_id),
            'user_id': str(self.user_id),
            'old_role': self.old_role,
            'new_role': self.new_role,
            'changed_by': str(self.changed_by)
        }
