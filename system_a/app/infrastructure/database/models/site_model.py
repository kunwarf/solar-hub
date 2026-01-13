"""
SQLAlchemy model for Site entity.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from .base import BaseModel
from ....domain.entities.site import (
    Site, SiteConfiguration, SiteStatus, SiteType,
    GridConnectionType, DiscoProvider
)
from ....domain.value_objects.address import Address, GeoLocation


class SiteModel(BaseModel):
    """SQLAlchemy model for sites table."""

    __tablename__ = 'sites'

    organization_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    name = Column(String(200), nullable=False)
    timezone = Column(String(50), default='Asia/Karachi', nullable=False)
    site_type = Column(
        Enum(SiteType, name='site_type'),
        default=SiteType.RESIDENTIAL,
        nullable=False,
        index=True
    )
    status = Column(
        Enum(SiteStatus, name='site_status'),
        default=SiteStatus.PENDING_SETUP,
        nullable=False,
        index=True
    )

    # Address (stored as JSON)
    address = Column(JSONB, nullable=False)

    # Configuration (stored as JSON)
    configuration = Column(JSONB, nullable=True)

    # Device IDs (array of UUIDs)
    device_ids = Column(ARRAY(PGUUID(as_uuid=True)), default=list, nullable=False)

    # Contact information
    notes = Column(Text, nullable=True)
    contact_name = Column(String(200), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_email = Column(String(254), nullable=True)

    # Relationships
    organization = relationship('OrganizationModel', back_populates='sites')
    devices = relationship('DeviceModel', back_populates='site', lazy='dynamic')

    def to_domain(self) -> Site:
        """Convert ORM model to domain entity."""
        site = Site(
            id=self.id,
            organization_id=self.organization_id,
            name=self.name,
            address=Address.from_dict(self.address),
            timezone=self.timezone,
            site_type=self.site_type,
            status=self.status,
            configuration=SiteConfiguration.from_dict(self.configuration) if self.configuration else None,
            device_ids=self.device_ids or [],
            notes=self.notes,
            contact_name=self.contact_name,
            contact_phone=self.contact_phone,
            contact_email=self.contact_email,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version
        )
        site._domain_events = []
        return site

    @classmethod
    def from_domain(cls, site: Site) -> 'SiteModel':
        """Create ORM model from domain entity."""
        return cls(
            id=site.id,
            organization_id=site.organization_id,
            name=site.name,
            address=site.address.to_dict(),
            timezone=site.timezone,
            site_type=site.site_type,
            status=site.status,
            configuration=site.configuration.to_dict() if site.configuration else None,
            device_ids=site.device_ids,
            notes=site.notes,
            contact_name=site.contact_name,
            contact_phone=site.contact_phone,
            contact_email=site.contact_email,
            created_at=site.created_at,
            updated_at=site.updated_at,
            version=site.version
        )

    def update_from_domain(self, site: Site) -> None:
        """Update ORM model from domain entity."""
        self.organization_id = site.organization_id
        self.name = site.name
        self.address = site.address.to_dict()
        self.timezone = site.timezone
        self.site_type = site.site_type
        self.status = site.status
        self.configuration = site.configuration.to_dict() if site.configuration else None
        self.device_ids = site.device_ids
        self.notes = site.notes
        self.contact_name = site.contact_name
        self.contact_phone = site.contact_phone
        self.contact_email = site.contact_email
        self.updated_at = site.updated_at
        self.version = site.version
