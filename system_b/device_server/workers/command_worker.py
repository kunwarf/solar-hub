"""
Command execution worker.

Processes commands from the queue and dispatches them to devices.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Protocol
from uuid import UUID

logger = logging.getLogger(__name__)


class CommandExecutor(Protocol):
    """Protocol for command executors."""

    async def execute(
        self,
        device_id: UUID,
        command_type: str,
        command_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a command on a device."""
        ...


class CommandWorker:
    """
    Background worker for processing device commands.

    Fetches pending commands from the database and dispatches
    them to devices through registered executors.
    """

    def __init__(
        self,
        poll_interval: float = 1.0,
        batch_size: int = 10,
    ):
        """
        Initialize the command worker.

        Args:
            poll_interval: Interval between queue checks in seconds.
            batch_size: Maximum commands to process per cycle.
        """
        self.poll_interval = poll_interval
        self.batch_size = batch_size

        # Executor callback
        self._executor: Optional[CommandExecutor] = None

        # Database callbacks
        self._fetch_pending: Optional[Callable] = None
        self._mark_sent: Optional[Callable] = None
        self._mark_completed: Optional[Callable] = None
        self._mark_failed: Optional[Callable] = None
        self._expire_stale: Optional[Callable] = None

        # State
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

        # Stats
        self._commands_processed = 0
        self._commands_failed = 0
        self._last_check_time: Optional[datetime] = None

    def set_executor(self, executor: CommandExecutor) -> None:
        """Set the command executor."""
        self._executor = executor

    def set_fetch_pending(self, callback: Callable) -> None:
        """Set callback to fetch pending commands."""
        self._fetch_pending = callback

    def set_mark_sent(self, callback: Callable) -> None:
        """Set callback to mark command as sent."""
        self._mark_sent = callback

    def set_mark_completed(self, callback: Callable) -> None:
        """Set callback to mark command as completed."""
        self._mark_completed = callback

    def set_mark_failed(self, callback: Callable) -> None:
        """Set callback to mark command as failed."""
        self._mark_failed = callback

    def set_expire_stale(self, callback: Callable) -> None:
        """Set callback to expire stale commands."""
        self._expire_stale = callback

    async def start(self) -> None:
        """Start the command worker."""
        if self._running:
            logger.warning("Command worker already running")
            return

        logger.info("Starting command worker")
        self._running = True
        self._shutdown_event.clear()

        self._task = asyncio.create_task(
            self._run_loop(),
            name="command_worker",
        )

    async def stop(self) -> None:
        """Stop the command worker."""
        if not self._running:
            return

        logger.info("Stopping command worker")
        self._running = False
        self._shutdown_event.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info(
            f"Command worker stopped. "
            f"Processed: {self._commands_processed}, Failed: {self._commands_failed}"
        )

    async def _run_loop(self) -> None:
        """Main processing loop."""
        logger.debug("Command worker loop started")

        # Run expire stale on startup
        await self._run_expire_stale()

        while self._running:
            try:
                self._last_check_time = datetime.now(timezone.utc)

                # Process pending commands
                await self._process_pending_commands()

                # Periodically expire stale commands (every 60 cycles)
                if self._commands_processed % 60 == 0:
                    await self._run_expire_stale()

                # Wait for next cycle
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.poll_interval,
                    )
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    pass  # Normal timeout

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in command worker loop: {e}")
                await asyncio.sleep(5)  # Brief pause on error

        logger.debug("Command worker loop ended")

    async def _process_pending_commands(self) -> None:
        """Process batch of pending commands."""
        if not self._fetch_pending or not self._executor:
            return

        try:
            # Fetch pending commands
            commands = await self._fetch_pending(limit=self.batch_size)

            for command in commands:
                await self._execute_command(command)

        except Exception as e:
            logger.error(f"Error fetching pending commands: {e}")

    async def _execute_command(self, command: Dict[str, Any]) -> None:
        """
        Execute a single command.

        Args:
            command: Command dictionary with id, device_id, command_type, command_params.
        """
        command_id = command.get("id")
        device_id = command.get("device_id")
        command_type = command.get("command_type")
        command_params = command.get("command_params") or {}

        logger.debug(f"Executing command {command_id} for device {device_id}")

        # Mark as sent
        if self._mark_sent:
            try:
                await self._mark_sent(command_id)
            except Exception as e:
                logger.error(f"Failed to mark command {command_id} as sent: {e}")

        try:
            # Execute through device
            result = await self._executor.execute(
                device_id=device_id,
                command_type=command_type,
                command_params=command_params,
            )

            # Mark as completed
            if self._mark_completed:
                await self._mark_completed(command_id, result)

            self._commands_processed += 1
            logger.debug(f"Command {command_id} completed successfully")

        except Exception as e:
            # Mark as failed
            if self._mark_failed:
                try:
                    await self._mark_failed(command_id, str(e))
                except Exception as mark_err:
                    logger.error(f"Failed to mark command {command_id} as failed: {mark_err}")

            self._commands_failed += 1
            logger.error(f"Command {command_id} failed: {e}")

    async def _run_expire_stale(self) -> None:
        """Expire stale commands."""
        if not self._expire_stale:
            return

        try:
            count = await self._expire_stale()
            if count > 0:
                logger.info(f"Expired {count} stale commands")
        except Exception as e:
            logger.error(f"Error expiring stale commands: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            "running": self._running,
            "commands_processed": self._commands_processed,
            "commands_failed": self._commands_failed,
            "last_check_time": self._last_check_time.isoformat() if self._last_check_time else None,
            "poll_interval": self.poll_interval,
            "batch_size": self.batch_size,
        }

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
