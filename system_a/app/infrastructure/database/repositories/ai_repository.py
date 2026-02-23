"""
SQLAlchemy repositories for the AI Intelligence layer.

  SQLAlchemyGridOutageRepository       – CRUD + pattern query for grid_outages
  SQLAlchemyAIInsightsLogRepository    – write + history queries for ai_insights_log
  SQLAlchemyAIPromptTemplateRepository – CRUD + version management for prompt templates
"""
import logging
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import desc, func, select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities.ai_entities import (
    AIInsightsLog,
    AIPromptTemplate,
    AIPromptTemplateVersion,
    GridOutage,
    OutagePrediction,
)
from ..models.ai_models import (
    AIInsightsLogModel,
    AIPromptTemplateModel,
    AIPromptTemplateVersionModel,
    GridOutageModel,
)

logger = logging.getLogger(__name__)

# Pakistan Standard Time (UTC+5, no DST)
_PKT = timezone(timedelta(hours=5))


# ---------------------------------------------------------------------------
# GridOutageRepository
# ---------------------------------------------------------------------------

class SQLAlchemyGridOutageRepository:
    """
    Manages grid outage records.

    Key responsibilities:
    - Create a new outage when grid goes down
    - Close an outage (fill ended_at, duration) when grid comes back
    - Return the open outage for a site (if any)
    - Return pattern data for prediction queries
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_outage(self, site_id: UUID) -> Optional[GridOutage]:
        """Return the currently-open outage for a site, or None."""
        result = await self._session.execute(
            select(GridOutageModel)
            .where(
                and_(
                    GridOutageModel.site_id == site_id,
                    GridOutageModel.ended_at.is_(None),
                )
            )
            .order_by(desc(GridOutageModel.started_at))
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def add(self, outage: GridOutage) -> GridOutage:
        """Insert a new outage record."""
        model = GridOutageModel.from_domain(outage)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def close_outage(self, outage: GridOutage) -> GridOutage:
        """Update an existing outage with its end time and duration."""
        result = await self._session.execute(
            select(GridOutageModel).where(GridOutageModel.id == outage.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(outage)
            await self._session.flush()
            return model.to_domain()
        return outage

    async def get_recent(
        self,
        site_id: UUID,
        days: int = 60,
    ) -> List[GridOutage]:
        """Return outage records for the last N days (completed outages only)."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self._session.execute(
            select(GridOutageModel)
            .where(
                and_(
                    GridOutageModel.site_id == site_id,
                    GridOutageModel.started_at >= since,
                    GridOutageModel.ended_at.isnot(None),
                )
            )
            .order_by(desc(GridOutageModel.started_at))
        )
        return [m.to_domain() for m in result.scalars().all()]

    async def get_pattern_by_hour_slot(
        self,
        site_id: UUID,
        day_of_week: int,
        days: int = 60,
        slot_hours: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Return 2-hour slot occurrence rates for a given day-of-week.

        Used by OutagePredictionService to compute confidence-scored windows.

        Returns rows: {slot_start, total_days_sampled, hit_count, rate}
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Count how many times the target day_of_week appeared in the history window
        day_count_result = await self._session.execute(
            text("""
                SELECT COUNT(DISTINCT date_trunc('day', started_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Karachi'))
                FROM grid_outages
                WHERE site_id = :site_id
                  AND started_at >= :since
                  AND day_of_week = :dow
            """),
            {"site_id": str(site_id), "since": since, "dow": day_of_week},
        )
        day_count = day_count_result.scalar() or 0
        if day_count == 0:
            return []

        # Count outages per 2-hour slot
        rows = await self._session.execute(
            text("""
                SELECT
                    (started_hour_pkt / :slot_h) * :slot_h      AS slot_start,
                    COUNT(*)                                     AS hit_count
                FROM grid_outages
                WHERE site_id      = :site_id
                  AND started_at   >= :since
                  AND day_of_week  = :dow
                  AND ended_at IS NOT NULL
                GROUP BY slot_start
                ORDER BY slot_start
            """),
            {
                "site_id": str(site_id),
                "since": since,
                "dow": day_of_week,
                "slot_h": slot_hours,
            },
        )
        return [
            {
                "slot_start": row.slot_start,
                "slot_end": row.slot_start + slot_hours,
                "hit_count": row.hit_count,
                "day_count": day_count,
                "rate": row.hit_count / day_count if day_count > 0 else 0.0,
            }
            for row in rows.fetchall()
        ]

    async def get_month_stats(
        self,
        site_id: UUID,
        billing_month_start: date,
        billing_month_end: date,
    ) -> Dict[str, Any]:
        """
        Aggregate outage statistics for a billing month.

        Returns total outage hours, event count, worst day.
        Battery coverage is computed by the caller (needs SoC data).
        """
        since = datetime.combine(billing_month_start,
                                 datetime.min.time()).replace(tzinfo=timezone.utc)
        until = datetime.combine(billing_month_end,
                                 datetime.max.time()).replace(tzinfo=timezone.utc)

        result = await self._session.execute(
            text("""
                SELECT
                    COUNT(*)                                      AS event_count,
                    COALESCE(SUM(duration_minutes), 0) / 60.0    AS total_hours,
                    MAX(duration_minutes)                         AS longest_min
                FROM grid_outages
                WHERE site_id    = :site_id
                  AND started_at >= :since
                  AND started_at <= :until
                  AND ended_at IS NOT NULL
            """),
            {"site_id": str(site_id), "since": since, "until": until},
        )
        row = result.fetchone()
        if not row:
            return {"event_count": 0, "total_hours": 0.0, "longest_min": 0}

        # Worst day
        worst_result = await self._session.execute(
            text("""
                SELECT
                    date_trunc('day', started_at AT TIME ZONE 'Asia/Karachi') AS day,
                    SUM(duration_minutes) / 60.0 AS day_hours
                FROM grid_outages
                WHERE site_id    = :site_id
                  AND started_at >= :since
                  AND started_at <= :until
                  AND ended_at IS NOT NULL
                GROUP BY day
                ORDER BY day_hours DESC
                LIMIT 1
            """),
            {"site_id": str(site_id), "since": since, "until": until},
        )
        worst = worst_result.fetchone()

        return {
            "event_count": row.event_count or 0,
            "total_hours": float(row.total_hours or 0),
            "longest_min": int(row.longest_min or 0),
            "worst_day": worst.day.date() if worst else None,
            "worst_day_hours": float(worst.day_hours) if worst else 0.0,
        }

    async def get_last_outage(self, site_id: UUID) -> Optional[GridOutage]:
        """Return the most recent completed outage."""
        result = await self._session.execute(
            select(GridOutageModel)
            .where(
                and_(
                    GridOutageModel.site_id == site_id,
                    GridOutageModel.ended_at.isnot(None),
                )
            )
            .order_by(desc(GridOutageModel.started_at))
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None


# ---------------------------------------------------------------------------
# AIInsightsLogRepository
# ---------------------------------------------------------------------------

class SQLAlchemyAIInsightsLogRepository:
    """
    Write-heavy repository for ai_insights_log.

    Supports:
    - Saving a new insight result after each Claude call
    - Fetching recent anomaly alerts for use as context in monthly/yearly prompts
    - Fetching monthly summaries for yearly context
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, log: AIInsightsLog) -> AIInsightsLog:
        """Persist a new insight generation result."""
        model = AIInsightsLogModel.from_domain(log)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def get_recent_anomalies(
        self,
        site_id: UUID,
        days: int = 30,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Return anomaly_alerts from the last N days of hourly logs.

        Used by the monthly prompt to add "recurring anomalies from AI log" context.
        Returns a flat list of alert dicts with 'generated_at' added.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self._session.execute(
            select(AIInsightsLogModel)
            .where(
                and_(
                    AIInsightsLogModel.site_id == site_id,
                    AIInsightsLogModel.tier == "hourly",
                    AIInsightsLogModel.generated_at >= since,
                )
            )
            .order_by(desc(AIInsightsLogModel.generated_at))
            .limit(limit)
        )
        alerts: List[Dict[str, Any]] = []
        for model in result.scalars().all():
            for alert in (model.anomaly_alerts or []):
                alerts.append({
                    **alert,
                    "generated_at": model.generated_at.isoformat()
                    if model.generated_at else None,
                })
        return alerts

    async def get_monthly_summaries(
        self,
        site_id: UUID,
        limit: int = 12,
    ) -> List[Dict[str, Any]]:
        """
        Return the most recent monthly analysis summaries.

        Used by the yearly prompt as context ("here is what each month looked like").
        Returns list of monthly_analysis dicts with billing_month added.
        """
        result = await self._session.execute(
            select(AIInsightsLogModel)
            .where(
                and_(
                    AIInsightsLogModel.site_id == site_id,
                    AIInsightsLogModel.tier == "monthly",
                    AIInsightsLogModel.monthly_analysis.isnot(None),
                )
            )
            .order_by(desc(AIInsightsLogModel.generated_at))
            .limit(limit)
        )
        summaries = []
        for model in result.scalars().all():
            if model.monthly_analysis:
                summaries.append({
                    "billing_month": model.billing_month.isoformat()
                    if model.billing_month else None,
                    **model.monthly_analysis,
                })
        return summaries

    async def get_recurring_anomalies(
        self,
        site_id: UUID,
        days: int = 365,
        min_occurrences: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Return anomaly types that appeared >= min_occurrences times in the last N days.

        Used by the yearly prompt to highlight chronic issues.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Use raw SQL for the JSONB array expansion
        result = await self._session.execute(
            text("""
                SELECT
                    alert->>'title'    AS title,
                    alert->>'category' AS category,
                    COUNT(*)           AS occurrences
                FROM ai_insights_log,
                     jsonb_array_elements(anomaly_alerts) AS alert
                WHERE site_id    = :site_id
                  AND tier       = 'hourly'
                  AND generated_at >= :since
                GROUP BY title, category
                HAVING COUNT(*) >= :min_occ
                ORDER BY occurrences DESC
            """),
            {"site_id": str(site_id), "since": since, "min_occ": min_occurrences},
        )
        return [
            {"title": r.title, "category": r.category, "occurrences": r.occurrences}
            for r in result.fetchall()
        ]

    async def get_latest_by_tier(
        self,
        site_id: UUID,
        tier: str,
    ) -> Optional[AIInsightsLog]:
        """Return the most recently generated log row for a site + tier."""
        result = await self._session.execute(
            select(AIInsightsLogModel)
            .where(
                and_(
                    AIInsightsLogModel.site_id == site_id,
                    AIInsightsLogModel.tier == tier,
                )
            )
            .order_by(desc(AIInsightsLogModel.generated_at))
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_for_site(
        self,
        site_id: UUID,
        tier: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AIInsightsLog]:
        """Paginated list of log entries for a site (for admin browsing)."""
        q = select(AIInsightsLogModel).where(AIInsightsLogModel.site_id == site_id)
        if tier:
            q = q.where(AIInsightsLogModel.tier == tier)
        q = q.order_by(desc(AIInsightsLogModel.generated_at)).limit(limit).offset(offset)
        result = await self._session.execute(q)
        return [m.to_domain() for m in result.scalars().all()]


# ---------------------------------------------------------------------------
# AIPromptTemplateRepository
# ---------------------------------------------------------------------------

class SQLAlchemyAIPromptTemplateRepository:
    """
    CRUD + version management for ai_prompt_templates.

    The service calls get_active_by_key() to load a template at runtime.
    Admin endpoints call update() + add_version() to save edits.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_by_key(self, key: str) -> Optional[AIPromptTemplate]:
        """Load the active template for a given key. Returns None if not found."""
        result = await self._session.execute(
            select(AIPromptTemplateModel)
            .where(
                and_(
                    AIPromptTemplateModel.key == key,
                    AIPromptTemplateModel.is_active == True,
                )
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_id(self, id: UUID) -> Optional[AIPromptTemplate]:
        result = await self._session.execute(
            select(AIPromptTemplateModel).where(AIPromptTemplateModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def list_all(self) -> List[AIPromptTemplate]:
        """Return all templates ordered by tier then prompt_type."""
        result = await self._session.execute(
            select(AIPromptTemplateModel)
            .order_by(AIPromptTemplateModel.tier, AIPromptTemplateModel.prompt_type)
        )
        return [m.to_domain() for m in result.scalars().all()]

    async def update(self, template: AIPromptTemplate) -> AIPromptTemplate:
        """Update an existing template (increments version, updates updated_at)."""
        result = await self._session.execute(
            select(AIPromptTemplateModel)
            .where(AIPromptTemplateModel.id == template.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Prompt template {template.id} not found")
        model.update_from_domain(template)
        await self._session.flush()
        return model.to_domain()

    async def add_version(self, version: AIPromptTemplateVersion) -> AIPromptTemplateVersion:
        """Write one version snapshot (called alongside every update())."""
        model = AIPromptTemplateVersionModel.from_domain(version)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def get_versions(
        self,
        template_id: UUID,
        limit: int = 20,
    ) -> List[AIPromptTemplateVersion]:
        """Return version history for a template, newest first."""
        result = await self._session.execute(
            select(AIPromptTemplateVersionModel)
            .where(AIPromptTemplateVersionModel.template_id == template_id)
            .order_by(desc(AIPromptTemplateVersionModel.version))
            .limit(limit)
        )
        return [m.to_domain() for m in result.scalars().all()]

    async def get_version(
        self,
        template_id: UUID,
        version: int,
    ) -> Optional[AIPromptTemplateVersion]:
        """Return a specific version snapshot."""
        result = await self._session.execute(
            select(AIPromptTemplateVersionModel)
            .where(
                and_(
                    AIPromptTemplateVersionModel.template_id == template_id,
                    AIPromptTemplateVersionModel.version == version,
                )
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None
