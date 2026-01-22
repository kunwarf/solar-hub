"""
Alembic environment configuration.

This file is executed every time Alembic runs a migration.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.database.models import Base
from app.config import get_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from settings or environment."""
    # Try to get from environment first (for CI/CD)
    url = os.getenv("DATABASE_URL")
    if url:
        # Convert postgres:// to postgresql+asyncpg://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Fall back to settings
    try:
        settings = get_settings()
        return settings.database.url  # Use async URL for migrations
    except Exception:
        # Return a default for development if settings fail
        return "postgresql+asyncpg://postgres:postgres@localhost:5432/solar_hub"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    # Create a custom DDL visitor that checks if enum types exist before creating them
    from sqlalchemy.dialects.postgresql.base import PGDDLCompiler
    from sqlalchemy.dialects.postgresql.named_types import ENUM
    
    original_visit_enum = PGDDLCompiler.visit_ENUM
    
    def visit_ENUM_with_check(self, element, **kw):
        """Check if enum exists before creating it."""
        # Check if enum type exists
        result = connection.execute(
            sa.text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type 
                    WHERE typname = :enum_name
                )
            """),
            {"enum_name": element.name}
        )
        exists = result.scalar()
        
        if exists:
            # Enum already exists, don't try to create it
            return ""
        else:
            # Enum doesn't exist, create it using the original method
            return original_visit_enum(self, element, **kw)
    
    # Temporarily replace the visit_ENUM method
    PGDDLCompiler.visit_ENUM = visit_ENUM_with_check
    
    try:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()
    finally:
        # Restore the original method
        PGDDLCompiler.visit_ENUM = original_visit_enum


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
