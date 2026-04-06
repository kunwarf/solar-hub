"""
Command executor for Modbus devices.

Executes commands by translating them to Modbus register write operations.
"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
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
    settings: Optional[Dict[str, Any]] = None
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
            "settings": self.settings,
            "error": self.error,
            "executed_at": self.executed_at.isoformat(),
        }


class ModbusCommandExecutor:
    """
    Executes commands on devices via Modbus write operations.

    Translates high-level commands (e.g., "set_power_limit") to
    Modbus register writes using command definitions.
    """

    def __init__(self, device_manager: "DeviceManager", device_registry_client=None):
        """
        Initialize the command executor.

        Args:
            device_manager: Device manager for accessing device adapters
            device_registry_client: Optional device registry client for UUID to serial mapping
        """
        self.device_manager = device_manager
        self.device_registry_client = device_registry_client

    async def _resolve_device(self, device_id: UUID):
        """
        Resolve device by UUID.

        First tries direct UUID lookup in device_manager.
        If not found, queries device registry to get serial number,
        then looks up by serial number.

        Args:
            device_id: Device UUID (could be from System A or device_server)

        Returns:
            Tuple of (device_state, error_message)
        """
        # Try direct UUID lookup first (for device_server's own UUIDs)
        device_state = self.device_manager.get_device(device_id)
        if device_state:
            logger.debug(f"[COMMAND_EXECUTOR] Device found by UUID: {device_id}")
            return device_state, None

        # Device not found by UUID - try looking up by serial from device registry
        if not self.device_registry_client:
            error_msg = f"Device {device_id} not found and no device registry available"
            logger.warning(f"[COMMAND_EXECUTOR] {error_msg}")
            return None, error_msg

        logger.info(f"[COMMAND_EXECUTOR] Device {device_id} not found by UUID, querying device registry...")

        try:
            # Query device registry to get serial number from UUID
            from sqlalchemy import text
            async with self.device_registry_client._session_factory() as session:
                result = await session.execute(
                    text("SELECT serial_number FROM device_registry WHERE device_id = :device_id"),
                    {"device_id": str(device_id)}
                )
                row = result.fetchone()

                if not row:
                    error_msg = f"Device {device_id} not found in device registry"
                    logger.warning(f"[COMMAND_EXECUTOR] {error_msg}")
                    return None, error_msg

                serial_number = row[0]
                logger.info(f"[COMMAND_EXECUTOR] Found data logger serial {serial_number} for device {device_id}")

                # Log what devices are currently in DeviceManager
                all_devices = list(self.device_manager._devices.values())
                logger.info(
                    f"[COMMAND_EXECUTOR] DeviceManager has {len(all_devices)} devices: " +
                    ", ".join([f"{d.serial_number} ({d.device_type})" for d in all_devices[:5]])
                )

                # Try lookup by data logger serial first
                device_state = self.device_manager.get_device_by_serial(serial_number)
                if device_state:
                    logger.info(
                        f"[COMMAND_EXECUTOR] Device found by data logger serial: {serial_number} "
                        f"(internal ID: {device_state.device_id})"
                    )
                    return device_state, None

                # Data logger serial didn't work, try inverter serial from metadata
                logger.info(f"[COMMAND_EXECUTOR] Device not found by data logger serial, checking inverter serial...")
                result2 = await session.execute(
                    text("SELECT metadata->>'inverter_serial' FROM device_registry WHERE device_id = :device_id"),
                    {"device_id": str(device_id)}
                )
                row2 = result2.fetchone()

                if row2:
                    inverter_serial = row2[0]
                    logger.info(f"[COMMAND_EXECUTOR] Metadata query returned: {inverter_serial}")

                    if inverter_serial:
                        logger.info(f"[COMMAND_EXECUTOR] Found inverter serial {inverter_serial} in metadata, looking up device...")

                        device_state = self.device_manager.get_device_by_serial(inverter_serial)
                        if device_state:
                            logger.info(
                                f"[COMMAND_EXECUTOR] ✓ Device found by inverter serial: {inverter_serial} "
                                f"(internal ID: {device_state.device_id})"
                            )
                            return device_state, None
                        else:
                            logger.warning(
                                f"[COMMAND_EXECUTOR] Inverter serial {inverter_serial} found in metadata "
                                f"but device not found in DeviceManager"
                            )
                    else:
                        logger.warning(f"[COMMAND_EXECUTOR] Metadata query returned None - inverter_serial not set in metadata")
                else:
                    logger.warning(f"[COMMAND_EXECUTOR] No metadata row found for device {device_id}")

                # Fallback: if we have exactly one device connected, use it
                all_devices = list(self.device_manager._devices.values())
                if len(all_devices) == 1:
                    device_state = all_devices[0]
                    logger.info(
                        f"[COMMAND_EXECUTOR] Using fallback: only one device connected "
                        f"(serial={device_state.serial_number}, internal_id={device_state.device_id})"
                    )
                    return device_state, None

                # Neither serial worked and no single-device fallback
                error_msg = (
                    f"Device with data logger serial {serial_number} is registered but not connected. "
                    f"Metadata doesn't have inverter_serial and {len(all_devices)} devices are connected. "
                    f"Ensure the device is powered on and connected to the network."
                )
                logger.warning(f"[COMMAND_EXECUTOR] {error_msg}")
                return None, error_msg

        except Exception as e:
            error_msg = f"Error resolving device {device_id}: {str(e)}"
            logger.error(f"[COMMAND_EXECUTOR] {error_msg}", exc_info=True)
            return None, error_msg

    async def _execute_on_device(
        self,
        device_state,
        command_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> CommandResult:
        """
        Execute a command on a resolved device.

        Args:
            device_state: Resolved device state from DeviceManager
            command_type: Type of command to execute
            params: Command parameters

        Returns:
            CommandResult with execution status
        """
        params = params or {}

        try:
            logger.info(
                f"[COMMAND_EXECUTOR] Executing on device: "
                f"serial={device_state.serial_number}, type={device_state.device_type}, "
                f"command={command_type}, params={params}"
            )

            # Get adapter using the device_server's internal device ID
            adapter = self.device_manager.get_adapter(device_state.device_id)
            if not adapter:
                error_msg = f"No adapter for device: {device_state.serial_number}"
                logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    device_id=device_state.device_id,
                    error=error_msg,
                )

            # ---------------------------------------------------------------
            # Voltronic serial-command path
            # ---------------------------------------------------------------
            # Voltronic inverters use ASCII serial commands (POP01, MCHGC040 …)
            # not Modbus register writes.  Detect by adapter class + protocol_id.
            from ..devices.adapter_factory import TCPCommandAdapter
            protocol_id = getattr(device_state, "protocol_id", "") or ""
            if isinstance(adapter, TCPCommandAdapter) and "voltronic" in protocol_id.lower():
                logger.info(
                    "[COMMAND_EXECUTOR] Routing to Voltronic serial command handler "
                    "(protocol=%s)", protocol_id
                )
                result = await adapter.execute_voltronic_command(command_type, params)
                if result["success"]:
                    return CommandResult(
                        success=True,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        settings={"command_sent": result.get("command"),
                                  "response": result.get("response")},
                    )
                else:
                    return CommandResult(
                        success=False,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        error=result.get("error"),
                    )

            # Get device type
            device_type = device_state.device_type
            if hasattr(device_type, 'value'):
                device_type = device_type.value

            logger.info(f"[COMMAND_EXECUTOR] Looking up command definition for device_type={device_type}")

            # Get command definition
            cmd_def = get_command_definition(device_type, command_type)
            if not cmd_def:
                available = list(DEVICE_COMMANDS.get(device_type, {}).keys())
                error_msg = f"Unknown command '{command_type}' for {device_type}. Available: {available}"
                logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    device_id=device_state.device_id,
                    error=error_msg,
                )

            logger.info(f"[COMMAND_EXECUTOR] Command definition found: register={cmd_def.get('register')}")

            # Handle read operations (query commands)
            if cmd_def.get("operation") == "read":
                logger.info(f"[COMMAND_EXECUTOR] Executing read operation for {command_type}")
                settings = {}

                for reg_def in cmd_def.get("registers", []):
                    try:
                        address = reg_def["address"]
                        name = reg_def["name"]
                        scale = reg_def.get("scale", 1)

                        # Read single register
                        values = await adapter._read_holding_regs(address, 1)
                        if values and len(values) > 0:
                            raw_value = values[0]
                            scaled_value = raw_value * scale
                            settings[name] = scaled_value
                            logger.info(
                                f"[COMMAND_EXECUTOR] Read {name} from register {address}: "
                                f"raw={raw_value}, scaled={scaled_value}"
                            )
                        else:
                            logger.warning(f"[COMMAND_EXECUTOR] Failed to read register {address}")
                            settings[name] = None
                    except Exception as e:
                        logger.error(f"[COMMAND_EXECUTOR] Error reading register {reg_def['address']}: {e}")
                        settings[reg_def["name"]] = None

                logger.info(f"[COMMAND_EXECUTOR] ✓ Successfully queried settings: {settings}")
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_state.device_id,
                    values=list(settings.values()),
                    error=None,
                )

            # Handle read_all_configurable operations (query ALL RW registers)
            if cmd_def.get("operation") == "read_all_configurable":
                logger.info(f"[COMMAND_EXECUTOR] Executing read_all_configurable operation for {command_type}")

                # Get protocol and register map
                protocol_id = device_state.protocol_id
                from ..devices.adapter_factory import AdapterFactory
                from ..config import get_device_server_settings

                settings_obj = get_device_server_settings()
                factory = AdapterFactory(settings=settings_obj)

                # Load register map
                from ..protocols.registry import get_protocol_registry
                registry = get_protocol_registry()
                protocol = registry.get(protocol_id)

                if not protocol:
                    error_msg = f"Protocol '{protocol_id}' not found"
                    logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
                    return CommandResult(
                        success=False,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        error=error_msg,
                    )

                register_map = factory.load_register_map(protocol)
                if not register_map:
                    # Fallback to legacy registers if defined
                    logger.warning(f"[COMMAND_EXECUTOR] No register map found, using legacy registers")
                    settings = {}
                    for reg_def in cmd_def.get("registers", []):
                        try:
                            address = reg_def["address"]
                            name = reg_def["name"]
                            scale = reg_def.get("scale", 1)
                            values = await adapter._read_holding_regs(address, 1)
                            if values and len(values) > 0:
                                settings[name] = values[0] * scale
                        except Exception as e:
                            logger.error(f"[COMMAND_EXECUTOR] Error reading register {address}: {e}")

                    return CommandResult(
                        success=True,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        values=list(settings.values()),
                        settings=settings,
                        error=None,
                    )

                # Filter for writable registers only
                writable_registers = [r for r in register_map if r.get("rw") in ("RW", "RW/RO")]
                logger.info(f"[COMMAND_EXECUTOR] Found {len(writable_registers)} writable registers")

                # Try to load chunk configuration for optimized reading
                chunk_config_path = Path(__file__).parent.parent / "register_chunks" / f"{protocol_id}_chunks.json"
                settings = {}

                if chunk_config_path.exists():
                    # Use optimized chunk reading
                    logger.info(f"[COMMAND_EXECUTOR] Using chunk configuration: {chunk_config_path.name}")

                    try:
                        with open(chunk_config_path, "r") as f:
                            chunk_config = json.load(f)

                        # Build register lookup for fast access
                        register_lookup = {r["id"]: r for r in register_map if r.get("id")}

                        # Read each chunk
                        for chunk_idx, chunk in enumerate(chunk_config.get("chunks", []), 1):
                            start_addr = chunk["start_address"]
                            count = chunk["count"]
                            expected_ids = set(chunk.get("register_ids", []))

                            try:
                                logger.debug(f"[COMMAND_EXECUTOR] Reading chunk {chunk_idx}: {count} registers from {start_addr}")
                                chunk_values = await adapter._read_holding_regs(start_addr, count)

                                if not chunk_values:
                                    logger.warning(f"[COMMAND_EXECUTOR] Chunk {chunk_idx} read failed")
                                    continue

                                # Extract values for registers in this chunk
                                for reg_id in expected_ids:
                                    if reg_id not in register_lookup:
                                        continue

                                    reg = register_lookup[reg_id]
                                    reg_addr = reg["addr"]
                                    offset = reg_addr - start_addr

                                    if offset < 0 or offset >= len(chunk_values):
                                        logger.debug(f"[COMMAND_EXECUTOR] Register {reg_id} offset {offset} out of bounds")
                                        continue

                                    size = max(1, reg.get("size", 1))
                                    scale = reg.get("scale", 1.0)

                                    if size == 1:
                                        raw_value = chunk_values[offset]
                                    else:
                                        # Multi-register value
                                        raw_value = chunk_values[offset:offset+size]

                                    scaled_value = raw_value * scale
                                    settings[reg_id] = scaled_value
                                    logger.debug(f"[COMMAND_EXECUTOR] Read {reg_id} from chunk offset {offset}: {scaled_value}")

                            except Exception as e:
                                logger.warning(f"[COMMAND_EXECUTOR] Error reading chunk {chunk_idx}: {e}")
                                # Continue with next chunk

                        logger.info(
                            f"[COMMAND_EXECUTOR] ✓ Chunk reading completed: "
                            f"{len(settings)}/{len(writable_registers)} registers read "
                            f"using {len(chunk_config.get('chunks', []))} chunks"
                        )

                    except Exception as e:
                        logger.error(f"[COMMAND_EXECUTOR] Error loading chunk config: {e}")
                        logger.info(f"[COMMAND_EXECUTOR] Falling back to individual register reads")
                        settings = {}

                # Fall back to individual register reads if no chunks or chunk reading failed
                if not settings:
                    logger.info(f"[COMMAND_EXECUTOR] Reading registers individually")
                    for reg in writable_registers:
                        reg_id = reg.get("id")
                        if not reg_id:
                            continue

                        try:
                            address = reg["addr"]
                            size = max(1, reg.get("size", 1))
                            scale = reg.get("scale", 1.0)

                            # Read register
                            values = await adapter._read_holding_regs(address, size)
                            if values and len(values) > 0:
                                # Decode value
                                raw_value = values[0] if size == 1 else values
                                scaled_value = raw_value * scale
                                settings[reg_id] = scaled_value
                                logger.debug(f"[COMMAND_EXECUTOR] Read {reg_id} from register {address}: {scaled_value}")
                        except Exception as e:
                            logger.debug(f"[COMMAND_EXECUTOR] Could not read register {reg_id} (addr {address}): {e}")
                            # Continue reading other registers

                logger.info(f"[COMMAND_EXECUTOR] ✓ Successfully queried {len(settings)} settings")
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_state.device_id,
                    values=list(settings.values()),
                    settings=settings,
                    error=None,
                )

            # Handle read_modify_write operations (update_settings)
            if cmd_def.get("operation") == "read_modify_write":
                logger.info(f"[COMMAND_EXECUTOR] Executing read_modify_write operation for {command_type}")

                # Get settings to update
                settings_to_update = params.get("settings", {})
                if not settings_to_update:
                    return CommandResult(
                        success=True,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        error=None,
                        values=[],
                    )

                logger.info(f"[COMMAND_EXECUTOR] Updating {len(settings_to_update)} settings: {list(settings_to_update.keys())}")

                # Get protocol and register map
                protocol_id = device_state.protocol_id
                from ..devices.adapter_factory import AdapterFactory
                from ..config import get_device_server_settings
                from ..protocols.registry import get_protocol_registry

                settings_obj = get_device_server_settings()
                factory = AdapterFactory(settings=settings_obj)
                registry = get_protocol_registry()
                protocol = registry.get(protocol_id)

                if not protocol:
                    error_msg = f"Protocol '{protocol_id}' not found"
                    logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
                    return CommandResult(
                        success=False,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        error=error_msg,
                    )

                register_map = factory.load_register_map(protocol)
                if not register_map:
                    error_msg = "No register map available for this device"
                    logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
                    return CommandResult(
                        success=False,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        error=error_msg,
                    )

                # Build register lookup
                register_lookup = {r["id"]: r for r in register_map if r.get("id")}

                # Step 1: Read current values for registers being updated
                logger.info(f"[COMMAND_EXECUTOR] Step 1: Reading current values")
                current_values = {}
                for reg_id in settings_to_update.keys():
                    reg_def = register_lookup.get(reg_id)
                    if not reg_def:
                        error_msg = f"Register '{reg_id}' not found in register map"
                        logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
                        return CommandResult(
                            success=False,
                            command_type=command_type,
                            device_id=device_state.device_id,
                            error=error_msg,
                        )

                    # Check if writable
                    if reg_def.get("rw") not in ("RW", "WO"):
                        error_msg = f"Register '{reg_id}' is read-only"
                        logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
                        return CommandResult(
                            success=False,
                            command_type=command_type,
                            device_id=device_state.device_id,
                            error=error_msg,
                        )

                    try:
                        address = reg_def["addr"]
                        size = max(1, reg_def.get("size", 1))
                        scale = reg_def.get("scale", 1.0)

                        values = await adapter._read_holding_regs(address, size)
                        if values and len(values) > 0:
                            raw_value = values[0] if size == 1 else values
                            current_values[reg_id] = raw_value * scale
                            logger.debug(f"[COMMAND_EXECUTOR] Current value for {reg_id}: {current_values[reg_id]}")
                    except Exception as e:
                        logger.warning(f"[COMMAND_EXECUTOR] Could not read current value for {reg_id}: {e}")
                        current_values[reg_id] = None

                # Step 2: Identify changed registers
                logger.info(f"[COMMAND_EXECUTOR] Step 2: Identifying changes")
                changed_registers = {}
                for reg_id, new_value in settings_to_update.items():
                    current = current_values.get(reg_id)
                    if current != new_value:
                        changed_registers[reg_id] = new_value
                        logger.info(f"[COMMAND_EXECUTOR] Register {reg_id} changed: {current} → {new_value}")

                if not changed_registers:
                    logger.info(f"[COMMAND_EXECUTOR] No changes detected")
                    return CommandResult(
                        success=True,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        error=None,
                        values=list(current_values.values()),
                    )

                # Step 3: Validate new values
                logger.info(f"[COMMAND_EXECUTOR] Step 3: Validating new values")
                from ..registers import get_register_metadata_registry
                metadata_registry = get_register_metadata_registry()

                # Load metadata if not already loaded
                if protocol_id not in metadata_registry._metadata:
                    register_map_path = settings_obj.register_maps_dir / protocol.register_map_file
                    metadata_registry.load_from_register_map(protocol_id, register_map_path)

                validation_errors = []
                for reg_id, new_value in changed_registers.items():
                    is_valid, error_msg = metadata_registry.validate_register_write(
                        protocol_id, reg_id, new_value
                    )
                    if not is_valid:
                        validation_errors.append(f"{reg_id}: {error_msg}")

                if validation_errors:
                    error_msg = f"Validation errors: {'; '.join(validation_errors)}"
                    logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
                    return CommandResult(
                        success=False,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        error=error_msg,
                    )

                # Step 4: Write changed registers (with rollback on failure)
                logger.info(f"[COMMAND_EXECUTOR] Step 4: Writing {len(changed_registers)} changed registers")
                written_registers = []
                try:
                    for reg_id, new_value in changed_registers.items():
                        reg_def = register_lookup[reg_id]
                        address = reg_def["addr"]
                        scale = reg_def.get("scale", 1.0)
                        encoder = (reg_def.get("encoder") or "").lower()

                        # Encode value for HHMM time registers.
                        # Both formats expect the user to supply decimal HHMM (e.g. 630 = 06:30).
                        if encoder == "hhmm_decimal":
                            # Powdrive: decimal HHMM stored directly (630 → register 630).
                            raw_value = int(new_value)
                        elif encoder == "hhmm_binary":
                            # Senergy: binary-packed byte — High byte=hour, Low byte=minute.
                            # e.g. 630 → hour=6, minute=30 → 6*256+30 = 1566 (0x061E).
                            decimal_hhmm = int(new_value)
                            hour = decimal_hhmm // 100
                            minute = decimal_hhmm % 100
                            raw_value = (hour << 8) | minute
                        else:
                            # Unscale value before writing (round to avoid float precision errors,
                            # e.g. int(56.0 / 0.01) = int(5599.999...) = 5599 instead of 5600)
                            raw_value = round(new_value / scale)

                        logger.info(f"[COMMAND_EXECUTOR] Writing {reg_id} to register {address}: {new_value} (raw={raw_value}, encoder={encoder or 'none'})")
                        await adapter.write_register(address, raw_value)
                        written_registers.append(reg_id)
                        logger.debug(f"[COMMAND_EXECUTOR] Successfully wrote {reg_id}")

                except Exception as e:
                    # Rollback: restore previous values
                    logger.error(
                        f"[COMMAND_EXECUTOR] Write failed at {reg_id}: "
                        f"{type(e).__name__}: {e}"
                    )
                    logger.warning(f"[COMMAND_EXECUTOR] Attempting rollback of {len(written_registers)} registers")

                    for rolled_back_reg_id in written_registers:
                        try:
                            reg_def = register_lookup[rolled_back_reg_id]
                            address = reg_def["addr"]
                            scale = reg_def.get("scale", 1.0)
                            encoder = (reg_def.get("encoder") or "").lower()
                            original_value = current_values[rolled_back_reg_id]

                            if encoder == "hhmm_decimal":
                                raw_value = int(original_value)
                            elif encoder == "hhmm_binary":
                                decimal_hhmm = int(original_value)
                                hour = decimal_hhmm // 100
                                minute = decimal_hhmm % 100
                                raw_value = (hour << 8) | minute
                            else:
                                raw_value = round(original_value / scale)

                            await adapter.write_register(address, raw_value)
                            logger.info(f"[COMMAND_EXECUTOR] Rolled back {rolled_back_reg_id} to {original_value}")
                        except Exception as rollback_error:
                            logger.error(f"[COMMAND_EXECUTOR] Rollback failed for {rolled_back_reg_id}: {rollback_error}")

                    error_msg = f"Write failed ({type(e).__name__}), rollback attempted: {str(e)}"
                    return CommandResult(
                        success=False,
                        command_type=command_type,
                        device_id=device_state.device_id,
                        error=error_msg,
                    )

                # Step 5: Verify writes succeeded
                logger.info(f"[COMMAND_EXECUTOR] Step 5: Verifying writes")
                verified_settings = {}
                for reg_id in written_registers:
                    reg_def = register_lookup[reg_id]
                    address = reg_def["addr"]
                    size = max(1, reg_def.get("size", 1))
                    scale = reg_def.get("scale", 1.0)

                    try:
                        values = await adapter._read_holding_regs(address, size)
                        if values and len(values) > 0:
                            raw_value = values[0] if size == 1 else values
                            verified_settings[reg_id] = raw_value * scale
                    except Exception as e:
                        logger.warning(f"[COMMAND_EXECUTOR] Could not verify {reg_id}: {e}")
                        verified_settings[reg_id] = changed_registers[reg_id]  # Assume success

                logger.info(f"[COMMAND_EXECUTOR] ✓ Successfully updated {len(changed_registers)} settings")
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_state.device_id,
                    register=None,
                    value=None,
                    values=list(verified_settings.values()),
                    settings=verified_settings,
                    error=None,
                )

            # Validate parameters
            is_valid, error_msg = validate_command_params(cmd_def, params)
            if not is_valid:
                logger.error(f"[COMMAND_EXECUTOR] Parameter validation failed: {error_msg}")
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    device_id=device_state.device_id,
                    error=error_msg,
                )

            logger.info(f"[COMMAND_EXECUTOR] Parameters validated successfully")

            # Encode value(s)
            register = cmd_def["register"]

            if "fixed_value" in cmd_def:
                # Fixed value command (e.g., restart)
                value = cmd_def["fixed_value"]
                logger.info(
                    f"[COMMAND_EXECUTOR] Writing fixed value to Modbus: "
                    f"device={device_state.device_id}, register={register}, value={value}"
                )
                await adapter.write_register(register, value)
                logger.info(
                    f"[COMMAND_EXECUTOR] ✓ Successfully executed {command_type} on device {device_state.device_id}: "
                    f"wrote value={value} to register={register}"
                )
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_state.device_id,
                    register=register,
                    value=value,
                )

            elif "values" in cmd_def:
                # Enum value command (e.g., set_mode)
                param_name = cmd_def["param"]
                param_value = params[param_name]
                value = cmd_def["values"][param_value]
                logger.info(
                    f"[COMMAND_EXECUTOR] Writing enum value to Modbus: "
                    f"device={device_state.device_id}, register={register}, {param_name}={param_value} (raw={value})"
                )
                await adapter.write_register(register, value)
                logger.info(
                    f"[COMMAND_EXECUTOR] ✓ Successfully executed {command_type} on device {device_state.device_id}: "
                    f"set {param_name}={param_value} (register {register}={value})"
                )
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_state.device_id,
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

                logger.info(
                    f"[COMMAND_EXECUTOR] Writing multiple values to Modbus: "
                    f"device={device_state.device_id}, register={register}, values={values}, params={params}"
                )
                await adapter.write_registers(register, values)
                logger.info(
                    f"[COMMAND_EXECUTOR] ✓ Successfully executed {command_type} on device {device_state.device_id}: "
                    f"wrote {values} to registers starting at {register}"
                )
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_state.device_id,
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

                logger.info(
                    f"[COMMAND_EXECUTOR] Writing scaled value to Modbus: "
                    f"device={device_state.device_id}, register={register}, "
                    f"{param_name}={raw_value} (scaled={value})"
                )
                await adapter.write_register(register, value)
                logger.info(
                    f"[COMMAND_EXECUTOR] ✓ Successfully executed {command_type} on device {device_state.device_id}: "
                    f"set {param_name}={raw_value} (register {register}={value})"
                )
                return CommandResult(
                    success=True,
                    command_type=command_type,
                    device_id=device_state.device_id,
                    register=register,
                    value=value,
                )

        except Exception as e:
            logger.error(
                f"[COMMAND_EXECUTOR] ✗ Command execution failed: {e}",
                exc_info=True
            )
            return CommandResult(
                success=False,
                command_type=command_type,
                device_id=device_state.device_id,
                error=str(e),
            )

    async def execute_command(
        self,
        device_id: UUID,
        command_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> CommandResult:
        """
        Execute a command on a device (with UUID resolution for backwards compatibility).

        Args:
            device_id: Target device ID (System A's UUID)
            command_type: Type of command to execute
            params: Command parameters

        Returns:
            CommandResult with execution status
        """
        logger.info(
            f"[COMMAND_EXECUTOR] Starting execution with UUID: device={device_id}, "
            f"type={command_type}"
        )

        # Resolve device (handles both device_server UUIDs and System A UUIDs)
        device_state, error_msg = await self._resolve_device(device_id)
        if not device_state:
            logger.error(f"[COMMAND_EXECUTOR] {error_msg}")
            return CommandResult(
                success=False,
                command_type=command_type,
                device_id=device_id,
                error=error_msg,
            )

        # Execute on resolved device
        return await self._execute_on_device(device_state, command_type, params)

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
        device_serial: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a command on a device (CommandExecutor protocol).

        This method matches the CommandExecutor protocol expected by
        CommandWorker for queue-based command processing.

        Args:
            device_id: Target device ID (System A's UUID)
            command_type: Type of command to execute
            command_params: Command parameters
            device_serial: Optional device serial for direct lookup (preferred)

        Returns:
            Dictionary with execution result
        """
        # If serial is provided, use it directly (no fallbacks needed!)
        if device_serial:
            logger.info(f"[COMMAND_EXECUTOR] Using device_serial from command: {device_serial}")
            device_state = self.device_manager.get_device_by_serial(device_serial)

            if device_state:
                logger.info(
                    f"[COMMAND_EXECUTOR] ✓ Device found by serial: {device_serial} "
                    f"(type={device_state.device_type}, internal_id={device_state.device_id})"
                )
                result = await self._execute_on_device(device_state, command_type, command_params)
                return result.to_dict()
            else:
                logger.warning(f"[COMMAND_EXECUTOR] Device with serial {device_serial} not found in DeviceManager")
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    device_id=device_id,
                    error=f"Device with serial {device_serial} not connected",
                ).to_dict()

        # Fallback to old UUID resolution (will be removed once System A sends serial)
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
