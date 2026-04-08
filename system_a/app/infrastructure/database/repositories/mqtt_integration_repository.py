"""
SQLAlchemy implementation of MQTT integration repositories.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.interfaces.repositories import (
    MqttIntegrationRepository,
    MqttIntegrationDeviceRepository,
)
from ....domain.entities.mqtt_integration import MqttIntegration, MqttIntegrationDevice
from ..models.mqtt_integration_model import MqttIntegrationModel, MqttIntegrationDeviceModel
from ..models.device_model import DeviceModel


class SQLAlchemyMqttIntegrationRepository(MqttIntegrationRepository):
    """SQLAlchemy implementation of MqttIntegrationRepository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[MqttIntegration]:
        result = await self._session.execute(
            select(MqttIntegrationModel).where(MqttIntegrationModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_user_id(self, user_id: UUID) -> Optional[MqttIntegration]:
        result = await self._session.execute(
            select(MqttIntegrationModel).where(MqttIntegrationModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_ha_username(self, ha_username: str) -> Optional[MqttIntegration]:
        result = await self._session.execute(
            select(MqttIntegrationModel).where(
                MqttIntegrationModel.ha_username == ha_username
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_all_enabled(self) -> List[MqttIntegration]:
        result = await self._session.execute(
            select(MqttIntegrationModel).where(MqttIntegrationModel.enabled == True)
        )
        return [m.to_domain() for m in result.scalars().all()]

    async def add(self, entity: MqttIntegration) -> MqttIntegration:
        model = MqttIntegrationModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: MqttIntegration) -> MqttIntegration:
        result = await self._session.execute(
            select(MqttIntegrationModel).where(MqttIntegrationModel.id == entity.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"MqttIntegration {entity.id} not found")
        model.update_from_domain(entity)
        await self._session.flush()
        return model.to_domain()

    async def delete(self, id: UUID) -> bool:
        result = await self._session.execute(
            select(MqttIntegrationModel).where(MqttIntegrationModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True


class SQLAlchemyMqttIntegrationDeviceRepository(MqttIntegrationDeviceRepository):
    """SQLAlchemy implementation of MqttIntegrationDeviceRepository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[MqttIntegrationDevice]:
        result = await self._session.execute(
            select(MqttIntegrationDeviceModel).where(MqttIntegrationDeviceModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_integration_id(self, integration_id: UUID) -> List[MqttIntegrationDevice]:
        result = await self._session.execute(
            select(MqttIntegrationDeviceModel).where(
                MqttIntegrationDeviceModel.integration_id == integration_id
            )
        )
        return [m.to_domain() for m in result.scalars().all()]

    async def get_by_integration_and_device(
        self, integration_id: UUID, device_id: UUID
    ) -> Optional[MqttIntegrationDevice]:
        result = await self._session.execute(
            select(MqttIntegrationDeviceModel).where(
                and_(
                    MqttIntegrationDeviceModel.integration_id == integration_id,
                    MqttIntegrationDeviceModel.device_id == device_id,
                )
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_all_enabled_enrollments(self) -> List[Dict[str, Any]]:
        """
        Join mqtt_integrations + mqtt_integration_devices + devices to produce
        the enriched list that System B needs to publish telemetry.
        """
        result = await self._session.execute(
            select(
                MqttIntegrationModel.ha_username,
                MqttIntegrationModel.publish_interval_seconds,
                MqttIntegrationDeviceModel.device_id,
                DeviceModel.serial_number,
                DeviceModel.name,
                DeviceModel.manufacturer,
                DeviceModel.model,
            )
            .join(
                MqttIntegrationDeviceModel,
                MqttIntegrationDeviceModel.integration_id == MqttIntegrationModel.id,
            )
            .join(DeviceModel, DeviceModel.id == MqttIntegrationDeviceModel.device_id)
            .where(
                and_(
                    MqttIntegrationModel.enabled == True,
                    MqttIntegrationDeviceModel.enabled == True,
                )
            )
        )
        rows = result.all()
        return [
            {
                "ha_username": row.ha_username,
                "publish_interval_seconds": row.publish_interval_seconds,
                "device_id": str(row.device_id),
                "device_serial": row.serial_number,
                "device_name": row.name,
                "manufacturer": row.manufacturer,
                "model": row.model,
            }
            for row in rows
        ]

    async def add(self, entity: MqttIntegrationDevice) -> MqttIntegrationDevice:
        model = MqttIntegrationDeviceModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: MqttIntegrationDevice) -> MqttIntegrationDevice:
        result = await self._session.execute(
            select(MqttIntegrationDeviceModel).where(
                MqttIntegrationDeviceModel.id == entity.id
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"MqttIntegrationDevice {entity.id} not found")
        model.update_from_domain(entity)
        await self._session.flush()
        return model.to_domain()

    async def delete(self, id: UUID) -> bool:
        result = await self._session.execute(
            select(MqttIntegrationDeviceModel).where(MqttIntegrationDeviceModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
