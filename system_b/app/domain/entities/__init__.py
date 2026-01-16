"""
Domain entities for System B.
"""
from .base import Entity
from .telemetry import (
    DataQuality,
    DeviceType,
    ConnectionStatus,
    TelemetryPoint,
    TelemetryBatch,
    TelemetryAggregate,
    MetricDefinition,
    Metrics,
)
from .device import (
    DeviceRegistry,
    DeviceSession,
)
from .event import (
    EventType,
    EventSeverity,
    DeviceEvent,
)
from .command import (
    CommandStatus,
    CommandType,
    DeviceCommand,
    CommandResult,
)

__all__ = [
    # Base
    "Entity",
    # Telemetry
    "DataQuality",
    "DeviceType",
    "ConnectionStatus",
    "TelemetryPoint",
    "TelemetryBatch",
    "TelemetryAggregate",
    "MetricDefinition",
    "Metrics",
    # Device
    "DeviceRegistry",
    "DeviceSession",
    # Event
    "EventType",
    "EventSeverity",
    "DeviceEvent",
    # Command
    "CommandStatus",
    "CommandType",
    "DeviceCommand",
    "CommandResult",
]
