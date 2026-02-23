"""
AI Insights API endpoints.

GET  /insights           — three-tier insights (hourly cached 1h, monthly cached 24h, yearly cached 30d)
POST /insights/{id}/feedback — record thumbs-up/down feedback

Data sources:
- Real-time telemetry: Redis cache (via telemetry_cache singleton)
- Historical data: System B energy chart API (via SystemBClient)
- Load shedding: grid_outages table + OutagePredictionService
- Prompt templates: ai_prompt_templates table (Redis-cached 5min)
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..dependencies import get_current_user, get_unit_of_work, get_system_b_client_instance
from ...application.interfaces.unit_of_work import UnitOfWork
from ...application.services.ai_insights_service import AIInsightsService
from ...domain.entities.user import User
from ...infrastructure.cache.telemetry_cache import telemetry_cache
from ...infrastructure.database.connection import DatabaseManager
from ...infrastructure.external.system_b_client import SystemBClient
from .dashboard_widgets import get_site_with_devices

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["AI Insights"])


# ============================================================================
# Response Schemas
# ============================================================================

class InsightSchema(BaseModel):
    id: str
    type: str
    category: str
    title: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class WeeklyDigestSchema(BaseModel):
    total_generated_kwh: float
    total_saved_pkr: float
    self_sufficiency_pct: float
    prev_week_generated_kwh: float
    prev_week_saved_pkr: float
    prev_week_self_sufficiency_pct: float
    generated_change_pct: float
    saved_change_pct: float
    self_sufficiency_change_pct: float
    tip_of_the_week: str


class MonthlyAnalysisSchema(BaseModel):
    summary: str = ""
    highlights: List[str] = []
    recommendations: List[str] = []
    load_shedding_insight: str = ""


class YearlyAnalysisSchema(BaseModel):
    summary: str = ""
    best_month: str = ""
    worst_month: str = ""
    trends: List[str] = []
    recommendations: List[str] = []
    roi_insight: str = ""


class InsightsResponse(BaseModel):
    site_id: UUID
    site_name: str
    daily_insights: List[InsightSchema]
    anomaly_alerts: List[InsightSchema]
    weekly_digest: Optional[WeeklyDigestSchema] = None
    monthly_analysis: Optional[MonthlyAnalysisSchema] = None
    yearly_analysis: Optional[YearlyAnalysisSchema] = None
    generated_at: datetime
    source: str = "rule_based"


class FeedbackRequest(BaseModel):
    insight_id: str
    positive: bool


class FeedbackResponse(BaseModel):
    message: str
    insight_id: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    response_model=InsightsResponse,
    summary="Get AI insights (three-tier)",
    description=(
        "Returns AI-generated insights for the site. "
        "Hourly insights cached 1h, monthly analysis cached 24h, yearly analysis cached 30d. "
        "All tiers use Claude when AI_API_KEY is set; rule-based fallback otherwise."
    ),
)
async def get_insights(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    import_rate_pkr: float = Query(35.0, description="PKR per kWh import rate"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """
    Generate AI insights for the site (all three tiers).

    - Hourly tier: live telemetry + LS prediction + system alerts (Haiku, cached 1h)
    - Monthly tier: 30-day energy + billing + outage history (Sonnet, cached 24h)
    - Yearly tier: 365-day energy + YTD summary (Sonnet, cached 30d)
    """
    site_info = await get_site_with_devices(current_user, uow, site_id)

    service = AIInsightsService(
        telemetry_cache=telemetry_cache,
        system_b_client=system_b_client,
        session_factory=DatabaseManager.get_session_factory(),
    )

    result = await service.get_insights(
        site_id=site_info.site_id,
        device_serials=site_info.device_serials,
        import_rate_pkr=import_rate_pkr,
    )

    def _to_schema(i) -> InsightSchema:
        return InsightSchema(
            id=i.id,
            type=i.type,
            category=i.category,
            title=i.title,
            message=i.message,
            timestamp=i.timestamp,
            metadata=i.metadata,
        )

    return InsightsResponse(
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        daily_insights=[_to_schema(i) for i in result.daily_insights],
        anomaly_alerts=[_to_schema(i) for i in result.anomaly_alerts],
        weekly_digest=WeeklyDigestSchema(
            total_generated_kwh=result.weekly_digest.total_generated_kwh,
            total_saved_pkr=result.weekly_digest.total_saved_pkr,
            self_sufficiency_pct=result.weekly_digest.self_sufficiency_pct,
            prev_week_generated_kwh=result.weekly_digest.prev_week_generated_kwh,
            prev_week_saved_pkr=result.weekly_digest.prev_week_saved_pkr,
            prev_week_self_sufficiency_pct=result.weekly_digest.prev_week_self_sufficiency_pct,
            generated_change_pct=result.weekly_digest.generated_change_pct,
            saved_change_pct=result.weekly_digest.saved_change_pct,
            self_sufficiency_change_pct=result.weekly_digest.self_sufficiency_change_pct,
            tip_of_the_week=result.weekly_digest.tip_of_the_week,
        ) if result.weekly_digest else None,
        monthly_analysis=MonthlyAnalysisSchema(**result.monthly_analysis)
            if result.monthly_analysis else None,
        yearly_analysis=YearlyAnalysisSchema(**result.yearly_analysis)
            if result.yearly_analysis else None,
        generated_at=result.generated_at,
        source=result.source,
    )


@router.post(
    "/{insight_id}/feedback",
    response_model=FeedbackResponse,
    summary="Submit insight feedback",
    description="Record thumbs-up or thumbs-down feedback for an insight.",
)
async def submit_feedback(
    insight_id: str,
    feedback: FeedbackRequest,
    current_user: User = Depends(get_current_user),
):
    logger.info(
        "Insight feedback: user=%s insight=%s positive=%s",
        current_user.id, insight_id, feedback.positive,
    )
    return FeedbackResponse(message="Feedback recorded. Thank you!", insight_id=insight_id)
