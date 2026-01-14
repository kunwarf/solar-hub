"""
Report domain entities.

Handles report generation and scheduling for solar monitoring.
"""
from dataclasses import dataclass, field
from datetime import datetime, date, time
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID

from .base import Entity


class ReportType(str, Enum):
    """Types of reports that can be generated."""
    # Performance reports
    PERFORMANCE_SUMMARY = "performance_summary"      # Overall system performance
    ENERGY_GENERATION = "energy_generation"          # Energy generation details
    ENERGY_CONSUMPTION = "energy_consumption"        # Energy consumption analysis

    # Financial reports
    BILLING_SUMMARY = "billing_summary"              # Billing and savings summary
    ROI_ANALYSIS = "roi_analysis"                    # Return on investment analysis
    COST_SAVINGS = "cost_savings"                    # Cost savings breakdown

    # Operational reports
    DEVICE_STATUS = "device_status"                  # Device health and status
    MAINTENANCE = "maintenance"                      # Maintenance schedule/history
    ALERT_SUMMARY = "alert_summary"                  # Alert history and analysis

    # Comparison reports
    SITE_COMPARISON = "site_comparison"              # Compare multiple sites
    PERIOD_COMPARISON = "period_comparison"          # Compare different time periods
    BENCHMARK = "benchmark"                          # Performance benchmarking

    # Environmental reports
    ENVIRONMENTAL_IMPACT = "environmental_impact"    # CO2, trees equivalent
    SUSTAINABILITY = "sustainability"                # Sustainability metrics

    # Custom
    CUSTOM = "custom"                                # Custom report template


class ReportFormat(str, Enum):
    """Output formats for reports."""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    HTML = "html"
    JSON = "json"


class ReportFrequency(str, Enum):
    """Frequency options for scheduled reports."""
    ONCE = "once"           # One-time report
    DAILY = "daily"         # Every day
    WEEKLY = "weekly"       # Every week
    BIWEEKLY = "biweekly"   # Every two weeks
    MONTHLY = "monthly"     # Every month
    QUARTERLY = "quarterly" # Every quarter
    YEARLY = "yearly"       # Every year


class ReportStatus(str, Enum):
    """Status of a report generation job."""
    PENDING = "pending"         # Queued for generation
    GENERATING = "generating"   # Currently being generated
    COMPLETED = "completed"     # Successfully generated
    FAILED = "failed"           # Generation failed
    CANCELLED = "cancelled"     # Cancelled by user


class DeliveryMethod(str, Enum):
    """How the report should be delivered."""
    DOWNLOAD = "download"   # Available for download in app
    EMAIL = "email"         # Send via email
    WEBHOOK = "webhook"     # POST to webhook URL
    STORAGE = "storage"     # Save to cloud storage


@dataclass
class ReportDateRange:
    """Date range for report data."""
    start_date: date
    end_date: date

    @property
    def days(self) -> int:
        """Number of days in the range."""
        return (self.end_date - self.start_date).days + 1

    def contains(self, check_date: date) -> bool:
        """Check if date is within range."""
        return self.start_date <= check_date <= self.end_date


@dataclass
class ReportRecipient:
    """Recipient for report delivery."""
    email: str
    name: Optional[str] = None
    include_summary: bool = True  # Include summary in email body


@dataclass
class ReportDeliveryConfig:
    """Configuration for report delivery."""
    method: DeliveryMethod = DeliveryMethod.DOWNLOAD
    recipients: List[ReportRecipient] = field(default_factory=list)
    webhook_url: Optional[str] = None
    storage_path: Optional[str] = None

    # Email settings
    email_subject_template: Optional[str] = None
    include_inline_preview: bool = True


@dataclass
class ReportParameters:
    """Parameters that control report content."""
    # Scope
    site_ids: List[UUID] = field(default_factory=list)  # Empty = all sites
    device_ids: List[UUID] = field(default_factory=list)  # Empty = all devices

    # Time range
    date_range: Optional[ReportDateRange] = None

    # Grouping and aggregation
    group_by: Optional[str] = None  # day, week, month, site, device
    compare_previous_period: bool = False

    # Content options
    include_charts: bool = True
    include_raw_data: bool = False
    include_recommendations: bool = True

    # Filters
    alert_severities: Optional[List[str]] = None
    device_types: Optional[List[str]] = None

    # Custom fields
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Report(Entity):
    """
    A generated or scheduled report.

    Reports provide insights into solar system performance,
    billing, alerts, and other metrics.
    """
    # Ownership
    organization_id: UUID
    created_by: UUID  # User who created/requested the report

    # Report definition
    report_type: ReportType
    name: str
    description: Optional[str] = None

    # Parameters
    parameters: ReportParameters = field(default_factory=ReportParameters)

    # Output
    format: ReportFormat = ReportFormat.PDF

    # Status
    status: ReportStatus = ReportStatus.PENDING

    # Generation tracking
    requested_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Result
    file_path: Optional[str] = None  # Path to generated file
    file_size_bytes: Optional[int] = None
    page_count: Optional[int] = None

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    # Delivery
    delivery_config: ReportDeliveryConfig = field(default_factory=ReportDeliveryConfig)
    delivered_at: Optional[datetime] = None

    # Expiration
    expires_at: Optional[datetime] = None  # When the file will be deleted

    # Schedule reference (if from scheduled report)
    schedule_id: Optional[UUID] = None

    def mark_generating(self) -> None:
        """Mark report as currently generating."""
        self.status = ReportStatus.GENERATING
        self.started_at = datetime.utcnow()

    def mark_completed(self, file_path: str, file_size: int, page_count: Optional[int] = None) -> None:
        """Mark report as successfully completed."""
        self.status = ReportStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.file_path = file_path
        self.file_size_bytes = file_size
        self.page_count = page_count

    def mark_failed(self, error: str) -> None:
        """Mark report as failed."""
        self.status = ReportStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error
        self.retry_count += 1

    def can_retry(self) -> bool:
        """Check if report can be retried."""
        return self.status == ReportStatus.FAILED and self.retry_count < self.max_retries

    @property
    def generation_duration_seconds(self) -> Optional[float]:
        """Time taken to generate the report."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_expired(self) -> bool:
        """Check if report file has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass(kw_only=True)
class ReportSchedule(Entity):
    """
    Schedule for automatic report generation.

    Allows users to set up recurring reports that are
    automatically generated and delivered.
    """
    # Ownership
    organization_id: UUID
    created_by: UUID

    # Schedule definition
    name: str
    description: Optional[str] = None

    # Report template
    report_type: ReportType
    parameters: ReportParameters = field(default_factory=ReportParameters)
    format: ReportFormat = ReportFormat.PDF

    # Scheduling
    frequency: ReportFrequency = ReportFrequency.MONTHLY

    # Time settings
    # For daily: time of day to run
    # For weekly: day of week (0=Monday) and time
    # For monthly: day of month and time
    run_time: time = field(default_factory=lambda: time(6, 0))  # 6:00 AM default
    day_of_week: Optional[int] = None  # 0=Monday, 6=Sunday
    day_of_month: Optional[int] = None  # 1-28 (avoid 29-31 for consistency)

    # Timezone
    timezone: str = "Asia/Karachi"

    # Active period
    is_active: bool = True
    start_date: Optional[date] = None  # When to start generating
    end_date: Optional[date] = None    # When to stop (None = indefinite)

    # Delivery
    delivery_config: ReportDeliveryConfig = field(default_factory=ReportDeliveryConfig)

    # Tracking
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_report_id: Optional[UUID] = None

    # Statistics
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0

    def activate(self) -> None:
        """Activate the schedule."""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate the schedule."""
        self.is_active = False

    def record_run(self, report_id: UUID, success: bool) -> None:
        """Record a scheduled run."""
        self.last_run_at = datetime.utcnow()
        self.last_report_id = report_id
        self.total_runs += 1
        if success:
            self.successful_runs += 1
        else:
            self.failed_runs += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_runs == 0:
            return 100.0
        return (self.successful_runs / self.total_runs) * 100

    def should_run(self, check_time: Optional[datetime] = None) -> bool:
        """Check if schedule should run now."""
        if not self.is_active:
            return False

        check_time = check_time or datetime.utcnow()
        current_date = check_time.date()

        # Check date bounds
        if self.start_date and current_date < self.start_date:
            return False
        if self.end_date and current_date > self.end_date:
            return False

        # Check if next_run_at has passed
        if self.next_run_at and check_time >= self.next_run_at:
            return True

        return False


@dataclass(kw_only=True)
class ReportTemplate(Entity):
    """
    Custom report template for organizations.

    Allows organizations to define their own report formats
    with custom branding and sections.
    """
    # Ownership
    organization_id: UUID
    created_by: UUID

    # Template info
    name: str
    description: Optional[str] = None
    report_type: ReportType

    # Branding
    logo_url: Optional[str] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    color_scheme: Dict[str, str] = field(default_factory=dict)  # primary, secondary, accent

    # Content sections (JSON)
    # Structure: [
    #   {"type": "summary", "title": "Executive Summary", "enabled": true},
    #   {"type": "chart", "chart_type": "line", "metric": "energy_generated", "enabled": true},
    #   {"type": "table", "columns": ["date", "energy", "savings"], "enabled": true},
    #   {"type": "text", "content": "Custom text block", "enabled": true}
    # ]
    sections: List[Dict[str, Any]] = field(default_factory=list)

    # Default parameters
    default_parameters: ReportParameters = field(default_factory=ReportParameters)

    # Status
    is_active: bool = True
    is_default: bool = False  # Default template for this report type

    # Usage tracking
    usage_count: int = 0
    last_used_at: Optional[datetime] = None

    def increment_usage(self) -> None:
        """Track template usage."""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()
