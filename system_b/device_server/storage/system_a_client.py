"""
System A API client for device registration.

Communicates with System A to register devices, update status,
and sync device snapshots.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

try:
    import httpx
except ImportError:
    httpx = None

from ..config import DeviceServerSettings, get_device_server_settings
from ..devices.device_state import DeviceState, DeviceStatus

logger = logging.getLogger(__name__)


class SystemAClient:
    """
    Client for System A API.

    Responsibilities:
    - Register new devices
    - Update device status
    - Update device snapshots
    """

    def __init__(
        self,
        settings: Optional[DeviceServerSettings] = None,
    ):
        """
        Initialize the System A client.

        Args:
            settings: Server settings.
        """
        self.settings = settings or get_device_server_settings()
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        """Initialize HTTP client."""
        if httpx is None:
            logger.warning(
                "httpx not installed, System A integration disabled"
            )
            return

        system_a = self.settings.system_a
        self._client = httpx.AsyncClient(
            base_url=system_a.base_url,
            headers={
                "Authorization": f"Bearer {system_a.api_key}",
                "Content-Type": "application/json",
            },
            timeout=system_a.timeout,
        )
        logger.info(f"System A client initialized: {system_a.base_url}")

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("System A client disconnected")

    async def register_device(
        self,
        site_id: UUID,
        serial_number: str,
        device_type: str,
        protocol_id: str,
        model: Optional[str] = None,
        manufacturer: Optional[str] = None,
    ) -> Optional[UUID]:
        """
        Register a device in System A.

        Args:
            site_id: Site ID to register device under.
            serial_number: Device serial number.
            device_type: Type of device (inverter, meter, battery).
            protocol_id: Protocol identifier.
            model: Device model.
            manufacturer: Device manufacturer.

        Returns:
            Device UUID if registered, None on failure.
        """
        if not self._client:
            logger.debug("No System A client, skipping registration")
            return None

        payload = {
            "site_id": str(site_id),
            "serial_number": serial_number,
            "device_type": device_type,
            "protocol": protocol_id,
            "model": model,
            "manufacturer": manufacturer,
            "status": "online",
        }

        try:
            response = await self._client.post(
                "/devices/register",
                json=payload,
            )

            if response.status_code == 201:
                data = response.json()
                device_id = UUID(data["device_id"])
                logger.info(
                    f"Registered device {serial_number} in System A "
                    f"as {device_id}"
                )
                return device_id

            elif response.status_code == 409:
                # Device already exists, get existing ID
                data = response.json()
                device_id = UUID(data.get("device_id", ""))
                logger.info(
                    f"Device {serial_number} already registered "
                    f"as {device_id}"
                )
                return device_id

            else:
                logger.error(
                    f"Failed to register device: {response.status_code} - "
                    f"{response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error registering device: {e}")
            return None

    async def update_device_status(
        self,
        device_id: UUID,
        status: DeviceStatus,
        message: Optional[str] = None,
    ) -> bool:
        """
        Update device status in System A.

        Args:
            device_id: Device ID.
            status: New status.
            message: Optional status message.

        Returns:
            True if updated successfully.
        """
        if not self._client:
            return False

        payload = {
            "status": status.value,
            "status_message": message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            response = await self._client.patch(
                f"/devices/{device_id}/status",
                json=payload,
            )

            if response.status_code == 200:
                logger.debug(f"Updated device {device_id} status to {status}")
                return True
            else:
                logger.error(
                    f"Failed to update status: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error updating device status: {e}")
            return False

    async def update_device_snapshot(
        self,
        device_id: UUID,
        telemetry: Dict[str, Any],
    ) -> bool:
        """
        Update device telemetry snapshot in System A.

        Args:
            device_id: Device ID.
            telemetry: Latest telemetry data.

        Returns:
            True if updated successfully.
        """
        if not self._client:
            return False

        # Remove metadata fields
        snapshot = {
            k: v for k, v in telemetry.items()
            if not k.startswith("_")
        }

        payload = {
            "snapshot": snapshot,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            response = await self._client.patch(
                f"/devices/{device_id}/snapshot",
                json=payload,
            )

            if response.status_code == 200:
                logger.debug(f"Updated snapshot for device {device_id}")
                return True
            else:
                logger.warning(
                    f"Failed to update snapshot: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error updating device snapshot: {e}")
            return False

    async def get_device(self, device_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get device details from System A.

        Args:
            device_id: Device ID.

        Returns:
            Device data or None.
        """
        if not self._client:
            return None

        try:
            response = await self._client.get(f"/devices/{device_id}")

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting device: {e}")
            return None

    async def get_device_by_serial(
        self,
        serial_number: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get device by serial number from System A.

        Args:
            serial_number: Device serial number.

        Returns:
            Device data or None.
        """
        if not self._client:
            return None

        try:
            response = await self._client.get(
                "/devices/by-serial",
                params={"serial_number": serial_number},
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting device by serial: {e}")
            return None

    async def get_site_for_device(
        self,
        remote_addr: str,
    ) -> Optional[UUID]:
        """
        Get site ID for a device based on its remote address.

        This can be used to auto-assign devices to sites based on
        IP address or other criteria.

        Args:
            remote_addr: Remote address of device.

        Returns:
            Site UUID or None.
        """
        if not self._client:
            return None

        try:
            response = await self._client.get(
                "/sites/by-address",
                params={"address": remote_addr},
            )

            if response.status_code == 200:
                data = response.json()
                return UUID(data["site_id"]) if data.get("site_id") else None
            else:
                return None

        except Exception as e:
            logger.debug(f"Error getting site for device: {e}")
            return None

    async def heartbeat(self) -> bool:
        """
        Send heartbeat to System A.

        Returns:
            True if System A is reachable.
        """
        if not self._client:
            return False

        try:
            response = await self._client.get("/health")
            return response.status_code == 200

        except Exception:
            return False

    async def batch_update_status(
        self,
        updates: Dict[UUID, DeviceStatus],
    ) -> int:
        """
        Batch update device statuses.

        Args:
            updates: Dictionary of device_id to new status.

        Returns:
            Number of successful updates.
        """
        if not self._client:
            return 0

        success_count = 0
        for device_id, status in updates.items():
            if await self.update_device_status(device_id, status):
                success_count += 1

        return success_count
