"""
Command executor for Modbus devices.

Executes commands by translating them to Modbus register write operations.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from .command_definitions import (
    DEVICE_COMMANDS,
    get_command_definition,
    validate_command_params,
)

if TYPE_CHECKING:
    from ..devices.device_manager import DeviceManager
    from ..devices.adapter_factory import TCPModbusAdapter

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of command execution."""
    success: bool
    command_type: str
    device_id: UUID
    register: Optional[int] = None
    value: Optional[int] = None
    values: Optional[List[int]] = None
    error: Optional[str] = None
    executed_at: datetime = None

    def __post_init__(self):
        if self.executed_at is None:
            self.executed_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "command_type": self.command_type,
            "device_id": str(self.device_id),
            "register": self.register,
            "value": self.value,
            "values": self.values,
            "error": self.error,
            "executed_at": self.executed_at.isoformat(),
        }


class ModbusCommandExecutor:
    """
    Executes commands on devices via Modbus write operations.

    Translates high-level commands (e.g., "set_power_limit") to
    Modbus register writes using command definitions.
    """

    def __init__(self, device_manager: "DeviceManager"):
        """
        Initialize the command executor.

        Args:
            device_manager: Device manager for accessing device adapters
        """
        self.device_manager = device_manager

    async def execute_command(
        self,
        device_id: UUID,
        command_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> CommandResult:
        """
        Execute a command on a device.

        Args:
            device_id: Target device ID
            command_type: Type of command to execute
            params: Command parameters

        Returns:
            CommandResult with execution status
        """
        params = params or {}

        try:
            # Get device state and adapter
            device_state = self.device_manager.get_device(device_id)
            if not device_state:
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    device_id=device_id,
                    error=f"Device not found: {device_id}",
                )

            adapter = self.device_manager.get_adapter(device_id)
            if not adapter:
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    device_id=device_id,
                    error=f"No adapter for device: {device_id}",
                )

            # Get device type
            device_type = device_state.device_type
            if hasattr(device_type, 'value'):
                device_type = device_type.value

            # Get command definition
            cmd_def = get_command_definition(device_type, command_type)
            if not cmd_def:
                available = list(DEVICE_COMMANDS.get(device_type, {}).keys())
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    device_id=device_id,
                    error=f"Unknown command '{command_type}' for {device_type}. "
                          f"Available: {available}",
                )

            # Validate parameters
            is_valid, error_msg = validate_command_params(cmd_def, params)
            if not is_valid:
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    device_id=device_id,
                    error=error_msg,
                )

            # Encode value(s)
            register = cmd_def["register"]

            if "fixed_value" in cmd_def:
                # Fixed value command (e.g., restart)
                value = cmd_def["fixed_value"]
                await adapter.write_register(register, value)
                logger.info(
                    f"Executed {command_type} on device {device_id}: "
                    f"wrote {value} to register {register}"
                )
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_id,
                    register=register,
                    value=value,
                )

            elif "values" in cmd_def:
                # Enum value command (e.g., set_mode)
                param_name = cmd_def["param"]
                param_value = params[param_name]
                value = cmd_def["values"][param_value]
                await adapter.write_register(register, value)
                logger.info(
                    f"Executed {command_type} on device {device_id}: "
                    f"set {param_name}={param_value} (register {register}={value})"
                )
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_id,
                    register=register,
                    value=value,
                )

            elif "params" in cmd_def:
                # Multi-value command (e.g., set_soc_limits)
                values = []
                for param_name in cmd_def["params"]:
                    val = params[param_name]
                    if "scale" in cmd_def:
                        val = int(val * cmd_def["scale"])
                    else:
                        val = int(val)
                    values.append(val)

                await adapter.write_registers(register, values)
                logger.info(
                    f"Executed {command_type} on device {device_id}: "
                    f"wrote {values} to registers starting at {register}"
                )
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_id,
                    register=register,
                    values=values,
                )

            else:
                # Single scaled value command (e.g., set_power_limit)
                param_name = cmd_def["param"]
                raw_value = params[param_name]

                if "scale" in cmd_def:
                    value = int(float(raw_value) * cmd_def["scale"])
                else:
                    value = int(raw_value)

                await adapter.write_register(register, value)
                logger.info(
                    f"Executed {command_type} on device {device_id}: "
                    f"set {param_name}={raw_value} (register {register}={value})"
                )
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_id,
                    register=register,
                    value=value,
                )

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return CommandResult(
                success=False,
                command_type=command_type,
                device_id=device_id,
                error=str(e),
            )

    async def read_register(
        self,
        device_id: UUID,
        register: int,
        count: int = 1,
    ) -> Optional[List[int]]:
        """
        Read register value(s) from device.

        Useful for verifying command execution.

        Args:
            device_id: Target device ID
            register: Starting register address
            count: Number of registers to read

        Returns:
            List of register values or None on error
        """
        try:
            adapter = self.device_manager.get_adapter(device_id)
            if not adapter:
                return None

            # Use the adapter's internal read method
            values = await adapter._read_holding_regs(register, count)
            return values

        except Exception as e:
            logger.error(f"Failed to read register {register}: {e}")
            return None

    async def execute(
        self,
        device_id: UUID,
        command_type: str,
        command_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a command on a device (CommandExecutor protocol).

        This method matches the CommandExecutor protocol expected by
        CommandWorker for queue-based command processing.

        Args:
            device_id: Target device ID
            command_type: Type of command to execute
            command_params: Command parameters

        Returns:
            Dictionary with execution result
        """
        result = await self.execute_command(device_id, command_type, command_params)
        return result.to_dict()

    async def execute_and_verify(
        self,
        device_id: UUID,
        command_type: str,
        params: Optional[Dict[str, Any]] = None,
        verify_delay: float = 0.5,
    ) -> CommandResult:
        """
        Execute command and verify by reading back the register.

        Args:
            device_id: Target device ID
            command_type: Type of command
            params: Command parameters
            verify_delay: Delay before verification read (seconds)

        Returns:
            CommandResult with verification status
        """
        import asyncio

        # Execute command
        result = await self.execute_command(device_id, command_type, params)

        if not result.success:
            return result

        # Wait for device to process
        await asyncio.sleep(verify_delay)

        # Read back register
        read_values = await self.read_register(
            device_id,
            result.register,
            count=len(result.values) if result.values else 1,
        )

        if read_values is None:
            result.error = "Verification read failed"
            return result

        # Verify value(s)
        if result.values:
            if read_values != result.values:
                result.error = (
                    f"Verification failed: expected {result.values}, "
                    f"got {read_values}"
                )
                result.success = False
        else:
            if read_values[0] != result.value:
                result.error = (
                    f"Verification failed: expected {result.value}, "
                    f"got {read_values[0]}"
                )
                result.success = False

        return result
