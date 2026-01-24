"""
HTTP client for System B API communication.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Device information from System B."""
    id: UUID
    serial_number: str
    device_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    protocol: Optional[str] = None
    status: str = "orphan"
    owner_id: Optional[UUID] = None
    site_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    connection_status: str = "disconnected"
    is_claimed: bool = False


class SystemBClientError(Exception):
    """Base exception for System B client errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class DeviceNotFoundError(SystemBClientError):
    """Device not found in System B."""
    pass


class DeviceAlreadyClaimedError(SystemBClientError):
    """Device is already claimed by another user."""
    pass


class SystemBClient:
    """
    HTTP client for communicating with System B telemetry service.

    Handles device registration, claiming, and status queries.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        timeout: float = 30.0,
        api_key: Optional[str] = None,
    ):
        """
        Initialize System B client.

        Args:
            base_url: System B API base URL
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._get_headers(),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_device_by_serial(self, serial_number: str) -> Optional[DeviceInfo]:
        """
        Get device by serial number.

        Args:
            serial_number: Device serial number

        Returns:
            DeviceInfo if found, None otherwise

        Raises:
            SystemBClientError: On API errors
        """
        try:
            client = await self._get_client()
            response = await client.get(f"/api/v1/devices/serial/{serial_number}")

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            return DeviceInfo(
                id=UUID(data["id"]),
                serial_number=data["serial_number"],
                device_type=data["device_type"],
                manufacturer=data.get("manufacturer"),
                model=data.get("model"),
                firmware_version=data.get("firmware_version"),
                protocol=data.get("protocol"),
                status=data.get("status", "orphan"),
                owner_id=UUID(data["owner_id"]) if data.get("owner_id") else None,
                site_id=UUID(data["site_id"]) if data.get("site_id") else None,
                organization_id=UUID(data["organization_id"]) if data.get("organization_id") else None,
                connection_status=data.get("connection_status", "disconnected"),
                is_claimed=data.get("status") == "claimed",
            )

        except httpx.HTTPStatusError as e:
            logger.error("System B API error: %s", e)
            raise SystemBClientError(
                f"Failed to get device: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def claim_device(
        self,
        device_id: UUID,
        owner_id: UUID,
        site_id: UUID,
        organization_id: UUID,
    ) -> DeviceInfo:
        """
        Claim an orphan device for a user.

        Args:
            device_id: Device UUID in System B
            owner_id: User UUID who is claiming the device
            site_id: Site UUID to attach the device to
            organization_id: Organization UUID

        Returns:
            Updated DeviceInfo

        Raises:
            DeviceNotFoundError: If device doesn't exist
            DeviceAlreadyClaimedError: If device is already claimed
            SystemBClientError: On other API errors
        """
        try:
            client = await self._get_client()
            response = await client.put(
                f"/api/v1/devices/{device_id}/claim",
                json={
                    "owner_id": str(owner_id),
                    "site_id": str(site_id),
                    "organization_id": str(organization_id),
                }
            )

            if response.status_code == 404:
                raise DeviceNotFoundError("Device not found", status_code=404)

            if response.status_code == 400:
                data = response.json()
                if "already claimed" in data.get("detail", "").lower():
                    raise DeviceAlreadyClaimedError("Device is already claimed", status_code=400)
                raise SystemBClientError(data.get("detail", "Bad request"), status_code=400)

            response.raise_for_status()
            data = response.json()

            device_data = data.get("device", {})
            return DeviceInfo(
                id=UUID(device_data["id"]),
                serial_number=device_data["serial_number"],
                device_type=device_data["device_type"],
                manufacturer=device_data.get("manufacturer"),
                model=device_data.get("model"),
                firmware_version=device_data.get("firmware_version"),
                protocol=device_data.get("protocol"),
                status=device_data.get("status", "claimed"),
                owner_id=UUID(device_data["owner_id"]) if device_data.get("owner_id") else None,
                site_id=UUID(device_data["site_id"]) if device_data.get("site_id") else None,
                organization_id=UUID(device_data["organization_id"]) if device_data.get("organization_id") else None,
                connection_status=device_data.get("connection_status", "disconnected"),
                is_claimed=True,
            )

        except httpx.HTTPStatusError as e:
            logger.error("System B claim error: %s", e)
            raise SystemBClientError(
                f"Failed to claim device: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def release_device(self, device_id: UUID) -> DeviceInfo:
        """
        Release a claimed device back to orphan state.

        Args:
            device_id: Device UUID

        Returns:
            Updated DeviceInfo

        Raises:
            DeviceNotFoundError: If device doesn't exist
            SystemBClientError: On API errors
        """
        try:
            client = await self._get_client()
            response = await client.put(f"/api/v1/devices/{device_id}/release")

            if response.status_code == 404:
                raise DeviceNotFoundError("Device not found", status_code=404)

            response.raise_for_status()
            data = response.json()

            device_data = data.get("device", {})
            return DeviceInfo(
                id=UUID(device_data["id"]),
                serial_number=device_data["serial_number"],
                device_type=device_data["device_type"],
                manufacturer=device_data.get("manufacturer"),
                model=device_data.get("model"),
                firmware_version=device_data.get("firmware_version"),
                protocol=device_data.get("protocol"),
                status=device_data.get("status", "orphan"),
                owner_id=None,
                site_id=None,
                organization_id=None,
                connection_status=device_data.get("connection_status", "disconnected"),
                is_claimed=False,
            )

        except httpx.HTTPStatusError as e:
            logger.error("System B release error: %s", e)
            raise SystemBClientError(
                f"Failed to release device: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_orphan_devices(self) -> list[DeviceInfo]:
        """
        Get all orphan devices.

        Returns:
            List of orphan DeviceInfo objects

        Raises:
            SystemBClientError: On API errors
        """
        try:
            client = await self._get_client()
            response = await client.get("/api/v1/devices/orphan")
            response.raise_for_status()
            data = response.json()

            devices = []
            for device_data in data:
                devices.append(DeviceInfo(
                    id=UUID(device_data["id"]),
                    serial_number=device_data["serial_number"],
                    device_type=device_data["device_type"],
                    manufacturer=device_data.get("manufacturer"),
                    model=device_data.get("model"),
                    firmware_version=device_data.get("firmware_version"),
                    protocol=device_data.get("protocol"),
                    status="orphan",
                    owner_id=None,
                    site_id=None,
                    organization_id=None,
                    connection_status=device_data.get("connection_status", "disconnected"),
                    is_claimed=False,
                ))
            return devices

        except httpx.HTTPStatusError as e:
            logger.error("System B API error: %s", e)
            raise SystemBClientError(
                f"Failed to get orphan devices: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")


# Singleton instance for dependency injection
_system_b_client: Optional[SystemBClient] = None


def get_system_b_client() -> SystemBClient:
    """Get or create System B client singleton."""
    global _system_b_client
    if _system_b_client is None:
        import os
        base_url = os.getenv("SYSTEM_B_URL", "http://localhost:8001")
        api_key = os.getenv("SYSTEM_B_API_KEY")
        _system_b_client = SystemBClient(base_url=base_url, api_key=api_key)
    return _system_b_client
