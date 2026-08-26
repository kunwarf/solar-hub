"""
SQLAlchemy models for OTA firmware management.
"""
from datetime import datetime, timezone as dt_timezone
from uuid import uuid4
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, ForeignKey,
    Index, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

# Same relative-import convention as the other models in this package.
# The absolute `system_b.app.…` path does NOT work at runtime because
# uvicorn launches with `WorkingDirectory=system_b` and no `system_b`
# package is on the module path.
from .base import Base


class FirmwareVersion(Base):
    """Firmware version metadata."""
    __tablename__ = "firmware_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    version = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    device_type = Column(String(50), nullable=False, default="datalogger", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(dt_timezone.utc))
    created_by = Column(String(100), nullable=True)
    # NOTE: `metadata` is a reserved attribute on Declarative Base (it holds
    # the MetaData registry).  We map to the DB column of the same name via
    # the string arg; Python attribute is `metadata_`.  Callers must use
    # `.metadata_` when reading/writing.
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Relationships
    files = relationship("FirmwareFile", back_populates="firmware_version", cascade="all, delete-orphan")
    campaigns = relationship("FirmwareUpdateCampaign", back_populates="firmware_version")


class FirmwareFile(Base):
    """Firmware file content."""
    __tablename__ = "firmware_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    firmware_version_id = Column(UUID(as_uuid=True), ForeignKey("firmware_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)  # Base64 for binary, plain text for .py
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)  # SHA256 hash
    file_type = Column(String(20), nullable=False, default="python")  # python, config, binary
    is_required = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(dt_timezone.utc))

    # Relationships
    firmware_version = relationship("FirmwareVersion", back_populates="files")


class DeviceFirmwareStatus(Base):
    """Device firmware status tracking."""
    __tablename__ = "device_firmware_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_serial = Column(String(50), nullable=False, unique=True, index=True)
    current_version = Column(String(50), nullable=True)
    target_version_id = Column(UUID(as_uuid=True), ForeignKey("firmware_versions.id", ondelete="SET NULL"), nullable=True)
    update_status = Column(String(20), nullable=False, default="up_to_date", index=True)
    # Status: up_to_date, pending, downloading, applying, success, failed, rollback
    update_progress = Column(Integer, nullable=False, default=0)  # 0-100
    last_check_at = Column(DateTime(timezone=True), nullable=True)
    update_started_at = Column(DateTime(timezone=True), nullable=True)
    update_completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    # See FirmwareVersion.metadata_ comment — reserved name, mapped to
    # existing DB column via string arg.
    metadata_ = Column("metadata", JSONB, nullable=True)  # Device info, memory, etc.
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(dt_timezone.utc))

    # Relationships
    target_version = relationship("FirmwareVersion", foreign_keys=[target_version_id])


class FirmwareUpdateCampaign(Base):
    """Firmware update campaign for managing rollouts."""
    __tablename__ = "firmware_update_campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), nullable=False)
    firmware_version_id = Column(UUID(as_uuid=True), ForeignKey("firmware_versions.id", ondelete="CASCADE"), nullable=False)
    target_devices = Column(ARRAY(String), nullable=True)  # Specific device serials
    target_filter = Column(JSONB, nullable=True)  # Filter criteria
    rollout_strategy = Column(String(20), nullable=False, default="immediate")
    # Strategies: immediate, staged, canary, scheduled
    rollout_percentage = Column(Integer, nullable=False, default=100)  # For staged rollouts
    status = Column(String(20), nullable=False, default="draft", index=True)
    # Status: draft, active, paused, completed, cancelled
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(dt_timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(100), nullable=True)
    # See FirmwareVersion.metadata_ comment.
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Relationships
    firmware_version = relationship("FirmwareVersion", back_populates="campaigns")


class FirmwareUpdateHistory(Base):
    """Firmware update history for audit trail."""
    __tablename__ = "firmware_update_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    device_serial = Column(String(50), nullable=False, index=True)
    from_version = Column(String(50), nullable=True)
    to_version = Column(String(50), nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("firmware_update_campaigns.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), nullable=False)  # success, failed, rollback
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    # See FirmwareVersion.metadata_ comment.
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Relationships
    campaign = relationship("FirmwareUpdateCampaign")
