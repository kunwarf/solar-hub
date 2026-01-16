"""
SQLAlchemy model for ProtocolDefinition entity.
"""
from typing import Optional

from sqlalchemy import Boolean, Column, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

from .base import BaseModel
from ....domain.entities.device import DeviceType, ProtocolType
from ....domain.entities.protocol_definition import (
    ProtocolDefinition,
    IdentificationConfig,
    SerialNumberConfig,
    PollingConfig,
    ModbusConfig,
    CommandConfig
)


class ProtocolDefinitionModel(BaseModel):
    """SQLAlchemy model for protocol_definitions table."""

    __tablename__ = 'protocol_definitions'

    protocol_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    device_type = Column(
        Enum(DeviceType, name='device_type', create_type=False),
        nullable=False,
        index=True
    )
    protocol_type = Column(
        Enum(ProtocolType, name='protocol_type', create_type=False),
        nullable=False,
        index=True
    )

    priority = Column(Integer, nullable=False, default=100)
    manufacturer = Column(String(100), nullable=True)
    model_pattern = Column(String(200), nullable=True)
    adapter_class = Column(String(200), nullable=False)
    register_map_file = Column(String(200), nullable=True)

    # Configuration as JSONB
    identification_config = Column(JSONB, nullable=True)
    serial_number_config = Column(JSONB, nullable=True)
    polling_config = Column(JSONB, nullable=True)
    modbus_config = Column(JSONB, nullable=True)
    command_config = Column(JSONB, nullable=True)
    default_connection_config = Column(JSONB, nullable=True)

    # Metadata
    is_active = Column(Boolean, nullable=False, default=True)
    is_system = Column(Boolean, nullable=False, default=False)

    def to_domain(self) -> ProtocolDefinition:
        """Convert ORM model to domain entity."""
        return ProtocolDefinition(
            id=self.id,
            protocol_id=self.protocol_id,
            name=self.name,
            description=self.description,
            device_type=self.device_type,
            protocol_type=self.protocol_type,
            priority=self.priority,
            manufacturer=self.manufacturer,
            model_pattern=self.model_pattern,
            adapter_class=self.adapter_class,
            register_map_file=self.register_map_file,
            identification_config=IdentificationConfig.from_dict(
                self.identification_config
            ) if self.identification_config else None,
            serial_number_config=SerialNumberConfig.from_dict(
                self.serial_number_config
            ) if self.serial_number_config else None,
            polling_config=PollingConfig.from_dict(
                self.polling_config
            ) if self.polling_config else None,
            modbus_config=ModbusConfig.from_dict(
                self.modbus_config
            ) if self.modbus_config else None,
            command_config=CommandConfig.from_dict(
                self.command_config
            ) if self.command_config else None,
            default_connection_config=self.default_connection_config,
            is_active=self.is_active,
            is_system=self.is_system,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version
        )

    @classmethod
    def from_domain(cls, entity: ProtocolDefinition) -> 'ProtocolDefinitionModel':
        """Create ORM model from domain entity."""
        return cls(
            id=entity.id,
            protocol_id=entity.protocol_id,
            name=entity.name,
            description=entity.description,
            device_type=entity.device_type,
            protocol_type=entity.protocol_type,
            priority=entity.priority,
            manufacturer=entity.manufacturer,
            model_pattern=entity.model_pattern,
            adapter_class=entity.adapter_class,
            register_map_file=entity.register_map_file,
            identification_config=entity.identification_config.to_dict() if entity.identification_config else None,
            serial_number_config=entity.serial_number_config.to_dict() if entity.serial_number_config else None,
            polling_config=entity.polling_config.to_dict() if entity.polling_config else None,
            modbus_config=entity.modbus_config.to_dict() if entity.modbus_config else None,
            command_config=entity.command_config.to_dict() if entity.command_config else None,
            default_connection_config=entity.default_connection_config,
            is_active=entity.is_active,
            is_system=entity.is_system,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            version=entity.version
        )

    def update_from_domain(self, entity: ProtocolDefinition) -> None:
        """Update ORM model from domain entity."""
        self.protocol_id = entity.protocol_id
        self.name = entity.name
        self.description = entity.description
        self.device_type = entity.device_type
        self.protocol_type = entity.protocol_type
        self.priority = entity.priority
        self.manufacturer = entity.manufacturer
        self.model_pattern = entity.model_pattern
        self.adapter_class = entity.adapter_class
        self.register_map_file = entity.register_map_file
        self.identification_config = entity.identification_config.to_dict() if entity.identification_config else None
        self.serial_number_config = entity.serial_number_config.to_dict() if entity.serial_number_config else None
        self.polling_config = entity.polling_config.to_dict() if entity.polling_config else None
        self.modbus_config = entity.modbus_config.to_dict() if entity.modbus_config else None
        self.command_config = entity.command_config.to_dict() if entity.command_config else None
        self.default_connection_config = entity.default_connection_config
        self.is_active = entity.is_active
        self.is_system = entity.is_system
        self.updated_at = entity.updated_at
        self.version = entity.version
