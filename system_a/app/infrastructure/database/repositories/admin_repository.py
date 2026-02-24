"""
SQLAlchemy repositories for admin portal entities.
"""
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.admin import (
    AdminAuditLog,
    BillingScheduleStatus,
    ElectricityProvider,
    ElectricityTariff,
    LoadSheddingSchedule,
    ProviderBillingSchedule,
    ProviderStatus,
    TariffStatus,
)
from ..models.admin_models import (
    AdminAuditLogModel,
    ElectricityProviderModel,
    ElectricityTariffModel,
    LoadSheddingScheduleModel,
    ProviderBillingScheduleModel,
)


# ---------------------------------------------------------------------------
# Electricity Provider Repository
# ---------------------------------------------------------------------------

class SQLAlchemyElectricityProviderRepository:
    """Repository for electricity provider CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[ElectricityProvider]:
        result = await self._session.execute(
            select(ElectricityProviderModel).where(ElectricityProviderModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_all(
        self,
        status: Optional[ProviderStatus] = None,
        region: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ElectricityProvider]:
        query = select(ElectricityProviderModel)
        if status is not None:
            query = query.where(ElectricityProviderModel.status == status)
        if region is not None:
            query = query.where(ElectricityProviderModel.region == region)
        query = query.order_by(ElectricityProviderModel.name).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return [m.to_domain() for m in result.scalars().all()]

    async def count(
        self,
        status: Optional[ProviderStatus] = None,
        region: Optional[str] = None,
    ) -> int:
        query = select(func.count()).select_from(ElectricityProviderModel)
        if status is not None:
            query = query.where(ElectricityProviderModel.status == status)
        if region is not None:
            query = query.where(ElectricityProviderModel.region == region)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def add(self, provider: ElectricityProvider) -> ElectricityProvider:
        model = ElectricityProviderModel.from_domain(provider)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, provider: ElectricityProvider) -> ElectricityProvider:
        result = await self._session.execute(
            select(ElectricityProviderModel).where(ElectricityProviderModel.id == provider.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(provider)
            await self._session.flush()
            return model.to_domain()
        return provider

    async def delete(self, id: UUID) -> bool:
        result = await self._session.execute(
            select(ElectricityProviderModel).where(ElectricityProviderModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False

    async def update_tariff_count(self, provider_id: UUID) -> None:
        """Refresh denormalised tariff_count for a provider."""
        count_result = await self._session.execute(
            select(func.count()).select_from(ElectricityTariffModel).where(
                ElectricityTariffModel.provider_id == provider_id
            )
        )
        count = count_result.scalar() or 0
        result = await self._session.execute(
            select(ElectricityProviderModel).where(ElectricityProviderModel.id == provider_id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.tariff_count = count
            await self._session.flush()


# ---------------------------------------------------------------------------
# Electricity Tariff Repository
# ---------------------------------------------------------------------------

class SQLAlchemyElectricityTariffRepository:
    """Repository for electricity tariff CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[ElectricityTariff]:
        result = await self._session.execute(
            select(ElectricityTariffModel).where(ElectricityTariffModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_by_provider(
        self,
        provider_id: UUID,
        status: Optional[TariffStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ElectricityTariff]:
        query = select(ElectricityTariffModel).where(
            ElectricityTariffModel.provider_id == provider_id
        )
        if status is not None:
            query = query.where(ElectricityTariffModel.status == status)
        query = query.order_by(ElectricityTariffModel.name).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return [m.to_domain() for m in result.scalars().all()]

    async def list_all(
        self,
        status: Optional[TariffStatus] = None,
        provider_id: Optional[UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ElectricityTariff]:
        query = select(ElectricityTariffModel)
        if provider_id is not None:
            query = query.where(ElectricityTariffModel.provider_id == provider_id)
        if status is not None:
            query = query.where(ElectricityTariffModel.status == status)
        query = query.order_by(ElectricityTariffModel.name).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return [m.to_domain() for m in result.scalars().all()]

    async def count_by_provider(self, provider_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(ElectricityTariffModel).where(
                ElectricityTariffModel.provider_id == provider_id
            )
        )
        return result.scalar() or 0

    async def add(self, tariff: ElectricityTariff) -> ElectricityTariff:
        model = ElectricityTariffModel.from_domain(tariff)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, tariff: ElectricityTariff) -> ElectricityTariff:
        result = await self._session.execute(
            select(ElectricityTariffModel).where(ElectricityTariffModel.id == tariff.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(tariff)
            await self._session.flush()
            return model.to_domain()
        return tariff

    async def delete(self, id: UUID) -> bool:
        result = await self._session.execute(
            select(ElectricityTariffModel).where(ElectricityTariffModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False


# ---------------------------------------------------------------------------
# Load Shedding Schedule Repository
# ---------------------------------------------------------------------------

class SQLAlchemyLoadSheddingScheduleRepository:
    """Repository for load shedding schedule CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[LoadSheddingSchedule]:
        result = await self._session.execute(
            select(LoadSheddingScheduleModel).where(LoadSheddingScheduleModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_all(
        self,
        region: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[LoadSheddingSchedule]:
        query = select(LoadSheddingScheduleModel)
        if region is not None:
            query = query.where(LoadSheddingScheduleModel.region == region)
        if is_active is not None:
            query = query.where(LoadSheddingScheduleModel.is_active == is_active)
        query = query.order_by(LoadSheddingScheduleModel.area_name).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return [m.to_domain() for m in result.scalars().all()]

    async def count(
        self,
        region: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> int:
        query = select(func.count()).select_from(LoadSheddingScheduleModel)
        if region is not None:
            query = query.where(LoadSheddingScheduleModel.region == region)
        if is_active is not None:
            query = query.where(LoadSheddingScheduleModel.is_active == is_active)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def add(self, sched: LoadSheddingSchedule) -> LoadSheddingSchedule:
        model = LoadSheddingScheduleModel.from_domain(sched)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, sched: LoadSheddingSchedule) -> LoadSheddingSchedule:
        result = await self._session.execute(
            select(LoadSheddingScheduleModel).where(LoadSheddingScheduleModel.id == sched.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(sched)
            await self._session.flush()
            return model.to_domain()
        return sched

    async def delete(self, id: UUID) -> bool:
        result = await self._session.execute(
            select(LoadSheddingScheduleModel).where(LoadSheddingScheduleModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False


# ---------------------------------------------------------------------------
# Admin Audit Log Repository
# ---------------------------------------------------------------------------

class SQLAlchemyAdminAuditLogRepository:
    """Repository for admin audit log (append-only)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, log: AdminAuditLog) -> AdminAuditLog:
        model = AdminAuditLogModel.from_domain(log)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def list_all(
        self,
        admin_user_id: Optional[UUID] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AdminAuditLog]:
        query = select(AdminAuditLogModel)
        if admin_user_id is not None:
            query = query.where(AdminAuditLogModel.admin_user_id == admin_user_id)
        if action is not None:
            query = query.where(AdminAuditLogModel.action == action)
        if resource_type is not None:
            query = query.where(AdminAuditLogModel.resource_type == resource_type)
        query = query.order_by(AdminAuditLogModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(query)
        return [m.to_domain() for m in result.scalars().all()]

    async def count(
        self,
        admin_user_id: Optional[UUID] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> int:
        query = select(func.count()).select_from(AdminAuditLogModel)
        if admin_user_id is not None:
            query = query.where(AdminAuditLogModel.admin_user_id == admin_user_id)
        if action is not None:
            query = query.where(AdminAuditLogModel.action == action)
        if resource_type is not None:
            query = query.where(AdminAuditLogModel.resource_type == resource_type)
        result = await self._session.execute(query)
        return result.scalar() or 0


# ---------------------------------------------------------------------------
# Provider Billing Schedule Repository
# ---------------------------------------------------------------------------

class SQLAlchemyProviderBillingScheduleRepository:
    """Repository for provider billing schedule CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[ProviderBillingSchedule]:
        result = await self._session.execute(
            select(ProviderBillingScheduleModel).where(ProviderBillingScheduleModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_active_for_provider_category(
        self,
        provider_id: UUID,
        tariff_category: str,
    ) -> Optional[ProviderBillingSchedule]:
        """
        Get the active billing schedule for a provider + tariff category.

        Case-insensitive category match. Returns None if no active schedule found.
        This is the critical lookup used by the billing engine.
        """
        today = date.today()
        query = (
            select(ProviderBillingScheduleModel)
            .where(
                and_(
                    ProviderBillingScheduleModel.provider_id == provider_id,
                    func.lower(ProviderBillingScheduleModel.tariff_category) == tariff_category.lower(),
                    ProviderBillingScheduleModel.status == BillingScheduleStatus.ACTIVE,
                    ProviderBillingScheduleModel.effective_from <= today,
                    or_(
                        ProviderBillingScheduleModel.effective_to.is_(None),
                        ProviderBillingScheduleModel.effective_to >= today,
                    ),
                )
            )
            .limit(1)
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_all(
        self,
        provider_id: Optional[UUID] = None,
        category: Optional[str] = None,
        status: Optional[BillingScheduleStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProviderBillingSchedule]:
        query = select(ProviderBillingScheduleModel)
        if provider_id is not None:
            query = query.where(ProviderBillingScheduleModel.provider_id == provider_id)
        if category is not None:
            query = query.where(
                func.lower(ProviderBillingScheduleModel.tariff_category) == category.lower()
            )
        if status is not None:
            query = query.where(ProviderBillingScheduleModel.status == status)
        query = (
            query.order_by(ProviderBillingScheduleModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(query)
        return [m.to_domain() for m in result.scalars().all()]

    async def count(
        self,
        provider_id: Optional[UUID] = None,
        category: Optional[str] = None,
        status: Optional[BillingScheduleStatus] = None,
    ) -> int:
        query = select(func.count()).select_from(ProviderBillingScheduleModel)
        if provider_id is not None:
            query = query.where(ProviderBillingScheduleModel.provider_id == provider_id)
        if category is not None:
            query = query.where(
                func.lower(ProviderBillingScheduleModel.tariff_category) == category.lower()
            )
        if status is not None:
            query = query.where(ProviderBillingScheduleModel.status == status)
        result = await self._session.execute(query)
        return result.scalar() or 0

    async def add(self, schedule: ProviderBillingSchedule) -> ProviderBillingSchedule:
        model = ProviderBillingScheduleModel.from_domain(schedule)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, schedule: ProviderBillingSchedule) -> ProviderBillingSchedule:
        result = await self._session.execute(
            select(ProviderBillingScheduleModel).where(
                ProviderBillingScheduleModel.id == schedule.id
            )
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(schedule)
            await self._session.flush()
            return model.to_domain()
        return schedule

    async def delete(self, id: UUID) -> bool:
        result = await self._session.execute(
            select(ProviderBillingScheduleModel).where(ProviderBillingScheduleModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False
