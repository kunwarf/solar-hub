"""
SQLAlchemy base model and common mixins.
"""
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, declared_attr


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class."""

    # Common configuration
    __table_args__ = {'extend_existing': True}

    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        # Convert CamelCase to snake_case
        name = cls.__name__
        return ''.join(
            ['_' + c.lower() if c.isupper() else c for c in name]
        ).lstrip('_') + 's'


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps."""

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=None,
        onupdate=utc_now,
        nullable=True
    )


class UUIDMixin:
    """Mixin that adds UUID primary key."""

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False
    )


class VersionMixin:
    """Mixin for optimistic locking."""

    version = Column(Integer, default=1, nullable=False)


class BaseModel(Base, UUIDMixin, TimestampMixin, VersionMixin):
    """
    Abstract base model with common fields.

    Includes: id (UUID), created_at, updated_at, version
    """
    __abstract__ = True
