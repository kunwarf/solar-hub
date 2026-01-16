"""
Repository for device commands in System B.

Handles command queueing, status tracking, and result storage.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import select, update, delete, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.telemetry_model import DeviceCommandsModel
from ....domain.entities.command import DeviceCommand, CommandStatus, CommandResult

logger = logging.getLogger(__name__)


class CommandRepository:
    """
    Repository for device command operations.

    Manages command lifecycle from creation to completion.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def get_by_id(self, command_id: UUID) -> Optional[DeviceCommand]:
        """
        Get a command by ID.

        Args:
            command_id: Command UUID.

        Returns:
            DeviceCommand if found, None otherwise.
        """
        query = select(DeviceCommandsModel).where(
            DeviceCommandsModel.id == command_id
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        return self._model_to_entity(model) if model else None

    async def create(self, command: DeviceCommand) -> DeviceCommand:
        """
        Create a new command.

        Args:
            command: DeviceCommand entity to create.

        Returns:
            Created DeviceCommand entity.
        """
        if not command.id:
            command.id = uuid4()

        model = DeviceCommandsModel(
            id=command.id,
            device_id=command.device_id,
            site_id=command.site_id,
            command_type=command.command_type,
            command_params=command.command_params,
            status=command.status.value if isinstance(command.status, CommandStatus) else command.status,
            scheduled_at=command.scheduled_at,
            expires_at=command.expires_at,
            created_by=command.created_by,
            priority=command.priority,
            max_retries=command.max_retries,
            created_at=command.created_at,
        )

        self._session.add(model)
        await self._session.flush()

        logger.info(f"Created command {command.id} for device {command.device_id}: {command.command_type}")

        return command

    async def update(self, command: DeviceCommand) -> DeviceCommand:
        """
        Update a command.

        Args:
            command: DeviceCommand entity with updated values.

        Returns:
            Updated DeviceCommand entity.
        """
        command.updated_at = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(DeviceCommandsModel.id == command.id)
            .values(
                status=command.status.value if isinstance(command.status, CommandStatus) else command.status,
                sent_at=command.sent_at,
                acknowledged_at=command.acknowledged_at,
                completed_at=command.completed_at,
                result=command.result,
                error_message=command.error_message,
                retry_count=command.retry_count,
            )
        )

        await self._session.execute(stmt)
        return command

    async def delete(self, command_id: UUID) -> bool:
        """
        Delete a command.

        Args:
            command_id: Command UUID to delete.

        Returns:
            True if deleted, False if not found.
        """
        stmt = delete(DeviceCommandsModel).where(
            DeviceCommandsModel.id == command_id
        )
        result = await self._session.execute(stmt)

        return result.rowcount > 0

    # =========================================================================
    # Queue Operations
    # =========================================================================

    async def get_pending_commands(
        self,
        device_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> List[DeviceCommand]:
        """
        Get pending commands ready for execution.

        Args:
            device_id: Optional device filter.
            limit: Maximum commands to return.

        Returns:
            List of pending DeviceCommand entities, ordered by priority and time.
        """
        now = datetime.now(timezone.utc)

        conditions = [
            DeviceCommandsModel.status == CommandStatus.PENDING.value,
            or_(
                DeviceCommandsModel.scheduled_at.is_(None),
                DeviceCommandsModel.scheduled_at <= now,
            ),
            or_(
                DeviceCommandsModel.expires_at.is_(None),
                DeviceCommandsModel.expires_at > now,
            ),
        ]

        if device_id:
            conditions.append(DeviceCommandsModel.device_id == device_id)

        query = (
            select(DeviceCommandsModel)
            .where(and_(*conditions))
            .order_by(
                DeviceCommandsModel.priority,
                DeviceCommandsModel.created_at,
            )
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    async def get_device_queue(
        self,
        device_id: UUID,
        include_completed: bool = False,
        limit: int = 50,
    ) -> List[DeviceCommand]:
        """
        Get command queue for a device.

        Args:
            device_id: Device UUID.
            include_completed: Include completed commands.
            limit: Maximum commands to return.

        Returns:
            List of DeviceCommand entities.
        """
        conditions = [DeviceCommandsModel.device_id == device_id]

        if not include_completed:
            conditions.append(
                DeviceCommandsModel.status.in_([
                    CommandStatus.PENDING.value,
                    CommandStatus.SENT.value,
                    CommandStatus.ACKNOWLEDGED.value,
                ])
            )

        query = (
            select(DeviceCommandsModel)
            .where(and_(*conditions))
            .order_by(desc(DeviceCommandsModel.created_at))
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    async def claim_pending_command(
        self,
        device_id: UUID,
    ) -> Optional[DeviceCommand]:
        """
        Claim the next pending command for a device (atomic operation).

        Args:
            device_id: Device UUID.

        Returns:
            Claimed DeviceCommand, or None if no pending commands.
        """
        now = datetime.now(timezone.utc)

        # Select and update in one query (PostgreSQL specific)
        subquery = (
            select(DeviceCommandsModel.id)
            .where(
                and_(
                    DeviceCommandsModel.device_id == device_id,
                    DeviceCommandsModel.status == CommandStatus.PENDING.value,
                    or_(
                        DeviceCommandsModel.scheduled_at.is_(None),
                        DeviceCommandsModel.scheduled_at <= now,
                    ),
                    or_(
                        DeviceCommandsModel.expires_at.is_(None),
                        DeviceCommandsModel.expires_at > now,
                    ),
                )
            )
            .order_by(DeviceCommandsModel.priority, DeviceCommandsModel.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        result = await self._session.execute(subquery)
        command_id = result.scalar_one_or_none()

        if not command_id:
            return None

        # Update status to SENT
        stmt = (
            update(DeviceCommandsModel)
            .where(DeviceCommandsModel.id == command_id)
            .values(
                status=CommandStatus.SENT.value,
                sent_at=now,
            )
            .returning(DeviceCommandsModel)
        )

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        return self._model_to_entity(model) if model else None

    # =========================================================================
    # Status Updates
    # =========================================================================

    async def mark_sent(self, command_id: UUID) -> None:
        """
        Mark command as sent to device.

        Args:
            command_id: Command UUID.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(DeviceCommandsModel.id == command_id)
            .values(
                status=CommandStatus.SENT.value,
                sent_at=now,
            )
        )

        await self._session.execute(stmt)

    async def mark_acknowledged(self, command_id: UUID) -> None:
        """
        Mark command as acknowledged by device.

        Args:
            command_id: Command UUID.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(DeviceCommandsModel.id == command_id)
            .values(
                status=CommandStatus.ACKNOWLEDGED.value,
                acknowledged_at=now,
            )
        )

        await self._session.execute(stmt)

    async def mark_completed(
        self,
        command_id: UUID,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark command as completed successfully.

        Args:
            command_id: Command UUID.
            result: Optional result data.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(DeviceCommandsModel.id == command_id)
            .values(
                status=CommandStatus.COMPLETED.value,
                completed_at=now,
                result=result,
            )
        )

        await self._session.execute(stmt)
        logger.info(f"Command {command_id} completed successfully")

    async def mark_failed(
        self,
        command_id: UUID,
        error_message: str,
    ) -> None:
        """
        Mark command as failed.

        Args:
            command_id: Command UUID.
            error_message: Error description.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(DeviceCommandsModel.id == command_id)
            .values(
                status=CommandStatus.FAILED.value,
                completed_at=now,
                error_message=error_message,
            )
        )

        await self._session.execute(stmt)
        logger.warning(f"Command {command_id} failed: {error_message}")

    async def mark_timeout(self, command_id: UUID) -> None:
        """
        Mark command as timed out.

        Args:
            command_id: Command UUID.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(DeviceCommandsModel.id == command_id)
            .values(
                status=CommandStatus.TIMEOUT.value,
                completed_at=now,
                error_message="Command timed out",
            )
        )

        await self._session.execute(stmt)
        logger.warning(f"Command {command_id} timed out")

    async def cancel_command(self, command_id: UUID) -> bool:
        """
        Cancel a pending command.

        Args:
            command_id: Command UUID.

        Returns:
            True if cancelled, False if not found or not cancellable.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(
                and_(
                    DeviceCommandsModel.id == command_id,
                    DeviceCommandsModel.status.in_([
                        CommandStatus.PENDING.value,
                        CommandStatus.SENT.value,
                    ])
                )
            )
            .values(
                status=CommandStatus.CANCELLED.value,
                completed_at=now,
            )
        )

        result = await self._session.execute(stmt)
        return result.rowcount > 0

    # =========================================================================
    # Retry Operations
    # =========================================================================

    async def retry_command(self, command_id: UUID) -> Optional[DeviceCommand]:
        """
        Retry a failed command.

        Args:
            command_id: Command UUID.

        Returns:
            Updated DeviceCommand if retry is possible, None otherwise.
        """
        # Get current command
        command = await self.get_by_id(command_id)
        if not command:
            return None

        if not command.can_retry():
            logger.warning(f"Command {command_id} cannot be retried")
            return None

        # Reset for retry
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(DeviceCommandsModel.id == command_id)
            .values(
                status=CommandStatus.PENDING.value,
                sent_at=None,
                acknowledged_at=None,
                completed_at=None,
                error_message=None,
                retry_count=DeviceCommandsModel.retry_count + 1,
            )
        )

        await self._session.execute(stmt)
        logger.info(f"Command {command_id} queued for retry (attempt {command.retry_count + 1})")

        return await self.get_by_id(command_id)

    async def get_retryable_commands(
        self,
        device_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> List[DeviceCommand]:
        """
        Get commands that can be retried.

        Args:
            device_id: Optional device filter.
            limit: Maximum commands to return.

        Returns:
            List of retryable DeviceCommand entities.
        """
        now = datetime.now(timezone.utc)

        conditions = [
            DeviceCommandsModel.status.in_([
                CommandStatus.FAILED.value,
                CommandStatus.TIMEOUT.value,
            ]),
            DeviceCommandsModel.retry_count < DeviceCommandsModel.max_retries,
            or_(
                DeviceCommandsModel.expires_at.is_(None),
                DeviceCommandsModel.expires_at > now,
            ),
        ]

        if device_id:
            conditions.append(DeviceCommandsModel.device_id == device_id)

        query = (
            select(DeviceCommandsModel)
            .where(and_(*conditions))
            .order_by(DeviceCommandsModel.created_at)
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    # =========================================================================
    # Expiration Handling
    # =========================================================================

    async def expire_old_commands(
        self,
        batch_size: int = 100,
    ) -> int:
        """
        Expire commands that have passed their expiration time.

        Args:
            batch_size: Maximum commands to expire per call.

        Returns:
            Number of commands expired.
        """
        now = datetime.now(timezone.utc)

        stmt = (
            update(DeviceCommandsModel)
            .where(
                and_(
                    DeviceCommandsModel.status.in_([
                        CommandStatus.PENDING.value,
                        CommandStatus.SENT.value,
                    ]),
                    DeviceCommandsModel.expires_at.isnot(None),
                    DeviceCommandsModel.expires_at <= now,
                )
            )
            .values(
                status=CommandStatus.TIMEOUT.value,
                completed_at=now,
                error_message="Command expired",
            )
        )

        result = await self._session.execute(stmt)
        count = result.rowcount

        if count > 0:
            logger.info(f"Expired {count} commands")

        return count

    # =========================================================================
    # Query Operations
    # =========================================================================

    async def get_command_history(
        self,
        device_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        command_type: Optional[str] = None,
        status: Optional[CommandStatus] = None,
        limit: int = 100,
    ) -> List[DeviceCommand]:
        """
        Get command history for a device.

        Args:
            device_id: Device UUID.
            start_time: Filter from this time.
            end_time: Filter to this time.
            command_type: Filter by command type.
            status: Filter by status.
            limit: Maximum commands to return.

        Returns:
            List of DeviceCommand entities.
        """
        conditions = [DeviceCommandsModel.device_id == device_id]

        if start_time:
            conditions.append(DeviceCommandsModel.created_at >= start_time)
        if end_time:
            conditions.append(DeviceCommandsModel.created_at <= end_time)
        if command_type:
            conditions.append(DeviceCommandsModel.command_type == command_type)
        if status:
            conditions.append(DeviceCommandsModel.status == status.value)

        query = (
            select(DeviceCommandsModel)
            .where(and_(*conditions))
            .order_by(desc(DeviceCommandsModel.created_at))
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    async def get_site_commands(
        self,
        site_id: UUID,
        pending_only: bool = False,
        limit: int = 100,
    ) -> List[DeviceCommand]:
        """
        Get all commands for devices at a site.

        Args:
            site_id: Site UUID.
            pending_only: Only return pending commands.
            limit: Maximum commands to return.

        Returns:
            List of DeviceCommand entities.
        """
        conditions = [DeviceCommandsModel.site_id == site_id]

        if pending_only:
            conditions.append(
                DeviceCommandsModel.status.in_([
                    CommandStatus.PENDING.value,
                    CommandStatus.SENT.value,
                    CommandStatus.ACKNOWLEDGED.value,
                ])
            )

        query = (
            select(DeviceCommandsModel)
            .where(and_(*conditions))
            .order_by(desc(DeviceCommandsModel.created_at))
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_command_stats(
        self,
        device_id: Optional[UUID] = None,
        site_id: Optional[UUID] = None,
        since: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """
        Get command statistics.

        Args:
            device_id: Optional device filter.
            site_id: Optional site filter.
            since: Get stats since this time.

        Returns:
            Dict with counts by status.
        """
        conditions = []

        if device_id:
            conditions.append(DeviceCommandsModel.device_id == device_id)
        if site_id:
            conditions.append(DeviceCommandsModel.site_id == site_id)
        if since:
            conditions.append(DeviceCommandsModel.created_at >= since)

        query = select(
            DeviceCommandsModel.status,
            func.count().label("count"),
        ).group_by(DeviceCommandsModel.status)

        if conditions:
            query = query.where(and_(*conditions))

        result = await self._session.execute(query)
        rows = result.all()

        return {row.status: row.count for row in rows}

    async def get_pending_count(
        self,
        device_id: Optional[UUID] = None,
    ) -> int:
        """
        Get count of pending commands.

        Args:
            device_id: Optional device filter.

        Returns:
            Number of pending commands.
        """
        conditions = [
            DeviceCommandsModel.status == CommandStatus.PENDING.value
        ]

        if device_id:
            conditions.append(DeviceCommandsModel.device_id == device_id)

        query = select(func.count()).where(and_(*conditions))
        result = await self._session.execute(query)

        return result.scalar() or 0

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def cleanup_old_commands(
        self,
        older_than: datetime,
        statuses: Optional[List[CommandStatus]] = None,
    ) -> int:
        """
        Delete old commands from the database.

        Args:
            older_than: Delete commands completed before this time.
            statuses: Only delete commands with these statuses.

        Returns:
            Number of commands deleted.
        """
        conditions = [DeviceCommandsModel.completed_at < older_than]

        if statuses:
            conditions.append(
                DeviceCommandsModel.status.in_([s.value for s in statuses])
            )
        else:
            # Default to terminal statuses
            conditions.append(
                DeviceCommandsModel.status.in_([
                    CommandStatus.COMPLETED.value,
                    CommandStatus.FAILED.value,
                    CommandStatus.TIMEOUT.value,
                    CommandStatus.CANCELLED.value,
                ])
            )

        stmt = delete(DeviceCommandsModel).where(and_(*conditions))
        result = await self._session.execute(stmt)

        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} old commands")

        return count

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _model_to_entity(self, model: DeviceCommandsModel) -> DeviceCommand:
        """Convert SQLAlchemy model to domain entity."""
        return DeviceCommand(
            id=model.id,
            device_id=model.device_id,
            site_id=model.site_id,
            command_type=model.command_type,
            command_params=model.command_params,
            status=CommandStatus(model.status) if model.status else CommandStatus.PENDING,
            scheduled_at=model.scheduled_at,
            sent_at=model.sent_at,
            acknowledged_at=model.acknowledged_at,
            completed_at=model.completed_at,
            expires_at=model.expires_at,
            result=model.result,
            error_message=model.error_message,
            retry_count=model.retry_count,
            max_retries=model.max_retries,
            created_by=model.created_by,
            priority=model.priority,
            created_at=model.created_at,
        )
