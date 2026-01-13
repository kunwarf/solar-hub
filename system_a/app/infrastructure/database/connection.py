"""
Database connection management for System A (PostgreSQL).

Provides async SQLAlchemy engine and session management.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import MetaData, event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from ...config import get_settings

settings = get_settings()


# Naming convention for database constraints
# This helps with Alembic migrations
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    metadata = metadata


class DatabaseManager:
    """
    Manages database connections and sessions.

    Implements the connection pool and provides async session factory.
    """

    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    @classmethod
    def get_engine(cls) -> AsyncEngine:
        """Get or create the async database engine."""
        if cls._engine is None:
            cls._engine = create_async_engine(
                settings.database.url,
                echo=settings.database.echo_sql,
                pool_size=settings.database.pool_size,
                max_overflow=settings.database.max_overflow,
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,   # Recycle connections every hour
            )

            # Add event listeners for connection lifecycle
            @event.listens_for(cls._engine.sync_engine, "connect")
            def set_timezone(dbapi_conn, connection_record):
                """Set timezone on new connections."""
                cursor = dbapi_conn.cursor()
                cursor.execute(f"SET timezone = '{settings.default_timezone}'")
                cursor.close()

        return cls._engine

    @classmethod
    def get_session_factory(cls) -> async_sessionmaker[AsyncSession]:
        """Get or create the async session factory."""
        if cls._session_factory is None:
            cls._session_factory = async_sessionmaker(
                bind=cls.get_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            )
        return cls._session_factory

    @classmethod
    async def close(cls) -> None:
        """Close the database engine and all connections."""
        if cls._engine is not None:
            await cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional scope around a series of operations.

    Usage:
        async with get_db_session() as session:
            # use session
            session.add(entity)
            await session.commit()
    """
    session_factory = DatabaseManager.get_session_factory()
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get database session.

    Usage in FastAPI:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_db_session() as session:
        yield session


async def init_db() -> None:
    """
    Initialize database tables.

    Should be called on application startup.
    """
    engine = DatabaseManager.get_engine()
    async with engine.begin() as conn:
        # Import all models to register them with metadata
        from .models import (  # noqa: F401
            user_model,
            organization_model,
            site_model,
            device_model,
            alert_model,
            billing_model,
        )
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """
    Drop all database tables.

    WARNING: This is destructive. Use only in development/testing.
    """
    if settings.is_production:
        raise RuntimeError("Cannot drop database in production")

    engine = DatabaseManager.get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def health_check() -> bool:
    """
    Check database connectivity.

    Returns True if database is accessible.
    """
    from sqlalchemy import text
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_unit_of_work():
    """
    Get a Unit of Work instance for transaction management.

    Usage:
        async with get_unit_of_work() as uow:
            user = await uow.users.get_by_id(user_id)
            # ... do work ...
            await uow.commit()
    """
    from .unit_of_work import SQLAlchemyUnitOfWork
    return SQLAlchemyUnitOfWork(DatabaseManager.get_session_factory())
