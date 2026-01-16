"""
SQLAlchemy implementation of ProtocolDefinitionRepository.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.interfaces.repositories import ProtocolDefinitionRepository
from ....domain.entities.device import DeviceType, ProtocolType
from ....domain.entities.protocol_definition import ProtocolDefinition
from ..models.protocol_definition_model import ProtocolDefinitionModel


class SQLAlchemyProtocolDefinitionRepository(ProtocolDefinitionRepository):
    """SQLAlchemy implementation of protocol definition repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[ProtocolDefinition]:
        """Get protocol definition by ID."""
        result = await self._session.execute(
            select(ProtocolDefinitionModel).where(ProtocolDefinitionModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_protocol_id(self, protocol_id: str) -> Optional[ProtocolDefinition]:
        """Get protocol definition by unique protocol_id string."""
        result = await self._session.execute(
            select(ProtocolDefinitionModel).where(
                ProtocolDefinitionModel.protocol_id == protocol_id
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_device_type(
        self,
        device_type: DeviceType,
        is_active: Optional[bool] = True
    ) -> List[ProtocolDefinition]:
        """Get protocol definitions for a device type."""
        query = select(ProtocolDefinitionModel).where(
            ProtocolDefinitionModel.device_type == device_type
        )

        if is_active is not None:
            query = query.where(ProtocolDefinitionModel.is_active == is_active)

        query = query.order_by(ProtocolDefinitionModel.priority)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_by_protocol_type(
        self,
        protocol_type: ProtocolType,
        is_active: Optional[bool] = True
    ) -> List[ProtocolDefinition]:
        """Get protocol definitions for a protocol type."""
        query = select(ProtocolDefinitionModel).where(
            ProtocolDefinitionModel.protocol_type == protocol_type
        )

        if is_active is not None:
            query = query.where(ProtocolDefinitionModel.is_active == is_active)

        query = query.order_by(ProtocolDefinitionModel.priority)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_all_active(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[ProtocolDefinition]:
        """Get all active protocol definitions ordered by priority."""
        query = select(ProtocolDefinitionModel).where(
            ProtocolDefinitionModel.is_active == True
        ).order_by(
            ProtocolDefinitionModel.priority
        ).limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        is_active: Optional[bool] = None
    ) -> List[ProtocolDefinition]:
        """Get all protocol definitions with optional filtering."""
        query = select(ProtocolDefinitionModel)

        if is_active is not None:
            query = query.where(ProtocolDefinitionModel.is_active == is_active)

        query = query.order_by(
            ProtocolDefinitionModel.priority
        ).limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def count(self, is_active: Optional[bool] = None) -> int:
        """Count protocol definitions."""
        query = select(func.count()).select_from(ProtocolDefinitionModel)

        if is_active is not None:
            query = query.where(ProtocolDefinitionModel.is_active == is_active)

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def protocol_id_exists(self, protocol_id: str) -> bool:
        """Check if protocol_id is already registered."""
        query = select(func.count()).select_from(ProtocolDefinitionModel).where(
            ProtocolDefinitionModel.protocol_id == protocol_id
        )
        result = await self._session.execute(query)
        return (result.scalar() or 0) > 0

    async def add(self, entity: ProtocolDefinition) -> ProtocolDefinition:
        """Add new protocol definition."""
        model = ProtocolDefinitionModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: ProtocolDefinition) -> ProtocolDefinition:
        """Update existing protocol definition."""
        result = await self._session.execute(
            select(ProtocolDefinitionModel).where(
                ProtocolDefinitionModel.id == entity.id
            )
        )
        model = result.scalar_one_or_none()

        if not model:
            raise ValueError(f"ProtocolDefinition with id {entity.id} not found")

        model.update_from_domain(entity)
        await self._session.flush()
        return model.to_domain()

    async def delete(self, id: UUID) -> bool:
        """Delete protocol definition by ID."""
        result = await self._session.execute(
            select(ProtocolDefinitionModel).where(ProtocolDefinitionModel.id == id)
        )
        model = result.scalar_one_or_none()

        if not model:
            return False

        await self._session.delete(model)
        await self._session.flush()
        return True
