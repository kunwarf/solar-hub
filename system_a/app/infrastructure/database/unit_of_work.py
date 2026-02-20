"""
SQLAlchemy Unit of Work implementation.
"""
from typing import List, Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.base import DomainEvent
from .repositories.user_repository import SQLAlchemyUserRepository
from .repositories.organization_repository import SQLAlchemyOrganizationRepository
from .repositories.site_repository import SQLAlchemySiteRepository
from .repositories.device_repository import SQLAlchemyDeviceRepository
from .repositories.alert_repository import SQLAlchemyAlertRepository, SQLAlchemyAlertRuleRepository
from .repositories.dashboard_repository import (
    SQLAlchemyDashboardPreferencesRepository,
    SQLAlchemyCustomPresetRepository,
)
from .repositories.admin_repository import (
    SQLAlchemyElectricityProviderRepository,
    SQLAlchemyElectricityTariffRepository,
    SQLAlchemyLoadSheddingScheduleRepository,
    SQLAlchemyAdminAuditLogRepository,
)

logger = logging.getLogger(__name__)


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
        self._dashboard_preferences: Optional[SQLAlchemyDashboardPreferencesRepository] = None
        self._custom_presets: Optional[SQLAlchemyCustomPresetRepository] = None
        self._electricity_providers: Optional[SQLAlchemyElectricityProviderRepository] = None
        self._electricity_tariffs: Optional[SQLAlchemyElectricityTariffRepository] = None
        self._load_shedding_schedules: Optional[SQLAlchemyLoadSheddingScheduleRepository] = None
        self._admin_audit_logs: Optional[SQLAlchemyAdminAuditLogRepository] = None

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

    @property
    def dashboard_preferences(self) -> SQLAlchemyDashboardPreferencesRepository:
        """Get dashboard preferences repository."""
        if self._dashboard_preferences is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._dashboard_preferences = SQLAlchemyDashboardPreferencesRepository(self._session)
        return self._dashboard_preferences

    @property
    def custom_presets(self) -> SQLAlchemyCustomPresetRepository:
        """Get custom presets repository."""
        if self._custom_presets is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._custom_presets = SQLAlchemyCustomPresetRepository(self._session)
        return self._custom_presets

    @property
    def electricity_providers(self) -> SQLAlchemyElectricityProviderRepository:
        """Get electricity provider repository."""
        if self._electricity_providers is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._electricity_providers = SQLAlchemyElectricityProviderRepository(self._session)
        return self._electricity_providers

    @property
    def electricity_tariffs(self) -> SQLAlchemyElectricityTariffRepository:
        """Get electricity tariff repository."""
        if self._electricity_tariffs is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._electricity_tariffs = SQLAlchemyElectricityTariffRepository(self._session)
        return self._electricity_tariffs

    @property
    def load_shedding_schedules(self) -> SQLAlchemyLoadSheddingScheduleRepository:
        """Get load shedding schedule repository."""
        if self._load_shedding_schedules is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._load_shedding_schedules = SQLAlchemyLoadSheddingScheduleRepository(self._session)
        return self._load_shedding_schedules

    @property
    def admin_audit_logs(self) -> SQLAlchemyAdminAuditLogRepository:
        """Get admin audit log repository."""
        if self._admin_audit_logs is None:
            if self._session is None:
                raise RuntimeError("Unit of work not started. Use 'async with' context.")
            self._admin_audit_logs = SQLAlchemyAdminAuditLogRepository(self._session)
        return self._admin_audit_logs

    async def commit(self) -> None:
        """Commit current transaction."""
        if self._session:
            logger.info("[UOW_COMMIT] Committing transaction")
            await self._session.commit()
            logger.info("[UOW_COMMIT] Transaction committed successfully")
        else:
            logger.warning("[UOW_COMMIT] No session to commit!")

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
            self._dashboard_preferences = None
            self._custom_presets = None
            self._electricity_providers = None
            self._electricity_tariffs = None
            self._load_shedding_schedules = None
            self._admin_audit_logs = None

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
