"""
SQLAlchemy ORM models for reports and report scheduling.
"""
from datetime import datetime, date, time
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    Date,
    Time,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base, BaseModel


class ReportModel(Base, BaseModel):
    """
    Generated report instance.

    Stores metadata about generated reports including status,
    file location, and delivery information.
    """
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())

    # Ownership
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Report definition
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Parameters (JSON)
    # Structure: {
    #   "site_ids": ["uuid1", "uuid2"],
    #   "device_ids": [],
    #   "date_range": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
    #   "group_by": "day",
    #   "include_charts": true,
    #   "include_raw_data": false
    # }
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Output format
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="pdf")

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)

    # Generation tracking
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Result
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Delivery configuration (JSON)
    # Structure: {
    #   "method": "email",
    #   "recipients": [{"email": "user@example.com", "name": "User"}],
    #   "webhook_url": null,
    #   "email_subject_template": "Monthly Report - {month}"
    # }
    delivery_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Schedule reference
    schedule_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), ForeignKey("report_schedules.id", ondelete="SET NULL"), nullable=True, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel", back_populates="reports")
    creator: Mapped[Optional["UserModel"]] = relationship("UserModel", back_populates="reports")
    schedule: Mapped[Optional["ReportScheduleModel"]] = relationship("ReportScheduleModel", back_populates="reports")

    # Indexes
    __table_args__ = (
        Index("idx_reports_org_type", "organization_id", "report_type"),
        Index("idx_reports_status_requested", "status", "requested_at"),
        Index("idx_reports_org_status", "organization_id", "status"),
    )


class ReportScheduleModel(Base, BaseModel):
    """
    Schedule for automatic report generation.

    Defines recurring reports with frequency, timing, and delivery settings.
    """
    __tablename__ = "report_schedules"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())

    # Ownership
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Schedule definition
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Report template
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    format: Mapped[str] = mapped_column(String(20), nullable=False, default="pdf")

    # Scheduling
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")

    # Time settings
    run_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(6, 0))
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0=Monday
    day_of_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-28

    # Timezone
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Karachi")

    # Active period
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Delivery configuration (JSON)
    delivery_config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Tracking
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_report_id: Mapped[Optional[UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    # Statistics
    total_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel", back_populates="report_schedules")
    creator: Mapped[Optional["UserModel"]] = relationship("UserModel", back_populates="report_schedules")
    reports: Mapped[list["ReportModel"]] = relationship("ReportModel", back_populates="schedule", lazy="dynamic")

    # Indexes
    __table_args__ = (
        Index("idx_schedules_org_active", "organization_id", "is_active"),
        Index("idx_schedules_next_run", "is_active", "next_run_at"),
    )


class ReportTemplateModel(Base, BaseModel):
    """
    Custom report template for organizations.

    Allows organizations to define custom report formats with branding.
    """
    __tablename__ = "report_templates"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())

    # Ownership
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Template info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Branding (JSON)
    # Structure: {
    #   "logo_url": "https://...",
    #   "header_text": "Company Name",
    #   "footer_text": "Confidential",
    #   "color_scheme": {"primary": "#1a73e8", "secondary": "#34a853"}
    # }
    branding: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Content sections (JSON array)
    # Structure: [
    #   {"type": "summary", "title": "Executive Summary", "enabled": true},
    #   {"type": "chart", "chart_type": "line", "metric": "energy_generated"},
    #   {"type": "table", "columns": ["date", "energy", "savings"]}
    # ]
    sections: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    # Default parameters
    default_parameters: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Usage tracking
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    organization: Mapped["OrganizationModel"] = relationship("OrganizationModel", back_populates="report_templates")
    creator: Mapped[Optional["UserModel"]] = relationship("UserModel", back_populates="report_templates")

    # Indexes
    __table_args__ = (
        Index("idx_templates_org_type", "organization_id", "report_type"),
        Index("idx_templates_org_default", "organization_id", "is_default"),
    )


# Import for type hints (avoid circular imports)
from .organization_model import OrganizationModel
from .user_model import UserModel
