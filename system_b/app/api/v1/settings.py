"""
Settings Schema API endpoints for System B.

Exposes the per-protocol settings schema so that System A and the frontend
can determine which controls to render for each inverter family without
hard-coding them.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from ....device_server.settings_schema import get_schema, SCHEMAS_BY_PROTOCOL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["Settings Schema"])


@router.get(
    "/schema/{protocol}",
    summary="Get settings schema for a protocol",
    description=(
        "Returns the complete settings metadata for an inverter protocol family "
        "(powdrive, senergy, voltronic_pi30, etc.). "
        "The schema describes each writable field: label, type, unit, min/max, "
        "allowed enum values, scale factor, and whether the field is destructive."
    ),
)
async def get_settings_schema(protocol: str) -> Dict[str, Any]:
    """Return settings schema for a given protocol."""
    schema = get_schema(protocol)
    if schema is None:
        known = sorted(SCHEMAS_BY_PROTOCOL.keys())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown protocol '{protocol}'. Known protocols: {known}",
        )
    return schema


@router.get(
    "/schema",
    summary="List all available protocol schemas",
    description="Returns protocol IDs for all supported families.",
)
async def list_settings_schemas() -> Dict[str, Any]:
    """List all available protocol schema IDs."""
    return {
        "protocols": sorted(SCHEMAS_BY_PROTOCOL.keys()),
    }
