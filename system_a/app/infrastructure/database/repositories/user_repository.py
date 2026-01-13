"""
SQLAlchemy implementation of UserRepository.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.interfaces.repositories import UserRepository
from ....domain.entities.user import User, UserStatus
from ..models.user_model import UserModel


class SQLAlchemyUserRepository(UserRepository):
    """SQLAlchemy implementation of user repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email.lower())
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.phone == phone)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def email_exists(self, email: str) -> bool:
        """Check if email is already registered."""
        result = await self._session.execute(
            select(func.count()).select_from(UserModel).where(
                UserModel.email == email.lower()
            )
        )
        count = result.scalar()
        return count > 0

    async def add(self, entity: User) -> User:
        """Add new user."""
        model = UserModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: User) -> User:
        """Update existing user."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == entity.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(entity)
            await self._session.flush()
            return model.to_domain()
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete user by ID."""
        result = await self._session.execute(
            select(UserModel).where(UserModel.id == id)
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
    ) -> List[User]:
        """List users with pagination."""
        query = select(UserModel)

        if status:
            query = query.where(UserModel.status == UserStatus(status))

        query = query.order_by(UserModel.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def count(self, status: Optional[str] = None) -> int:
        """Count total users."""
        query = select(func.count()).select_from(UserModel)

        if status:
            query = query.where(UserModel.status == UserStatus(status))

        result = await self._session.execute(query)
        return result.scalar() or 0
