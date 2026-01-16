"""
API Version 1 routes for System B.

Includes telemetry ingestion, device management, commands, and events.
"""
from fastapi import APIRouter

from .telemetry import router as telemetry_router
from .devices import router as devices_router
from .commands import router as commands_router
from .events import router as events_router

# Main API router that includes all sub-routers
api_router = APIRouter(prefix="/api/v1")

api_router.include_router(telemetry_router)
api_router.include_router(devices_router)
api_router.include_router(commands_router)
api_router.include_router(events_router)

__all__ = [
    "api_router",
    "telemetry_router",
    "devices_router",
    "commands_router",
    "events_router",
]
