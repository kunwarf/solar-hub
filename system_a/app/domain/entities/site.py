"""
Site domain entity and related value objects.
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from .base import AggregateRoot, utc_now
from ..value_objects.address import Address, GeoLocation
from ..exceptions import ValidationException, BusinessRuleViolationException


class SiteStatus(str, Enum):
    """Site operational status."""
    PENDING_SETUP = "pending_setup"    # Initial setup
    COMMISSIONING = "commissioning"    # Being commissioned
    ACTIVE = "active"                  # Fully operational
    MAINTENANCE = "maintenance"        # Under maintenance
    OFFLINE = "offline"                # Temporarily offline
    DECOMMISSIONED = "decommissioned"  # Permanently decommissioned


class SiteType(str, Enum):
    """Type of solar installation."""
    RESIDENTIAL = "residential"        # Home installation
    COMMERCIAL = "commercial"          # Business/office
    INDUSTRIAL = "industrial"          # Factory/warehouse
    UTILITY = "utility"                # Large-scale utility
    AGRICULTURAL = "agricultural"      # Farm installation


class GridConnectionType(str, Enum):
    """Type of grid connection."""
    ON_GRID = "on_grid"               # Connected to grid
    OFF_GRID = "off_grid"             # Standalone
    HYBRID = "hybrid"                  # Grid + Battery backup


class DiscoProvider(str, Enum):
    """Pakistani electricity distribution companies."""
    LESCO = "LESCO"           # Lahore
    FESCO = "FESCO"           # Faisalabad
    IESCO = "IESCO"           # Islamabad
    GEPCO = "GEPCO"           # Gujranwala
    MEPCO = "MEPCO"           # Multan
    PESCO = "PESCO"           # Peshawar
    HESCO = "HESCO"           # Hyderabad
    SEPCO = "SEPCO"           # Sukkur
    QESCO = "QESCO"           # Quetta
    TESCO = "TESCO"           # Tribal Areas
    KE = "KE"                 # K-Electric (Karachi)


@dataclass(frozen=True)
class SiteConfiguration:
    """
    Site solar system configuration (value object).

    Contains all technical details about the solar installation.
    """
    # System capacity
    system_capacity_kw: Decimal
    panel_count: int
    panel_wattage: Decimal
    panel_manufacturer: Optional[str] = None
    panel_model: Optional[str] = None

    # Inverter details
    inverter_capacity_kw: Decimal
    inverter_count: int = 1
    inverter_manufacturer: Optional[str] = None
    inverter_model: Optional[str] = None

    # Battery (optional)
    battery_capacity_kwh: Optional[Decimal] = None
    battery_count: int = 0
    battery_manufacturer: Optional[str] = None
    battery_model: Optional[str] = None

    # Grid connection
    grid_connection_type: GridConnectionType = GridConnectionType.ON_GRID
    net_metering_enabled: bool = False
    net_metering_capacity_kw: Optional[Decimal] = None
    sanctioned_load_kw: Optional[Decimal] = None

    # DISCO (Distribution Company) details
    disco_provider: Optional[DiscoProvider] = None
    tariff_category: Optional[str] = None  # e.g., "A-1", "B-2", "Industrial"
    consumer_reference: Optional[str] = None  # DISCO consumer number

    # Installation details
    installation_date: Optional[datetime] = None
    warranty_expiry: Optional[datetime] = None
    installer_company: Optional[str] = None

    # Array configuration
    tilt_angle: Optional[float] = None       # Panel tilt angle in degrees
    azimuth_angle: Optional[float] = None    # Panel direction (180 = South)
    mounting_type: Optional[str] = None      # "roof", "ground", "carport"

    def __post_init__(self) -> None:
        """Validate configuration."""
        errors = {}

        if self.system_capacity_kw <= 0:
            errors['system_capacity_kw'] = ['System capacity must be positive']

        if self.panel_count <= 0:
            errors['panel_count'] = ['Panel count must be positive']

        if self.panel_wattage <= 0:
            errors['panel_wattage'] = ['Panel wattage must be positive']

        if self.inverter_capacity_kw <= 0:
            errors['inverter_capacity_kw'] = ['Inverter capacity must be positive']

        if self.battery_capacity_kwh is not None and self.battery_capacity_kwh < 0:
            errors['battery_capacity_kwh'] = ['Battery capacity cannot be negative']

        if self.tilt_angle is not None and not 0 <= self.tilt_angle <= 90:
            errors['tilt_angle'] = ['Tilt angle must be between 0 and 90 degrees']

        if self.azimuth_angle is not None and not 0 <= self.azimuth_angle <= 360:
            errors['azimuth_angle'] = ['Azimuth angle must be between 0 and 360 degrees']

        if errors:
            raise ValidationException(
                message="Invalid site configuration",
                errors=errors
            )

    @property
    def calculated_capacity_kw(self) -> Decimal:
        """Calculate system capacity from panels."""
        return Decimal(self.panel_count) * self.panel_wattage / Decimal(1000)

    @property
    def has_battery(self) -> bool:
        """Check if system has battery storage."""
        return self.battery_capacity_kwh is not None and self.battery_capacity_kwh > 0

    @property
    def is_net_metered(self) -> bool:
        """Check if system is net metered."""
        return self.net_metering_enabled and self.grid_connection_type != GridConnectionType.OFF_GRID

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'system_capacity_kw': float(self.system_capacity_kw),
            'panel_count': self.panel_count,
            'panel_wattage': float(self.panel_wattage),
            'panel_manufacturer': self.panel_manufacturer,
            'panel_model': self.panel_model,
            'inverter_capacity_kw': float(self.inverter_capacity_kw),
            'inverter_count': self.inverter_count,
            'inverter_manufacturer': self.inverter_manufacturer,
            'inverter_model': self.inverter_model,
            'battery_capacity_kwh': float(self.battery_capacity_kwh) if self.battery_capacity_kwh else None,
            'battery_count': self.battery_count,
            'battery_manufacturer': self.battery_manufacturer,
            'battery_model': self.battery_model,
            'grid_connection_type': self.grid_connection_type.value,
            'net_metering_enabled': self.net_metering_enabled,
            'net_metering_capacity_kw': float(self.net_metering_capacity_kw) if self.net_metering_capacity_kw else None,
            'sanctioned_load_kw': float(self.sanctioned_load_kw) if self.sanctioned_load_kw else None,
            'disco_provider': self.disco_provider.value if self.disco_provider else None,
            'tariff_category': self.tariff_category,
            'consumer_reference': self.consumer_reference,
            'installation_date': self.installation_date.isoformat() if self.installation_date else None,
            'warranty_expiry': self.warranty_expiry.isoformat() if self.warranty_expiry else None,
            'installer_company': self.installer_company,
            'tilt_angle': self.tilt_angle,
            'azimuth_angle': self.azimuth_angle,
            'mounting_type': self.mounting_type,
            'has_battery': self.has_battery,
            'is_net_metered': self.is_net_metered
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SiteConfiguration':
        """Create from dictionary."""
        return cls(
            system_capacity_kw=Decimal(str(data.get('system_capacity_kw', 0))),
            panel_count=data.get('panel_count', 0),
            panel_wattage=Decimal(str(data.get('panel_wattage', 0))),
            panel_manufacturer=data.get('panel_manufacturer'),
            panel_model=data.get('panel_model'),
            inverter_capacity_kw=Decimal(str(data.get('inverter_capacity_kw', 0))),
            inverter_count=data.get('inverter_count', 1),
            inverter_manufacturer=data.get('inverter_manufacturer'),
            inverter_model=data.get('inverter_model'),
            battery_capacity_kwh=Decimal(str(data['battery_capacity_kwh'])) if data.get('battery_capacity_kwh') else None,
            battery_count=data.get('battery_count', 0),
            battery_manufacturer=data.get('battery_manufacturer'),
            battery_model=data.get('battery_model'),
            grid_connection_type=GridConnectionType(data.get('grid_connection_type', 'on_grid')),
            net_metering_enabled=data.get('net_metering_enabled', False),
            net_metering_capacity_kw=Decimal(str(data['net_metering_capacity_kw'])) if data.get('net_metering_capacity_kw') else None,
            sanctioned_load_kw=Decimal(str(data['sanctioned_load_kw'])) if data.get('sanctioned_load_kw') else None,
            disco_provider=DiscoProvider(data['disco_provider']) if data.get('disco_provider') else None,
            tariff_category=data.get('tariff_category'),
            consumer_reference=data.get('consumer_reference'),
            installation_date=datetime.fromisoformat(data['installation_date']) if data.get('installation_date') else None,
            warranty_expiry=datetime.fromisoformat(data['warranty_expiry']) if data.get('warranty_expiry') else None,
            installer_company=data.get('installer_company'),
            tilt_angle=data.get('tilt_angle'),
            azimuth_angle=data.get('azimuth_angle'),
            mounting_type=data.get('mounting_type')
        )


@dataclass
class Site(AggregateRoot):
    """
    Site aggregate root.

    Represents a solar installation site with its configuration,
    location, and operational status.
    """
    organization_id: UUID
    name: str
    address: Address
    timezone: str = "Asia/Karachi"
    site_type: SiteType = SiteType.RESIDENTIAL
    status: SiteStatus = SiteStatus.PENDING_SETUP
    configuration: Optional[SiteConfiguration] = None
    device_ids: List[UUID] = field(default_factory=list)
    notes: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate site data."""
        self._validate()

    def _validate(self) -> None:
        """Validate site data."""
        errors = {}

        if not self.name or len(self.name.strip()) < 2:
            errors['name'] = ['Site name must be at least 2 characters']

        if len(self.name) > 200:
            errors['name'] = ['Site name cannot exceed 200 characters']

        if self.notes and len(self.notes) > 2000:
            errors['notes'] = ['Notes cannot exceed 2000 characters']

        if errors:
            raise ValidationException(
                message="Invalid site data",
                errors=errors
            )

    @property
    def is_active(self) -> bool:
        """Check if site is active."""
        return self.status == SiteStatus.ACTIVE

    @property
    def is_operational(self) -> bool:
        """Check if site can receive telemetry."""
        return self.status in (SiteStatus.ACTIVE, SiteStatus.COMMISSIONING)

    @property
    def geo_location(self) -> Optional[GeoLocation]:
        """Get site's geographic location."""
        return self.address.geo_location

    @property
    def device_count(self) -> int:
        """Get number of devices at this site."""
        return len(self.device_ids)

    @property
    def system_capacity_kw(self) -> Optional[Decimal]:
        """Get system capacity from configuration."""
        return self.configuration.system_capacity_kw if self.configuration else None

    def configure(self, configuration: SiteConfiguration) -> None:
        """Set or update site configuration."""
        self.configuration = configuration
        self.mark_updated()

        from ..events.site_events import SiteConfigured
        self.add_domain_event(SiteConfigured(
            site_id=self.id,
            system_capacity_kw=float(configuration.system_capacity_kw)
        ))

    def update_details(
        self,
        name: Optional[str] = None,
        address: Optional[Address] = None,
        site_type: Optional[SiteType] = None,
        notes: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_phone: Optional[str] = None,
        contact_email: Optional[str] = None
    ) -> None:
        """Update site details."""
        if name is not None:
            self.name = name
        if address is not None:
            self.address = address
        if site_type is not None:
            self.site_type = site_type
        if notes is not None:
            self.notes = notes
        if contact_name is not None:
            self.contact_name = contact_name
        if contact_phone is not None:
            self.contact_phone = contact_phone
        if contact_email is not None:
            self.contact_email = contact_email

        self._validate()
        self.mark_updated()

        from ..events.site_events import SiteUpdated
        self.add_domain_event(SiteUpdated(site_id=self.id))

    def change_status(self, new_status: SiteStatus, changed_by: UUID, reason: Optional[str] = None) -> None:
        """Change site operational status."""
        old_status = self.status

        # Validate status transitions
        valid_transitions = {
            SiteStatus.PENDING_SETUP: [SiteStatus.COMMISSIONING, SiteStatus.DECOMMISSIONED],
            SiteStatus.COMMISSIONING: [SiteStatus.ACTIVE, SiteStatus.PENDING_SETUP, SiteStatus.DECOMMISSIONED],
            SiteStatus.ACTIVE: [SiteStatus.MAINTENANCE, SiteStatus.OFFLINE, SiteStatus.DECOMMISSIONED],
            SiteStatus.MAINTENANCE: [SiteStatus.ACTIVE, SiteStatus.OFFLINE, SiteStatus.DECOMMISSIONED],
            SiteStatus.OFFLINE: [SiteStatus.ACTIVE, SiteStatus.MAINTENANCE, SiteStatus.DECOMMISSIONED],
            SiteStatus.DECOMMISSIONED: []  # Terminal state
        }

        if new_status not in valid_transitions.get(old_status, []):
            raise BusinessRuleViolationException(
                message=f"Cannot transition from {old_status.value} to {new_status.value}",
                rule="site_status_transition"
            )

        self.status = new_status
        self.mark_updated()

        from ..events.site_events import SiteStatusChanged
        self.add_domain_event(SiteStatusChanged(
            site_id=self.id,
            old_status=old_status.value,
            new_status=new_status.value,
            changed_by=changed_by,
            reason=reason
        ))

    def activate(self, activated_by: UUID) -> None:
        """Activate site (shorthand for status change)."""
        self.change_status(SiteStatus.ACTIVE, activated_by)

    def decommission(self, decommissioned_by: UUID, reason: str) -> None:
        """Decommission site permanently."""
        self.change_status(SiteStatus.DECOMMISSIONED, decommissioned_by, reason)

        from ..events.site_events import SiteDecommissioned
        self.add_domain_event(SiteDecommissioned(
            site_id=self.id,
            organization_id=self.organization_id,
            reason=reason,
            decommissioned_by=decommissioned_by
        ))

    def add_device(self, device_id: UUID) -> None:
        """Add device to this site."""
        if device_id in self.device_ids:
            raise BusinessRuleViolationException(
                message="Device already assigned to this site",
                rule="duplicate_device"
            )
        self.device_ids.append(device_id)
        self.mark_updated()

    def remove_device(self, device_id: UUID) -> None:
        """Remove device from this site."""
        if device_id not in self.device_ids:
            raise BusinessRuleViolationException(
                message="Device not found at this site",
                rule="device_not_found"
            )
        self.device_ids.remove(device_id)
        self.mark_updated()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize site to dictionary."""
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'name': self.name,
            'address': self.address.to_dict(),
            'timezone': self.timezone,
            'site_type': self.site_type.value,
            'status': self.status.value,
            'configuration': self.configuration.to_dict() if self.configuration else None,
            'device_count': self.device_count,
            'device_ids': [str(d) for d in self.device_ids],
            'notes': self.notes,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone,
            'contact_email': self.contact_email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def create(
        cls,
        organization_id: UUID,
        name: str,
        address: Address,
        site_type: SiteType = SiteType.RESIDENTIAL,
        timezone: str = "Asia/Karachi",
        configuration: Optional[SiteConfiguration] = None
    ) -> 'Site':
        """
        Factory method to create a new site.

        Args:
            organization_id: ID of owning organization
            name: Site name
            address: Site address
            site_type: Type of installation
            timezone: Site timezone
            configuration: Optional initial configuration

        Returns:
            New Site instance with SiteCreated event
        """
        site = cls(
            organization_id=organization_id,
            name=name.strip(),
            address=address,
            site_type=site_type,
            timezone=timezone,
            configuration=configuration
        )

        from ..events.site_events import SiteCreated
        site.add_domain_event(SiteCreated(
            site_id=site.id,
            organization_id=organization_id,
            name=site.name,
            city=address.city
        ))

        return site
