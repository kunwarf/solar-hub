"""
AI Chat endpoint.

POST /api/v1/chat — answers a free-form user question about their solar site.
Uses AIChatService (Claude when API key is set, rule-based fallback otherwise).
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..dependencies import get_current_user, get_unit_of_work, get_system_b_client_instance
from ...application.interfaces.unit_of_work import UnitOfWork
from ...application.services.ai_chat_service import AIChatService
from ...domain.entities.user import User
from ...infrastructure.cache.telemetry_cache import telemetry_cache
from ...infrastructure.external.system_b_client import SystemBClient
from .dashboard_widgets import get_site_with_devices

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="User question")
    site_id: Optional[UUID] = Field(None, description="Site ID (uses default if not provided)")
    import_rate_pkr: float = Field(35.0, description="PKR per kWh import rate for savings calculation")


class ChatResponse(BaseModel):
    reply: str


@router.post(
    "",
    response_model=ChatResponse,
    summary="Ask a question about your solar site",
    description=(
        "Send a free-form question and receive a contextual answer based on real "
        "telemetry data. Claude (claude-haiku) is used when AI_API_KEY is configured; "
        "a deterministic rule-based engine is used otherwise."
    ),
)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    system_b_client: SystemBClient = Depends(get_system_b_client_instance),
) -> ChatResponse:
    site_info = await get_site_with_devices(current_user, uow, request.site_id)

    service = AIChatService(
        telemetry_cache=telemetry_cache,
        system_b_client=system_b_client,
    )

    reply = await service.chat(
        message=request.message,
        site_id=site_info.site_id,
        device_serials=site_info.device_serials,
        site_name=site_info.site_name,
        import_rate_pkr=request.import_rate_pkr,
    )

    logger.info(
        "[chat] site=%s user=%s message=%r",
        site_info.site_id, current_user.id, request.message[:80],
    )

    return ChatResponse(reply=reply)
