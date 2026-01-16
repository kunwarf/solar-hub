"""
Protocol Definition application service.
"""
import logging
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from ..interfaces.repositories import ProtocolDefinitionRepository
from ...domain.entities.device import DeviceType, ProtocolType
from ...domain.entities.protocol_definition import (
    ProtocolDefinition,
    IdentificationConfig,
    SerialNumberConfig,
    PollingConfig,
    ModbusConfig,
    CommandConfig
)

logger = logging.getLogger(__name__)


@dataclass
class CreateProtocolDefinitionRequest:
    """Request data for creating a protocol definition."""
    protocol_id: str
    name: str
    device_type: str
    protocol_type: str
    adapter_class: str
    description: Optional[str] = None
    priority: int = 100
    manufacturer: Optional[str] = None
    model_pattern: Optional[str] = None
    register_map_file: Optional[str] = None
    identification_config: Optional[dict] = None
    serial_number_config: Optional[dict] = None
    polling_config: Optional[dict] = None
    modbus_config: Optional[dict] = None
    command_config: Optional[dict] = None
    default_connection_config: Optional[dict] = None


@dataclass
class UpdateProtocolDefinitionRequest:
    """Request data for updating a protocol definition."""
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    manufacturer: Optional[str] = None
    model_pattern: Optional[str] = None
    adapter_class: Optional[str] = None
    register_map_file: Optional[str] = None
    identification_config: Optional[dict] = None
    serial_number_config: Optional[dict] = None
    polling_config: Optional[dict] = None
    modbus_config: Optional[dict] = None
    command_config: Optional[dict] = None
    default_connection_config: Optional[dict] = None
    is_active: Optional[bool] = None


class ProtocolDefinitionService:
    """
    Protocol Definition service for managing device communication protocols.
    """

    def __init__(self, repository: ProtocolDefinitionRepository):
        self._repository = repository

    async def create(
        self,
        request: CreateProtocolDefinitionRequest
    ) -> ProtocolDefinition:
        """
        Create a new protocol definition.

        Args:
            request: Creation request data

        Returns:
            Created ProtocolDefinition

        Raises:
            ValueError: If protocol_id already exists
        """
        # Check if protocol_id already exists
        if await self._repository.protocol_id_exists(request.protocol_id):
            raise ValueError(f"Protocol ID '{request.protocol_id}' already exists")

        # Parse configuration objects
        identification_config = None
        if request.identification_config:
            identification_config = IdentificationConfig.from_dict(
                request.identification_config
            )

        serial_number_config = None
        if request.serial_number_config:
            serial_number_config = SerialNumberConfig.from_dict(
                request.serial_number_config
            )

        polling_config = None
        if request.polling_config:
            polling_config = PollingConfig.from_dict(request.polling_config)

        modbus_config = None
        if request.modbus_config:
            modbus_config = ModbusConfig.from_dict(request.modbus_config)

        command_config = None
        if request.command_config:
            command_config = CommandConfig.from_dict(request.command_config)

        # Create entity
        entity = ProtocolDefinition.create(
            protocol_id=request.protocol_id,
            name=request.name,
            description=request.description,
            device_type=DeviceType(request.device_type),
            protocol_type=ProtocolType(request.protocol_type),
            priority=request.priority,
            manufacturer=request.manufacturer,
            model_pattern=request.model_pattern,
            adapter_class=request.adapter_class,
            register_map_file=request.register_map_file,
            identification_config=identification_config,
            serial_number_config=serial_number_config,
            polling_config=polling_config,
            modbus_config=modbus_config,
            command_config=command_config,
            default_connection_config=request.default_connection_config,
            is_system=False
        )

        result = await self._repository.add(entity)
        logger.info(f"Created protocol definition: {result.protocol_id}")
        return result

    async def update(
        self,
        id: UUID,
        request: UpdateProtocolDefinitionRequest
    ) -> ProtocolDefinition:
        """
        Update an existing protocol definition.

        Args:
            id: Protocol definition UUID
            request: Update request data

        Returns:
            Updated ProtocolDefinition

        Raises:
            ValueError: If not found or is a system protocol
        """
        entity = await self._repository.get_by_id(id)
        if not entity:
            raise ValueError(f"Protocol definition with id {id} not found")

        if entity.is_system:
            raise ValueError("Cannot modify system protocol definitions")

        # Parse configuration objects if provided
        identification_config = None
        if request.identification_config is not None:
            identification_config = IdentificationConfig.from_dict(
                request.identification_config
            ) if request.identification_config else None

        serial_number_config = None
        if request.serial_number_config is not None:
            serial_number_config = SerialNumberConfig.from_dict(
                request.serial_number_config
            ) if request.serial_number_config else None

        polling_config = None
        if request.polling_config is not None:
            polling_config = PollingConfig.from_dict(
                request.polling_config
            ) if request.polling_config else None

        modbus_config = None
        if request.modbus_config is not None:
            modbus_config = ModbusConfig.from_dict(
                request.modbus_config
            ) if request.modbus_config else None

        command_config = None
        if request.command_config is not None:
            command_config = CommandConfig.from_dict(
                request.command_config
            ) if request.command_config else None

        # Update entity
        entity.update(
            name=request.name,
            description=request.description,
            priority=request.priority,
            manufacturer=request.manufacturer,
            model_pattern=request.model_pattern,
            adapter_class=request.adapter_class,
            register_map_file=request.register_map_file,
            identification_config=identification_config,
            serial_number_config=serial_number_config,
            polling_config=polling_config,
            modbus_config=modbus_config,
            command_config=command_config,
            default_connection_config=request.default_connection_config,
            is_active=request.is_active
        )

        result = await self._repository.update(entity)
        logger.info(f"Updated protocol definition: {result.protocol_id}")
        return result

    async def get_by_id(self, id: UUID) -> Optional[ProtocolDefinition]:
        """Get protocol definition by ID."""
        return await self._repository.get_by_id(id)

    async def get_by_protocol_id(self, protocol_id: str) -> Optional[ProtocolDefinition]:
        """Get protocol definition by protocol_id string."""
        return await self._repository.get_by_protocol_id(protocol_id)

    async def get_by_device_type(
        self,
        device_type: str,
        is_active: Optional[bool] = True
    ) -> List[ProtocolDefinition]:
        """Get protocol definitions for a device type."""
        return await self._repository.get_by_device_type(
            DeviceType(device_type),
            is_active
        )

    async def get_by_protocol_type(
        self,
        protocol_type: str,
        is_active: Optional[bool] = True
    ) -> List[ProtocolDefinition]:
        """Get protocol definitions for a protocol type."""
        return await self._repository.get_by_protocol_type(
            ProtocolType(protocol_type),
            is_active
        )

    async def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        is_active: Optional[bool] = None
    ) -> List[ProtocolDefinition]:
        """Get all protocol definitions with optional filtering."""
        return await self._repository.get_all(limit, offset, is_active)

    async def get_all_active(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[ProtocolDefinition]:
        """Get all active protocol definitions ordered by priority."""
        return await self._repository.get_all_active(limit, offset)

    async def count(self, is_active: Optional[bool] = None) -> int:
        """Count protocol definitions."""
        return await self._repository.count(is_active)

    async def delete(self, id: UUID) -> bool:
        """
        Delete a protocol definition.

        Args:
            id: Protocol definition UUID

        Returns:
            True if deleted

        Raises:
            ValueError: If not found or is a system protocol
        """
        entity = await self._repository.get_by_id(id)
        if not entity:
            raise ValueError(f"Protocol definition with id {id} not found")

        if entity.is_system:
            raise ValueError("Cannot delete system protocol definitions")

        result = await self._repository.delete(id)
        if result:
            logger.info(f"Deleted protocol definition: {entity.protocol_id}")
        return result

    async def deactivate(self, id: UUID) -> ProtocolDefinition:
        """Deactivate a protocol definition (soft delete)."""
        entity = await self._repository.get_by_id(id)
        if not entity:
            raise ValueError(f"Protocol definition with id {id} not found")

        entity.deactivate()
        result = await self._repository.update(entity)
        logger.info(f"Deactivated protocol definition: {result.protocol_id}")
        return result

    async def activate(self, id: UUID) -> ProtocolDefinition:
        """Activate a protocol definition."""
        entity = await self._repository.get_by_id(id)
        if not entity:
            raise ValueError(f"Protocol definition with id {id} not found")

        entity.activate()
        result = await self._repository.update(entity)
        logger.info(f"Activated protocol definition: {result.protocol_id}")
        return result
