"""
Repository interfaces (ports) for domain entities.

These interfaces define the contract for persistence operations
without specifying the implementation details.
"""
from abc import ABC, abstractmethod
from typing import Generic, List, Optional, TypeVar
from uuid import UUID

from ...domain.entities.user import User
from ...domain.entities.organization import Organization
from ...domain.entities.site import Site
from ...domain.entities.device import Device
from ...domain.entities.alert import Alert, AlertRule


# Generic type for entities
T = TypeVar('T')


class Repository(ABC, Generic[T]):
    """
    Base repository interface.

    Defines common CRUD operations for all repositories.
    """

    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            id: Entity UUID

        Returns:
            Entity if found, None otherwise
        """
        pass

    @abstractmethod
    async def add(self, entity: T) -> T:
        """
        Add new entity.

        Args:
            entity: Entity to add

        Returns:
            Added entity with generated ID
        """
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """
        Update existing entity.

        Args:
            entity: Entity to update

        Returns:
            Updated entity
        """
        pass

    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """
        Delete entity by ID.

        Args:
            id: Entity UUID

        Returns:
            True if deleted, False if not found
        """
        pass


class UserRepository(Repository[User]):
    """Repository interface for User entities."""

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        pass

    @abstractmethod
    async def get_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number."""
        pass

    @abstractmethod
    async def email_exists(self, email: str) -> bool:
        """Check if email is already registered."""
        pass

    @abstractmethod
    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[User]:
        """List users with pagination and optional filtering."""
        pass

    @abstractmethod
    async def count(self, status: Optional[str] = None) -> int:
        """Count total users with optional status filter."""
        pass


class OrganizationRepository(Repository[Organization]):
    """Repository interface for Organization entities."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by URL slug."""
        pass

    @abstractmethod
    async def get_by_owner_id(self, owner_id: UUID) -> List[Organization]:
        """Get organizations owned by a user."""
        pass

    @abstractmethod
    async def get_by_member_id(self, user_id: UUID) -> List[Organization]:
        """Get organizations where user is a member."""
        pass

    @abstractmethod
    async def slug_exists(self, slug: str) -> bool:
        """Check if organization slug is already taken."""
        pass

    @abstractmethod
    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Organization]:
        """List organizations with pagination."""
        pass

    @abstractmethod
    async def count(self, status: Optional[str] = None) -> int:
        """Count total organizations."""
        pass


class SiteRepository(Repository[Site]):
    """Repository interface for Site entities."""

    @abstractmethod
    async def get_by_organization_id(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Site]:
        """Get sites belonging to an organization."""
        pass

    @abstractmethod
    async def count_by_organization_id(
        self,
        organization_id: UUID,
        status: Optional[str] = None
    ) -> int:
        """Count sites in an organization."""
        pass

    @abstractmethod
    async def get_active_sites(self, organization_id: UUID) -> List[Site]:
        """Get all active sites for an organization."""
        pass

    @abstractmethod
    async def search_by_name(
        self,
        organization_id: UUID,
        name_query: str,
        limit: int = 20
    ) -> List[Site]:
        """Search sites by name within an organization."""
        pass

    @abstractmethod
    async def get_sites_by_city(
        self,
        city: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Site]:
        """Get sites in a specific city."""
        pass


class DeviceRepository(Repository[Device]):
    """Repository interface for Device entities."""

    @abstractmethod
    async def get_by_serial_number(self, serial_number: str) -> Optional[Device]:
        """Get device by serial number."""
        pass

    @abstractmethod
    async def get_by_site_id(
        self,
        site_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Device]:
        """Get devices at a specific site."""
        pass

    @abstractmethod
    async def get_by_organization_id(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        device_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Device]:
        """Get devices belonging to an organization."""
        pass

    @abstractmethod
    async def count_by_site_id(self, site_id: UUID, status: Optional[str] = None) -> int:
        """Count devices at a site."""
        pass

    @abstractmethod
    async def count_by_organization_id(
        self,
        organization_id: UUID,
        device_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """Count devices in an organization."""
        pass

    @abstractmethod
    async def serial_number_exists(self, serial_number: str) -> bool:
        """Check if serial number is already registered."""
        pass

    @abstractmethod
    async def get_online_devices(self, site_id: UUID) -> List[Device]:
        """Get online devices at a site."""
        pass

    @abstractmethod
    async def get_offline_devices(
        self,
        organization_id: UUID,
        threshold_minutes: int = 5
    ) -> List[Device]:
        """Get devices that have been offline for specified time."""
        pass

    @abstractmethod
    async def get_devices_with_errors(self, organization_id: UUID) -> List[Device]:
        """Get devices currently in error state."""
        pass

    @abstractmethod
    async def update_device_status(
        self,
        device_id: UUID,
        status: str,
        last_seen_at: Optional[str] = None
    ) -> bool:
        """Update device status efficiently (for bulk operations)."""
        pass


class AlertRuleRepository(Repository[AlertRule]):
    """Repository interface for AlertRule entities."""

    @abstractmethod
    async def get_by_organization_id(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        is_active: Optional[bool] = None
    ) -> List[AlertRule]:
        """Get alert rules for an organization."""
        pass

    @abstractmethod
    async def get_by_site_id(
        self,
        site_id: UUID,
        is_active: Optional[bool] = None
    ) -> List[AlertRule]:
        """Get alert rules for a specific site."""
        pass

    @abstractmethod
    async def get_active_rules_for_metric(
        self,
        organization_id: UUID,
        metric: str,
        site_id: Optional[UUID] = None
    ) -> List[AlertRule]:
        """Get active rules that monitor a specific metric."""
        pass

    @abstractmethod
    async def count_by_organization_id(
        self,
        organization_id: UUID,
        is_active: Optional[bool] = None
    ) -> int:
        """Count alert rules in an organization."""
        pass


class AlertRepository(Repository[Alert]):
    """Repository interface for Alert entities."""

    @abstractmethod
    async def get_by_organization_id(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Alert]:
        """Get alerts for an organization."""
        pass

    @abstractmethod
    async def get_by_site_id(
        self,
        site_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Alert]:
        """Get alerts for a specific site."""
        pass

    @abstractmethod
    async def get_by_device_id(
        self,
        device_id: UUID,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List[Alert]:
        """Get alerts for a specific device."""
        pass

    @abstractmethod
    async def get_active_alerts(
        self,
        organization_id: UUID,
        site_id: Optional[UUID] = None
    ) -> List[Alert]:
        """Get all active (unresolved) alerts."""
        pass

    @abstractmethod
    async def get_critical_alerts(
        self,
        organization_id: UUID,
        site_id: Optional[UUID] = None
    ) -> List[Alert]:
        """Get critical severity active alerts."""
        pass

    @abstractmethod
    async def count_by_organization_id(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> int:
        """Count alerts in an organization."""
        pass

    @abstractmethod
    async def count_by_site_id(
        self,
        site_id: UUID,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> int:
        """Count alerts for a site."""
        pass

    @abstractmethod
    async def get_unacknowledged_alerts_past_escalation(
        self,
        escalation_threshold_minutes: int
    ) -> List[Alert]:
        """Get alerts that should be escalated."""
        pass
