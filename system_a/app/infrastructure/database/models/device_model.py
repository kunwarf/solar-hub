"""
SQLAlchemy model for Device entity.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from .base import BaseModel
from ....domain.entities.device import (
    Device, DeviceType, DeviceStatus, ProtocolType,
    ConnectionConfig, DeviceMetrics
)


class DeviceModel(BaseModel):
    """SQLAlchemy model for devices table."""

    __tablename__ = 'devices'

    site_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('sites.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    organization_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    device_type = Column(
        Enum(DeviceType, name='device_type'),
        nullable=False,
        index=True
    )
    name = Column(String(200), nullable=False)
    manufacturer = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    serial_number = Column(String(100), unique=True, nullable=False, index=True)
    firmware_version = Column(String(50), nullable=True)

    status = Column(
        Enum(DeviceStatus, name='device_status'),
        default=DeviceStatus.PENDING,
        nullable=False,
        index=True
    )

    # Connection configuration (JSON)
    connection_config = Column(JSONB, nullable=True)

    # Status tracking
    last_seen_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    last_error_message = Column(Text, nullable=True)

    # Latest metrics (JSON snapshot)
    latest_metrics = Column(JSONB, nullable=True)

    # Metadata and tags
    device_metadata = Column('metadata', JSONB, default=dict, nullable=False)
    tags = Column(ARRAY(String), default=list, nullable=False)

    # Statistics
    total_messages_received = Column(Integer, default=0, nullable=False)
    total_errors = Column(Integer, default=0, nullable=False)
    uptime_percentage = Column(Float, default=0.0, nullable=False)

    # Relationships
    site = relationship('SiteModel', back_populates='devices')

    def to_domain(self) -> Device:
        """Convert ORM model to domain entity."""
        device = Device(
            id=self.id,
            site_id=self.site_id,
            organization_id=self.organization_id,
            device_type=self.device_type,
            name=self.name,
            manufacturer=self.manufacturer,
            model=self.model,
            serial_number=self.serial_number,
            firmware_version=self.firmware_version,
            status=self.status,
            connection_config=ConnectionConfig.from_dict(self.connection_config) if self.connection_config else None,
            last_seen_at=self.last_seen_at,
            last_error_at=self.last_error_at,
            last_error_message=self.last_error_message,
            latest_metrics=self._parse_metrics(self.latest_metrics),
            metadata=self.device_metadata or {},
            tags=self.tags or [],
            total_messages_received=self.total_messages_received,
            total_errors=self.total_errors,
            uptime_percentage=self.uptime_percentage,
            created_at=self.created_at,
            updated_at=self.updated_at,
            version=self.version
        )
        device._domain_events = []
        return device

    def _parse_metrics(self, metrics_dict: Optional[dict]) -> Optional[DeviceMetrics]:
        """Parse metrics JSON to DeviceMetrics."""
        if not metrics_dict:
            return None

        from datetime import datetime
        recorded_at = metrics_dict.get('recorded_at')
        if recorded_at and isinstance(recorded_at, str):
            recorded_at = datetime.fromisoformat(recorded_at)
        else:
            recorded_at = datetime.now()

        return DeviceMetrics(
            power_output_w=metrics_dict.get('power_output_w'),
            energy_today_kwh=metrics_dict.get('energy_today_kwh'),
            energy_total_kwh=metrics_dict.get('energy_total_kwh'),
            voltage_v=metrics_dict.get('voltage_v'),
            current_a=metrics_dict.get('current_a'),
            frequency_hz=metrics_dict.get('frequency_hz'),
            temperature_c=metrics_dict.get('temperature_c'),
            battery_soc_percent=metrics_dict.get('battery_soc_percent'),
            battery_power_w=metrics_dict.get('battery_power_w'),
            grid_power_w=metrics_dict.get('grid_power_w'),
            load_power_w=metrics_dict.get('load_power_w'),
            efficiency_percent=metrics_dict.get('efficiency_percent'),
            error_codes=metrics_dict.get('error_codes', []),
            recorded_at=recorded_at
        )

    @classmethod
    def from_domain(cls, device: Device) -> 'DeviceModel':
        """Create ORM model from domain entity."""
        return cls(
            id=device.id,
            site_id=device.site_id,
            organization_id=device.organization_id,
            device_type=device.device_type,
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model,
            serial_number=device.serial_number,
            firmware_version=device.firmware_version,
            status=device.status,
            connection_config=device.connection_config.to_dict() if device.connection_config else None,
            last_seen_at=device.last_seen_at,
            last_error_at=device.last_error_at,
            last_error_message=device.last_error_message,
            latest_metrics=device.latest_metrics.to_dict() if device.latest_metrics else None,
            device_metadata=device.metadata,
            tags=device.tags,
            total_messages_received=device.total_messages_received,
            total_errors=device.total_errors,
            uptime_percentage=device.uptime_percentage,
            created_at=device.created_at,
            updated_at=device.updated_at,
            version=device.version
        )

    def update_from_domain(self, device: Device) -> None:
        """Update ORM model from domain entity."""
        self.site_id = device.site_id
        self.organization_id = device.organization_id
        self.device_type = device.device_type
        self.name = device.name
        self.manufacturer = device.manufacturer
        self.model = device.model
        self.serial_number = device.serial_number
        self.firmware_version = device.firmware_version
        self.status = device.status
        self.connection_config = device.connection_config.to_dict() if device.connection_config else None
        self.last_seen_at = device.last_seen_at
        self.last_error_at = device.last_error_at
        self.last_error_message = device.last_error_message
        self.latest_metrics = device.latest_metrics.to_dict() if device.latest_metrics else None
        self.device_metadata = device.metadata
        self.tags = device.tags
        self.total_messages_received = device.total_messages_received
        self.total_errors = device.total_errors
        self.uptime_percentage = device.uptime_percentage
        self.updated_at = device.updated_at
        self.version = device.version
