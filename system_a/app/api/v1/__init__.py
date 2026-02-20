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
from .scheduler_admin import router as scheduler_admin_router
# Admin portal routers
from .admin_auth import router as admin_auth_router
from .admin_providers import router as admin_providers_router
from .admin_tariffs import router as admin_tariffs_router
from .admin_load_shedding import router as admin_load_shedding_router
from .admin_audit_log import router as admin_audit_log_router
from .admin_users import router as admin_users_router
# AI Insights
from .ai_insights import router as ai_insights_router
# Public endpoints served to authenticated end-users
from .public_providers import router as public_providers_router
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
api_router.include_router(scheduler_admin_router)
# Admin portal
api_router.include_router(admin_auth_router)
api_router.include_router(admin_providers_router)
api_router.include_router(admin_tariffs_router)
api_router.include_router(admin_load_shedding_router)
api_router.include_router(admin_audit_log_router)
api_router.include_router(admin_users_router)
# AI Insights
api_router.include_router(ai_insights_router)
# Public endpoints for end-users
api_router.include_router(public_providers_router)
# api_router.include_router(performance_metrics_router)
# api_router.include_router(telemetry_sync_router)

__all__ = ['api_router']
