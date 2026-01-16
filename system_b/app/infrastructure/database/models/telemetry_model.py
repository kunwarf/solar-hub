"""
SQLAlchemy models for telemetry data in TimescaleDB.

These models represent the hypertables and regular tables in System B.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy import (
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    LargeBinary,
    ForeignKey,
    Index,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


# Enum types matching the database
class DataQualityEnum:
    GOOD = "good"
    INTERPOLATED = "interpolated"
    ESTIMATED = "estimated"
    SUSPECT = "suspect"
    MISSING = "missing"
    INVALID = "invalid"


class DeviceTypeEnum:
    INVERTER = "inverter"
    METER = "meter"
    BATTERY = "battery"
    WEATHER_STATION = "weather_station"
    SENSOR = "sensor"
    GATEWAY = "gateway"


class ConnectionStatusEnum:
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    TIMEOUT = "timeout"


class CommandStatusEnum:
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class DeviceRegistryModel(Base):
    """
    Device registry for System B.

    Lightweight device information for telemetry collection.
    """
    __tablename__ = "device_registry"

    device_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    site_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)

    # Device info
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # Authentication
    auth_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Connection state
    connection_status: Mapped[str] = mapped_column(String(20), nullable=False, default="disconnected")
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reconnect_count: Mapped[int] = mapped_column(Integer, default=0)

    # Protocol configuration
    protocol: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    connection_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Polling configuration
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    last_polled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_poll_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_device_registry_status", "connection_status"),
        Index("idx_device_registry_next_poll", "next_poll_at"),
    )


class TelemetryRawModel(Base):
    """
    Raw telemetry readings (TimescaleDB hypertable).

    This table is converted to a hypertable with time-based partitioning.
    """
    __tablename__ = "telemetry_raw"

    # Composite primary key for hypertable
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, nullable=False)
    device_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), primary_key=True, nullable=False)

    # Site reference
    site_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Metric values
    metric_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    metric_value_str: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Data quality
    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="good")

    # Metadata
    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    raw_value: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    # Ingestion tracking
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Indexes for common query patterns
    __table_args__ = (
        Index("idx_telemetry_raw_device_time", "device_id", "time"),
        Index("idx_telemetry_raw_site_time", "site_id", "time"),
        Index("idx_telemetry_raw_metric", "metric_name", "time"),
        Index("idx_telemetry_raw_device_metric", "device_id", "metric_name", "time"),
    )


class DeviceEventsModel(Base):
    """
    Device events (TimescaleDB hypertable).

    Captures significant device events for monitoring.
    """
    __tablename__ = "device_events"

    # Composite primary key for hypertable
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, nullable=False)
    device_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), primary_key=True, nullable=False)

    # Site reference
    site_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Event details
    event_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Acknowledgment
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_device_events_device", "device_id", "time"),
        Index("idx_device_events_site", "site_id", "time"),
        Index("idx_device_events_type", "event_type", "time"),
    )


class DeviceCommandsModel(Base):
    """
    Device commands for remote control.
    """
    __tablename__ = "device_commands"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    device_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    site_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    # Command details
    command_type: Mapped[str] = mapped_column(String(100), nullable=False)
    command_params: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Result
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Audit
    created_by: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)

    # Indexes
    __table_args__ = (
        Index("idx_device_commands_pending", "device_id", "priority", "created_at"),
    )


class MetricDefinitionsModel(Base):
    """
    Standard metric definitions.
    """
    __tablename__ = "metric_definitions"

    metric_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # float, integer, string, boolean
    device_types: Mapped[list] = mapped_column(ARRAY(String(50)), nullable=False)
    min_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    aggregation_method: Mapped[str] = mapped_column(String(20), default="avg")
    is_cumulative: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class IngestionBatchesModel(Base):
    """
    Telemetry ingestion batch tracking.
    """
    __tablename__ = "ingestion_batches"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)

    # Source
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Batch info
    device_count: Mapped[int] = mapped_column(Integer, default=0)
    record_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Errors
    errors: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Performance
    processing_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Index
    __table_args__ = (
        Index("idx_ingestion_batches_status", "status", "started_at"),
    )
