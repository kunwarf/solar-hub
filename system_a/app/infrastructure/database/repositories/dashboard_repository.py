"""
SQLAlchemy implementation of Dashboard repositories.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from ....application.interfaces.repositories import (
    DashboardPreferencesRepository,
    CustomPresetRepository,
)
from ....domain.entities.dashboard import DashboardPreferences, CustomPreset
from ..models.dashboard_model import DashboardPreferencesModel, CustomPresetModel


class SQLAlchemyDashboardPreferencesRepository(DashboardPreferencesRepository):
    """SQLAlchemy implementation of dashboard preferences repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[DashboardPreferences]:
        """Get dashboard preferences by ID (user_id in this case)."""
        return await self.get_by_user_id(id)

    async def get_by_user_id(self, user_id: UUID) -> Optional[DashboardPreferences]:
        """Get dashboard preferences for a user."""
        result = await self._session.execute(
            select(DashboardPreferencesModel).where(
                DashboardPreferencesModel.user_id == user_id
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def add(self, entity: DashboardPreferences) -> DashboardPreferences:
        """Add new dashboard preferences."""
        model = DashboardPreferencesModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: DashboardPreferences) -> DashboardPreferences:
        """Update existing dashboard preferences."""
        result = await self._session.execute(
            select(DashboardPreferencesModel).where(
                DashboardPreferencesModel.user_id == entity.user_id
            )
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(entity)
            await self._session.flush()
            return model.to_domain()
        return entity

    async def upsert(self, entity: DashboardPreferences) -> DashboardPreferences:
        """Insert or update dashboard preferences for a user."""
        from datetime import datetime, timezone

        # Use PostgreSQL's INSERT ... ON CONFLICT for upsert
        widget_layout_json = [w.to_dict() for w in entity.widget_layout]

        # Use current time if updated_at is None
        updated_at = entity.updated_at if entity.updated_at else datetime.now(timezone.utc)

        stmt = insert(DashboardPreferencesModel).values(
            user_id=entity.user_id,
            layout_preset=entity.layout_preset,
            grid_layout=entity.grid_layout.value,
            widget_layout=widget_layout_json,
            created_at=entity.created_at,
            updated_at=updated_at,
            version=entity.version,
        ).on_conflict_do_update(
            index_elements=['user_id'],
            set_={
                'layout_preset': entity.layout_preset,
                'grid_layout': entity.grid_layout.value,
                'widget_layout': widget_layout_json,
                'updated_at': updated_at,
                'version': entity.version,
            }
        ).returning(DashboardPreferencesModel)

        result = await self._session.execute(stmt)
        model = result.scalar_one()
        await self._session.flush()
        return model.to_domain()

    async def delete(self, id: UUID) -> bool:
        """Delete dashboard preferences by user ID."""
        result = await self._session.execute(
            select(DashboardPreferencesModel).where(
                DashboardPreferencesModel.user_id == id
            )
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False


class SQLAlchemyCustomPresetRepository(CustomPresetRepository):
    """SQLAlchemy implementation of custom preset repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[CustomPreset]:
        """Get custom preset by ID."""
        result = await self._session.execute(
            select(CustomPresetModel).where(CustomPresetModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_user_id(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[CustomPreset]:
        """Get custom presets for a user."""
        query = (
            select(CustomPresetModel)
            .where(CustomPresetModel.user_id == user_id)
            .order_by(CustomPresetModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def count_by_user_id(self, user_id: UUID) -> int:
        """Count custom presets for a user."""
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count()).select_from(CustomPresetModel).where(
                CustomPresetModel.user_id == user_id
            )
        )
        return result.scalar() or 0

    async def add(self, entity: CustomPreset) -> CustomPreset:
        """Add new custom preset."""
        model = CustomPresetModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: CustomPreset) -> CustomPreset:
        """Update existing custom preset."""
        result = await self._session.execute(
            select(CustomPresetModel).where(CustomPresetModel.id == entity.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(entity)
            await self._session.flush()
            return model.to_domain()
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete custom preset by ID."""
        result = await self._session.execute(
            select(CustomPresetModel).where(CustomPresetModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False

    async def delete_by_user_and_id(self, user_id: UUID, preset_id: UUID) -> bool:
        """Delete a custom preset owned by a specific user."""
        result = await self._session.execute(
            select(CustomPresetModel).where(
                CustomPresetModel.id == preset_id,
                CustomPresetModel.user_id == user_id
            )
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False
