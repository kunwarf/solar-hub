"""
Protocol Definition API endpoints.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..dependencies import (
    get_current_user,
    get_unit_of_work,
    require_admin,
)
from ..schemas.protocol_definition_schemas import (
    ProtocolDefinitionCreate,
    ProtocolDefinitionUpdate,
    ProtocolDefinitionResponse,
    ProtocolDefinitionListResponse,
)
from ..schemas.auth_schemas import MessageResponse
from ...application.interfaces.unit_of_work import UnitOfWork
from ...application.services.protocol_definition_service import (
    ProtocolDefinitionService,
    CreateProtocolDefinitionRequest,
    UpdateProtocolDefinitionRequest,
)
from ...domain.entities.user import User
from ...infrastructure.database.repositories.protocol_definition_repository import (
    SQLAlchemyProtocolDefinitionRepository,
)

router = APIRouter(prefix="/protocol-definitions", tags=["Protocol Definitions"])


def get_protocol_definition_service(
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProtocolDefinitionService:
    """Get protocol definition service instance."""
    repo = SQLAlchemyProtocolDefinitionRepository(uow._session)
    return ProtocolDefinitionService(repo)


def entity_to_response(entity) -> ProtocolDefinitionResponse:
    """Convert domain entity to API response."""
    return ProtocolDefinitionResponse(
        id=entity.id,
        protocol_id=entity.protocol_id,
        name=entity.name,
        description=entity.description,
        device_type=entity.device_type.value,
        protocol_type=entity.protocol_type.value,
        priority=entity.priority,
        manufacturer=entity.manufacturer,
        model_pattern=entity.model_pattern,
        adapter_class=entity.adapter_class,
        register_map_file=entity.register_map_file,
        identification_config=entity.identification_config.to_dict() if entity.identification_config else None,
        serial_number_config=entity.serial_number_config.to_dict() if entity.serial_number_config else None,
        polling_config=entity.polling_config.to_dict() if entity.polling_config else None,
        modbus_config=entity.modbus_config.to_dict() if entity.modbus_config else None,
        command_config=entity.command_config.to_dict() if entity.command_config else None,
        default_connection_config=entity.default_connection_config,
        is_active=entity.is_active,
        is_system=entity.is_system,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.get(
    "",
    response_model=ProtocolDefinitionListResponse,
    summary="List protocol definitions",
    description="Get all protocol definitions with optional filtering.",
)
async def list_protocol_definitions(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    is_active: Optional[bool] = Query(default=None),
    device_type: Optional[str] = Query(default=None),
    protocol_type: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: ProtocolDefinitionService = Depends(get_protocol_definition_service),
) -> ProtocolDefinitionListResponse:
    """List protocol definitions with pagination and filtering."""
    # Get filtered list based on device_type or protocol_type
    if device_type:
        items = await service.get_by_device_type(device_type, is_active)
    elif protocol_type:
        items = await service.get_by_protocol_type(protocol_type, is_active)
    else:
        items = await service.get_all(limit, offset, is_active)

    total = await service.count(is_active)

    return ProtocolDefinitionListResponse(
        items=[entity_to_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{id}",
    response_model=ProtocolDefinitionResponse,
    summary="Get protocol definition",
    description="Get a protocol definition by ID.",
)
async def get_protocol_definition(
    id: UUID,
    current_user: User = Depends(get_current_user),
    service: ProtocolDefinitionService = Depends(get_protocol_definition_service),
) -> ProtocolDefinitionResponse:
    """Get a protocol definition by ID."""
    entity = await service.get_by_id(id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Protocol definition not found",
        )
    return entity_to_response(entity)


@router.get(
    "/by-protocol-id/{protocol_id}",
    response_model=ProtocolDefinitionResponse,
    summary="Get by protocol ID",
    description="Get a protocol definition by its unique protocol_id string.",
)
async def get_by_protocol_id(
    protocol_id: str,
    current_user: User = Depends(get_current_user),
    service: ProtocolDefinitionService = Depends(get_protocol_definition_service),
) -> ProtocolDefinitionResponse:
    """Get a protocol definition by protocol_id string."""
    entity = await service.get_by_protocol_id(protocol_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Protocol definition '{protocol_id}' not found",
        )
    return entity_to_response(entity)


@router.post(
    "",
    response_model=ProtocolDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create protocol definition",
    description="Create a new protocol definition. Requires admin role.",
)
async def create_protocol_definition(
    data: ProtocolDefinitionCreate,
    current_user: User = Depends(require_admin),
    service: ProtocolDefinitionService = Depends(get_protocol_definition_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProtocolDefinitionResponse:
    """Create a new protocol definition."""
    request = CreateProtocolDefinitionRequest(
        protocol_id=data.protocol_id,
        name=data.name,
        description=data.description,
        device_type=data.device_type,
        protocol_type=data.protocol_type,
        priority=data.priority,
        manufacturer=data.manufacturer,
        model_pattern=data.model_pattern,
        adapter_class=data.adapter_class,
        register_map_file=data.register_map_file,
        identification_config=data.identification_config.model_dump() if data.identification_config else None,
        serial_number_config=data.serial_number_config.model_dump() if data.serial_number_config else None,
        polling_config=data.polling_config.model_dump() if data.polling_config else None,
        modbus_config=data.modbus_config.model_dump() if data.modbus_config else None,
        command_config=data.command_config.model_dump() if data.command_config else None,
        default_connection_config=data.default_connection_config,
    )

    try:
        entity = await service.create(request)
        await uow.commit()
        return entity_to_response(entity)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.patch(
    "/{id}",
    response_model=ProtocolDefinitionResponse,
    summary="Update protocol definition",
    description="Update an existing protocol definition. Cannot modify system protocols.",
)
async def update_protocol_definition(
    id: UUID,
    data: ProtocolDefinitionUpdate,
    current_user: User = Depends(require_admin),
    service: ProtocolDefinitionService = Depends(get_protocol_definition_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProtocolDefinitionResponse:
    """Update a protocol definition."""
    request = UpdateProtocolDefinitionRequest(
        name=data.name,
        description=data.description,
        priority=data.priority,
        manufacturer=data.manufacturer,
        model_pattern=data.model_pattern,
        adapter_class=data.adapter_class,
        register_map_file=data.register_map_file,
        identification_config=data.identification_config.model_dump() if data.identification_config else None,
        serial_number_config=data.serial_number_config.model_dump() if data.serial_number_config else None,
        polling_config=data.polling_config.model_dump() if data.polling_config else None,
        modbus_config=data.modbus_config.model_dump() if data.modbus_config else None,
        command_config=data.command_config.model_dump() if data.command_config else None,
        default_connection_config=data.default_connection_config,
        is_active=data.is_active,
    )

    try:
        entity = await service.update(id, request)
        await uow.commit()
        return entity_to_response(entity)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{id}",
    response_model=MessageResponse,
    summary="Delete protocol definition",
    description="Delete a protocol definition. Cannot delete system protocols.",
)
async def delete_protocol_definition(
    id: UUID,
    current_user: User = Depends(require_admin),
    service: ProtocolDefinitionService = Depends(get_protocol_definition_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> MessageResponse:
    """Delete a protocol definition."""
    try:
        await service.delete(id)
        await uow.commit()
        return MessageResponse(message="Protocol definition deleted successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{id}/deactivate",
    response_model=ProtocolDefinitionResponse,
    summary="Deactivate protocol definition",
    description="Deactivate a protocol definition (soft delete).",
)
async def deactivate_protocol_definition(
    id: UUID,
    current_user: User = Depends(require_admin),
    service: ProtocolDefinitionService = Depends(get_protocol_definition_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProtocolDefinitionResponse:
    """Deactivate a protocol definition."""
    try:
        entity = await service.deactivate(id)
        await uow.commit()
        return entity_to_response(entity)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{id}/activate",
    response_model=ProtocolDefinitionResponse,
    summary="Activate protocol definition",
    description="Activate a previously deactivated protocol definition.",
)
async def activate_protocol_definition(
    id: UUID,
    current_user: User = Depends(require_admin),
    service: ProtocolDefinitionService = Depends(get_protocol_definition_service),
    uow: UnitOfWork = Depends(get_unit_of_work),
) -> ProtocolDefinitionResponse:
    """Activate a protocol definition."""
    try:
        entity = await service.activate(id)
        await uow.commit()
        return entity_to_response(entity)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
