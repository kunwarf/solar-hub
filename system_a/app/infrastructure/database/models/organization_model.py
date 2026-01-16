"""
SQLAlchemy models for Organization entity.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin, UUIDMixin, Base
from ....domain.entities.organization import (
    Organization, OrganizationMember, OrganizationSettings,
    OrganizationStatus, MembershipStatus
)
from ....domain.entities.user import UserRole


class OrganizationMemberModel(Base, UUIDMixin, TimestampMixin):
    """SQLAlchemy model for organization_members table."""

    __tablename__ = 'organization_members'

    organization_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    user_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    role = Column(
        Enum(UserRole, name='user_role'),
        nullable=False
    )
    status = Column(
        Enum(MembershipStatus, name='membership_status'),
        default=MembershipStatus.PENDING,
        nullable=False
    )
    invited_by = Column(PGUUID(as_uuid=True), nullable=True)
    invited_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship('OrganizationModel', back_populates='members')
    user = relationship('UserModel', back_populates='memberships')

    def to_domain(self) -> OrganizationMember:
        """Convert to domain entity."""
        return OrganizationMember(
            id=self.id,
            organization_id=self.organization_id,
            user_id=self.user_id,
            role=self.role,
            status=self.status,
            invited_by=self.invited_by,
            invited_at=self.invited_at,
            accepted_at=self.accepted_at,
            created_at=self.created_at,
            updated_at=self.updated_at
        )

    @classmethod
    def from_domain(cls, member: OrganizationMember) -> 'OrganizationMemberModel':
        """Create from domain entity."""
        return cls(
            id=member.id,
            organization_id=member.organization_id,
            user_id=member.user_id,
            role=member.role,
            status=member.status,
            invited_by=member.invited_by,
            invited_at=member.invited_at,
            accepted_at=member.accepted_at,
            created_at=member.created_at,
            updated_at=member.updated_at
        )


class OrganizationModel(BaseModel):
    """SQLAlchemy model for organizations table."""

    __tablename__ = 'organizations'

    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('users.id'),
        nullable=False,
        index=True
    )
    status = Column(
        Enum(OrganizationStatus, name='organization_status'),
        default=OrganizationStatus.ACTIVE,
        nullable=False,
        index=True
    )
    settings = Column(JSONB, default=dict, nullable=False)
    site_count = Column(Integer, default=0, nullable=False)

    # Relationships
    owner = relationship(
        'UserModel',
        back_populates='owned_organizations',
        foreign_keys=[owner_id]
    )
    members = relationship(
        'OrganizationMemberModel',
        back_populates='organization',
        lazy='selectin',
        cascade='all, delete-orphan'
    )
    sites = relationship(
        'SiteModel',
        back_populates='organization',
        lazy='dynamic'
    )
    reports = relationship(
        'ReportModel',
        back_populates='organization',
        lazy='dynamic'
    )
    report_schedules = relationship(
        'ReportScheduleModel',
        back_populates='organization',
        lazy='dynamic'
    )
    report_templates = relationship(
        'ReportTemplateModel',
        back_populates='organization',
        lazy='dynamic'
    )

    def to_domain(self) -> Organization:
        """Convert ORM model to domain entity."""
        org = Organization(
            id=self.id,
            name=self.name,
            slug=self.slug,
            description=self.description,
            owner_id=self.owner_id,
            status=self.status,
            settings=OrganizationSettings.from_dict(self.settings or {}),
            site_count=self.site_count,
            members=[m.to_domain() for m in self.members],
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version
        )
        org._domain_events = []
        return org

    @classmethod
    def from_domain(cls, org: Organization) -> 'OrganizationModel':
        """Create ORM model from domain entity."""
        model = cls(
            id=org.id,
            name=org.name,
            slug=org.slug,
            description=org.description,
            owner_id=org.owner_id,
            status=org.status,
            settings=org.settings.to_dict(),
            site_count=org.site_count,
            created_at=org.created_at,
            updated_at=org.updated_at,
            version=org.version
        )
        # Members are handled separately via relationship
        return model

    def update_from_domain(self, org: Organization) -> None:
        """Update ORM model from domain entity."""
        self.name = org.name
        self.slug = org.slug
        self.description = org.description
        self.owner_id = org.owner_id
        self.status = org.status
        self.settings = org.settings.to_dict()
        self.site_count = org.site_count
        self.updated_at = org.updated_at
        self.version = org.version
