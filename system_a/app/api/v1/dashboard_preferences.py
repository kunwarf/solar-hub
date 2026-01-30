"""
Dashboard preferences and custom presets API endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import get_current_user, get_unit_of_work
from ..schemas.dashboard_preference_schemas import (
    DashboardPreferencesResponse,
    DashboardPreferencesUpdate,
    CustomPresetResponse,
    CustomPresetListResponse,
    CustomPresetCreate,
    CustomPresetUpdate,
)
from ..schemas.auth_schemas import MessageResponse, ErrorResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...domain.entities.user import User
from ...domain.entities.dashboard import (
    DashboardPreferences,
    CustomPreset,
    GridLayout,
    WidgetConfig,
    PresetWidgetConfig,
    WidgetSize,
)

router = APIRouter(prefix="/users/me/dashboard", tags=["Dashboard Preferences"])


@router.get(
    "/preferences",
    response_model=DashboardPreferencesResponse,
    responses={401: {"model": ErrorResponse}},
)
async def get_dashboard_preferences(
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get current user's dashboard preferences."""
    prefs = await uow.dashboard_preferences.get_by_user_id(current_user.id)

    if not prefs:
        # Return default preferences if none exist
        default_prefs = DashboardPreferences(
            user_id=current_user.id,
            layout_preset="standard",
            grid_layout=GridLayout.LIST,
            widget_layout=[],
        )
        # Use created_at for updated_at if not set
        updated_at = default_prefs.updated_at if default_prefs.updated_at else default_prefs.created_at
        return DashboardPreferencesResponse(
            user_id=default_prefs.user_id,
            layout_preset=default_prefs.layout_preset,
            grid_layout=default_prefs.grid_layout.value,
            widget_layout=[],
            created_at=default_prefs.created_at,
            updated_at=updated_at,
        )

    return DashboardPreferencesResponse(
        user_id=prefs.user_id,
        layout_preset=prefs.layout_preset,
        grid_layout=prefs.grid_layout.value,
        widget_layout=[
            {
                "id": w.id,
                "visible": w.visible,
                "size": w.size.value,
                "settings": w.settings,
            }
            for w in prefs.widget_layout
        ],
        created_at=prefs.created_at,
        updated_at=prefs.updated_at,
    )


@router.put(
    "/preferences",
    response_model=DashboardPreferencesResponse,
    responses={401: {"model": ErrorResponse}},
)
async def update_dashboard_preferences(
    request: DashboardPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update current user's dashboard preferences."""
    try:
        logger.info(f"[DASHBOARD_PREFS] Starting update for user {current_user.id}")
        logger.info(f"[DASHBOARD_PREFS] Request data: preset={request.layout_preset}, grid={request.grid_layout}, widgets={len(request.widget_layout) if request.widget_layout else 0}")

        # Get existing preferences or create new
        logger.info(f"[DASHBOARD_PREFS] Fetching existing preferences for user {current_user.id}")
        prefs = await uow.dashboard_preferences.get_by_user_id(current_user.id)
        logger.info(f"[DASHBOARD_PREFS] Existing preferences found: {prefs is not None}")

        if not prefs:
            # Create new preferences
            logger.info(f"[DASHBOARD_PREFS] Creating NEW preferences for user {current_user.id}")
            prefs = DashboardPreferences(
                user_id=current_user.id,
                layout_preset=request.layout_preset or "standard",
                grid_layout=GridLayout(request.grid_layout) if request.grid_layout else GridLayout.LIST,
                widget_layout=[
                    WidgetConfig(
                        id=w.id,
                        visible=w.visible,
                        size=WidgetSize(w.size),
                        settings=w.settings,
                    )
                    for w in (request.widget_layout or [])
                ],
            )
            logger.info(f"[DASHBOARD_PREFS] Created new prefs: preset={prefs.layout_preset}, widgets={len(prefs.widget_layout)}")
        else:
            # Update existing preferences
            logger.info(f"[DASHBOARD_PREFS] Updating EXISTING preferences for user {current_user.id}")
            if request.layout_preset is not None:
                logger.info(f"[DASHBOARD_PREFS] Updating preset to: {request.layout_preset}")
                prefs.update_preset(request.layout_preset)

            if request.grid_layout is not None:
                logger.info(f"[DASHBOARD_PREFS] Updating grid_layout to: {request.grid_layout}")
                prefs.update_grid_layout(GridLayout(request.grid_layout))

            if request.widget_layout is not None:
                logger.info(f"[DASHBOARD_PREFS] Updating widget_layout with {len(request.widget_layout)} widgets")
                widget_configs = [
                    WidgetConfig(
                        id=w.id,
                        visible=w.visible,
                        size=WidgetSize(w.size),
                        settings=w.settings,
                    )
                    for w in request.widget_layout
                ]
                prefs.update_widget_layout(widget_configs)
                logger.info(f"[DASHBOARD_PREFS] Widget layout updated successfully")

        # Upsert (insert or update)
        logger.info(f"[DASHBOARD_PREFS] Calling upsert for user {current_user.id}")
        saved_prefs = await uow.dashboard_preferences.upsert(prefs)
        logger.info(f"[DASHBOARD_PREFS] Upsert completed, saved_prefs id: {saved_prefs.id if hasattr(saved_prefs, 'id') else 'NO_ID'}")

        logger.info(f"[DASHBOARD_PREFS] Calling commit()")
        await uow.commit()
        logger.info(f"[DASHBOARD_PREFS] Commit completed successfully")

        response_data = DashboardPreferencesResponse(
            user_id=saved_prefs.user_id,
            layout_preset=saved_prefs.layout_preset,
            grid_layout=saved_prefs.grid_layout.value,
            widget_layout=[
                {
                    "id": w.id,
                    "visible": w.visible,
                    "size": w.size.value,
                    "settings": w.settings,
                }
                for w in saved_prefs.widget_layout
            ],
            created_at=saved_prefs.created_at,
            updated_at=saved_prefs.updated_at,
        )
        logger.info(f"[DASHBOARD_PREFS] Returning response with {len(response_data.widget_layout)} widgets")
        return response_data

    except Exception as e:
        logger.error(f"[DASHBOARD_PREFS] ERROR in update_dashboard_preferences: {str(e)}", exc_info=True)
        raise


@router.get(
    "/presets",
    response_model=CustomPresetListResponse,
    responses={401: {"model": ErrorResponse}},
)
async def list_custom_presets(
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List current user's custom presets."""
    presets = await uow.custom_presets.get_by_user_id(
        current_user.id, limit=limit, offset=offset
    )
    total = await uow.custom_presets.count_by_user_id(current_user.id)

    return CustomPresetListResponse(
        presets=[
            CustomPresetResponse(
                id=p.id,
                user_id=p.user_id,
                name=p.name,
                description=p.description,
                widget_config=[
                    {
                        "id": w.id,
                        "visible": w.visible,
                        "size": w.size.value,
                    }
                    for w in p.widget_config
                ],
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in presets
        ],
        total=total,
    )


@router.post(
    "/presets",
    response_model=CustomPresetResponse,
    status_code=status.HTTP_201_CREATED,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def create_custom_preset(
    request: CustomPresetCreate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Create a new custom preset."""
    # Create preset entity
    preset = CustomPreset(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        widget_config=[
            PresetWidgetConfig(
                id=w.id,
                visible=w.visible,
                size=WidgetSize(w.size),
            )
            for w in request.widget_config
        ],
    )

    # Save to database
    saved_preset = await uow.custom_presets.add(preset)
    await uow.commit()

    return CustomPresetResponse(
        id=saved_preset.id,
        user_id=saved_preset.user_id,
        name=saved_preset.name,
        description=saved_preset.description,
        widget_config=[
            {
                "id": w.id,
                "visible": w.visible,
                "size": w.size.value,
            }
            for w in saved_preset.widget_config
        ],
        created_at=saved_preset.created_at,
        updated_at=saved_preset.updated_at,
    )


@router.get(
    "/presets/{preset_id}",
    response_model=CustomPresetResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_custom_preset(
    preset_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get a specific custom preset."""
    preset = await uow.custom_presets.get_by_id(preset_id)

    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom preset not found",
        )

    # Verify ownership
    if preset.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom preset not found",
        )

    return CustomPresetResponse(
        id=preset.id,
        user_id=preset.user_id,
        name=preset.name,
        description=preset.description,
        widget_config=[
            {
                "id": w.id,
                "visible": w.visible,
                "size": w.size.value,
            }
            for w in preset.widget_config
        ],
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


@router.put(
    "/presets/{preset_id}",
    response_model=CustomPresetResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_custom_preset(
    preset_id: UUID,
    request: CustomPresetUpdate,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Update a custom preset."""
    preset = await uow.custom_presets.get_by_id(preset_id)

    if not preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom preset not found",
        )

    # Verify ownership
    if preset.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom preset not found",
        )

    # Update fields
    if request.name is not None:
        preset.update_name(request.name)

    if request.description is not None:
        preset.update_description(request.description)

    if request.widget_config is not None:
        widget_configs = [
            PresetWidgetConfig(
                id=w.id,
                visible=w.visible,
                size=WidgetSize(w.size),
            )
            for w in request.widget_config
        ]
        preset.update_widget_config(widget_configs)

    # Save changes
    saved_preset = await uow.custom_presets.update(preset)
    await uow.commit()

    return CustomPresetResponse(
        id=saved_preset.id,
        user_id=saved_preset.user_id,
        name=saved_preset.name,
        description=saved_preset.description,
        widget_config=[
            {
                "id": w.id,
                "visible": w.visible,
                "size": w.size.value,
            }
            for w in saved_preset.widget_config
        ],
        created_at=saved_preset.created_at,
        updated_at=saved_preset.updated_at,
    )


@router.delete(
    "/presets/{preset_id}",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_custom_preset(
    preset_id: UUID,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Delete a custom preset."""
    # Use the repository method that checks ownership
    deleted = await uow.custom_presets.delete_by_user_and_id(
        current_user.id, preset_id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom preset not found",
        )

    await uow.commit()

    return MessageResponse(message="Custom preset deleted successfully")
