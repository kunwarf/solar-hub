"""
SQLAlchemy ORM models for the AI Intelligence layer.

Tables:
  grid_outages                  – per-site detected grid outage events
  ai_insights_log               – persisted Claude / rule-based insight results
  ai_prompt_templates           – admin-editable prompt templates
  ai_prompt_template_versions   – immutable version history of prompt edits
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    SmallInteger, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship

from .base import BaseModel, Base


# ---------------------------------------------------------------------------
# grid_outages
# ---------------------------------------------------------------------------

class GridOutageModel(Base):
    """
    One row per detected grid outage event for a site.

    Rows are written by OutageDetectionService (background job) and read by
    OutagePredictionService to compute today's likely load-shedding windows.

    The PKT convenience columns (day_of_week, started_hour_pkt, …) are
    pre-computed at insert time so the pattern-analysis SQL stays simple.
    """

    __tablename__ = "grid_outages"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)

    # FK
    site_id = Column(PGUUID(as_uuid=True),
                     ForeignKey("sites.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    # Timing (UTC)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at   = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)   # filled when outage ends

    # PKT convenience columns (UTC+5, no DST)
    day_of_week      = Column(SmallInteger, nullable=False)   # 0=Mon … 6=Sun
    week_of_year     = Column(SmallInteger, nullable=False)
    month_pkt        = Column(SmallInteger, nullable=False)   # 1–12
    started_hour_pkt = Column(SmallInteger, nullable=False)   # 0–23
    ended_hour_pkt   = Column(SmallInteger, nullable=True)

    # Source / quality
    detected_by_serial = Column(String(100), nullable=True)
    was_predicted      = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=datetime.utcnow)

    def to_domain(self) -> "GridOutage":
        from ....domain.entities.ai_entities import GridOutage
        return GridOutage(
            id=self.id,
            site_id=self.site_id,
            started_at=self.started_at,
            ended_at=self.ended_at,
            duration_minutes=self.duration_minutes,
            day_of_week=self.day_of_week,
            week_of_year=self.week_of_year,
            month_pkt=self.month_pkt,
            started_hour_pkt=self.started_hour_pkt,
            ended_hour_pkt=self.ended_hour_pkt,
            detected_by_serial=self.detected_by_serial,
            was_predicted=self.was_predicted,
            created_at=self.created_at,
        )

    @classmethod
    def from_domain(cls, outage: "GridOutage") -> "GridOutageModel":
        from ....domain.entities.ai_entities import GridOutage
        return cls(
            id=outage.id,
            site_id=outage.site_id,
            started_at=outage.started_at,
            ended_at=outage.ended_at,
            duration_minutes=outage.duration_minutes,
            day_of_week=outage.day_of_week,
            week_of_year=outage.week_of_year,
            month_pkt=outage.month_pkt,
            started_hour_pkt=outage.started_hour_pkt,
            ended_hour_pkt=outage.ended_hour_pkt,
            detected_by_serial=outage.detected_by_serial,
            was_predicted=outage.was_predicted,
        )

    def update_from_domain(self, outage: "GridOutage") -> None:
        """Apply end-of-outage updates."""
        self.ended_at = outage.ended_at
        self.ended_hour_pkt = outage.ended_hour_pkt
        self.duration_minutes = outage.duration_minutes


# ---------------------------------------------------------------------------
# ai_insights_log
# ---------------------------------------------------------------------------

class AIInsightsLogModel(Base):
    """
    Persisted result of every Claude (or rule-based) insight generation.

    One row per site × tier × generation. The input_stats column stores the
    exact data sent to Claude so results can be debugged or reproduced.
    Monthly and yearly analyses pull prior rows from this table to use as
    contextual history in their prompts.
    """

    __tablename__ = "ai_insights_log"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)

    # FK
    site_id = Column(PGUUID(as_uuid=True),
                     ForeignKey("sites.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    # Classification
    tier  = Column(String(20),  nullable=False)   # hourly|monthly|yearly
    model = Column(String(100), nullable=False)   # model id or 'rule-based'

    # Time period covered
    period_start  = Column(DateTime(timezone=True), nullable=False)
    period_end    = Column(DateTime(timezone=True), nullable=True)
    billing_month = Column(Date, nullable=True)   # monthly/yearly only

    # Claude output (parsed)
    daily_insights   = Column(JSONB, nullable=False, default=list)
    anomaly_alerts   = Column(JSONB, nullable=False, default=list)
    monthly_analysis = Column(JSONB, nullable=True)   # monthly tier only
    yearly_analysis  = Column(JSONB, nullable=True)   # yearly  tier only

    # Raw input snapshot sent to Claude
    input_stats = Column(JSONB, nullable=False)

    # Redis cache key for this result
    cache_key = Column(String(200), nullable=True)

    generated_at = Column(DateTime(timezone=True), nullable=False,
                          default=datetime.utcnow)
    created_at   = Column(DateTime(timezone=True), nullable=False,
                          default=datetime.utcnow)

    def to_domain(self) -> "AIInsightsLog":
        from ....domain.entities.ai_entities import AIInsightsLog
        return AIInsightsLog(
            id=self.id,
            site_id=self.site_id,
            tier=self.tier,
            model=self.model,
            period_start=self.period_start,
            period_end=self.period_end,
            billing_month=self.billing_month,
            daily_insights=self.daily_insights or [],
            anomaly_alerts=self.anomaly_alerts or [],
            monthly_analysis=self.monthly_analysis,
            yearly_analysis=self.yearly_analysis,
            input_stats=self.input_stats or {},
            cache_key=self.cache_key,
            generated_at=self.generated_at,
            created_at=self.created_at,
        )

    @classmethod
    def from_domain(cls, log: "AIInsightsLog") -> "AIInsightsLogModel":
        from ....domain.entities.ai_entities import AIInsightsLog
        return cls(
            id=log.id,
            site_id=log.site_id,
            tier=log.tier,
            model=log.model,
            period_start=log.period_start,
            period_end=log.period_end,
            billing_month=log.billing_month,
            daily_insights=log.daily_insights,
            anomaly_alerts=log.anomaly_alerts,
            monthly_analysis=log.monthly_analysis,
            yearly_analysis=log.yearly_analysis,
            input_stats=log.input_stats,
            cache_key=log.cache_key,
            generated_at=log.generated_at,
        )


# ---------------------------------------------------------------------------
# ai_prompt_templates
# ---------------------------------------------------------------------------

class AIPromptTemplateModel(Base):
    """
    Admin-editable prompt template for a Claude call tier + type.

    The service loads the active template by `key` at runtime (Redis TTL=5min)
    and falls back to hardcoded defaults if the table is unavailable.
    Templates use Python str.format_map() placeholders: {variable_name}.
    """

    __tablename__ = "ai_prompt_templates"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, nullable=False)

    # Unique business key
    key         = Column(String(100), nullable=False, unique=True)

    # Classification
    tier        = Column(String(20), nullable=False)   # hourly|monthly|yearly
    prompt_type = Column(String(20), nullable=False)   # system|user

    # Human-readable
    name        = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Template text with {variable} placeholders
    template  = Column(Text, nullable=False)

    # Variable manifest for admin UI reference panel
    # JSON array: [{"name":…,"type":…,"description":…}]
    variables = Column(JSONB, nullable=False, default=list)

    # Target model (informational only — service uses AI_MODEL env var)
    model      = Column(String(100), nullable=True)
    max_tokens = Column(Integer, nullable=True)

    # Versioning
    version   = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)

    # Audit
    created_by = Column(PGUUID(as_uuid=True),
                        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(PGUUID(as_uuid=True),
                        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    versions = relationship("AIPromptTemplateVersionModel",
                            back_populates="template_obj",
                            cascade="all, delete-orphan",
                            order_by="AIPromptTemplateVersionModel.version.desc()")

    def to_domain(self) -> "AIPromptTemplate":
        from ....domain.entities.ai_entities import AIPromptTemplate
        return AIPromptTemplate(
            id=self.id,
            key=self.key,
            tier=self.tier,
            prompt_type=self.prompt_type,
            name=self.name,
            description=self.description,
            template=self.template,
            variables=self.variables or [],
            model=self.model,
            max_tokens=self.max_tokens,
            version=self.version,
            is_active=self.is_active,
            created_by=self.created_by,
            updated_by=self.updated_by,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_domain(cls, t: "AIPromptTemplate") -> "AIPromptTemplateModel":
        from ....domain.entities.ai_entities import AIPromptTemplate
        return cls(
            id=t.id,
            key=t.key,
            tier=t.tier,
            prompt_type=t.prompt_type,
            name=t.name,
            description=t.description,
            template=t.template,
            variables=t.variables,
            model=t.model,
            max_tokens=t.max_tokens,
            version=t.version,
            is_active=t.is_active,
            created_by=t.created_by,
            updated_by=t.updated_by,
        )

    def update_from_domain(self, t: "AIPromptTemplate") -> None:
        self.name        = t.name
        self.description = t.description
        self.template    = t.template
        self.variables   = t.variables
        self.model       = t.model
        self.max_tokens  = t.max_tokens
        self.version     = t.version
        self.is_active   = t.is_active
        self.updated_by  = t.updated_by
        self.updated_at  = datetime.utcnow()


# ---------------------------------------------------------------------------
# ai_prompt_template_versions
# ---------------------------------------------------------------------------

class AIPromptTemplateVersionModel(Base):
    """
    Immutable audit trail of every admin edit to a prompt template.

    One row is written per save, capturing the template text, variables,
    who made the change, and an optional change note.
    """

    __tablename__ = "ai_prompt_template_versions"

    id          = Column(PGUUID(as_uuid=True), primary_key=True,
                         default=uuid4, nullable=False)
    template_id = Column(PGUUID(as_uuid=True),
                         ForeignKey("ai_prompt_templates.id", ondelete="CASCADE"),
                         nullable=False, index=True)

    # Snapshot of the template at this version
    version   = Column(Integer, nullable=False)
    template  = Column(Text, nullable=False)
    variables = Column(JSONB, nullable=False)

    # Who changed it and why
    changed_by  = Column(PGUUID(as_uuid=True),
                         ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_note = Column(Text, nullable=True)
    changed_at  = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationship back to parent
    template_obj = relationship("AIPromptTemplateModel", back_populates="versions")

    def to_domain(self) -> "AIPromptTemplateVersion":
        from ....domain.entities.ai_entities import AIPromptTemplateVersion
        return AIPromptTemplateVersion(
            id=self.id,
            template_id=self.template_id,
            version=self.version,
            template=self.template,
            variables=self.variables or [],
            changed_by=self.changed_by,
            change_note=self.change_note,
            changed_at=self.changed_at,
        )

    @classmethod
    def from_domain(cls, v: "AIPromptTemplateVersion") -> "AIPromptTemplateVersionModel":
        from ....domain.entities.ai_entities import AIPromptTemplateVersion
        return cls(
            id=v.id,
            template_id=v.template_id,
            version=v.version,
            template=v.template,
            variables=v.variables,
            changed_by=v.changed_by,
            change_note=v.change_note,
            changed_at=v.changed_at,
        )
