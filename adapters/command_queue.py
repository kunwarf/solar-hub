"""
Command Queue Manager for Inverter Operations
Provides a thread-safe queue system for executing inverter commands sequentially
to avoid locking issues and ensure proper synchronization with telemetry polling.
"""
import asyncio
import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)

@dataclass
class InverterCommand:
    """Represents a command to be executed on an inverter."""
    inverter_id: str
    command: Dict[str, Any]
    callback: Optional[Callable] = None
    timestamp: datetime = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

class CommandQueueManager:
    """
    Manages a queue of inverter commands and executes them sequentially
    in a dedicated thread to avoid locking issues.
    """
    
    def __init__(self, telemetry_polling_interval: float = 10.0):
        """
        Initialize the command queue manager.
        
        Args:
            telemetry_polling_interval: Interval between telemetry polls (seconds)
        """
        self.command_queue = queue.Queue()
        self.telemetry_polling_interval = telemetry_polling_interval
        self.telemetry_lock = threading.Lock()
        self.last_telemetry_time = 0.0
        self.is_running = False
        self.worker_thread = None
        self.adapters: Dict[str, Any] = {}  # Will be populated with actual adapters
        self.command_timeout = 30.0  # 30 seconds timeout for commands
        
        # Statistics
        self.commands_processed = 0
        self.commands_failed = 0
        self.last_command_time = 0.0
        
        log.info(f"CommandQueueManager initialized with telemetry interval: {telemetry_polling_interval}s")
    
    def register_adapter(self, inverter_id: str, adapter: Any):
        """Register an inverter adapter for command execution."""
        self.adapters[inverter_id] = adapter
        log.info(f"Registered adapter for inverter: {inverter_id}")
    
    def start(self):
        """Start the command queue worker thread."""
        if self.is_running:
            log.warning("Command queue manager is already running")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        log.info("Command queue manager started")
    
    def stop(self):
        """Stop the command queue worker thread."""
        if not self.is_running:
            return
        
        self.is_running = False
        # Add a poison pill to wake up the worker thread
        self.command_queue.put(None)
        
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
        
        log.info("Command queue manager stopped")
    
    def enqueue_command(self, inverter_id: str, command: Dict[str, Any], 
                       callback: Optional[Callable] = None) -> bool:
        """
        Enqueue a command for execution.
        
        Args:
            inverter_id: ID of the inverter
            command: Command dictionary
            callback: Optional callback function to call after execution
            
        Returns:
            True if command was enqueued successfully
        """
        try:
            cmd = InverterCommand(
                inverter_id=inverter_id,
                command=command,
                callback=callback
            )
            
            self.command_queue.put(cmd, timeout=5.0)
            log.debug(f"Enqueued command for {inverter_id}: {command.get('action', 'unknown')}")
            return True
            
        except queue.Full:
            log.error(f"Command queue is full, failed to enqueue command for {inverter_id}")
            return False
        except Exception as e:
            log.error(f"Failed to enqueue command for {inverter_id}: {e}")
            return False
    
    def notify_telemetry_polling(self):
        """Notify that telemetry polling is about to start."""
        with self.telemetry_lock:
            self.last_telemetry_time = time.time()
            log.debug("Telemetry polling notification received")
    
    def _worker_loop(self):
        """Main worker loop that processes commands from the queue."""
        log.info("Command queue worker thread started")
        
        while self.is_running:
            try:
                # Get next command with timeout
                try:
                    cmd = self.command_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Check for poison pill
                if cmd is None:
                    break
                
                # Check if we should wait for telemetry polling to complete
                self._wait_for_telemetry_slot()
                
                # Execute the command
                self._execute_command(cmd)
                
                # Mark task as done
                self.command_queue.task_done()
                
            except Exception as e:
                log.error(f"Error in command queue worker loop: {e}")
                time.sleep(1.0)
        
        log.info("Command queue worker thread stopped")
    
    def _wait_for_telemetry_slot(self):
        """
        Wait for an appropriate time slot to execute commands,
        ensuring we don't interfere with telemetry polling.
        """
        with self.telemetry_lock:
            current_time = time.time()
            time_since_last_telemetry = current_time - self.last_telemetry_time
            
            # If telemetry polling is happening or just happened, wait
            if time_since_last_telemetry < self.telemetry_polling_interval * 0.8:
                wait_time = self.telemetry_polling_interval * 0.8 - time_since_last_telemetry
                if wait_time > 0:
                    log.debug(f"Waiting {wait_time:.1f}s for telemetry slot")
                    time.sleep(wait_time)
    
    def _execute_command(self, cmd: InverterCommand):
        """
        Execute a single command.
        
        Args:
            cmd: Command to execute
        """
        start_time = time.time()
        
        try:
            # Get the adapter for this inverter
            adapter = self.adapters.get(cmd.inverter_id)
            if not adapter:
                log.error(f"No adapter found for inverter: {cmd.inverter_id}")
                self.commands_failed += 1
                return
            
            # Check if adapter has the required method
            if not hasattr(adapter, 'handle_command'):
                log.error(f"Adapter for {cmd.inverter_id} does not have handle_command method")
                self.commands_failed += 1
                return
            
            # Execute the command
            action = cmd.command.get('action', 'unknown')
            log.info(f"Executing command for {cmd.inverter_id}: {action}")
            
            # Handle special inverter config commands
            if action == "inverter_config":
                result = self._execute_inverter_config_command(cmd)
            else:
                # Run async command in the client's event loop to avoid lock binding issues
                # The adapter stores a reference to the event loop where the client was created
                client_loop = getattr(adapter, '_client_loop', None)
                
                if client_loop and not client_loop.is_closed():
                    # Use the client's event loop via run_coroutine_threadsafe
                    future = asyncio.run_coroutine_threadsafe(
                        asyncio.wait_for(
                            adapter.handle_command(cmd.command),
                            timeout=self.command_timeout
                        ),
                        client_loop
                    )
                    result = future.result(timeout=self.command_timeout + 1)
                else:
                    # Fallback: create or get event loop for this thread
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    result = loop.run_until_complete(
                        asyncio.wait_for(
                            adapter.handle_command(cmd.command),
                            timeout=self.command_timeout
                        )
                    )
            
            execution_time = time.time() - start_time
            self.commands_processed += 1
            self.last_command_time = time.time()
            
            log.info(f"Command executed successfully for {cmd.inverter_id} in {execution_time:.2f}s: {result}")
            
            # Call callback if provided
            if cmd.callback:
                try:
                    cmd.callback(cmd.inverter_id, cmd.command, result, None)
                except Exception as e:
                    log.warning(f"Callback failed for {cmd.inverter_id}: {e}")
            
        except asyncio.TimeoutError:
            log.error(f"Command timeout for {cmd.inverter_id}: {cmd.command.get('action', 'unknown')}")
            self.commands_failed += 1
            
            # Retry logic
            if cmd.retry_count < cmd.max_retries:
                cmd.retry_count += 1
                log.info(f"Retrying command for {cmd.inverter_id} (attempt {cmd.retry_count}/{cmd.max_retries})")
                self.command_queue.put(cmd)
            else:
                log.error(f"Command failed after {cmd.max_retries} retries for {cmd.inverter_id}")
                if cmd.callback:
                    try:
                        cmd.callback(cmd.inverter_id, cmd.command, None, "Command timeout after retries")
                    except Exception as e:
                        log.warning(f"Error callback failed for {cmd.inverter_id}: {e}")
        
        except Exception as e:
            log.error(f"Command execution failed for {cmd.inverter_id}: {e}")
            self.commands_failed += 1
            
            if cmd.callback:
                try:
                    cmd.callback(cmd.inverter_id, cmd.command, None, str(e))
                except Exception as callback_error:
                    log.warning(f"Error callback failed for {cmd.inverter_id}: {callback_error}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get command queue statistics."""
        return {
            "queue_size": self.command_queue.qsize(),
            "commands_processed": self.commands_processed,
            "commands_failed": self.commands_failed,
            "last_command_time": self.last_command_time,
            "is_running": self.is_running,
            "telemetry_polling_interval": self.telemetry_polling_interval
        }
    
    def clear_queue(self):
        """Clear all pending commands from the queue."""
        cleared_count = 0
        try:
            while True:
                self.command_queue.get_nowait()
                cleared_count += 1
        except queue.Empty:
            pass
        
        log.info(f"Cleared {cleared_count} commands from queue")
        return cleared_count
    
    def _execute_inverter_config_command(self, cmd: InverterCommand):
        """
        Execute an inverter config command through the handler.
        
        Args:
            cmd: Command containing inverter config data
            
        Returns:
            Result of the command execution
        """
        try:
            sensor_id = cmd.command.get('sensor_id')
            data = cmd.command.get('data')
            handler = cmd.command.get('handler')
            
            if not all([sensor_id, data, handler]):
                raise ValueError("Missing required fields for inverter config command")
            
            # Create a new event loop for this thread if needed
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Execute the inverter config command
            result = loop.run_until_complete(
                asyncio.wait_for(
                    handler.handle_command(cmd.inverter_id, sensor_id, data),
                    timeout=self.command_timeout
                )
            )
            
            log.info(f"Inverter config command executed for {cmd.inverter_id}.{sensor_id}: {result}")
            return result
            
        except Exception as e:
            log.error(f"Failed to execute inverter config command for {cmd.inverter_id}: {e}")
            raise
