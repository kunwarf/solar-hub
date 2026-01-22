"""
Alembic environment configuration.

This file is executed every time Alembic runs a migration.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool, text as sa_text
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
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    # Run migrations - duplicate enum errors are handled in the migration itself
    # The migration uses DO blocks to create enums only if they don't exist
    # SQLAlchemy may still try to create them, but the DO block handles duplicates
    with context.begin_transaction():
        try:
            context.run_migrations()
        except Exception as e:
            # Check if this is a duplicate enum error that slipped through
            error_str = str(e).lower()
            if 'duplicate' in error_str and ('type' in error_str or 'enum' in error_str) and 'already exists' in error_str:
                # This is a duplicate enum error - the enum was already created
                # Rollback and try again (the enum now exists, so SQLAlchemy won't try to create it)
                connection.rollback()
                # Re-run migrations - this time the enum exists so SQLAlchemy won't try to create it
                with context.begin_transaction():
                    context.run_migrations()
            else:
                # Different error, re-raise
                raise


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
