"""
FastAPI dependencies for System B API.

Provides database sessions and service instances via dependency injection.
"""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from ..infrastructure.database.repositories import (
    TelemetryRepository,
    DeviceRegistryRepository,
    CommandRepository,
    EventRepository,
)
from ..application.services import (
    TelemetryService,
    DeviceService,
    CommandService,
    DeviceAuthService,
)

# Database URL from environment
DATABASE_URL = os.getenv(
    "SYSTEM_B_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/solar_hub_timescale"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_size=20,
    max_overflow=10,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_telemetry_repository(
    session: AsyncSession = None,
) -> TelemetryRepository:
    """Get telemetry repository instance."""
    if session is None:
        async with async_session_maker() as session:
            return TelemetryRepository(session)
    return TelemetryRepository(session)


async def get_device_repository(
    session: AsyncSession = None,
) -> DeviceRegistryRepository:
    """Get device registry repository instance."""
    if session is None:
        async with async_session_maker() as session:
            return DeviceRegistryRepository(session)
    return DeviceRegistryRepository(session)


async def get_command_repository(
    session: AsyncSession = None,
) -> CommandRepository:
    """Get command repository instance."""
    if session is None:
        async with async_session_maker() as session:
            return CommandRepository(session)
    return CommandRepository(session)


async def get_event_repository(
    session: AsyncSession = None,
) -> EventRepository:
    """Get event repository instance."""
    if session is None:
        async with async_session_maker() as session:
            return EventRepository(session)
    return EventRepository(session)


async def get_telemetry_service(
    session: AsyncSession = None,
) -> TelemetryService:
    """Get telemetry service instance."""
    if session is None:
        async with async_session_maker() as session:
            telemetry_repo = TelemetryRepository(session)
            event_repo = EventRepository(session)
            return TelemetryService(telemetry_repo, event_repo)
    telemetry_repo = TelemetryRepository(session)
    event_repo = EventRepository(session)
    return TelemetryService(telemetry_repo, event_repo)


async def get_device_service(
    session: AsyncSession = None,
) -> DeviceService:
    """Get device service instance."""
    if session is None:
        async with async_session_maker() as session:
            device_repo = DeviceRegistryRepository(session)
            event_repo = EventRepository(session)
            return DeviceService(device_repo, event_repo)
    device_repo = DeviceRegistryRepository(session)
    event_repo = EventRepository(session)
    return DeviceService(device_repo, event_repo)


async def get_command_service(
    session: AsyncSession = None,
) -> CommandService:
    """Get command service instance."""
    if session is None:
        async with async_session_maker() as session:
            command_repo = CommandRepository(session)
            event_repo = EventRepository(session)
            return CommandService(command_repo, event_repo)
    command_repo = CommandRepository(session)
    event_repo = EventRepository(session)
    return CommandService(command_repo, event_repo)


async def get_auth_service(
    session: AsyncSession = None,
) -> DeviceAuthService:
    """Get device auth service instance."""
    if session is None:
        async with async_session_maker() as session:
            device_repo = DeviceRegistryRepository(session)
            return DeviceAuthService(device_repo)
    device_repo = DeviceRegistryRepository(session)
    return DeviceAuthService(device_repo)
