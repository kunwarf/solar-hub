"""
Base domain classes for System B.
"""
from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4


@dataclass(kw_only=True)
class Entity(ABC):
    """Base class for all entities with identity."""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
