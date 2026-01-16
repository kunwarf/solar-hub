"""
Command Service for System B.

Handles device command queueing, execution, and result tracking.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Callable, Awaitable
from uuid import UUID, uuid4

from ...domain.entities.command import DeviceCommand, CommandStatus, CommandResult
from ...domain.entities.event import DeviceEvent, EventType, EventSeverity
from ...infrastructure.database.repositories import CommandRepository, EventRepository

logger = logging.getLogger(__name__)


# Type for command execution callbacks
CommandExecutor = Callable[[DeviceCommand], Awaitable[CommandResult]]


class CommandService:
    """
    Application service for device commands.

    Coordinates command lifecycle from creation to completion.
    """

    def __init__(
        self,
        command_repo: CommandRepository,
        event_repo: Optional[EventRepository] = None,
    ):
        self._command_repo = command_repo
        self._event_repo = event_repo
        self._executors: Dict[str, CommandExecutor] = {}
        self._pending_callbacks: Dict[UUID, asyncio.Future] = {}

    # =========================================================================
    # Command Creation
    # =========================================================================

    async def create_command(
        self,
        device_id: UUID,
        site_id: UUID,
        command_type: str,
        command_params: Optional[Dict[str, Any]] = None,
        scheduled_at: Optional[datetime] = None,
        expires_in_minutes: int = 60,
        priority: int = 5,
        created_by: Optional[UUID] = None,
    ) -> DeviceCommand:
        """
        Create a new device command.

        Args:
            device_id: Target device UUID.
            site_id: Site UUID.
            command_type: Type of command.
            command_params: Command parameters.
            scheduled_at: Optional scheduled execution time.
            expires_in_minutes: Command expiration time.
            priority: Priority (1=highest, 10=lowest).
            created_by: User who created the command.

        Returns:
            Created DeviceCommand entity.
        """
        command = DeviceCommand(
            id=uuid4(),
            device_id=device_id,
            site_id=site_id,
            command_type=command_type,
            command_params=command_params or {},
            scheduled_at=scheduled_at,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
            priority=priority,
            created_by=created_by,
        )

        created = await self._command_repo.create(command)

        logger.info(f"Created command {created.id}: {command_type} for device {device_id}")

        return created

    async def create_immediate_command(
        self,
        device_id: UUID,
        site_id: UUID,
        command_type: str,
        command_params: Optional[Dict[str, Any]] = None,
        created_by: Optional[UUID] = None,
        wait_for_completion: bool = False,
        timeout_seconds: int = 30,
    ) -> DeviceCommand:
        """
        Create and optionally wait for command completion.

        Args:
            device_id: Target device UUID.
            site_id: Site UUID.
            command_type: Type of command.
            command_params: Command parameters.
            created_by: User who created the command.
            wait_for_completion: Whether to wait for command to complete.
            timeout_seconds: Timeout when waiting.

        Returns:
            DeviceCommand (with result if waited).
        """
        command = await self.create_command(
            device_id=device_id,
            site_id=site_id,
            command_type=command_type,
            command_params=command_params,
            priority=1,  # High priority for immediate commands
            created_by=created_by,
        )

        if wait_for_completion:
            return await self.wait_for_completion(command.id, timeout_seconds)

        return command

    # =========================================================================
    # Command Retrieval
    # =========================================================================

    async def get_command(self, command_id: UUID) -> Optional[DeviceCommand]:
        """
        Get a command by ID.

        Args:
            command_id: Command UUID.

        Returns:
            DeviceCommand if found, None otherwise.
        """
        return await self._command_repo.get_by_id(command_id)

    async def get_device_commands(
        self,
        device_id: UUID,
        include_completed: bool = False,
        limit: int = 50,
    ) -> List[DeviceCommand]:
        """
        Get commands for a device.

        Args:
            device_id: Device UUID.
            include_completed: Include completed commands.
            limit: Maximum commands to return.

        Returns:
            List of DeviceCommand entities.
        """
        return await self._command_repo.get_device_queue(
            device_id=device_id,
            include_completed=include_completed,
            limit=limit,
        )

    async def get_site_commands(
        self,
        site_id: UUID,
        pending_only: bool = False,
        limit: int = 100,
    ) -> List[DeviceCommand]:
        """
        Get commands for all devices at a site.

        Args:
            site_id: Site UUID.
            pending_only: Only return pending commands.
            limit: Maximum commands to return.

        Returns:
            List of DeviceCommand entities.
        """
        return await self._command_repo.get_site_commands(
            site_id=site_id,
            pending_only=pending_only,
            limit=limit,
        )

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
            List of pending DeviceCommand entities.
        """
        return await self._command_repo.get_pending_commands(device_id, limit)

    async def get_command_history(
        self,
        device_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        command_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeviceCommand]:
        """
        Get command history for a device.

        Args:
            device_id: Device UUID.
            start_time: Filter from this time.
            end_time: Filter to this time.
            command_type: Filter by command type.
            limit: Maximum commands to return.

        Returns:
            List of historical DeviceCommand entities.
        """
        return await self._command_repo.get_command_history(
            device_id=device_id,
            start_time=start_time,
            end_time=end_time,
            command_type=command_type,
            limit=limit,
        )

    # =========================================================================
    # Command Execution
    # =========================================================================

    def register_executor(
        self,
        command_type: str,
        executor: CommandExecutor,
    ) -> None:
        """
        Register a command executor for a command type.

        Args:
            command_type: Type of command.
            executor: Async function to execute the command.
        """
        self._executors[command_type] = executor
        logger.debug(f"Registered executor for command type: {command_type}")

    async def claim_and_execute(
        self,
        device_id: UUID,
        executor: Optional[CommandExecutor] = None,
    ) -> Optional[CommandResult]:
        """
        Claim next pending command for a device and execute it.

        Args:
            device_id: Device UUID.
            executor: Optional executor (uses registered if not provided).

        Returns:
            CommandResult if command was executed, None if no pending commands.
        """
        # Claim command atomically
        command = await self._command_repo.claim_pending_command(device_id)
        if not command:
            return None

        return await self.execute_command(command, executor)

    async def execute_command(
        self,
        command: DeviceCommand,
        executor: Optional[CommandExecutor] = None,
    ) -> CommandResult:
        """
        Execute a command using registered or provided executor.

        Args:
            command: Command to execute.
            executor: Optional executor.

        Returns:
            CommandResult with execution outcome.
        """
        # Get executor
        exec_func = executor or self._executors.get(command.command_type)
        if not exec_func:
            error_msg = f"No executor registered for command type: {command.command_type}"
            await self._command_repo.mark_failed(command.id, error_msg)
            logger.error(error_msg)
            return CommandResult(
                command_id=command.id,
                device_id=command.device_id,
                success=False,
                error_code="NO_EXECUTOR",
                error_message=error_msg,
            )

        # Mark as sent if not already
        if command.status == CommandStatus.PENDING:
            await self._command_repo.mark_sent(command.id)

        try:
            # Execute command
            result = await exec_func(command)

            # Update command status based on result
            if result.success:
                await self._command_repo.mark_completed(command.id, result.data)
            else:
                await self._command_repo.mark_failed(
                    command.id,
                    result.error_message or "Execution failed",
                )

            # Notify waiters
            await self._notify_completion(command.id, result)

            # Log event if event repo available
            if self._event_repo:
                await self._log_command_event(command, result)

            return result

        except asyncio.TimeoutError:
            await self._command_repo.mark_timeout(command.id)
            result = CommandResult(
                command_id=command.id,
                device_id=command.device_id,
                success=False,
                error_code="TIMEOUT",
                error_message="Command execution timed out",
            )
            await self._notify_completion(command.id, result)
            return result

        except Exception as e:
            error_msg = str(e)
            await self._command_repo.mark_failed(command.id, error_msg)
            logger.exception(f"Command {command.id} execution failed: {e}")
            result = CommandResult(
                command_id=command.id,
                device_id=command.device_id,
                success=False,
                error_code="EXCEPTION",
                error_message=error_msg,
            )
            await self._notify_completion(command.id, result)
            return result

    async def report_result(
        self,
        command_id: UUID,
        success: bool,
        data: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Report command execution result (for external executors).

        Args:
            command_id: Command UUID.
            success: Whether command succeeded.
            data: Result data.
            error_code: Error code if failed.
            error_message: Error message if failed.
        """
        command = await self._command_repo.get_by_id(command_id)
        if not command:
            logger.warning(f"Cannot report result for unknown command: {command_id}")
            return

        if success:
            await self._command_repo.mark_completed(command_id, data)
        else:
            await self._command_repo.mark_failed(command_id, error_message or "Failed")

        result = CommandResult(
            command_id=command_id,
            device_id=command.device_id,
            success=success,
            data=data,
            error_code=error_code,
            error_message=error_message,
        )

        await self._notify_completion(command_id, result)

        if self._event_repo:
            await self._log_command_event(command, result)

    # =========================================================================
    # Command Status Updates
    # =========================================================================

    async def mark_acknowledged(self, command_id: UUID) -> None:
        """
        Mark command as acknowledged by device.

        Args:
            command_id: Command UUID.
        """
        await self._command_repo.mark_acknowledged(command_id)

    async def cancel_command(self, command_id: UUID) -> bool:
        """
        Cancel a pending command.

        Args:
            command_id: Command UUID.

        Returns:
            True if cancelled, False if not found or not cancellable.
        """
        cancelled = await self._command_repo.cancel_command(command_id)

        if cancelled:
            logger.info(f"Cancelled command {command_id}")

        return cancelled

    async def cancel_device_commands(
        self,
        device_id: UUID,
    ) -> int:
        """
        Cancel all pending commands for a device.

        Args:
            device_id: Device UUID.

        Returns:
            Number of commands cancelled.
        """
        commands = await self._command_repo.get_device_queue(
            device_id=device_id,
            include_completed=False,
        )

        cancelled = 0
        for command in commands:
            if command.status in [CommandStatus.PENDING, CommandStatus.SENT]:
                if await self._command_repo.cancel_command(command.id):
                    cancelled += 1

        if cancelled > 0:
            logger.info(f"Cancelled {cancelled} commands for device {device_id}")

        return cancelled

    # =========================================================================
    # Retry Operations
    # =========================================================================

    async def retry_command(self, command_id: UUID) -> Optional[DeviceCommand]:
        """
        Retry a failed command.

        Args:
            command_id: Command UUID.

        Returns:
            Updated DeviceCommand if retry is possible.
        """
        return await self._command_repo.retry_command(command_id)

    async def retry_failed_commands(
        self,
        device_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> int:
        """
        Retry all retryable failed commands.

        Args:
            device_id: Optional device filter.
            limit: Maximum commands to retry.

        Returns:
            Number of commands queued for retry.
        """
        commands = await self._command_repo.get_retryable_commands(device_id, limit)

        retried = 0
        for command in commands:
            if await self._command_repo.retry_command(command.id):
                retried += 1

        if retried > 0:
            logger.info(f"Queued {retried} commands for retry")

        return retried

    # =========================================================================
    # Waiting for Completion
    # =========================================================================

    async def wait_for_completion(
        self,
        command_id: UUID,
        timeout_seconds: int = 30,
    ) -> DeviceCommand:
        """
        Wait for a command to complete.

        Args:
            command_id: Command UUID.
            timeout_seconds: Maximum time to wait.

        Returns:
            DeviceCommand with final status.

        Raises:
            asyncio.TimeoutError: If timeout is reached.
        """
        # Check if already completed
        command = await self._command_repo.get_by_id(command_id)
        if not command:
            raise ValueError(f"Command {command_id} not found")

        if command.is_completed():
            return command

        # Create future for callback
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending_callbacks[command_id] = future

        try:
            await asyncio.wait_for(future, timeout=timeout_seconds)
            # Get updated command
            return await self._command_repo.get_by_id(command_id) or command
        except asyncio.TimeoutError:
            await self._command_repo.mark_timeout(command_id)
            return await self._command_repo.get_by_id(command_id) or command
        finally:
            self._pending_callbacks.pop(command_id, None)

    async def _notify_completion(
        self,
        command_id: UUID,
        result: CommandResult,
    ) -> None:
        """
        Notify waiters that command has completed.

        Args:
            command_id: Command UUID.
            result: Command result.
        """
        future = self._pending_callbacks.get(command_id)
        if future and not future.done():
            future.set_result(result)

    # =========================================================================
    # Maintenance
    # =========================================================================

    async def expire_commands(self) -> int:
        """
        Expire old pending commands.

        Returns:
            Number of commands expired.
        """
        return await self._command_repo.expire_old_commands()

    async def cleanup_old_commands(
        self,
        days: int = 30,
    ) -> int:
        """
        Delete old completed commands.

        Args:
            days: Days of history to keep.

        Returns:
            Number of commands deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return await self._command_repo.cleanup_old_commands(cutoff)

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_command_stats(
        self,
        device_id: Optional[UUID] = None,
        site_id: Optional[UUID] = None,
        hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Get command execution statistics.

        Args:
            device_id: Optional device filter.
            site_id: Optional site filter.
            hours: Lookback period.

        Returns:
            Dict with command statistics.
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        stats = await self._command_repo.get_command_stats(device_id, site_id, since)
        pending_count = await self._command_repo.get_pending_count(device_id)

        # Calculate success rate
        total = sum(stats.values())
        completed = stats.get(CommandStatus.COMPLETED.value, 0)
        failed = stats.get(CommandStatus.FAILED.value, 0) + stats.get(CommandStatus.TIMEOUT.value, 0)

        return {
            "by_status": stats,
            "total_commands": total,
            "pending_commands": pending_count,
            "success_rate": (completed / (completed + failed) * 100) if (completed + failed) > 0 else 0,
            "active_waiters": len(self._pending_callbacks),
        }

    # =========================================================================
    # Event Logging
    # =========================================================================

    async def _log_command_event(
        self,
        command: DeviceCommand,
        result: CommandResult,
    ) -> None:
        """
        Log command execution as an event.

        Args:
            command: Executed command.
            result: Execution result.
        """
        if not self._event_repo:
            return

        event = DeviceEvent(
            time=datetime.now(timezone.utc),
            device_id=command.device_id,
            site_id=command.site_id,
            event_type=EventType.COMMAND,
            severity=EventSeverity.INFO if result.success else EventSeverity.WARNING,
            event_code=f"command_{command.command_type}",
            message=(
                f"Command {command.command_type} completed successfully"
                if result.success
                else f"Command {command.command_type} failed: {result.error_message}"
            ),
            details={
                "command_id": str(command.id),
                "command_type": command.command_type,
                "success": result.success,
                "error_code": result.error_code,
                "error_message": result.error_message,
                "result_data": result.data,
            },
        )

        await self._event_repo.create(event)
