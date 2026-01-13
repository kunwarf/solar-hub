"""
SQLAlchemy implementation of Alert repositories.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.interfaces.repositories import AlertRepository, AlertRuleRepository
from ....domain.entities.alert import Alert, AlertRule, AlertSeverity, AlertStatus
from ..models.alert_model import AlertModel, AlertRuleModel


class SQLAlchemyAlertRuleRepository(AlertRuleRepository):
    """SQLAlchemy implementation of alert rule repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[AlertRule]:
        """Get alert rule by ID."""
        result = await self._session.execute(
            select(AlertRuleModel).where(AlertRuleModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_organization_id(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        is_active: Optional[bool] = None
    ) -> List[AlertRule]:
        """Get alert rules for an organization."""
        query = select(AlertRuleModel).where(
            AlertRuleModel.organization_id == organization_id
        )

        if is_active is not None:
            query = query.where(AlertRuleModel.is_active == is_active)

        query = query.order_by(AlertRuleModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_by_site_id(
        self,
        site_id: UUID,
        is_active: Optional[bool] = None
    ) -> List[AlertRule]:
        """Get alert rules for a specific site."""
        query = select(AlertRuleModel).where(
            AlertRuleModel.site_id == site_id
        )

        if is_active is not None:
            query = query.where(AlertRuleModel.is_active == is_active)

        query = query.order_by(AlertRuleModel.created_at.desc())

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_active_rules_for_metric(
        self,
        organization_id: UUID,
        metric: str,
        site_id: Optional[UUID] = None
    ) -> List[AlertRule]:
        """Get active rules that monitor a specific metric."""
        query = select(AlertRuleModel).where(
            AlertRuleModel.organization_id == organization_id,
            AlertRuleModel.is_active == True,
            AlertRuleModel.condition['metric'].astext == metric
        )

        if site_id:
            query = query.where(
                or_(
                    AlertRuleModel.site_id == site_id,
                    AlertRuleModel.site_id.is_(None)
                )
            )

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def count_by_organization_id(
        self,
        organization_id: UUID,
        is_active: Optional[bool] = None
    ) -> int:
        """Count alert rules in an organization."""
        query = select(func.count()).select_from(AlertRuleModel).where(
            AlertRuleModel.organization_id == organization_id
        )

        if is_active is not None:
            query = query.where(AlertRuleModel.is_active == is_active)

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def add(self, entity: AlertRule) -> AlertRule:
        """Add new alert rule."""
        model = AlertRuleModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: AlertRule) -> AlertRule:
        """Update existing alert rule."""
        result = await self._session.execute(
            select(AlertRuleModel).where(AlertRuleModel.id == entity.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(entity)
            await self._session.flush()
            return model.to_domain()
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete alert rule by ID."""
        result = await self._session.execute(
            select(AlertRuleModel).where(AlertRuleModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False


class SQLAlchemyAlertRepository(AlertRepository):
    """SQLAlchemy implementation of alert repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[Alert]:
        """Get alert by ID."""
        result = await self._session.execute(
            select(AlertModel).where(AlertModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_organization_id(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Alert]:
        """Get alerts for an organization."""
        query = select(AlertModel).where(
            AlertModel.organization_id == organization_id
        )

        if status:
            query = query.where(AlertModel.status == AlertStatus(status))

        if severity:
            query = query.where(AlertModel.severity == AlertSeverity(severity))

        query = query.order_by(AlertModel.triggered_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_by_site_id(
        self,
        site_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Alert]:
        """Get alerts for a specific site."""
        query = select(AlertModel).where(AlertModel.site_id == site_id)

        if status:
            query = query.where(AlertModel.status == AlertStatus(status))

        if severity:
            query = query.where(AlertModel.severity == AlertSeverity(severity))

        query = query.order_by(AlertModel.triggered_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_by_device_id(
        self,
        device_id: UUID,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List[Alert]:
        """Get alerts for a specific device."""
        query = select(AlertModel).where(AlertModel.device_id == device_id)

        if status:
            query = query.where(AlertModel.status == AlertStatus(status))

        query = query.order_by(AlertModel.triggered_at.desc())
        query = query.limit(limit)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_active_alerts(
        self,
        organization_id: UUID,
        site_id: Optional[UUID] = None
    ) -> List[Alert]:
        """Get all active (unresolved) alerts."""
        query = select(AlertModel).where(
            AlertModel.organization_id == organization_id,
            AlertModel.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED])
        )

        if site_id:
            query = query.where(AlertModel.site_id == site_id)

        query = query.order_by(AlertModel.triggered_at.desc())

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_critical_alerts(
        self,
        organization_id: UUID,
        site_id: Optional[UUID] = None
    ) -> List[Alert]:
        """Get critical severity active alerts."""
        query = select(AlertModel).where(
            AlertModel.organization_id == organization_id,
            AlertModel.severity == AlertSeverity.CRITICAL,
            AlertModel.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED])
        )

        if site_id:
            query = query.where(AlertModel.site_id == site_id)

        query = query.order_by(AlertModel.triggered_at.desc())

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def count_by_organization_id(
        self,
        organization_id: UUID,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> int:
        """Count alerts in an organization."""
        query = select(func.count()).select_from(AlertModel).where(
            AlertModel.organization_id == organization_id
        )

        if status:
            query = query.where(AlertModel.status == AlertStatus(status))

        if severity:
            query = query.where(AlertModel.severity == AlertSeverity(severity))

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def count_by_site_id(
        self,
        site_id: UUID,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> int:
        """Count alerts for a site."""
        query = select(func.count()).select_from(AlertModel).where(
            AlertModel.site_id == site_id
        )

        if status:
            query = query.where(AlertModel.status == AlertStatus(status))

        if severity:
            query = query.where(AlertModel.severity == AlertSeverity(severity))

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_unacknowledged_alerts_past_escalation(
        self,
        escalation_threshold_minutes: int
    ) -> List[Alert]:
        """Get alerts that should be escalated."""
        threshold_time = datetime.now(timezone.utc) - timedelta(
            minutes=escalation_threshold_minutes
        )

        result = await self._session.execute(
            select(AlertModel).where(
                AlertModel.status == AlertStatus.ACTIVE,
                AlertModel.escalated == False,
                AlertModel.triggered_at < threshold_time
            )
        )
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def add(self, entity: Alert) -> Alert:
        """Add new alert."""
        model = AlertModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: Alert) -> Alert:
        """Update existing alert."""
        result = await self._session.execute(
            select(AlertModel).where(AlertModel.id == entity.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(entity)
            await self._session.flush()
            return model.to_domain()
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete alert by ID."""
        result = await self._session.execute(
            select(AlertModel).where(AlertModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False
