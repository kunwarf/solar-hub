"""
TimescaleDB connection management for System B (Telemetry).

Provides async SQLAlchemy engine and session management for time-series data.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import MetaData, event, text
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


class TimescaleDBManager:
    """
    Manages TimescaleDB connections and sessions.

    Optimized for high-throughput time-series data ingestion.
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
                pool_pre_ping=True,
                pool_recycle=3600,
                # Optimizations for high-throughput writes
                execution_options={
                    "isolation_level": "AUTOCOMMIT"  # For faster inserts
                }
            )

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
    """
    session_factory = TimescaleDBManager.get_session_factory()
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
    """Dependency for FastAPI to get database session."""
    async with get_db_session() as session:
        yield session


async def init_db() -> None:
    """
    Initialize TimescaleDB tables and extensions.

    Creates hypertables for time-series data.
    """
    engine = TimescaleDBManager.get_engine()

    async with engine.begin() as conn:
        # Enable TimescaleDB extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))

        # Import models to register with metadata
        from .models import telemetry_model  # noqa: F401

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

        # Convert telemetry table to hypertable if not already
        await conn.execute(text("""
            SELECT create_hypertable(
                'telemetry',
                'time',
                if_not_exists => TRUE,
                chunk_time_interval => INTERVAL '1 day'
            )
        """))

        # Create continuous aggregates for hourly data
        await conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 hour', time) AS bucket,
                device_id,
                site_id,
                metric_name,
                AVG(metric_value) as avg_value,
                MIN(metric_value) as min_value,
                MAX(metric_value) as max_value,
                COUNT(*) as sample_count
            FROM telemetry
            GROUP BY bucket, device_id, site_id, metric_name
            WITH NO DATA
        """))

        # Create continuous aggregates for daily data
        await conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_daily
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 day', time) AS bucket,
                device_id,
                site_id,
                metric_name,
                AVG(metric_value) as avg_value,
                MIN(metric_value) as min_value,
                MAX(metric_value) as max_value,
                SUM(CASE WHEN metric_name LIKE '%energy%' THEN metric_value ELSE 0 END) as total_energy,
                COUNT(*) as sample_count
            FROM telemetry
            GROUP BY bucket, device_id, site_id, metric_name
            WITH NO DATA
        """))

        # Add retention policy
        retention_days = settings.database.retention_days
        await conn.execute(text(f"""
            SELECT add_retention_policy(
                'telemetry',
                INTERVAL '{retention_days} days',
                if_not_exists => TRUE
            )
        """))

        # Add compression policy
        compression_days = settings.database.compression_after_days
        await conn.execute(text(f"""
            ALTER TABLE telemetry SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'device_id, site_id, metric_name'
            )
        """))

        await conn.execute(text(f"""
            SELECT add_compression_policy(
                'telemetry',
                INTERVAL '{compression_days} days',
                if_not_exists => TRUE
            )
        """))


async def drop_db() -> None:
    """
    Drop all database tables.

    WARNING: This is destructive. Use only in development/testing.
    """
    if settings.is_production:
        raise RuntimeError("Cannot drop database in production")

    engine = TimescaleDBManager.get_engine()
    async with engine.begin() as conn:
        # Drop continuous aggregates first
        await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS telemetry_daily CASCADE"))
        await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS telemetry_hourly CASCADE"))
        # Drop tables
        await conn.run_sync(Base.metadata.drop_all)


async def health_check() -> bool:
    """Check database connectivity."""
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_database_stats() -> dict:
    """
    Get TimescaleDB statistics.

    Useful for monitoring and debugging.
    """
    async with get_db_session() as session:
        # Get hypertable info
        hypertable_result = await session.execute(text("""
            SELECT hypertable_name, num_chunks, total_bytes,
                   pg_size_pretty(total_bytes) as total_size
            FROM timescaledb_information.hypertables
            WHERE hypertable_name = 'telemetry'
        """))
        hypertable_info = hypertable_result.fetchone()

        # Get chunk info
        chunk_result = await session.execute(text("""
            SELECT COUNT(*) as chunk_count,
                   MIN(range_start) as oldest_data,
                   MAX(range_end) as newest_data
            FROM timescaledb_information.chunks
            WHERE hypertable_name = 'telemetry'
        """))
        chunk_info = chunk_result.fetchone()

        # Get compression stats
        compression_result = await session.execute(text("""
            SELECT COUNT(*) as compressed_chunks,
                   SUM(before_compression_total_bytes) as before_compression,
                   SUM(after_compression_total_bytes) as after_compression
            FROM timescaledb_information.compressed_chunk_stats
            WHERE hypertable_name = 'telemetry'
        """))
        compression_info = compression_result.fetchone()

        return {
            'hypertable': dict(hypertable_info._mapping) if hypertable_info else None,
            'chunks': dict(chunk_info._mapping) if chunk_info else None,
            'compression': dict(compression_info._mapping) if compression_info else None,
        }
