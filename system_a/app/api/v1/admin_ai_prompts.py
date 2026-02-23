"""
Admin portal — AI Prompt Template management.

CRUD endpoints for the 6 Claude prompt templates (hourly/monthly/yearly × system/user).
Admins can view, edit, and version-control templates without a code deploy.

All writes are versioned: every save creates an immutable row in ai_prompt_template_versions.
The prompt loader's Redis cache (5-minute TTL) is invalidated on every update.

Endpoints:
    GET    /admin/ai-prompts              — list all templates
    GET    /admin/ai-prompts/{key}        — get one template + variable reference
    PUT    /admin/ai-prompts/{key}        — update template text (creates version)
    GET    /admin/ai-prompts/{key}/versions        — list all versions for a key
    GET    /admin/ai-prompts/{key}/versions/{ver}  — get a specific version
    POST   /admin/ai-prompts/{key}/revert/{ver}    — revert to a specific version
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..dependencies import (
    get_unit_of_work,
    require_ops_admin,
)
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.ai_entities import AIPromptTemplateVersion
from ...domain.entities.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ai-prompts", tags=["Admin - AI Prompts"])


# ============================================================================
# Schemas
# ============================================================================

class PromptTemplateResponse(BaseModel):
    id: UUID
    key: str
    tier: str
    prompt_type: str
    template: str
    variables: List[dict]   # list of {name, description, example} dicts
    version: int
    is_active: bool
    updated_at: Optional[datetime] = None


class PromptTemplateListItem(BaseModel):
    id: UUID
    key: str
    tier: str
    prompt_type: str
    version: int
    is_active: bool
    updated_at: Optional[datetime] = None


class PromptTemplateUpdate(BaseModel):
    template: str
    change_note: Optional[str] = None


class PromptTemplateVersionResponse(BaseModel):
    id: UUID
    template_id: UUID
    version: int
    template: str
    changed_at: datetime
    change_note: Optional[str] = None


class PromptTemplateListResponse(BaseModel):
    items: List[PromptTemplateListItem]
    total: int


class PromptTemplateVersionListResponse(BaseModel):
    items: List[PromptTemplateVersionResponse]
    total: int


# ============================================================================
# Helpers
# ============================================================================

def _template_to_response(tmpl) -> PromptTemplateResponse:
    return PromptTemplateResponse(
        id=tmpl.id,
        key=tmpl.key,
        tier=tmpl.tier,
        prompt_type=tmpl.prompt_type,
        template=tmpl.template,
        variables=tmpl.variables or [],
        version=tmpl.version,
        is_active=tmpl.is_active,
        updated_at=tmpl.updated_at,
    )


def _version_to_response(ver) -> PromptTemplateVersionResponse:
    return PromptTemplateVersionResponse(
        id=ver.id,
        template_id=ver.template_id,
        version=ver.version,
        template=ver.template,
        changed_at=ver.changed_at,
        change_note=ver.change_note,
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    response_model=PromptTemplateListResponse,
    summary="List all AI prompt templates",
)
async def list_prompt_templates(
    current_admin: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List all 6 AI prompt templates with their current version numbers."""
    async with uow:
        templates = await uow.ai_prompt_templates.list_all()

    return PromptTemplateListResponse(
        items=[
            PromptTemplateListItem(
                id=t.id,
                key=t.key,
                tier=t.tier,
                prompt_type=t.prompt_type,
                version=t.version,
                is_active=t.is_active,
                updated_at=t.updated_at,
            )
            for t in templates
        ],
        total=len(templates),
    )


@router.get(
    "/{key}",
    response_model=PromptTemplateResponse,
    summary="Get a prompt template by key",
)
async def get_prompt_template(
    key: str,
    current_admin: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Get a single prompt template with its variable reference.

    Valid keys: hourly_system, hourly_user, monthly_system, monthly_user,
                yearly_system, yearly_user
    """
    async with uow:
        tmpl = await uow.ai_prompt_templates.get_active_by_key(key)

    if not tmpl:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt template '{key}' not found.",
        )
    return _template_to_response(tmpl)


@router.put(
    "/{key}",
    response_model=PromptTemplateResponse,
    summary="Update a prompt template",
)
async def update_prompt_template(
    key: str,
    body: PromptTemplateUpdate,
    current_admin: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Update the template text for a prompt key.

    Creates an immutable version snapshot.
    Invalidates the Redis cache for this key (5-minute TTL will expire immediately).
    """
    if not body.template.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Template text cannot be empty.",
        )

    async with uow:
        tmpl = await uow.ai_prompt_templates.get_active_by_key(key)
        if not tmpl:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt template '{key}' not found.",
            )

        # Update template text and bump version
        tmpl.template = body.template
        tmpl.bump_version(updated_by=current_admin.id)

        # Persist updated template + save version snapshot
        await uow.ai_prompt_templates.update(tmpl)
        version_entity = AIPromptTemplateVersion(
            id=uuid4(),
            template_id=tmpl.id,
            version=tmpl.version,
            template=tmpl.template,
            variables=tmpl.variables,
            changed_by=current_admin.id,
            change_note=body.change_note,
            changed_at=datetime.now(timezone.utc),
        )
        await uow.ai_prompt_templates.add_version(version_entity)
        await uow.commit()

    # Invalidate Redis cache so the loader picks up the new template
    try:
        from ...application.services.prompt_template_loader import PromptTemplateLoader
        from ...infrastructure.database.connection import DatabaseManager
        loader = PromptTemplateLoader(DatabaseManager.get_session_factory())
        await loader.invalidate(key)
        logger.info("[ai_prompts] Redis cache invalidated for key=%s", key)
    except Exception as exc:
        logger.warning("[ai_prompts] Cache invalidation failed for key=%s: %s", key, exc)

    logger.info(
        "[ai_prompts] Template '%s' updated to v%d by admin=%s",
        key, tmpl.version, current_admin.id,
    )
    return _template_to_response(tmpl)


@router.get(
    "/{key}/versions",
    response_model=PromptTemplateVersionListResponse,
    summary="List version history for a template",
)
async def list_template_versions(
    key: str,
    current_admin: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List all saved versions for a prompt template (newest first)."""
    async with uow:
        tmpl = await uow.ai_prompt_templates.get_active_by_key(key)
        if not tmpl:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{key}' not found.")
        versions = await uow.ai_prompt_templates.get_versions(tmpl.id)

    return PromptTemplateVersionListResponse(
        items=[_version_to_response(v) for v in versions],
        total=len(versions),
    )


@router.get(
    "/{key}/versions/{version_num}",
    response_model=PromptTemplateVersionResponse,
    summary="Get a specific version of a template",
)
async def get_template_version(
    key: str,
    version_num: int,
    current_admin: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Fetch the immutable snapshot for a specific version number."""
    async with uow:
        tmpl = await uow.ai_prompt_templates.get_active_by_key(key)
        if not tmpl:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{key}' not found.")
        ver = await uow.ai_prompt_templates.get_version(tmpl.id, version_num)

    if not ver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_num} not found for template '{key}'.",
        )
    return _version_to_response(ver)


@router.post(
    "/{key}/revert/{version_num}",
    response_model=PromptTemplateResponse,
    summary="Revert a template to a previous version",
)
async def revert_template_to_version(
    key: str,
    version_num: int,
    current_admin: User = Depends(require_ops_admin),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Revert the active template text to the content of a previous version.

    Creates a new version entry (the reverted text) — does not delete history.
    """
    async with uow:
        tmpl = await uow.ai_prompt_templates.get_active_by_key(key)
        if not tmpl:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{key}' not found.")

        ver = await uow.ai_prompt_templates.get_version(tmpl.id, version_num)
        if not ver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version {version_num} not found for template '{key}'.",
            )

        change_note = f"Reverted to version {version_num}"
        tmpl.template = ver.template
        tmpl.bump_version(updated_by=current_admin.id)
        await uow.ai_prompt_templates.update(tmpl)
        revert_version = AIPromptTemplateVersion(
            id=uuid4(),
            template_id=tmpl.id,
            version=tmpl.version,
            template=tmpl.template,
            variables=tmpl.variables,
            changed_by=current_admin.id,
            change_note=change_note,
            changed_at=datetime.now(timezone.utc),
        )
        await uow.ai_prompt_templates.add_version(revert_version)
        await uow.commit()

    # Invalidate Redis cache
    try:
        from ...application.services.prompt_template_loader import PromptTemplateLoader
        from ...infrastructure.database.connection import DatabaseManager
        loader = PromptTemplateLoader(DatabaseManager.get_session_factory())
        await loader.invalidate(key)
    except Exception as exc:
        logger.warning("[ai_prompts] Cache invalidation failed: %s", exc)

    logger.info(
        "[ai_prompts] Template '%s' reverted to v%d by admin=%s (now v%d)",
        key, version_num, current_admin.id, tmpl.version,
    )
    return _template_to_response(tmpl)
