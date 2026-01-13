"""
Unit of Work interface for managing transactions.

The Unit of Work pattern maintains a list of objects affected by a business
transaction and coordinates the writing out of changes and resolution of
concurrency problems.
"""
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Optional, Type

from .repositories import (
    UserRepository,
    OrganizationRepository,
    SiteRepository,
    DeviceRepository,
    AlertRepository,
    AlertRuleRepository,
)


class UnitOfWork(ABC):
    """
    Abstract Unit of Work.

    Provides access to repositories and manages database transactions.
    Use as async context manager:

    async with unit_of_work as uow:
        user = await uow.users.get_by_id(user_id)
        user.update_profile(...)
        await uow.users.update(user)
        await uow.commit()
    """

    users: UserRepository
    organizations: OrganizationRepository
    sites: SiteRepository
    devices: DeviceRepository
    alerts: AlertRepository
    alert_rules: AlertRuleRepository

    async def __aenter__(self) -> 'UnitOfWork':
        """Enter the context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """
        Exit the context manager.

        Rolls back if an exception occurred, otherwise just closes.
        """
        if exc_type is not None:
            await self.rollback()
        await self.close()

    @abstractmethod
    async def commit(self) -> None:
        """
        Commit the current transaction.

        Also dispatches any pending domain events.
        """
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Roll back the current transaction."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the unit of work and release resources."""
        pass

    @abstractmethod
    async def collect_domain_events(self) -> list:
        """
        Collect and clear domain events from all tracked entities.

        Returns:
            List of domain events to be dispatched
        """
        pass
