"""
SQLAlchemy implementation of DeviceRepository.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....application.interfaces.repositories import DeviceRepository
from ....domain.entities.device import Device, DeviceStatus, DeviceType
from ..models.device_model import DeviceModel


class SQLAlchemyDeviceRepository(DeviceRepository):
    """SQLAlchemy implementation of device repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[Device]:
        """Get device by ID."""
        result = await self._session.execute(
            select(DeviceModel).where(DeviceModel.id == id)
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_serial_number(self, serial_number: str) -> Optional[Device]:
        """Get device by serial number."""
        result = await self._session.execute(
            select(DeviceModel).where(
                DeviceModel.serial_number == serial_number
            )
        )
        model = result.scalar_one_or_none()
        return model.to_domain() if model else None

    async def get_by_site_id(
        self,
        site_id: UUID,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[Device]:
        """Get devices at a specific site."""
        query = select(DeviceModel).where(DeviceModel.site_id == site_id)

        if status:
            query = query.where(DeviceModel.status == DeviceStatus(status))

        query = query.order_by(DeviceModel.name)
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_by_organization_id(
        self,
        organization_id: UUID,
        limit: int = 100,
        offset: int = 0,
        device_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Device]:
        """Get devices belonging to an organization."""
        query = select(DeviceModel).where(
            DeviceModel.organization_id == organization_id
        )

        if device_type:
            query = query.where(
                DeviceModel.device_type == DeviceType(device_type)
            )

        if status:
            query = query.where(DeviceModel.status == DeviceStatus(status))

        query = query.order_by(DeviceModel.name)
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def count_by_site_id(
        self,
        site_id: UUID,
        status: Optional[str] = None
    ) -> int:
        """Count devices at a site."""
        query = select(func.count()).select_from(DeviceModel).where(
            DeviceModel.site_id == site_id
        )

        if status:
            query = query.where(DeviceModel.status == DeviceStatus(status))

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def count_by_organization_id(
        self,
        organization_id: UUID,
        device_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> int:
        """Count devices in an organization."""
        query = select(func.count()).select_from(DeviceModel).where(
            DeviceModel.organization_id == organization_id
        )

        if device_type:
            query = query.where(
                DeviceModel.device_type == DeviceType(device_type)
            )

        if status:
            query = query.where(DeviceModel.status == DeviceStatus(status))

        result = await self._session.execute(query)
        return result.scalar() or 0

    async def serial_number_exists(self, serial_number: str) -> bool:
        """Check if serial number is already registered."""
        result = await self._session.execute(
            select(func.count()).select_from(DeviceModel).where(
                DeviceModel.serial_number == serial_number
            )
        )
        count = result.scalar()
        return count > 0

    async def get_online_devices(self, site_id: UUID) -> List[Device]:
        """Get online devices at a site."""
        result = await self._session.execute(
            select(DeviceModel).where(
                DeviceModel.site_id == site_id,
                DeviceModel.status == DeviceStatus.ONLINE
            )
        )
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_offline_devices(
        self,
        organization_id: UUID,
        threshold_minutes: int = 5
    ) -> List[Device]:
        """Get devices that have been offline for specified time."""
        threshold_time = datetime.now(timezone.utc) - timedelta(
            minutes=threshold_minutes
        )

        result = await self._session.execute(
            select(DeviceModel).where(
                DeviceModel.organization_id == organization_id,
                DeviceModel.status == DeviceStatus.ONLINE,
                DeviceModel.last_seen_at < threshold_time
            )
        )
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def get_devices_with_errors(
        self,
        organization_id: UUID
    ) -> List[Device]:
        """Get devices currently in error state."""
        result = await self._session.execute(
            select(DeviceModel).where(
                DeviceModel.organization_id == organization_id,
                DeviceModel.status == DeviceStatus.ERROR
            )
        )
        models = result.scalars().all()
        return [m.to_domain() for m in models]

    async def update_device_status(
        self,
        device_id: UUID,
        status: str,
        last_seen_at: Optional[str] = None
    ) -> bool:
        """Update device status efficiently."""
        values = {'status': DeviceStatus(status)}

        if last_seen_at:
            values['last_seen_at'] = datetime.fromisoformat(last_seen_at)

        result = await self._session.execute(
            update(DeviceModel)
            .where(DeviceModel.id == device_id)
            .values(**values)
        )
        await self._session.flush()
        return result.rowcount > 0

    async def add(self, entity: Device) -> Device:
        """Add new device."""
        model = DeviceModel.from_domain(entity)
        self._session.add(model)
        await self._session.flush()
        return model.to_domain()

    async def update(self, entity: Device) -> Device:
        """Update existing device."""
        result = await self._session.execute(
            select(DeviceModel).where(DeviceModel.id == entity.id)
        )
        model = result.scalar_one_or_none()
        if model:
            model.update_from_domain(entity)
            await self._session.flush()
            return model.to_domain()
        return entity

    async def delete(self, id: UUID) -> bool:
        """Delete device by ID."""
        result = await self._session.execute(
            select(DeviceModel).where(DeviceModel.id == id)
        )
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()
            return True
        return False
