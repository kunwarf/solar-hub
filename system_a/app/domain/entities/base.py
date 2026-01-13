"""
Base classes for domain entities following Domain-Driven Design principles.
These are pure Python classes with no external dependencies.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar
from uuid import UUID, uuid4


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class DomainEvent(ABC):
    """
    Base class for all domain events.

    Domain events represent something that happened in the domain that
    domain experts care about. They are immutable and named in past tense.
    """
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=utc_now)

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Return the type name of this event."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary for messaging."""
        return {
            'event_id': str(self.event_id),
            'event_type': self.event_type,
            'occurred_at': self.occurred_at.isoformat(),
            'data': self._get_event_data()
        }

    @abstractmethod
    def _get_event_data(self) -> Dict[str, Any]:
        """Return event-specific data for serialization."""
        pass


@dataclass
class Entity(ABC):
    """
    Base class for all entities.

    Entities are objects that have a distinct identity that runs through
    time and different representations. They are identified by their ID,
    not by their attributes.
    """
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: Optional[datetime] = field(default=None)

    def __eq__(self, other: object) -> bool:
        """Entities are equal if they have the same ID."""
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on entity ID."""
        return hash(self.id)

    def mark_updated(self) -> None:
        """Mark entity as updated with current timestamp."""
        self.updated_at = utc_now()


T = TypeVar('T', bound=DomainEvent)


@dataclass
class AggregateRoot(Entity):
    """
    Base class for aggregate roots.

    An aggregate root is the entry point to an aggregate - a cluster of
    domain objects that can be treated as a single unit. All access to
    objects within the aggregate must go through the root.

    Aggregate roots also manage domain events - things that happened
    that the domain cares about.
    """
    _domain_events: List[DomainEvent] = field(default_factory=list, repr=False, compare=False)
    version: int = field(default=1, compare=False)

    def add_domain_event(self, event: DomainEvent) -> None:
        """
        Add a domain event to be dispatched after persistence.

        Args:
            event: The domain event to add
        """
        self._domain_events.append(event)

    def clear_domain_events(self) -> List[DomainEvent]:
        """
        Clear and return all pending domain events.

        Returns:
            List of domain events that were pending
        """
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events

    @property
    def domain_events(self) -> List[DomainEvent]:
        """Return pending domain events (read-only view)."""
        return self._domain_events.copy()

    def increment_version(self) -> None:
        """Increment version for optimistic locking."""
        self.version += 1
        self.mark_updated()


@dataclass(frozen=True)
class ValueObject(ABC):
    """
    Base class for value objects.

    Value objects are immutable objects that are defined by their
    attributes rather than by identity. Two value objects with the
    same attributes are considered equal.

    Note: Use @dataclass(frozen=True) on subclasses to ensure immutability.
    """

    def __eq__(self, other: object) -> bool:
        """Value objects are equal if all their attributes are equal."""
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        """Hash based on all attributes."""
        return hash(tuple(sorted(self.__dict__.items())))


class Specification(ABC):
    """
    Base class for specifications (predicate pattern).

    Specifications encapsulate business rules that can be combined
    and reused for filtering and validation.
    """

    @abstractmethod
    def is_satisfied_by(self, candidate: Any) -> bool:
        """Check if candidate satisfies this specification."""
        pass

    def and_(self, other: 'Specification') -> 'Specification':
        """Combine with AND logic."""
        return AndSpecification(self, other)

    def or_(self, other: 'Specification') -> 'Specification':
        """Combine with OR logic."""
        return OrSpecification(self, other)

    def not_(self) -> 'Specification':
        """Negate this specification."""
        return NotSpecification(self)


class AndSpecification(Specification):
    """Combines two specifications with AND logic."""

    def __init__(self, left: Specification, right: Specification):
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class OrSpecification(Specification):
    """Combines two specifications with OR logic."""

    def __init__(self, left: Specification, right: Specification):
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: Any) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class NotSpecification(Specification):
    """Negates a specification."""

    def __init__(self, spec: Specification):
        self._spec = spec

    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self._spec.is_satisfied_by(candidate)
