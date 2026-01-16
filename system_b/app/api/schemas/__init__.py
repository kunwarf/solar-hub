# Pydantic Schemas for telemetry data

from .telemetry_schemas import (
    TelemetryPointCreate,
    TelemetryBatchCreate,
    TelemetryIngestRequest,
    TelemetryPointResponse,
    TelemetryLatestResponse,
    TelemetryAggregateResponse,
    TelemetryQueryRequest,
    TelemetryStatsResponse,
    IngestResponse,
)
from .device_schemas import (
    DeviceRegisterRequest,
    DeviceSyncRequest,
    DeviceUpdateRequest,
    DeviceResponse,
    DeviceSessionResponse,
    DeviceSummaryResponse,
    DeviceListResponse,
    ConnectionStatsResponse,
    DeviceAuthRequest,
    DeviceAuthResponse,
    DeviceTokenResponse,
)
from .command_schemas import (
    CommandCreateRequest,
    CommandResponse,
    CommandListResponse,
    CommandResultRequest,
    CommandStatsResponse,
)
from .event_schemas import (
    EventCreateRequest,
    EventResponse,
    EventListResponse,
    EventAcknowledgeRequest,
    EventBulkAcknowledgeRequest,
    EventCountsResponse,
    EventTimelinePoint,
    EventTimelineResponse,
    EventStatsResponse,
    TopErrorDeviceResponse,
)

__all__ = [
    # Telemetry
    "TelemetryPointCreate",
    "TelemetryBatchCreate",
    "TelemetryIngestRequest",
    "TelemetryPointResponse",
    "TelemetryLatestResponse",
    "TelemetryAggregateResponse",
    "TelemetryQueryRequest",
    "TelemetryStatsResponse",
    "IngestResponse",
    # Device
    "DeviceRegisterRequest",
    "DeviceSyncRequest",
    "DeviceUpdateRequest",
    "DeviceResponse",
    "DeviceSessionResponse",
    "DeviceSummaryResponse",
    "DeviceListResponse",
    "ConnectionStatsResponse",
    "DeviceAuthRequest",
    "DeviceAuthResponse",
    "DeviceTokenResponse",
    # Command
    "CommandCreateRequest",
    "CommandResponse",
    "CommandListResponse",
    "CommandResultRequest",
    "CommandStatsResponse",
    # Event
    "EventCreateRequest",
    "EventResponse",
    "EventListResponse",
    "EventAcknowledgeRequest",
    "EventBulkAcknowledgeRequest",
    "EventCountsResponse",
    "EventTimelinePoint",
    "EventTimelineResponse",
    "EventStatsResponse",
    "TopErrorDeviceResponse",
]
