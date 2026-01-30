"""
Command Database Client for Device Server.

Provides database access to command queue for the CommandWorker.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update, Column, String, Integer, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base
from datetime import datetime
from enum import Enum

from ..config import DeviceRegistryDBSettings

# Define CommandStatus enum locally to avoid circular imports
class CommandStatus(str, Enum):
    """Command execution status."""
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

# Define minimal CommandModel locally to avoid cross-package imports
Base = declarative_base()

class CommandModel(Base):
    """Minimal command model for database operations."""
    __tablename__ = "device_commands"

    id = Column(PGUUID(as_uuid=True), primary_key=True)
    device_id = Column(PGUUID(as_uuid=True), nullable=False)
    site_id = Column(PGUUID(as_uuid=True), nullable=False)
    device_serial = Column(String(100), nullable=True)  # Optional: device serial for direct lookup
    command_type = Column(String(100), nullable=False)
    command_params = Column(JSON)
    status = Column(String(50), nullable=False)
    priority = Column(Integer, default=5)
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True))
    result = Column(JSON)  # Note: column is 'result', not 'result_data'
    error_message = Column(Text)

logger = logging.getLogger(__name__)


class CommandDatabaseClient:
    """
    Database client for accessing command queue.

    Provides methods for the CommandWorker to fetch and update commands.
    """

    def __init__(self, db_settings: DeviceRegistryDBSettings):
        """
        Initialize the command database client.

        Args:
            db_settings: Database connection settings.
        """
        self.db_settings = db_settings
        self.engine = None
        self.session_factory = None

    async def connect(self) -> None:
        """Establish database connection."""
        logger.info(f"[COMMAND_DB] Connecting to database: {self.db_settings.host}:{self.db_settings.port}/{self.db_settings.name}")

        self.engine = create_async_engine(
            self.db_settings.url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("[COMMAND_DB] Database connection established")

    async def disconnect(self) -> None:
        """Close database connection."""
        if self.engine:
            logger.info("[COMMAND_DB] Closing database connection")
            await self.engine.dispose()
            logger.info("[COMMAND_DB] Database connection closed")

    async def fetch_pending_commands(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch pending commands from database.

        Args:
            limit: Maximum number of commands to fetch.

        Returns:
            List of command dictionaries.
        """
        if not self.session_factory:
            logger.error("[COMMAND_DB] Cannot fetch commands: not connected")
            return []

        try:
            async with self.session_factory() as session:
                # Query pending commands ordered by priority and creation time
                result = await session.execute(
                    select(CommandModel)
                    .where(CommandModel.status == CommandStatus.PENDING.value)
                    .order_by(CommandModel.priority.asc(), CommandModel.created_at.asc())
                    .limit(limit)
                )

                models = result.scalars().all()

                commands = []
                for model in models:
                    commands.append({
                        "id": model.id,
                        "device_id": model.device_id,
                        "site_id": model.site_id,
                        "device_serial": model.device_serial,  # Include serial for direct lookup
                        "command_type": model.command_type,
                        "command_params": model.command_params or {},
                        "status": model.status,
                        "priority": model.priority,
                        "created_at": model.created_at,
                    })

                logger.debug(f"[COMMAND_DB] Fetched {len(commands)} pending commands")
                return commands

        except Exception as e:
            logger.error(f"[COMMAND_DB] Error fetching pending commands: {e}", exc_info=True)
            return []

    async def mark_sent(self, command_id: UUID) -> None:
        """
        Mark command as sent.

        Args:
            command_id: Command UUID.
        """
        if not self.session_factory:
            logger.error("[COMMAND_DB] Cannot mark command as sent: not connected")
            return

        try:
            async with self.session_factory() as session:
                await session.execute(
                    update(CommandModel)
                    .where(CommandModel.id == command_id)
                    .values(status=CommandStatus.SENT.value)
                )
                await session.commit()
                logger.debug(f"[COMMAND_DB] Marked command {command_id} as SENT")

        except Exception as e:
            logger.error(f"[COMMAND_DB] Error marking command {command_id} as sent: {e}", exc_info=True)

    async def mark_completed(self, command_id: UUID, result_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark command as completed.

        Args:
            command_id: Command UUID.
            result_data: Optional result data.
        """
        if not self.session_factory:
            logger.error("[COMMAND_DB] Cannot mark command as completed: not connected")
            return

        try:
            async with self.session_factory() as session:
                await session.execute(
                    update(CommandModel)
                    .where(CommandModel.id == command_id)
                    .values(
                        status=CommandStatus.COMPLETED.value,
                        result=result_data,  # Column name is 'result'
                    )
                )
                await session.commit()
                logger.debug(f"[COMMAND_DB] Marked command {command_id} as COMPLETED with result: {result_data}")

        except Exception as e:
            logger.error(f"[COMMAND_DB] Error marking command {command_id} as completed: {e}", exc_info=True)

    async def mark_failed(self, command_id: UUID, error_message: str) -> None:
        """
        Mark command as failed.

        Args:
            command_id: Command UUID.
            error_message: Error message.
        """
        if not self.session_factory:
            logger.error("[COMMAND_DB] Cannot mark command as failed: not connected")
            return

        try:
            async with self.session_factory() as session:
                await session.execute(
                    update(CommandModel)
                    .where(CommandModel.id == command_id)
                    .values(
                        status=CommandStatus.FAILED.value,
                        error_message=error_message,
                    )
                )
                await session.commit()
                logger.debug(f"[COMMAND_DB] Marked command {command_id} as FAILED: {error_message}")

        except Exception as e:
            logger.error(f"[COMMAND_DB] Error marking command {command_id} as failed: {e}", exc_info=True)

    async def expire_stale_commands(self) -> int:
        """
        Expire old pending commands.

        Returns:
            Number of commands expired.
        """
        if not self.session_factory:
            logger.error("[COMMAND_DB] Cannot expire commands: not connected")
            return 0

        try:
            async with self.session_factory() as session:
                from datetime import datetime, timezone

                # Expire commands that are past their expiration time
                result = await session.execute(
                    update(CommandModel)
                    .where(
                        CommandModel.status == CommandStatus.PENDING.value,
                        CommandModel.expires_at < datetime.now(timezone.utc)
                    )
                    .values(
                        status=CommandStatus.TIMEOUT.value,
                        error_message="Command expired before execution"
                    )
                )
                await session.commit()

                count = result.rowcount
                if count > 0:
                    logger.info(f"[COMMAND_DB] Expired {count} stale commands")
                return count

        except Exception as e:
            logger.error(f"[COMMAND_DB] Error expiring stale commands: {e}", exc_info=True)
            return 0
