"""
Repository for device registry in System B.

Handles device registration, authentication, and connection state management.
"""
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.telemetry_model import DeviceRegistryModel
from ....domain.entities.device import DeviceRegistry, DeviceSession
from ....domain.entities.telemetry import DeviceType, ConnectionStatus

logger = logging.getLogger(__name__)


class DeviceRegistryRepository:
    """
    Repository for device registry operations.

    Manages lightweight device records used for telemetry collection.
    Full device details are stored in System A.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    async def get_by_id(self, device_id: UUID) -> Optional[DeviceRegistry]:
        """
        Get a device by ID.

        Args:
            device_id: Device UUID.

        Returns:
            DeviceRegistry if found, None otherwise.
        """
        query = select(DeviceRegistryModel).where(
            DeviceRegistryModel.device_id == device_id
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        return self._model_to_entity(model) if model else None

    async def get_by_serial_number(self, serial_number: str) -> Optional[DeviceRegistry]:
        """
        Get a device by serial number.

        Args:
            serial_number: Device serial number.

        Returns:
            DeviceRegistry if found, None otherwise.
        """
        query = select(DeviceRegistryModel).where(
            DeviceRegistryModel.serial_number == serial_number
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        return self._model_to_entity(model) if model else None

    async def get_by_site(self, site_id: UUID) -> List[DeviceRegistry]:
        """
        Get all devices for a site.

        Args:
            site_id: Site UUID.

        Returns:
            List of DeviceRegistry entities.
        """
        query = (
            select(DeviceRegistryModel)
            .where(DeviceRegistryModel.site_id == site_id)
            .order_by(DeviceRegistryModel.device_type, DeviceRegistryModel.serial_number)
        )
        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    async def get_by_organization(self, organization_id: UUID) -> List[DeviceRegistry]:
        """
        Get all devices for an organization.

        Args:
            organization_id: Organization UUID.

        Returns:
            List of DeviceRegistry entities.
        """
        query = (
            select(DeviceRegistryModel)
            .where(DeviceRegistryModel.organization_id == organization_id)
            .order_by(DeviceRegistryModel.site_id, DeviceRegistryModel.device_type)
        )
        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    async def create(self, device: DeviceRegistry) -> DeviceRegistry:
        """
        Create a new device registry entry.

        Args:
            device: DeviceRegistry entity to create.

        Returns:
            Created DeviceRegistry entity.
        """
        model = DeviceRegistryModel(
            device_id=device.device_id,
            site_id=device.site_id,
            organization_id=device.organization_id,
            device_type=device.device_type.value if isinstance(device.device_type, DeviceType) else device.device_type,
            serial_number=device.serial_number,
            auth_token_hash=device.auth_token_hash,
            token_expires_at=device.token_expires_at,
            connection_status=device.connection_status.value if isinstance(device.connection_status, ConnectionStatus) else device.connection_status,
            last_connected_at=device.last_connected_at,
            last_disconnected_at=device.last_disconnected_at,
            reconnect_count=device.reconnect_count,
            protocol=device.protocol,
            connection_config=device.connection_config,
            polling_interval_seconds=device.polling_interval_seconds,
            last_polled_at=device.last_polled_at,
            next_poll_at=device.next_poll_at,
            metadata_=device.metadata,
            created_at=device.created_at,
        )

        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)

        return self._model_to_entity(model)

    async def update(self, device: DeviceRegistry) -> DeviceRegistry:
        """
        Update a device registry entry.

        Args:
            device: DeviceRegistry entity with updated values.

        Returns:
            Updated DeviceRegistry entity.
        """
        device.updated_at = datetime.now(timezone.utc)

        stmt = (
            update(DeviceRegistryModel)
            .where(DeviceRegistryModel.device_id == device.device_id)
            .values(
                site_id=device.site_id,
                organization_id=device.organization_id,
                device_type=device.device_type.value if isinstance(device.device_type, DeviceType) else device.device_type,
                serial_number=device.serial_number,
                auth_token_hash=device.auth_token_hash,
                token_expires_at=device.token_expires_at,
                connection_status=device.connection_status.value if isinstance(device.connection_status, ConnectionStatus) else device.connection_status,
                last_connected_at=device.last_connected_at,
                last_disconnected_at=device.last_disconnected_at,
                reconnect_count=device.reconnect_count,
                protocol=device.protocol,
                connection_config=device.connection_config,
                polling_interval_seconds=device.polling_interval_seconds,
                last_polled_at=device.last_polled_at,
                next_poll_at=device.next_poll_at,
                metadata_=device.metadata,
                updated_at=device.updated_at,
            )
        )

        await self._session.execute(stmt)
        return device

    async def delete(self, device_id: UUID) -> bool:
        """
        Delete a device registry entry.

        Args:
            device_id: Device UUID to delete.

        Returns:
            True if deleted, False if not found.
        """
        stmt = delete(DeviceRegistryModel).where(
            DeviceRegistryModel.device_id == device_id
        )
        result = await self._session.execute(stmt)

        return result.rowcount > 0

    async def upsert(self, device: DeviceRegistry) -> DeviceRegistry:
        """
        Insert or update a device registry entry.

        Args:
            device: DeviceRegistry entity.

        Returns:
            Upserted DeviceRegistry entity.
        """
        stmt = pg_insert(DeviceRegistryModel).values(
            device_id=device.device_id,
            site_id=device.site_id,
            organization_id=device.organization_id,
            device_type=device.device_type.value if isinstance(device.device_type, DeviceType) else device.device_type,
            serial_number=device.serial_number,
            auth_token_hash=device.auth_token_hash,
            token_expires_at=device.token_expires_at,
            connection_status=device.connection_status.value if isinstance(device.connection_status, ConnectionStatus) else device.connection_status,
            protocol=device.protocol,
            connection_config=device.connection_config,
            polling_interval_seconds=device.polling_interval_seconds,
            metadata_=device.metadata,
            created_at=device.created_at,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["device_id"],
            set_={
                "site_id": stmt.excluded.site_id,
                "organization_id": stmt.excluded.organization_id,
                "device_type": stmt.excluded.device_type,
                "serial_number": stmt.excluded.serial_number,
                "protocol": stmt.excluded.protocol,
                "connection_config": stmt.excluded.connection_config,
                "polling_interval_seconds": stmt.excluded.polling_interval_seconds,
                "metadata_": stmt.excluded.metadata_,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        await self._session.execute(stmt)
        return device

    # =========================================================================
    # Connection State Management
    # =========================================================================

    async def update_connection_status(
        self,
        device_id: UUID,
        status: ConnectionStatus,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update device connection status.

        Args:
            device_id: Device UUID.
            status: New connection status.
            error_message: Optional error message for ERROR status.
        """
        now = datetime.now(timezone.utc)
        values: Dict[str, Any] = {
            "connection_status": status.value,
            "updated_at": now,
        }

        if status == ConnectionStatus.CONNECTED:
            values["last_connected_at"] = now
            values["reconnect_count"] = DeviceRegistryModel.reconnect_count + 1
        elif status == ConnectionStatus.DISCONNECTED:
            values["last_disconnected_at"] = now

        stmt = (
            update(DeviceRegistryModel)
            .where(DeviceRegistryModel.device_id == device_id)
            .values(**values)
        )

        await self._session.execute(stmt)

    async def get_connected_devices(
        self,
        site_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
    ) -> List[DeviceRegistry]:
        """
        Get all connected devices.

        Args:
            site_id: Optional site filter.
            organization_id: Optional organization filter.

        Returns:
            List of connected DeviceRegistry entities.
        """
        conditions = [
            DeviceRegistryModel.connection_status == ConnectionStatus.CONNECTED.value
        ]

        if site_id:
            conditions.append(DeviceRegistryModel.site_id == site_id)
        if organization_id:
            conditions.append(DeviceRegistryModel.organization_id == organization_id)

        query = select(DeviceRegistryModel).where(and_(*conditions))
        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    async def get_disconnected_devices(
        self,
        since: datetime,
        site_id: Optional[UUID] = None,
    ) -> List[DeviceRegistry]:
        """
        Get devices disconnected since a given time.

        Args:
            since: Get devices disconnected after this time.
            site_id: Optional site filter.

        Returns:
            List of disconnected DeviceRegistry entities.
        """
        conditions = [
            DeviceRegistryModel.connection_status == ConnectionStatus.DISCONNECTED.value,
            DeviceRegistryModel.last_disconnected_at >= since,
        ]

        if site_id:
            conditions.append(DeviceRegistryModel.site_id == site_id)

        query = select(DeviceRegistryModel).where(and_(*conditions))
        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    # =========================================================================
    # Polling Management
    # =========================================================================

    async def get_devices_due_for_polling(
        self,
        limit: int = 100,
    ) -> List[DeviceRegistry]:
        """
        Get devices that are due for polling.

        Args:
            limit: Maximum devices to return.

        Returns:
            List of DeviceRegistry entities due for polling.
        """
        now = datetime.now(timezone.utc)

        query = (
            select(DeviceRegistryModel)
            .where(
                and_(
                    DeviceRegistryModel.connection_status == ConnectionStatus.CONNECTED.value,
                    or_(
                        DeviceRegistryModel.next_poll_at.is_(None),
                        DeviceRegistryModel.next_poll_at <= now,
                    )
                )
            )
            .order_by(DeviceRegistryModel.next_poll_at.nullsfirst())
            .limit(limit)
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    async def update_poll_time(
        self,
        device_id: UUID,
        polled_at: Optional[datetime] = None,
    ) -> None:
        """
        Update device poll time and calculate next poll.

        Args:
            device_id: Device UUID.
            polled_at: Poll timestamp (defaults to now).
        """
        now = polled_at or datetime.now(timezone.utc)

        # Get device's polling interval
        query = select(DeviceRegistryModel.polling_interval_seconds).where(
            DeviceRegistryModel.device_id == device_id
        )
        result = await self._session.execute(query)
        interval = result.scalar() or 60

        next_poll = now + timedelta(seconds=interval)

        stmt = (
            update(DeviceRegistryModel)
            .where(DeviceRegistryModel.device_id == device_id)
            .values(
                last_polled_at=now,
                next_poll_at=next_poll,
                updated_at=now,
            )
        )

        await self._session.execute(stmt)

    # =========================================================================
    # Authentication
    # =========================================================================

    async def generate_auth_token(
        self,
        device_id: UUID,
        expires_in_days: int = 365,
    ) -> str:
        """
        Generate a new authentication token for a device.

        Args:
            device_id: Device UUID.
            expires_in_days: Token validity period.

        Returns:
            The generated plain-text token (store securely, cannot be retrieved).
        """
        # Generate secure token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        stmt = (
            update(DeviceRegistryModel)
            .where(DeviceRegistryModel.device_id == device_id)
            .values(
                auth_token_hash=token_hash,
                token_expires_at=expires_at,
                updated_at=datetime.now(timezone.utc),
            )
        )

        await self._session.execute(stmt)

        return token

    async def validate_auth_token(
        self,
        device_id: UUID,
        token: str,
    ) -> bool:
        """
        Validate a device authentication token.

        Args:
            device_id: Device UUID.
            token: Plain-text token to validate.

        Returns:
            True if token is valid and not expired.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        query = select(DeviceRegistryModel).where(
            and_(
                DeviceRegistryModel.device_id == device_id,
                DeviceRegistryModel.auth_token_hash == token_hash,
                or_(
                    DeviceRegistryModel.token_expires_at.is_(None),
                    DeviceRegistryModel.token_expires_at > now,
                )
            )
        )

        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None

    async def authenticate_by_serial(
        self,
        serial_number: str,
        token: str,
    ) -> Optional[DeviceRegistry]:
        """
        Authenticate device by serial number and token.

        Args:
            serial_number: Device serial number.
            token: Authentication token.

        Returns:
            DeviceRegistry if authenticated, None otherwise.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc)

        query = select(DeviceRegistryModel).where(
            and_(
                DeviceRegistryModel.serial_number == serial_number,
                DeviceRegistryModel.auth_token_hash == token_hash,
                or_(
                    DeviceRegistryModel.token_expires_at.is_(None),
                    DeviceRegistryModel.token_expires_at > now,
                )
            )
        )

        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        return self._model_to_entity(model) if model else None

    async def revoke_auth_token(self, device_id: UUID) -> None:
        """
        Revoke a device's authentication token.

        Args:
            device_id: Device UUID.
        """
        stmt = (
            update(DeviceRegistryModel)
            .where(DeviceRegistryModel.device_id == device_id)
            .values(
                auth_token_hash=None,
                token_expires_at=None,
                updated_at=datetime.now(timezone.utc),
            )
        )

        await self._session.execute(stmt)

    # =========================================================================
    # Sync Operations
    # =========================================================================

    async def mark_synced(
        self,
        device_ids: List[UUID],
        synced_at: Optional[datetime] = None,
    ) -> int:
        """
        Mark devices as synced with System A.

        Args:
            device_ids: List of device UUIDs.
            synced_at: Sync timestamp (defaults to now).

        Returns:
            Number of devices updated.
        """
        if not device_ids:
            return 0

        now = synced_at or datetime.now(timezone.utc)

        stmt = (
            update(DeviceRegistryModel)
            .where(DeviceRegistryModel.device_id.in_(device_ids))
            .values(synced_at=now, updated_at=now)
        )

        result = await self._session.execute(stmt)
        return result.rowcount

    async def get_unsynced_devices(
        self,
        older_than: timedelta = timedelta(minutes=5),
    ) -> List[DeviceRegistry]:
        """
        Get devices that haven't been synced recently.

        Args:
            older_than: Consider unsynced if last sync is older than this.

        Returns:
            List of unsynced DeviceRegistry entities.
        """
        cutoff = datetime.now(timezone.utc) - older_than

        query = select(DeviceRegistryModel).where(
            or_(
                DeviceRegistryModel.synced_at.is_(None),
                DeviceRegistryModel.synced_at < cutoff,
            )
        )

        result = await self._session.execute(query)
        models = result.scalars().all()

        return [self._model_to_entity(m) for m in models]

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_connection_stats(
        self,
        organization_id: Optional[UUID] = None,
    ) -> Dict[str, int]:
        """
        Get connection statistics.

        Args:
            organization_id: Optional organization filter.

        Returns:
            Dict with counts by connection status.
        """
        conditions = []
        if organization_id:
            conditions.append(DeviceRegistryModel.organization_id == organization_id)

        base_query = select(
            DeviceRegistryModel.connection_status,
            func.count().label("count"),
        ).group_by(DeviceRegistryModel.connection_status)

        if conditions:
            base_query = base_query.where(and_(*conditions))

        result = await self._session.execute(base_query)
        rows = result.all()

        return {row.connection_status: row.count for row in rows}

    async def get_device_type_counts(
        self,
        organization_id: Optional[UUID] = None,
    ) -> Dict[str, int]:
        """
        Get device counts by type.

        Args:
            organization_id: Optional organization filter.

        Returns:
            Dict with counts by device type.
        """
        conditions = []
        if organization_id:
            conditions.append(DeviceRegistryModel.organization_id == organization_id)

        base_query = select(
            DeviceRegistryModel.device_type,
            func.count().label("count"),
        ).group_by(DeviceRegistryModel.device_type)

        if conditions:
            base_query = base_query.where(and_(*conditions))

        result = await self._session.execute(base_query)
        rows = result.all()

        return {row.device_type: row.count for row in rows}

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _model_to_entity(self, model: DeviceRegistryModel) -> DeviceRegistry:
        """Convert SQLAlchemy model to domain entity."""
        return DeviceRegistry(
            id=model.device_id,
            device_id=model.device_id,
            site_id=model.site_id,
            organization_id=model.organization_id,
            device_type=DeviceType(model.device_type) if model.device_type else DeviceType.INVERTER,
            serial_number=model.serial_number,
            auth_token_hash=model.auth_token_hash,
            token_expires_at=model.token_expires_at,
            connection_status=ConnectionStatus(model.connection_status) if model.connection_status else ConnectionStatus.DISCONNECTED,
            last_connected_at=model.last_connected_at,
            last_disconnected_at=model.last_disconnected_at,
            reconnect_count=model.reconnect_count,
            protocol=model.protocol,
            connection_config=model.connection_config,
            polling_interval_seconds=model.polling_interval_seconds,
            last_polled_at=model.last_polled_at,
            next_poll_at=model.next_poll_at,
            metadata=model.metadata_,
            created_at=model.created_at,
            updated_at=model.updated_at,
            synced_at=model.synced_at,
        )
