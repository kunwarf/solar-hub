"""
SQLAlchemy model for User entity.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from .base import BaseModel
from ....domain.entities.user import User, UserRole, UserStatus, UserPreferences
from ....domain.value_objects.email import Email
from ....domain.value_objects.phone import PhoneNumber


class UserModel(BaseModel):
    """SQLAlchemy model for users table."""

    __tablename__ = 'users'

    # Authentication
    email = Column(String(254), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Profile
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True, index=True)

    # Status and role
    status = Column(
        Enum(UserStatus, name='user_status'),
        default=UserStatus.PENDING,
        nullable=False,
        index=True
    )
    role = Column(
        Enum(UserRole, name='user_role'),
        default=UserRole.VIEWER,
        nullable=False,
        index=True
    )

    # Verification
    email_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Login tracking
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Preferences (JSON)
    preferences = Column(JSONB, default=dict, nullable=False)

    # Relationships
    owned_organizations = relationship(
        'OrganizationModel',
        back_populates='owner',
        foreign_keys='OrganizationModel.owner_id',
        lazy='dynamic'
    )
    memberships = relationship(
        'OrganizationMemberModel',
        back_populates='user',
        lazy='dynamic'
    )

    def to_domain(self) -> User:
        """Convert ORM model to domain entity."""
        user = User(
            id=self.id,
            email=Email(self.email),
            password_hash=self.password_hash,
            first_name=self.first_name,
            last_name=self.last_name,
            phone=PhoneNumber.pakistan(self.phone) if self.phone else None,
            status=self.status,
            role=self.role,
            preferences=UserPreferences.from_dict(self.preferences or {}),
            email_verified_at=self.email_verified_at,
            last_login_at=self.last_login_at,
            failed_login_attempts=self.failed_login_attempts,
            locked_until=self.locked_until,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version
        )
        user._domain_events = []  # Clear events loaded from DB
        return user

    @classmethod
    def from_domain(cls, user: User) -> 'UserModel':
        """Create ORM model from domain entity."""
        return cls(
            id=user.id,
            email=str(user.email),
            password_hash=user.password_hash,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=str(user.phone) if user.phone else None,
            status=user.status,
            role=user.role,
            preferences=user.preferences.to_dict(),
            email_verified_at=user.email_verified_at,
            last_login_at=user.last_login_at,
            failed_login_attempts=user.failed_login_attempts,
            locked_until=user.locked_until,
            created_at=user.created_at,
            updated_at=user.updated_at,
            version=user.version
        )

    def update_from_domain(self, user: User) -> None:
        """Update ORM model from domain entity."""
        self.email = str(user.email)
        self.password_hash = user.password_hash
        self.first_name = user.first_name
        self.last_name = user.last_name
        self.phone = str(user.phone) if user.phone else None
        self.status = user.status
        self.role = user.role
        self.preferences = user.preferences.to_dict()
        self.email_verified_at = user.email_verified_at
        self.last_login_at = user.last_login_at
        self.failed_login_attempts = user.failed_login_attempts
        self.locked_until = user.locked_until
        self.updated_at = user.updated_at
        self.version = user.version
