"""
API Version 1 - Route definitions.
"""
from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .organizations import router as organizations_router
from .sites import router as sites_router
from .devices import router as devices_router
from .dashboards import router as dashboards_router
from .alerts import router as alerts_router
from .billing import router as billing_router
from .protocol_definitions import router as protocol_definitions_router
from .discovery import router as discovery_router

# Create main v1 router
api_router = APIRouter(prefix="/v1")

# Include all sub-routers
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(organizations_router)
api_router.include_router(sites_router)
api_router.include_router(devices_router)
api_router.include_router(dashboards_router)
api_router.include_router(alerts_router)
api_router.include_router(billing_router)
api_router.include_router(protocol_definitions_router)
api_router.include_router(discovery_router)

__all__ = ['api_router']
