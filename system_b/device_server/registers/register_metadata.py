"""
Register metadata system for device settings management.

Provides categorization, validation, and UI metadata for device registers.
Enables safe and user-friendly settings management across different device types.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RegisterGroup(str, Enum):
    """UI grouping categories for device registers."""
    SPECIFICATION = "specification"
    BATTERY = "battery"
    GRID = "grid"
    WORK_MODE = "work_mode"
    TOU_SCHEDULING = "tou_scheduling"
    PROTECTION = "protection"
    GENERATOR = "generator"
    AUXILIARY = "auxiliary"
    ADVANCED = "advanced"
    UNKNOWN = "unknown"


class RegisterCriticality(str, Enum):
    """Safety/criticality level for register writes."""
    SAFE = "safe"  # Can be changed freely
    WARNING = "warning"  # Requires caution
    CRITICAL = "critical"  # Could damage equipment or violate safety standards
    READ_ONLY = "read_only"  # Cannot be written


@dataclass
class RegisterValidation:
    """Validation constraints for a register value."""
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    enum_values: Optional[Dict[int, str]] = None  # {value: label}
    data_type: Optional[str] = None  # U16, S16, U32, S32, F32
    scale: float = 1.0
    regex_pattern: Optional[str] = None  # For string values


@dataclass
class RegisterMetadata:
    """
    Complete metadata for a device register.

    Combines register definition from JSON with additional metadata
    for UI display, validation, and safety checks.
    """
    # Core identification
    register_id: str
    name: str
    address: int
    size: int = 1

    # Access control
    read_write: str = "RO"  # RO, WO, RW
    criticality: RegisterCriticality = RegisterCriticality.SAFE
    requires_confirmation: bool = False

    # UI metadata
    group: RegisterGroup = RegisterGroup.UNKNOWN
    ui_label: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None

    # Validation
    validation: RegisterValidation = field(default_factory=RegisterValidation)

    # Additional info
    comment: Optional[str] = None
    firmware_version: Optional[str] = None  # Minimum firmware version required

    @property
    def is_writable(self) -> bool:
        """Check if register can be written."""
        return self.read_write in ("WO", "RW")

    @property
    def is_readable(self) -> bool:
        """Check if register can be read."""
        return self.read_write in ("RO", "RW")

    @property
    def display_label(self) -> str:
        """Get display label for UI."""
        return self.ui_label or self.name

    def validate_value(self, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate a value against register constraints.

        Args:
            value: The value to validate.

        Returns:
            Tuple of (is_valid, error_message)
        """
        validation = self.validation

        # Check data type
        if validation.data_type:
            if "16" in validation.data_type or "32" in validation.data_type:
                if not isinstance(value, (int, float)):
                    return False, f"Value must be numeric for {validation.data_type}"

        # Check enum
        if validation.enum_values:
            if value not in validation.enum_values.keys():
                valid_options = list(validation.enum_values.values())
                return False, f"Invalid value. Must be one of: {', '.join(valid_options)}"

        # Check range
        if isinstance(value, (int, float)):
            if validation.min_value is not None and value < validation.min_value:
                return False, f"Value {value} below minimum {validation.min_value}"
            if validation.max_value is not None and value > validation.max_value:
                return False, f"Value {value} exceeds maximum {validation.max_value}"

        # Check regex pattern (for strings)
        if validation.regex_pattern and isinstance(value, str):
            import re
            if not re.match(validation.regex_pattern, value):
                return False, f"Value does not match required pattern"

        return True, None

    def scale_value(self, raw_value: Union[int, float]) -> Union[int, float]:
        """Apply scaling to raw register value."""
        return raw_value * self.validation.scale

    def unscale_value(self, scaled_value: Union[int, float]) -> int:
        """Remove scaling from value before writing to register."""
        return int(scaled_value / self.validation.scale)


class RegisterMetadataRegistry:
    """
    Registry for managing register metadata across different device types.

    Loads register definitions from JSON files and enriches them with
    metadata for validation, grouping, and UI display.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._metadata: Dict[str, Dict[str, RegisterMetadata]] = {}
        # Structure: {protocol_id: {register_id: RegisterMetadata}}

    def load_from_register_map(
        self,
        protocol_id: str,
        register_map_path: Path,
        metadata_overrides: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """
        Load register metadata from a register map JSON file.

        Args:
            protocol_id: Protocol identifier (e.g., "powdrive", "senergy").
            register_map_path: Path to register map JSON file.
            metadata_overrides: Optional dict of {register_id: {field: value}}
                              to override default metadata.
        """
        if not register_map_path.exists():
            logger.error(f"Register map not found: {register_map_path}")
            return

        logger.info(f"Loading register metadata for protocol '{protocol_id}' from {register_map_path}")

        try:
            with open(register_map_path, "r", encoding="utf-8") as f:
                register_map = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load register map {register_map_path}: {e}")
            return

        protocol_metadata = {}
        overrides = metadata_overrides or {}

        for reg_def in register_map:
            register_id = reg_def.get("id")
            if not register_id:
                continue

            # Parse base register definition
            metadata = self._parse_register_definition(reg_def)

            # Apply metadata overrides if provided
            if register_id in overrides:
                for key, value in overrides[register_id].items():
                    if hasattr(metadata, key):
                        setattr(metadata, key, value)

            protocol_metadata[register_id] = metadata

        self._metadata[protocol_id] = protocol_metadata
        logger.info(f"Loaded {len(protocol_metadata)} register metadata entries for '{protocol_id}'")

    def _parse_register_definition(self, reg_def: Dict[str, Any]) -> RegisterMetadata:
        """Parse register definition from JSON to RegisterMetadata."""
        register_id = reg_def["id"]
        name = reg_def.get("name", register_id)
        address = reg_def["addr"]
        size = reg_def.get("size", 1)
        rw = reg_def.get("rw", "RO")

        # Determine group from register ID patterns
        group = self._infer_group(register_id)

        # Determine criticality
        criticality = self._infer_criticality(register_id, rw, group)

        # Build validation
        validation = RegisterValidation(
            min_value=reg_def.get("min"),
            max_value=reg_def.get("max"),
            enum_values=reg_def.get("enum"),
            data_type=reg_def.get("type", "U16"),
            scale=reg_def.get("scale", 1.0)
        )

        # Requires confirmation for critical registers
        requires_confirmation = (criticality == RegisterCriticality.CRITICAL)

        return RegisterMetadata(
            register_id=register_id,
            name=name,
            address=address,
            size=size,
            read_write=rw,
            criticality=criticality,
            requires_confirmation=requires_confirmation,
            group=group,
            ui_label=name,
            description=reg_def.get("comment"),
            unit=reg_def.get("unit"),
            validation=validation,
            comment=reg_def.get("comment")
        )

    def _infer_group(self, register_id: str) -> RegisterGroup:
        """Infer register group from ID patterns."""
        reg_id_lower = register_id.lower()

        if any(keyword in reg_id_lower for keyword in ["battery", "bat_", "soc", "bms"]):
            return RegisterGroup.BATTERY
        elif any(keyword in reg_id_lower for keyword in ["grid", "utility", "ac_"]):
            return RegisterGroup.GRID
        elif any(keyword in reg_id_lower for keyword in ["prog", "tou", "window", "schedule"]):
            return RegisterGroup.TOU_SCHEDULING
        elif any(keyword in reg_id_lower for keyword in ["mode", "priority", "work_", "operation"]):
            return RegisterGroup.WORK_MODE
        elif any(keyword in reg_id_lower for keyword in ["protection", "threshold", "limit", "safety"]):
            return RegisterGroup.PROTECTION
        elif any(keyword in reg_id_lower for keyword in ["generator", "gen_"]):
            return RegisterGroup.GENERATOR
        elif any(keyword in reg_id_lower for keyword in ["inverter_type", "serial", "protocol", "modbus", "rated"]):
            return RegisterGroup.SPECIFICATION
        elif any(keyword in reg_id_lower for keyword in ["smartload", "auxiliary", "aux_"]):
            return RegisterGroup.AUXILIARY
        else:
            return RegisterGroup.UNKNOWN

    def _infer_criticality(
        self,
        register_id: str,
        rw: str,
        group: RegisterGroup
    ) -> RegisterCriticality:
        """Infer criticality level from register characteristics."""
        if rw == "RO":
            return RegisterCriticality.READ_ONLY

        reg_id_lower = register_id.lower()

        # Critical: voltage/frequency/protection thresholds
        if any(keyword in reg_id_lower for keyword in [
            "voltage", "frequency", "equalization", "floating",
            "shutdown", "restart", "cutoff", "protection"
        ]):
            return RegisterCriticality.CRITICAL

        # Warning: battery/grid configuration
        if group in (RegisterGroup.BATTERY, RegisterGroup.GRID, RegisterGroup.PROTECTION):
            return RegisterCriticality.WARNING

        # Safe: TOU schedules, work modes, non-critical settings
        return RegisterCriticality.SAFE

    def get(self, protocol_id: str, register_id: str) -> Optional[RegisterMetadata]:
        """
        Get metadata for a specific register.

        Args:
            protocol_id: Protocol identifier.
            register_id: Register identifier.

        Returns:
            RegisterMetadata or None if not found.
        """
        protocol_meta = self._metadata.get(protocol_id, {})
        return protocol_meta.get(register_id)

    def get_all(self, protocol_id: str) -> Dict[str, RegisterMetadata]:
        """
        Get all register metadata for a protocol.

        Args:
            protocol_id: Protocol identifier.

        Returns:
            Dictionary of {register_id: RegisterMetadata}
        """
        return self._metadata.get(protocol_id, {})

    def get_writable_registers(self, protocol_id: str) -> List[RegisterMetadata]:
        """
        Get all writable registers for a protocol.

        Args:
            protocol_id: Protocol identifier.

        Returns:
            List of writable RegisterMetadata objects.
        """
        all_metadata = self.get_all(protocol_id)
        return [meta for meta in all_metadata.values() if meta.is_writable]

    def get_by_group(
        self,
        protocol_id: str,
        group: RegisterGroup
    ) -> List[RegisterMetadata]:
        """
        Get all registers in a specific group.

        Args:
            protocol_id: Protocol identifier.
            group: RegisterGroup to filter by.

        Returns:
            List of RegisterMetadata in the group.
        """
        all_metadata = self.get_all(protocol_id)
        return [meta for meta in all_metadata.values() if meta.group == group]

    def get_critical_registers(self, protocol_id: str) -> List[RegisterMetadata]:
        """
        Get all critical registers that require confirmation.

        Args:
            protocol_id: Protocol identifier.

        Returns:
            List of critical RegisterMetadata objects.
        """
        all_metadata = self.get_all(protocol_id)
        return [
            meta for meta in all_metadata.values()
            if meta.criticality == RegisterCriticality.CRITICAL
        ]

    def validate_register_write(
        self,
        protocol_id: str,
        register_id: str,
        value: Any
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a value before writing to a register.

        Args:
            protocol_id: Protocol identifier.
            register_id: Register identifier.
            value: Value to validate.

        Returns:
            Tuple of (is_valid, error_message)
        """
        metadata = self.get(protocol_id, register_id)
        if not metadata:
            return False, f"Register '{register_id}' not found for protocol '{protocol_id}'"

        if not metadata.is_writable:
            return False, f"Register '{register_id}' is read-only"

        return metadata.validate_value(value)


# Global registry instance
_global_registry: Optional[RegisterMetadataRegistry] = None


def get_register_metadata_registry() -> RegisterMetadataRegistry:
    """Get global register metadata registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = RegisterMetadataRegistry()
    return _global_registry
