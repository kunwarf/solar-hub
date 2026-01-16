"""
Device Service for System B.

Handles device registration, connection management, and synchronization.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from ...domain.entities.device import DeviceRegistry, DeviceSession
from ...domain.entities.telemetry import DeviceType, ConnectionStatus
from ...domain.entities.event import DeviceEvent, EventType, EventSeverity
from ...infrastructure.database.repositories import DeviceRegistryRepository, EventRepository

logger = logging.getLogger(__name__)


class DeviceService:
    """
    Application service for device management.

    Coordinates device registration, connection state, and polling.
    """

    def __init__(
        self,
        device_repo: DeviceRegistryRepository,
        event_repo: Optional[EventRepository] = None,
    ):
        self._device_repo = device_repo
        self._event_repo = event_repo
        self._active_sessions: Dict[UUID, DeviceSession] = {}

    # =========================================================================
    # Device Registration
    # =========================================================================

    async def register_device(
        self,
        device_id: UUID,
        site_id: UUID,
        organization_id: UUID,
        device_type: DeviceType,
        serial_number: str,
        protocol: Optional[str] = None,
        connection_config: Optional[Dict[str, Any]] = None,
        polling_interval_seconds: int = 60,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DeviceRegistry:
        """
        Register a new device.

        Args:
            device_id: Device UUID.
            site_id: Site UUID.
            organization_id: Organization UUID.
            device_type: Type of device.
            serial_number: Device serial number.
            protocol: Communication protocol.
            connection_config: Connection configuration.
            polling_interval_seconds: Polling interval.
            metadata: Additional metadata.

        Returns:
            Created DeviceRegistry entity.
        """
        device = DeviceRegistry(
            device_id=device_id,
            id=device_id,
            site_id=site_id,
            organization_id=organization_id,
            device_type=device_type,
            serial_number=serial_number,
            protocol=protocol,
            connection_config=connection_config,
            polling_interval_seconds=polling_interval_seconds,
            metadata=metadata,
        )

        created = await self._device_repo.create(device)

        logger.info(f"Registered device {device_id} ({serial_number})")

        return created

    async def sync_device_from_system_a(
        self,
        device_data: Dict[str, Any],
    ) -> DeviceRegistry:
        """
        Sync device information from System A.

        Args:
            device_data: Device data from System A.

        Returns:
            Synced DeviceRegistry entity.
        """
        device = DeviceRegistry(
            device_id=UUID(device_data["id"]),
            id=UUID(device_data["id"]),
            site_id=UUID(device_data["site_id"]),
            organization_id=UUID(device_data["organization_id"]),
            device_type=DeviceType(device_data["device_type"]),
            serial_number=device_data["serial_number"],
            protocol=device_data.get("protocol"),
            connection_config=device_data.get("connection_config"),
            polling_interval_seconds=device_data.get("polling_interval_seconds", 60),
            metadata=device_data.get("metadata"),
        )

        result = await self._device_repo.upsert(device)

        logger.debug(f"Synced device {device.device_id} from System A")

        return result

    async def get_device(self, device_id: UUID) -> Optional[DeviceRegistry]:
        """
        Get a device by ID.

        Args:
            device_id: Device UUID.

        Returns:
            DeviceRegistry if found, None otherwise.
        """
        return await self._device_repo.get_by_id(device_id)

    async def get_device_by_serial(self, serial_number: str) -> Optional[DeviceRegistry]:
        """
        Get a device by serial number.

        Args:
            serial_number: Device serial number.

        Returns:
            DeviceRegistry if found, None otherwise.
        """
        return await self._device_repo.get_by_serial_number(serial_number)

    async def get_site_devices(self, site_id: UUID) -> List[DeviceRegistry]:
        """
        Get all devices for a site.

        Args:
            site_id: Site UUID.

        Returns:
            List of DeviceRegistry entities.
        """
        return await self._device_repo.get_by_site(site_id)

    async def get_organization_devices(self, organization_id: UUID) -> List[DeviceRegistry]:
        """
        Get all devices for an organization.

        Args:
            organization_id: Organization UUID.

        Returns:
            List of DeviceRegistry entities.
        """
        return await self._device_repo.get_by_organization(organization_id)

    async def update_device(
        self,
        device_id: UUID,
        **updates,
    ) -> Optional[DeviceRegistry]:
        """
        Update device properties.

        Args:
            device_id: Device UUID.
            **updates: Fields to update.

        Returns:
            Updated DeviceRegistry, or None if not found.
        """
        device = await self._device_repo.get_by_id(device_id)
        if not device:
            return None

        # Apply updates
        for key, value in updates.items():
            if hasattr(device, key):
                setattr(device, key, value)

        return await self._device_repo.update(device)

    async def delete_device(self, device_id: UUID) -> bool:
        """
        Delete a device.

        Args:
            device_id: Device UUID.

        Returns:
            True if deleted, False if not found.
        """
        return await self._device_repo.delete(device_id)

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def handle_device_connect(
        self,
        device_id: UUID,
        session_id: str,
        client_address: Optional[str] = None,
        protocol: Optional[str] = None,
    ) -> Optional[DeviceSession]:
        """
        Handle device connection event.

        Args:
            device_id: Device UUID.
            session_id: Connection session ID.
            client_address: Client IP address.
            protocol: Connection protocol.

        Returns:
            DeviceSession if device exists, None otherwise.
        """
        device = await self._device_repo.get_by_id(device_id)
        if not device:
            logger.warning(f"Unknown device connected: {device_id}")
            return None

        # Update connection status
        await self._device_repo.update_connection_status(
            device_id=device_id,
            status=ConnectionStatus.CONNECTED,
        )

        # Create session
        session = DeviceSession(
            device_id=device_id,
            session_id=session_id,
            protocol=protocol or device.protocol,
            client_address=client_address,
        )
        self._active_sessions[device_id] = session

        # Log event
        if self._event_repo:
            event = DeviceEvent.create_connection_event(
                device_id=device_id,
                site_id=device.site_id,
                connected=True,
                details={"client_address": client_address, "session_id": session_id},
            )
            await self._event_repo.create(event)

        logger.info(f"Device {device_id} connected from {client_address}")

        return session

    async def handle_device_disconnect(
        self,
        device_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        """
        Handle device disconnection event.

        Args:
            device_id: Device UUID.
            reason: Disconnection reason.
        """
        # Update connection status
        await self._device_repo.update_connection_status(
            device_id=device_id,
            status=ConnectionStatus.DISCONNECTED,
        )

        # Remove session
        session = self._active_sessions.pop(device_id, None)

        # Log event
        device = await self._device_repo.get_by_id(device_id)
        if device and self._event_repo:
            event = DeviceEvent.create_connection_event(
                device_id=device_id,
                site_id=device.site_id,
                connected=False,
                details={
                    "reason": reason,
                    "session_duration_seconds": (
                        (datetime.now(timezone.utc) - session.connected_at).total_seconds()
                        if session else None
                    ),
                },
            )
            await self._event_repo.create(event)

        logger.info(f"Device {device_id} disconnected: {reason}")

    async def handle_device_error(
        self,
        device_id: UUID,
        error_code: str,
        error_message: str,
    ) -> None:
        """
        Handle device error event.

        Args:
            device_id: Device UUID.
            error_code: Error code.
            error_message: Error message.
        """
        # Update connection status
        await self._device_repo.update_connection_status(
            device_id=device_id,
            status=ConnectionStatus.ERROR,
            error_message=error_message,
        )

        # Log event
        device = await self._device_repo.get_by_id(device_id)
        if device and self._event_repo:
            event = DeviceEvent.create_error_event(
                device_id=device_id,
                site_id=device.site_id,
                error_code=error_code,
                message=error_message,
            )
            await self._event_repo.create(event)

        logger.warning(f"Device {device_id} error: {error_code} - {error_message}")

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
        return await self._device_repo.get_connected_devices(site_id, organization_id)

    def get_active_session(self, device_id: UUID) -> Optional[DeviceSession]:
        """
        Get active session for a device.

        Args:
            device_id: Device UUID.

        Returns:
            DeviceSession if device is connected, None otherwise.
        """
        session = self._active_sessions.get(device_id)
        if session:
            session.update_activity()
        return session

    async def cleanup_stale_sessions(
        self,
        timeout_seconds: int = 300,
    ) -> int:
        """
        Clean up stale device sessions.

        Args:
            timeout_seconds: Session timeout.

        Returns:
            Number of sessions cleaned up.
        """
        cleaned = 0
        stale_ids = []

        for device_id, session in self._active_sessions.items():
            if session.is_stale(timeout_seconds):
                stale_ids.append(device_id)

        for device_id in stale_ids:
            await self.handle_device_disconnect(device_id, "Session timeout")
            cleaned += 1

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} stale sessions")

        return cleaned

    # =========================================================================
    # Polling Management
    # =========================================================================

    async def get_devices_for_polling(
        self,
        limit: int = 100,
    ) -> List[DeviceRegistry]:
        """
        Get devices that need to be polled.

        Args:
            limit: Maximum devices to return.

        Returns:
            List of devices due for polling.
        """
        return await self._device_repo.get_devices_due_for_polling(limit)

    async def mark_device_polled(
        self,
        device_id: UUID,
        polled_at: Optional[datetime] = None,
    ) -> None:
        """
        Mark device as polled and update next poll time.

        Args:
            device_id: Device UUID.
            polled_at: Poll timestamp.
        """
        await self._device_repo.update_poll_time(device_id, polled_at)

        # Update session activity if active
        if device_id in self._active_sessions:
            self._active_sessions[device_id].update_activity()

    # =========================================================================
    # Authentication
    # =========================================================================

    async def generate_device_token(
        self,
        device_id: UUID,
        expires_in_days: int = 365,
    ) -> str:
        """
        Generate authentication token for a device.

        Args:
            device_id: Device UUID.
            expires_in_days: Token validity period.

        Returns:
            Plain-text token (store securely).
        """
        return await self._device_repo.generate_auth_token(device_id, expires_in_days)

    async def validate_device_token(
        self,
        device_id: UUID,
        token: str,
    ) -> bool:
        """
        Validate device authentication token.

        Args:
            device_id: Device UUID.
            token: Token to validate.

        Returns:
            True if valid, False otherwise.
        """
        return await self._device_repo.validate_auth_token(device_id, token)

    async def authenticate_device(
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
        return await self._device_repo.authenticate_by_serial(serial_number, token)

    async def revoke_device_token(self, device_id: UUID) -> None:
        """
        Revoke device authentication token.

        Args:
            device_id: Device UUID.
        """
        await self._device_repo.revoke_auth_token(device_id)

    # =========================================================================
    # Synchronization
    # =========================================================================

    async def mark_devices_synced(
        self,
        device_ids: List[UUID],
    ) -> int:
        """
        Mark devices as synced with System A.

        Args:
            device_ids: List of device UUIDs.

        Returns:
            Number of devices marked.
        """
        return await self._device_repo.mark_synced(device_ids)

    async def get_unsynced_devices(
        self,
        minutes: int = 5,
    ) -> List[DeviceRegistry]:
        """
        Get devices that need synchronization.

        Args:
            minutes: Consider unsynced if older than this.

        Returns:
            List of unsynced devices.
        """
        return await self._device_repo.get_unsynced_devices(timedelta(minutes=minutes))

    # =========================================================================
    # Statistics
    # =========================================================================

    async def get_connection_stats(
        self,
        organization_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """
        Get device connection statistics.

        Args:
            organization_id: Optional organization filter.

        Returns:
            Dict with connection statistics.
        """
        status_counts = await self._device_repo.get_connection_stats(organization_id)
        type_counts = await self._device_repo.get_device_type_counts(organization_id)

        return {
            "by_status": status_counts,
            "by_type": type_counts,
            "total_devices": sum(status_counts.values()),
            "active_sessions": len(self._active_sessions),
        }

    async def get_device_summary(self, device_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive device summary.

        Args:
            device_id: Device UUID.

        Returns:
            Dict with device summary, or None if not found.
        """
        device = await self._device_repo.get_by_id(device_id)
        if not device:
            return None

        session = self._active_sessions.get(device_id)

        return {
            "device_id": str(device.device_id),
            "site_id": str(device.site_id),
            "organization_id": str(device.organization_id),
            "device_type": device.device_type.value if isinstance(device.device_type, DeviceType) else device.device_type,
            "serial_number": device.serial_number,
            "protocol": device.protocol,
            "connection_status": device.connection_status.value if isinstance(device.connection_status, ConnectionStatus) else device.connection_status,
            "is_connected": device.is_connected(),
            "last_connected_at": device.last_connected_at.isoformat() if device.last_connected_at else None,
            "last_polled_at": device.last_polled_at.isoformat() if device.last_polled_at else None,
            "polling_interval_seconds": device.polling_interval_seconds,
            "reconnect_count": device.reconnect_count,
            "session": {
                "session_id": session.session_id,
                "connected_at": session.connected_at.isoformat(),
                "last_activity_at": session.last_activity_at.isoformat(),
                "client_address": session.client_address,
            } if session else None,
        }
