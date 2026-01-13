"""
Site domain events.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from .base import DomainEvent


@dataclass
class SiteCreated(DomainEvent):
    """Event raised when a new site is created."""
    site_id: UUID
    organization_id: UUID
    name: str
    city: str

    @property
    def event_type(self) -> str:
        return "site.created"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'site_id': str(self.site_id),
            'organization_id': str(self.organization_id),
            'name': self.name,
            'city': self.city
        }


@dataclass
class SiteUpdated(DomainEvent):
    """Event raised when site details are updated."""
    site_id: UUID

    @property
    def event_type(self) -> str:
        return "site.updated"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'site_id': str(self.site_id)
        }


@dataclass
class SiteConfigured(DomainEvent):
    """Event raised when site configuration is set or updated."""
    site_id: UUID
    system_capacity_kw: float

    @property
    def event_type(self) -> str:
        return "site.configured"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'site_id': str(self.site_id),
            'system_capacity_kw': self.system_capacity_kw
        }


@dataclass
class SiteStatusChanged(DomainEvent):
    """Event raised when site status changes."""
    site_id: UUID
    old_status: str
    new_status: str
    changed_by: UUID
    reason: Optional[str] = None

    @property
    def event_type(self) -> str:
        return "site.status_changed"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'site_id': str(self.site_id),
            'old_status': self.old_status,
            'new_status': self.new_status,
            'changed_by': str(self.changed_by),
            'reason': self.reason
        }


@dataclass
class SiteDecommissioned(DomainEvent):
    """Event raised when site is permanently decommissioned."""
    site_id: UUID
    organization_id: UUID
    reason: str
    decommissioned_by: UUID

    @property
    def event_type(self) -> str:
        return "site.decommissioned"

    def _get_event_data(self) -> Dict[str, Any]:
        return {
            'site_id': str(self.site_id),
            'organization_id': str(self.organization_id),
            'reason': self.reason,
            'decommissioned_by': str(self.decommissioned_by)
        }
