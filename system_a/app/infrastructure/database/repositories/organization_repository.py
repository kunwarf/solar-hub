"""
SQLAlchemy implementation of OrganizationRepository.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ....application.interfaces.repositories import OrganizationRepository
from ....domain.entities.organization import Organization, OrganizationStatus, MembershipStatus
from ..models.organization_model import OrganizationModel, OrganizationMemberModel


class SQLAlchemyOrganizationRepository(OrganizationRepository):
    """SQLAlchemy implementation of organization repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[Organization]:
        """Get organization by ID."""
        result = await self._session.execute(
            select(OrganizationModel)
            .options(selectinload(OrganizationModel.members))
            .where(OrganizationModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        """Get organization by URL slug."""
        result = await self._session.execute(
            select(OrganizationModel)
            .options(selectinload(OrganizationModel.members))
            .where(OrganizationModel.slug == slug)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_owner_id(self, owner_id: UUID) -> List[Organization]:
        """Get organizations owned by a user."""
        result = await self._session.execute(
            select(OrganizationModel)
            .options(selectinload(OrganizationModel.members))
            .where(OrganizationModel.owner_id == owner_id)
            .order_by(OrganizationModel.created_at.desc())
        )
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_by_member_id(self, user_id: UUID) -> List[Organization]:
        """Get organizations where user is a member."""
        result = await self._session.execute(
            select(OrganizationModel)
            .options(selectinload(OrganizationModel.members))
            .join(OrganizationMemberModel)
            .where(
                OrganizationMemberModel.user_id == user_id,
                OrganizationMemberModel.status == MembershipStatus.ACTIVE
            )
            .order_by(OrganizationModel.created_at.desc())
        )
        models = result.scalars().unique().all()
        return [m.to_domain() for m in models]

    async def slug_exists(self, slug: str) -> bool:
        """Check if organization slug is already taken."""
        result = await self._session.execute(
            select(func.count()).select_from(OrganizationModel).where(
                OrganizationModel.slug == slug
            )
        )
        count = result.scalar()
        return count > 0

    async def add(self, entity: Organization) -> Organization:
        """Add new organization."""
        model = OrganizationModel.from_domain(entity)

        # Add members
        for member in entity.members:
            member_model = OrganizationMemberModel.from_domain(member)
            model.members.append(member_model)

        self._session.add(model)
        await self._session.flush()

        # Reload to get relationships
        await self._session.refresh(model, ['members'])
        return model.to_domain()

    async def update(self, entity: Organization) -> Organization:
        """Update existing organization."""
        result = await self._session.execute(
            select(OrganizationModel)
            .options(selectinload(OrganizationModel.members))
            .where(OrganizationModel.id == entity.id)
        )
        model = result.scalar_one_or_none()

        if model:
            model.update_from_domain(entity)

            # Sync members
            existing_member_ids = {m.id for m in model.members}
            new_member_ids = {m.id for m in entity.members}

            # Remove deleted members
            for member_model in list(model.members):
                if member_model.id not in new_member_ids:
                    model.members.remove(member_model)

            # Add or update members
            for member in entity.members:
                existing = next(
                    (m for m in model.members if m.id == member.id),
                    None
                )
                if existing:
                    # Update existing
                    existing.role = member.role
                    existing.status = member.status
                    existing.accepted_at = member.accepted_at
                    existing.updated_at = member.updated_at
                else:
                    # Add new
                    member_model = OrganizationMemberModel.from_domain(member)
                    model.members.append(member_model)

            await self._session.flush()
            return model.to_domain()
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete organization by ID."""
        result = await self._session.execute(
            select(OrganizationModel).where(OrganizationModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Organization]:
        """List organizations with pagination."""
        query = select(OrganizationModel).options(
            selectinload(OrganizationModel.members)
        )

        if status:
            query = query.where(
                OrganizationModel.status == OrganizationStatus(status)
            )

        query = query.order_by(OrganizationModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def count(self, status: Optional[str] = None) -> int:
        """Count total organizations."""
        query = select(func.count()).select_from(OrganizationModel)

        if status:
            query = query.where(
                OrganizationModel.status == OrganizationStatus(status)
            )

        result = await self._session.execute(query)
        return result.scalar() or 0
