"""
SQLAlchemy ORM models for System B (TimescaleDB).
"""
from .base import Base, metadata
from .telemetry_model import (
    DataQualityEnum,
    DeviceTypeEnum,
    ConnectionStatusEnum,
    CommandStatusEnum,
    DeviceRegistryModel,
    TelemetryRawModel,
    DeviceEventsModel,
    DeviceCommandsModel,
    MetricDefinitionsModel,
    IngestionBatchesModel,
)

__all__ = [
    # Base
    "Base",
    "metadata",
    # Enums
    "DataQualityEnum",
    "DeviceTypeEnum",
    "ConnectionStatusEnum",
    "CommandStatusEnum",
    # Models
    "DeviceRegistryModel",
    "TelemetryRawModel",
    "DeviceEventsModel",
    "DeviceCommandsModel",
    "MetricDefinitionsModel",
    "IngestionBatchesModel",
]
