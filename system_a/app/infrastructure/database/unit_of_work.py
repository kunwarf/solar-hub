"""
SQLAlchemy Unit of Work implementation.
"""
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.base import DomainEvent
from .repositories.user_repository import SQLAlchemyUserRepository
from .repositories.organization_repository import SQLAlchemyOrganizationRepository
from .repositories.site_repository import SQLAlchemySiteRepository
from .repositories.device_repository import SQLAlchemyDeviceRepository
from .repositories.alert_repository import SQLAlchemyAlertRepository, SQLAlchemyAlertRuleRepository


class SQLAlchemyUnitOfWork(UnitOfWork):
    """
    SQLAlchemy implementation of Unit of Work pattern.

    Manages database transactions and provides access to repositories.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        """
        Initialize Unit of Work.

        Args:
            session_factory: Factory for creating async database sessions
        """
        self._session_factory = session_factory
        self._session: Optional[AsyncSession] = None
        self._users: Optional[SQLAlchemyUserRepository] = None
        self._organizations: Optional[SQLAlchemyOrganizationRepository] = None
        self._sites: Optional[SQLAlchemySiteRepository] = None
        self._devices: Optional[SQLAlchemyDeviceRepository] = None
        self._alerts: Optional[SQLAlchemyAlertRepository] = None
        self._alert_rules: Optional[SQLAlchemyAlertRuleRepository] = None

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        """Enter async context - create session."""
        self._session = self._session_factory()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context - rollback on error, close session."""
        if exc_type is not None:
            await self.rollback()
        await self.close()

    @property
    def users(self) -> SQLAlchemyUserRepository:
        """Get user repository."""
        if self._users is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._users = SQLAlchemyUserRepository(self._session)
        return self._users

    @property
    def organizations(self) -> SQLAlchemyOrganizationRepository:
        """Get organization repository."""
        if self._organizations is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._organizations = SQLAlchemyOrganizationRepository(self._session)
        return self._organizations

    @property
    def sites(self) -> SQLAlchemySiteRepository:
        """Get site repository."""
        if self._sites is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._sites = SQLAlchemySiteRepository(self._session)
        return self._sites

    @property
    def devices(self) -> SQLAlchemyDeviceRepository:
        """Get device repository."""
        if self._devices is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._devices = SQLAlchemyDeviceRepository(self._session)
        return self._devices

    @property
    def alerts(self) -> SQLAlchemyAlertRepository:
        """Get alert repository."""
        if self._alerts is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._alerts = SQLAlchemyAlertRepository(self._session)
        return self._alerts

    @property
    def alert_rules(self) -> SQLAlchemyAlertRuleRepository:
        """Get alert rule repository."""
        if self._alert_rules is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._alert_rules = SQLAlchemyAlertRuleRepository(self._session)
        return self._alert_rules

    async def commit(self) -> None:
        """Commit current transaction."""
        if self._session:
            await self._session.commit()

    async def rollback(self) -> None:
        """Rollback current transaction."""
        if self._session:
            await self._session.rollback()

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None
            # Reset repository references
            self._users = None
            self._organizations = None
            self._sites = None
            self._devices = None
            self._alerts = None
            self._alert_rules = None

    def collect_domain_events(self) -> List[DomainEvent]:
        """
        Collect all domain events from tracked entities.

        Note: This is a simplified implementation. In a more sophisticated
        setup, you would track all entities that were loaded/created during
        the session and collect their events.
        """
        events: List[DomainEvent] = []
        # Events are collected from entities directly when they are processed
        # This method is here for interface compliance and potential future use
        return events
