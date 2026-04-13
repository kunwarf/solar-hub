"""
HTTP client for System B API communication.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
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


@dataclass
class TelemetryAggregate:
    """Aggregated telemetry bucket from System B."""
    bucket: datetime
    avg: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    first: Optional[float] = None
    last: Optional[float] = None
    delta: Optional[float] = None
    sample_count: int = 0
    quality_percent: float = 100.0


@dataclass
class DeviceLatestTelemetry:
    """Latest telemetry readings for a device from System B."""
    device_id: UUID
    readings: Dict[str, Dict[str, Any]] = field(default_factory=dict)


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
            url = f"/api/v1/devices/serial/{serial_number}"
            logger.info("System B request: GET %s%s", self._base_url, url)
            response = await client.get(url)
            logger.info("System B response: status=%d, body=%s", response.status_code, response.text[:500] if response.text else "empty")

            if response.status_code == 404:
                logger.warning("Device not found in System B: %s", serial_number)
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
            url = f"/api/v1/devices/{device_id}/claim"
            payload = {
                "owner_id": str(owner_id),
                "site_id": str(site_id),
                "organization_id": str(organization_id),
            }
            logger.info("System B request: PUT %s%s, payload=%s", self._base_url, url, payload)
            response = await client.put(url, json=payload)
            logger.info("System B response: status=%d, body=%s", response.status_code, response.text[:500] if response.text else "empty")

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

    # =========================================================================
    # Telemetry Query Methods
    # =========================================================================

    async def get_device_aggregates(
        self,
        device_id: UUID,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "1 hour",
    ) -> List[TelemetryAggregate]:
        """
        Get time-bucketed aggregates for a device metric.

        Args:
            device_id: Device UUID in System B
            metric_name: Metric to aggregate (e.g., 'pv_power_w')
            start_time: Start of time range
            end_time: End of time range
            bucket_interval: Aggregation interval (e.g., '1 hour', '1 day')

        Returns:
            List of TelemetryAggregate buckets
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/telemetry/aggregate/{device_id}/{metric_name}"
            params = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "bucket_interval": bucket_interval,
            }
            logger.info("System B request: GET %s%s params=%s", self._base_url, url, params)
            response = await client.get(url, params=params)
            logger.info("System B response: status=%d, records=%s",
                        response.status_code,
                        len(response.json()) if response.status_code == 200 else "error")

            response.raise_for_status()
            data = response.json()

            return [
                TelemetryAggregate(
                    bucket=datetime.fromisoformat(item["bucket"]),
                    avg=item.get("avg"),
                    min=item.get("min"),
                    max=item.get("max"),
                    first=item.get("first"),
                    last=item.get("last"),
                    delta=item.get("delta"),
                    sample_count=item.get("sample_count", 0),
                    quality_percent=item.get("quality_percent", 100.0),
                )
                for item in data
            ]

        except httpx.HTTPStatusError as e:
            logger.error("System B aggregate error: %s", e)
            raise SystemBClientError(
                f"Failed to get aggregates: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_site_daily_peaks(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """
        Get today's peak instantaneous power metrics for a site from System B.

        Args:
            site_id: Site UUID.
            start_time: UTC start of "today" in the site's local timezone.
            end_time: UTC end of "today" in the site's local timezone.

        Returns:
            Dict with 'peaks' key containing pv, load, export, import sub-dicts,
            each with value_w (float|None) and occurred_at (ISO string|None).
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/telemetry/daily-peaks/{site_id}"
            params = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
            }
            logger.info("System B request: GET %s%s params=%s", self._base_url, url, params)
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("System B daily-peaks error: %s", e)
            raise SystemBClientError(
                f"Failed to get daily peaks: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_site_telemetry(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        metric_names: Optional[List[str]] = None,
        device_ids: Optional[List[UUID]] = None,
        limit: int = 50000,
    ) -> List[Dict[str, Any]]:
        """
        Get telemetry records for all devices at a site.

        Args:
            site_id: Site UUID
            start_time: Start of time range
            end_time: End of time range
            metric_names: Optional filter by metric names
            device_ids: Optional filter by device IDs
            limit: Maximum records to return

        Returns:
            List of telemetry records as dicts
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/telemetry/site/{site_id}"
            params: Dict[str, Any] = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "limit": limit,
            }
            if metric_names:
                params["metric_names"] = metric_names
            if device_ids:
                params["device_ids"] = [str(d) for d in device_ids]

            logger.info("System B request: GET %s%s params=%s", self._base_url, url, params)
            response = await client.get(url, params=params)
            logger.info("System B response: status=%d, records=%s",
                        response.status_code,
                        len(response.json()) if response.status_code == 200 else "error")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("System B site telemetry error: %s", e)
            raise SystemBClientError(
                f"Failed to get site telemetry: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_site_power_chart(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
        bucket_interval: str = "5 minutes",
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated power data for chart display.

        Args:
            site_id: Site UUID
            start_time: Start of time range
            end_time: End of time range
            bucket_interval: Aggregation interval

        Returns:
            List of power chart data points as dicts
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/telemetry/power-chart/{site_id}"
            params = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "bucket_interval": bucket_interval,
            }
            logger.info("System B request: GET %s%s params=%s", self._base_url, url, params)
            response = await client.get(url, params=params)
            logger.info("System B response: status=%d, records=%s",
                        response.status_code,
                        len(response.json()) if response.status_code == 200 else "error")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("System B power chart error: %s", e)
            raise SystemBClientError(
                f"Failed to get power chart: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_site_energy_chart(
        self,
        site_id: UUID,
        period: str = "day",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        bucket_interval: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive energy chart data for a site.

        Returns aggregated energy metrics with calculated efficiency
        and self-sufficiency from System B's TimescaleDB.

        Args:
            site_id: Site UUID
            period: Time period - "day" (24h), "week" (7d), "month" (30d), or "custom"
            start_time: Custom range start (required when period="custom")
            end_time: Custom range end (required when period="custom")
            bucket_interval: Custom bucket size e.g. "1 hour", "1 day" (optional for custom)

        Returns:
            Dict with site_id, period, start_time, end_time, bucket_interval, and data array

        Raises:
            SystemBClientError: If request fails
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/telemetry/energy-chart/{site_id}"
            params: Dict[str, Any] = {"period": period}
            if start_time is not None:
                params["start_time"] = start_time.isoformat()
            if end_time is not None:
                params["end_time"] = end_time.isoformat()
            if bucket_interval is not None:
                params["bucket_interval"] = bucket_interval

            logger.info("System B request: GET %s%s params=%s", self._base_url, url, params)
            response = await client.get(url, params=params)
            logger.info("System B response: status=%d, points=%s",
                        response.status_code,
                        len(response.json().get("data", [])) if response.status_code == 200 else "error")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("System B energy chart error: %s", e)
            raise SystemBClientError(
                f"Failed to get energy chart: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_device_latest(
        self,
        device_id: UUID,
    ) -> Optional[DeviceLatestTelemetry]:
        """
        Get the latest telemetry readings for a device.

        Args:
            device_id: Device UUID in System B

        Returns:
            DeviceLatestTelemetry if found, None if no readings exist
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/telemetry/latest/{device_id}"
            logger.info("System B request: GET %s%s", self._base_url, url)
            response = await client.get(url)
            logger.info("System B response: status=%d", response.status_code)

            if response.status_code == 404:
                return None

            response.raise_for_status()
            data = response.json()

            return DeviceLatestTelemetry(
                device_id=UUID(str(data["device_id"])),
                readings=data.get("readings", {}),
            )

        except httpx.HTTPStatusError as e:
            logger.error("System B latest telemetry error: %s", e)
            raise SystemBClientError(
                f"Failed to get latest telemetry: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_hourly_energy_summary(
        self,
        site_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Get hourly energy aggregates from System B for billing calculations.

        This method fetches hourly-bucketed energy data from System B's
        TimescaleDB continuous aggregates and returns it in a format
        suitable for the billing module.

        Args:
            site_id: Site UUID
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)

        Returns:
            List of dicts with hourly energy data, each containing:
                - timestamp: Hour timestamp
                - pv_kwh: Solar PV generation (kWh)
                - load_kwh: Load consumption (kWh)
                - grid_import_kwh: Energy imported from grid (kWh)
                - grid_export_kwh: Energy exported to grid (kWh)

        Raises:
            SystemBClientError: On API errors or connection failures
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/telemetry/energy-chart/{site_id}"

            # For billing, we need hourly buckets for the exact time range
            # System B's energy-chart endpoint supports period="custom" with custom time ranges
            # Use "auto" to let System B select the best aggregate table with DELTA calculations
            params = {
                "period": "custom",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "bucket_interval": "auto",
            }

            logger.info(
                "System B billing request: GET %s%s params=%s (start=%s, end=%s)",
                self._base_url, url, params, start_time, end_time
            )

            response = await client.get(url, params=params)

            logger.info(
                "System B billing response: status=%d, points=%s",
                response.status_code,
                len(response.json().get("data", [])) if response.status_code == 200 else "error"
            )

            response.raise_for_status()
            data = response.json()

            # Extract data points from response
            data_points = data.get("data", [])

            logger.info(
                "Fetched %d hourly data points from System B for site %s",
                len(data_points), site_id
            )

            return data_points

        except httpx.HTTPStatusError as e:
            logger.error("System B billing energy error: %s", e)
            raise SystemBClientError(
                f"Failed to get hourly energy summary: {e.response.text}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    # =========================================================================
    # Command Methods
    # =========================================================================

    async def send_command(
        self,
        device_id: UUID,
        site_id: UUID,
        command_type: str,
        command_params: Optional[Dict[str, Any]] = None,
        device_serial: Optional[str] = None,
        priority: int = 5,
        expires_in_minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        Send a command to a device via System B.

        Posts to System B's /api/v1/commands/ endpoint.

        Args:
            device_id: Device UUID in System B
            site_id: Site UUID
            command_type: Command type string
            command_params: Optional command parameters
            device_serial: Device serial number for direct lookup in System B
            priority: Command priority (1-10, default 5)
            expires_in_minutes: Expiry time in minutes

        Returns:
            Command response dict from System B

        Raises:
            SystemBClientError: On API errors
        """
        try:
            client = await self._get_client()
            url = "/api/v1/commands/"
            payload: Dict[str, Any] = {
                "device_id": str(device_id),
                "site_id": str(site_id),
                "command_type": command_type,
                "priority": priority,
                "expires_in_minutes": expires_in_minutes,
            }
            if command_params:
                payload["command_params"] = command_params
            if device_serial:
                payload["device_serial"] = device_serial

            logger.info("System B request: POST %s%s, payload=%s", self._base_url, url, payload)
            response = await client.post(url, json=payload)
            logger.info("System B response: status=%d, body=%s", response.status_code, response.text[:500] if response.text else "empty")

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("System B command error: %s", e)
            raise SystemBClientError(
                f"Failed to send command: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_command_status(self, command_id: UUID) -> Dict[str, Any]:
        """
        Get the status of a command from System B.

        Args:
            command_id: Command UUID

        Returns:
            Command status dict from System B

        Raises:
            SystemBClientError: On API errors
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/commands/{command_id}"
            logger.info("System B request: GET %s%s", self._base_url, url)
            response = await client.get(url)
            logger.info("System B response: status=%d", response.status_code)

            if response.status_code == 404:
                raise SystemBClientError("Command not found", status_code=404)

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("System B command status error: %s", e)
            raise SystemBClientError(
                f"Failed to get command status: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    async def get_device_commands(
        self,
        device_id: UUID,
        limit: int = 10,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent commands for a device from System B.

        Args:
            device_id: Device UUID in System B
            limit: Max number of commands to return
            status_filter: Optional status to filter by

        Returns:
            List of command dicts from System B

        Raises:
            SystemBClientError: On API errors
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/commands/device/{device_id}"
            params: Dict[str, Any] = {"limit": limit}
            if status_filter:
                params["status"] = status_filter

            logger.info("System B request: GET %s%s params=%s", self._base_url, url, params)
            response = await client.get(url, params=params)
            logger.info("System B response: status=%d", response.status_code)

            if response.status_code == 404:
                return []

            response.raise_for_status()
            data = response.json()
            # System B returns {"commands": [...], "total": N}
            return data.get("commands", data) if isinstance(data, dict) else data

        except httpx.HTTPStatusError as e:
            logger.error("System B device commands error: %s", e)
            raise SystemBClientError(
                f"Failed to get device commands: {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
            logger.error("System B connection error: %s", e)
            raise SystemBClientError(f"Connection error: {str(e)}")

    # =========================================================================
    # Device Management Methods
    # =========================================================================

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
            url = "/api/v1/devices/orphan"
            logger.info("System B request: GET %s%s", self._base_url, url)
            response = await client.get(url)
            logger.info("System B response: status=%d, body=%s", response.status_code, response.text[:500] if response.text else "empty")
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

    async def get_settings_schema(self, protocol: str) -> dict:
        """
        Get the settings schema for an inverter protocol from System B.

        Args:
            protocol: Protocol ID (e.g. "powdrive", "senergy", "voltronic_pi30")

        Returns:
            Schema dict with 'version', 'family', and 'groups' keys.

        Raises:
            SystemBClientError: If the protocol is unknown (404) or on connection error.
        """
        try:
            client = await self._get_client()
            url = f"/api/v1/settings/schema/{protocol}"
            logger.info("System B request: GET %s%s", self._base_url, url)
            response = await client.get(url)
            logger.info(
                "System B response: status=%d, body=%s",
                response.status_code,
                response.text[:200] if response.text else "empty",
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise SystemBClientError(
                f"Failed to get settings schema for '{protocol}': {e.response.text}",
                status_code=e.response.status_code,
            )
        except httpx.RequestError as e:
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
        logger.info("Creating System B client with base_url=%s", base_url)
        _system_b_client = SystemBClient(base_url=base_url, api_key=api_key)
    return _system_b_client
