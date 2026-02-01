"""
API Version 1 - Route definitions.
"""
from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .organizations import router as organizations_router
from .sites import router as sites_router
from .devices import router as devices_router
from .device_settings import router as device_settings_router
from .device_commands import router as device_commands_router
from .dashboards import router as dashboards_router
from .dashboard_widgets import router as dashboard_widgets_router
from .dashboard_preferences import router as dashboard_preferences_router
from .alerts import router as alerts_router
from .billing import router as billing_router
from .billing_daily import router as billing_daily_router
from .protocol_definitions import router as protocol_definitions_router
from .discovery import router as discovery_router
# Deprecated: telemetry_sync and performance_metrics moved to System B
# from .performance_metrics import router as performance_metrics_router
# from .telemetry_sync import router as telemetry_sync_router

# Create main v1 router
api_router = APIRouter(prefix="/v1")

# Include all sub-routers
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(organizations_router)
api_router.include_router(sites_router)
api_router.include_router(devices_router)
api_router.include_router(device_settings_router)
api_router.include_router(device_commands_router)
api_router.include_router(dashboards_router)
api_router.include_router(dashboard_widgets_router)
api_router.include_router(dashboard_preferences_router)
api_router.include_router(alerts_router)
api_router.include_router(billing_router)
api_router.include_router(billing_daily_router)
api_router.include_router(protocol_definitions_router)
api_router.include_router(discovery_router)
# api_router.include_router(performance_metrics_router)
# api_router.include_router(telemetry_sync_router)

__all__ = ['api_router']
