"""
Protocol registry for managing device protocol definitions.

Central registry for all supported device protocols, providing
lookup by ID, device type, and priority-ordered iteration.
"""
import logging
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .definitions import DeviceType, ProtocolDefinition, ProtocolType
from .loader import ProtocolLoader

logger = logging.getLogger(__name__)


class ProtocolRegistry:
    """
    Central registry for device protocol definitions.

    Provides methods for:
    - Registering and retrieving protocols
    - Lookup by protocol ID, device type, or protocol type
    - Priority-ordered iteration for device identification
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._protocols: Dict[str, ProtocolDefinition] = {}
        self._by_device_type: Dict[DeviceType, List[str]] = {
            device_type: [] for device_type in DeviceType
        }
        self._by_protocol_type: Dict[ProtocolType, List[str]] = {
            proto_type: [] for proto_type in ProtocolType
        }
        self._priority_order: List[str] = []

    @classmethod
    def from_config(
        cls,
        config_dir: Optional[Path] = None,
        register_maps_dir: Optional[Path] = None,
    ) -> "ProtocolRegistry":
        """
        Create a registry from configuration files.

        Args:
            config_dir: Directory containing protocol YAML files.
            register_maps_dir: Directory containing register map JSON files.

        Returns:
            ProtocolRegistry with loaded protocols.
        """
        registry = cls()
        loader = ProtocolLoader(config_dir)

        # Load all protocols from config
        protocols = loader.load_all()

        for protocol in protocols:
            registry.register(protocol)

        logger.info(
            f"Initialized protocol registry with {len(registry)} protocols"
        )
        return registry

    def register(self, protocol: ProtocolDefinition) -> None:
        """
        Register a protocol definition.

        Args:
            protocol: The protocol definition to register.

        Raises:
            ValueError: If a protocol with the same ID is already registered.
        """
        if protocol.protocol_id in self._protocols:
            raise ValueError(
                f"Protocol '{protocol.protocol_id}' is already registered"
            )

        self._protocols[protocol.protocol_id] = protocol

        # Index by device type
        self._by_device_type[protocol.device_type].append(protocol.protocol_id)

        # Index by protocol type
        self._by_protocol_type[protocol.protocol_type].append(protocol.protocol_id)

        # Update priority order
        self._priority_order.append(protocol.protocol_id)
        self._priority_order.sort(
            key=lambda pid: self._protocols[pid].priority
        )

        logger.debug(
            f"Registered protocol: {protocol.protocol_id} "
            f"(type={protocol.device_type.value}, priority={protocol.priority})"
        )

    def unregister(self, protocol_id: str) -> Optional[ProtocolDefinition]:
        """
        Remove a protocol from the registry.

        Args:
            protocol_id: ID of the protocol to remove.

        Returns:
            The removed protocol, or None if not found.
        """
        if protocol_id not in self._protocols:
            return None

        protocol = self._protocols.pop(protocol_id)

        # Remove from indices
        self._by_device_type[protocol.device_type].remove(protocol_id)
        self._by_protocol_type[protocol.protocol_type].remove(protocol_id)
        self._priority_order.remove(protocol_id)

        logger.debug(f"Unregistered protocol: {protocol_id}")
        return protocol

    def get(self, protocol_id: str) -> Optional[ProtocolDefinition]:
        """
        Get a protocol by ID.

        Args:
            protocol_id: The protocol ID.

        Returns:
            The protocol definition, or None if not found.
        """
        return self._protocols.get(protocol_id)

    def get_by_device_type(
        self, device_type: DeviceType
    ) -> List[ProtocolDefinition]:
        """
        Get all protocols for a specific device type.

        Args:
            device_type: The device type to filter by.

        Returns:
            List of matching protocols, sorted by priority.
        """
        protocol_ids = self._by_device_type.get(device_type, [])
        protocols = [self._protocols[pid] for pid in protocol_ids]
        return sorted(protocols, key=lambda p: p.priority)

    def get_by_protocol_type(
        self, protocol_type: ProtocolType
    ) -> List[ProtocolDefinition]:
        """
        Get all protocols using a specific protocol type.

        Args:
            protocol_type: The protocol type to filter by.

        Returns:
            List of matching protocols, sorted by priority.
        """
        protocol_ids = self._by_protocol_type.get(protocol_type, [])
        protocols = [self._protocols[pid] for pid in protocol_ids]
        return sorted(protocols, key=lambda p: p.priority)

    def get_modbus_protocols(self) -> List[ProtocolDefinition]:
        """Get all Modbus-based protocols (TCP and RTU)."""
        modbus_tcp = self.get_by_protocol_type(ProtocolType.MODBUS_TCP)
        modbus_rtu = self.get_by_protocol_type(ProtocolType.MODBUS_RTU)
        all_modbus = modbus_tcp + modbus_rtu
        return sorted(all_modbus, key=lambda p: p.priority)

    def get_command_protocols(self) -> List[ProtocolDefinition]:
        """Get all command-based protocols."""
        return self.get_by_protocol_type(ProtocolType.COMMAND)

    def iter_by_priority(self) -> Iterator[ProtocolDefinition]:
        """
        Iterate over all protocols in priority order.

        Lower priority numbers come first.

        Yields:
            ProtocolDefinition objects in priority order.
        """
        for protocol_id in self._priority_order:
            yield self._protocols[protocol_id]

    def iter_modbus_by_priority(self) -> Iterator[ProtocolDefinition]:
        """
        Iterate over Modbus protocols in priority order.

        Yields:
            Modbus ProtocolDefinition objects in priority order.
        """
        for protocol in self.iter_by_priority():
            if protocol.protocol_type in (
                ProtocolType.MODBUS_TCP,
                ProtocolType.MODBUS_RTU,
            ):
                yield protocol

    def iter_command_by_priority(self) -> Iterator[ProtocolDefinition]:
        """
        Iterate over command-based protocols in priority order.

        Yields:
            Command ProtocolDefinition objects in priority order.
        """
        for protocol in self.iter_by_priority():
            if protocol.protocol_type == ProtocolType.COMMAND:
                yield protocol

    def __len__(self) -> int:
        """Return the number of registered protocols."""
        return len(self._protocols)

    def __contains__(self, protocol_id: str) -> bool:
        """Check if a protocol is registered."""
        return protocol_id in self._protocols

    def __iter__(self) -> Iterator[ProtocolDefinition]:
        """Iterate over all protocols in priority order."""
        return self.iter_by_priority()

    def list_protocols(self) -> List[Dict]:
        """
        Get a list of all protocols with basic info.

        Returns:
            List of protocol dictionaries for display.
        """
        return [protocol.to_dict() for protocol in self.iter_by_priority()]

    def summary(self) -> str:
        """
        Get a summary of registered protocols.

        Returns:
            Human-readable summary string.
        """
        lines = [f"Protocol Registry: {len(self)} protocols"]
        for device_type in DeviceType:
            count = len(self._by_device_type.get(device_type, []))
            if count > 0:
                lines.append(f"  {device_type.value}: {count}")
        return "\n".join(lines)
