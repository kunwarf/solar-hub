"""
SQLAlchemy implementation of SiteRepository.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.interfaces.repositories import SiteRepository
from ....domain.entities.site import Site, SiteStatus
from ..models.site_model import SiteModel


class SQLAlchemySiteRepository(SiteRepository):
    """SQLAlchemy implementation of site repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[Site]:
        """Get site by ID."""
        result = await self._session.execute(
            select(SiteModel).where(SiteModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_organization_id(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Site]:
        """Get sites belonging to an organization."""
        query = select(SiteModel).where(
            SiteModel.organization_id == organization_id
        )

        if status:
            query = query.where(SiteModel.status == SiteStatus(status))

        query = query.order_by(SiteModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def count_by_organization_id(
        self,
        organization_id: UUID,
        status: Optional[str] = None
    ) -> int:
        """Count sites in an organization."""
        query = select(func.count()).select_from(SiteModel).where(
            SiteModel.organization_id == organization_id
        )

        if status:
            query = query.where(SiteModel.status == SiteStatus(status))

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def get_active_sites(self, organization_id: UUID) -> List[Site]:
        """Get all active sites for an organization."""
        result = await self._session.execute(
            select(SiteModel).where(
                SiteModel.organization_id == organization_id,
                SiteModel.status == SiteStatus.ACTIVE
            ).order_by(SiteModel.name)
        )
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def search_by_name(
        self,
        organization_id: UUID,
        name_query: str,
        limit: int = 20
    ) -> List[Site]:
        """Search sites by name within an organization."""
        result = await self._session.execute(
            select(SiteModel).where(
                SiteModel.organization_id == organization_id,
                SiteModel.name.ilike(f'%{name_query}%')
            ).limit(limit)
        )
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_sites_by_city(
        self,
        city: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Site]:
        """Get sites in a specific city."""
        # JSON query for city in address
        result = await self._session.execute(
            select(SiteModel).where(
                SiteModel.address['city'].astext.ilike(f'%{city}%')
            ).limit(limit).offset(offset)
        )
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def add(self, entity: Site) -> Site:
        """Add new site."""
        model = SiteModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: Site) -> Site:
        """Update existing site."""
        result = await self._session.execute(
            select(SiteModel).where(SiteModel.id == entity.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(entity)
            await self._session.flush()
            return model.to_domain()
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete site by ID."""
        result = await self._session.execute(
            select(SiteModel).where(SiteModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False
