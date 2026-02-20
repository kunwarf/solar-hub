"""
AI Insights API endpoints.

Provides GET /insights to fetch rule-based insights derived from real telemetry.
Provides POST /insights/{id}/feedback to record user feedback on insights.

Data sources:
- Real-time telemetry: Redis cache (via telemetry_cache singleton)
- Historical data: System B energy chart API (via SystemBClient)
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
from ...infrastructure.external.system_b_client import SystemBClient
from .dashboard_widgets import get_site_with_devices

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["AI Insights"])


# ============================================================================
# Response Schemas
# ============================================================================

class InsightSchema(BaseModel):
    """Single insight item."""
    id: str
    type: str
    category: str
    title: str
    message: str
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class WeeklyDigestSchema(BaseModel):
    """Weekly energy summary digest."""
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


class InsightsResponse(BaseModel):
    """Full insights response for a site."""
    site_id: UUID
    site_name: str
    daily_insights: List[InsightSchema]
    anomaly_alerts: List[InsightSchema]
    weekly_digest: Optional[WeeklyDigestSchema] = None
    generated_at: datetime


class FeedbackRequest(BaseModel):
    """Insight feedback payload."""
    insight_id: str
    positive: bool


class FeedbackResponse(BaseModel):
    """Feedback acknowledgement."""
    message: str
    insight_id: str


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    response_model=InsightsResponse,
    summary="Get AI insights",
    description=(
        "Returns rule-based insights generated from real telemetry data. "
        "Includes daily production summary, savings, anomaly alerts, and weekly digest. "
        "Refresh: 5 minutes."
    ),
)
async def get_insights(
    site_id: Optional[UUID] = Query(None, description="Site ID (uses default if not provided)"),
    import_rate_pkr: float = Query(35.0, description="PKR per kWh import rate for savings calculation"),
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
):
    """
    Generate AI insights for the site.

    Uses real telemetry from Redis + historical data from System B.
    Falls back gracefully if System B is unavailable.
    """
    site_info = await get_site_with_devices(current_user, uow, site_id)

    service = AIInsightsService(
        telemetry_cache=telemetry_cache,
        system_b_client=system_b_client,
    )

    result = await service.get_insights(
        site_id=site_info.site_id,
        device_serials=site_info.device_serials,
        import_rate_pkr=import_rate_pkr,
    )

    return InsightsResponse(
        site_id=site_info.site_id,
        site_name=site_info.site_name,
        daily_insights=[
            InsightSchema(
                id=i.id,
                type=i.type,
                category=i.category,
                title=i.title,
                message=i.message,
                timestamp=i.timestamp,
                metadata=i.metadata,
            )
            for i in result.daily_insights
        ],
        anomaly_alerts=[
            InsightSchema(
                id=i.id,
                type=i.type,
                category=i.category,
                title=i.title,
                message=i.message,
                timestamp=i.timestamp,
                metadata=i.metadata,
            )
            for i in result.anomaly_alerts
        ],
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
        generated_at=result.generated_at,
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
    """
    Record user feedback on an insight.

    Feedback is logged for future AI training / quality improvement.
    """
    logger.info(
        "Insight feedback: user=%s insight=%s positive=%s",
        current_user.id,
        insight_id,
        feedback.positive,
    )
    return FeedbackResponse(
        message="Feedback recorded. Thank you!",
        insight_id=insight_id,
    )
