"""
Pydantic schemas for telemetry API endpoints.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TelemetryPointCreate(BaseModel):
    """Schema for creating a single telemetry point."""
    metric_name: str = Field(..., min_length=1, max_length=100)
    metric_value: Optional[float] = None
    metric_value_str: Optional[str] = None
    timestamp: Optional[datetime] = None
    quality: str = Field(default="good")
    unit: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None

    @field_validator("metric_value", "metric_value_str")
    @classmethod
    def validate_value(cls, v, info):
        return v


class TelemetryBatchCreate(BaseModel):
    """Schema for batch telemetry ingestion."""
    device_id: UUID
    site_id: UUID
    timestamp: Optional[datetime] = None
    source: str = Field(default="device")
    metrics: Dict[str, Any] = Field(..., description="Map of metric_name to value")


class TelemetryIngestRequest(BaseModel):
    """Request for telemetry ingestion."""
    points: List[TelemetryBatchCreate]


class TelemetryPointResponse(BaseModel):
    """Response for a single telemetry point."""
    time: datetime
    device_id: UUID
    site_id: UUID
    metric_name: str
    value: Optional[float] = None
    value_str: Optional[str] = None
    quality: str
    unit: Optional[str] = None

    class Config:
        from_attributes = True


class TelemetryLatestResponse(BaseModel):
    """Response for latest telemetry readings."""
    device_id: UUID
    readings: Dict[str, Dict[str, Any]]


class TelemetryAggregateResponse(BaseModel):
    """Response for aggregated telemetry."""
    bucket: datetime
    avg: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    first: Optional[float] = None
    last: Optional[float] = None
    delta: Optional[float] = None
    sample_count: int
    quality_percent: float


class TelemetryQueryRequest(BaseModel):
    """Request for telemetry queries."""
    device_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    metric_names: Optional[List[str]] = None
    start_time: datetime
    end_time: datetime
    bucket_interval: Optional[str] = None
    limit: int = Field(default=10000, le=100000)


class TelemetryStatsResponse(BaseModel):
    """Response for telemetry statistics."""
    total_records: int
    first_reading: Optional[datetime] = None
    last_reading: Optional[datetime] = None
    distinct_metrics: int


class IngestResponse(BaseModel):
    """Response for telemetry ingestion."""
    success: bool
    inserted: int
    failed: int
    message: Optional[str] = None
