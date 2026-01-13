"""
Device domain entity and related value objects.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from .base import AggregateRoot, utc_now
from ..exceptions import ValidationException, BusinessRuleViolationException


class DeviceType(str, Enum):
    """Types of devices in a solar installation."""
    INVERTER = "inverter"              # Solar inverter
    METER = "meter"                    # Energy meter
    BATTERY = "battery"                # Battery storage
    WEATHER_STATION = "weather_station"  # Weather monitoring
    SENSOR = "sensor"                  # Generic sensor
    CONTROLLER = "controller"          # System controller
    GATEWAY = "gateway"                # Communication gateway
    OTHER = "other"


class DeviceStatus(str, Enum):
    """Device operational status."""
    PENDING = "pending"        # Registered but not yet connected
    ONLINE = "online"          # Connected and operating normally
    OFFLINE = "offline"        # Not communicating
    ERROR = "error"            # In error state
    MAINTENANCE = "maintenance"  # Under maintenance
    DECOMMISSIONED = "decommissioned"  # Removed from service


class ProtocolType(str, Enum):
    """Communication protocols supported."""
    MODBUS_TCP = "modbus_tcp"
    MODBUS_RTU = "modbus_rtu"
    MQTT = "mqtt"
    HTTP = "http"
    HTTPS = "https"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ConnectionConfig:
    """
    Device connection configuration (value object).

    Contains all necessary information to connect to the device.
    """
    protocol: ProtocolType
    host: Optional[str] = None          # IP or hostname
    port: Optional[int] = None
    slave_id: Optional[int] = None      # For Modbus
    topic_prefix: Optional[str] = None  # For MQTT
    endpoint: Optional[str] = None      # For HTTP
    username: Optional[str] = None
    password: Optional[str] = None      # Encrypted
    ssl_enabled: bool = False
    polling_interval_seconds: int = 30
    timeout_seconds: int = 10
    retry_attempts: int = 3
    custom_config: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Validate connection config."""
        errors = {}

        if self.protocol in (ProtocolType.MODBUS_TCP, ProtocolType.HTTP, ProtocolType.HTTPS):
            if not self.host:
                errors['host'] = ['Host is required for this protocol']

        if self.protocol == ProtocolType.MODBUS_TCP and not self.port:
            errors['port'] = ['Port is required for Modbus TCP']

        if self.protocol == ProtocolType.MODBUS_RTU and self.slave_id is None:
            errors['slave_id'] = ['Slave ID is required for Modbus RTU']

        if self.polling_interval_seconds < 1:
            errors['polling_interval_seconds'] = ['Polling interval must be at least 1 second']

        if self.timeout_seconds < 1:
            errors['timeout_seconds'] = ['Timeout must be at least 1 second']

        if errors:
            raise ValidationException(
                message="Invalid connection configuration",
                errors=errors
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (excluding sensitive data)."""
        return {
            'protocol': self.protocol.value,
            'host': self.host,
            'port': self.port,
            'slave_id': self.slave_id,
            'topic_prefix': self.topic_prefix,
            'endpoint': self.endpoint,
            'ssl_enabled': self.ssl_enabled,
            'polling_interval_seconds': self.polling_interval_seconds,
            'timeout_seconds': self.timeout_seconds,
            'retry_attempts': self.retry_attempts,
            'has_credentials': bool(self.username)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionConfig':
        """Create from dictionary."""
        return cls(
            protocol=ProtocolType(data.get('protocol', 'mqtt')),
            host=data.get('host'),
            port=data.get('port'),
            slave_id=data.get('slave_id'),
            topic_prefix=data.get('topic_prefix'),
            endpoint=data.get('endpoint'),
            username=data.get('username'),
            password=data.get('password'),
            ssl_enabled=data.get('ssl_enabled', False),
            polling_interval_seconds=data.get('polling_interval_seconds', 30),
            timeout_seconds=data.get('timeout_seconds', 10),
            retry_attempts=data.get('retry_attempts', 3),
            custom_config=data.get('custom_config')
        )


@dataclass(frozen=True)
class DeviceMetrics:
    """
    Current device metrics snapshot (value object).

    Represents the latest known state of the device.
    """
    power_output_w: Optional[float] = None
    energy_today_kwh: Optional[float] = None
    energy_total_kwh: Optional[float] = None
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    frequency_hz: Optional[float] = None
    temperature_c: Optional[float] = None
    battery_soc_percent: Optional[float] = None
    battery_power_w: Optional[float] = None
    grid_power_w: Optional[float] = None
    load_power_w: Optional[float] = None
    efficiency_percent: Optional[float] = None
    error_codes: List[str] = field(default_factory=list)
    recorded_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'power_output_w': self.power_output_w,
            'energy_today_kwh': self.energy_today_kwh,
            'energy_total_kwh': self.energy_total_kwh,
            'voltage_v': self.voltage_v,
            'current_a': self.current_a,
            'frequency_hz': self.frequency_hz,
            'temperature_c': self.temperature_c,
            'battery_soc_percent': self.battery_soc_percent,
            'battery_power_w': self.battery_power_w,
            'grid_power_w': self.grid_power_w,
            'load_power_w': self.load_power_w,
            'efficiency_percent': self.efficiency_percent,
            'error_codes': self.error_codes,
            'recorded_at': self.recorded_at.isoformat()
        }


@dataclass
class Device(AggregateRoot):
    """
    Device aggregate root.

    Represents a physical device (inverter, meter, etc.) at a site.
    """
    site_id: UUID
    organization_id: UUID
    device_type: DeviceType
    name: str
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: Optional[str] = None
    status: DeviceStatus = DeviceStatus.PENDING
    connection_config: Optional[ConnectionConfig] = None
    last_seen_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    latest_metrics: Optional[DeviceMetrics] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # Communication statistics
    total_messages_received: int = 0
    total_errors: int = 0
    uptime_percentage: float = 0.0

    # Constants
    OFFLINE_THRESHOLD_SECONDS = 300  # 5 minutes

    def __post_init__(self) -> None:
        """Validate device data."""
        self._validate()

    def _validate(self) -> None:
        """Validate device data."""
        errors = {}

        if not self.name or len(self.name.strip()) < 2:
            errors['name'] = ['Device name must be at least 2 characters']

        if len(self.name) > 200:
            errors['name'] = ['Device name cannot exceed 200 characters']

        if not self.manufacturer:
            errors['manufacturer'] = ['Manufacturer is required']

        if not self.model:
            errors['model'] = ['Model is required']

        if not self.serial_number:
            errors['serial_number'] = ['Serial number is required']

        if errors:
            raise ValidationException(
                message="Invalid device data",
                errors=errors
            )

    @property
    def is_online(self) -> bool:
        """Check if device is currently online."""
        if self.status != DeviceStatus.ONLINE:
            return False
        if self.last_seen_at is None:
            return False
        threshold = utc_now() - timedelta(seconds=self.OFFLINE_THRESHOLD_SECONDS)
        return self.last_seen_at > threshold

    @property
    def is_operational(self) -> bool:
        """Check if device is in operational state."""
        return self.status in (DeviceStatus.ONLINE, DeviceStatus.PENDING)

    @property
    def has_errors(self) -> bool:
        """Check if device has recent errors."""
        return self.status == DeviceStatus.ERROR

    @property
    def display_name(self) -> str:
        """Get display name for device."""
        return f"{self.name} ({self.manufacturer} {self.model})"

    def configure_connection(self, config: ConnectionConfig) -> None:
        """Set or update connection configuration."""
        self.connection_config = config
        self.mark_updated()

        from ..events.device_events import DeviceConnectionConfigured
        self.add_domain_event(DeviceConnectionConfigured(
            device_id=self.id,
            protocol=config.protocol.value
        ))

    def record_heartbeat(self) -> None:
        """Record that device has sent a heartbeat/message."""
        now = utc_now()
        was_offline = self.status == DeviceStatus.OFFLINE

        self.last_seen_at = now
        self.total_messages_received += 1

        if was_offline:
            self.status = DeviceStatus.ONLINE
            from ..events.device_events import DeviceOnline
            self.add_domain_event(DeviceOnline(device_id=self.id))

        self.mark_updated()

    def update_metrics(self, metrics: DeviceMetrics) -> None:
        """Update latest device metrics."""
        self.latest_metrics = metrics
        self.record_heartbeat()

    def record_error(self, error_message: str, error_code: Optional[str] = None) -> None:
        """Record a device error."""
        now = utc_now()
        self.last_error_at = now
        self.last_error_message = error_message
        self.total_errors += 1

        if self.status != DeviceStatus.ERROR:
            self.status = DeviceStatus.ERROR
            from ..events.device_events import DeviceError
            self.add_domain_event(DeviceError(
                device_id=self.id,
                error_message=error_message,
                error_code=error_code
            ))

        self.mark_updated()

    def clear_error(self) -> None:
        """Clear device error state."""
        if self.status == DeviceStatus.ERROR:
            self.status = DeviceStatus.ONLINE
            self.mark_updated()

            from ..events.device_events import DeviceErrorCleared
            self.add_domain_event(DeviceErrorCleared(device_id=self.id))

    def mark_offline(self) -> None:
        """Mark device as offline."""
        if self.status not in (DeviceStatus.OFFLINE, DeviceStatus.DECOMMISSIONED, DeviceStatus.MAINTENANCE):
            self.status = DeviceStatus.OFFLINE
            self.mark_updated()

            from ..events.device_events import DeviceOffline
            self.add_domain_event(DeviceOffline(device_id=self.id))

    def check_online_status(self) -> None:
        """Check and update online status based on last seen time."""
        if self.status == DeviceStatus.ONLINE and not self.is_online:
            self.mark_offline()

    def start_maintenance(self, reason: str, started_by: UUID) -> None:
        """Put device into maintenance mode."""
        old_status = self.status
        self.status = DeviceStatus.MAINTENANCE
        self.mark_updated()

        from ..events.device_events import DeviceMaintenanceStarted
        self.add_domain_event(DeviceMaintenanceStarted(
            device_id=self.id,
            reason=reason,
            started_by=started_by
        ))

    def end_maintenance(self, ended_by: UUID) -> None:
        """Take device out of maintenance mode."""
        if self.status != DeviceStatus.MAINTENANCE:
            raise BusinessRuleViolationException(
                message="Device is not in maintenance mode",
                rule="device_maintenance"
            )

        self.status = DeviceStatus.PENDING  # Will go online when data received
        self.mark_updated()

        from ..events.device_events import DeviceMaintenanceEnded
        self.add_domain_event(DeviceMaintenanceEnded(
            device_id=self.id,
            ended_by=ended_by
        ))

    def decommission(self, reason: str, decommissioned_by: UUID) -> None:
        """Permanently decommission device."""
        self.status = DeviceStatus.DECOMMISSIONED
        self.mark_updated()

        from ..events.device_events import DeviceDecommissioned
        self.add_domain_event(DeviceDecommissioned(
            device_id=self.id,
            site_id=self.site_id,
            reason=reason,
            decommissioned_by=decommissioned_by
        ))

    def update_details(
        self,
        name: Optional[str] = None,
        firmware_version: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """Update device details."""
        if name is not None:
            self.name = name
        if firmware_version is not None:
            self.firmware_version = firmware_version
        if metadata is not None:
            self.metadata.update(metadata)
        if tags is not None:
            self.tags = tags

        self._validate()
        self.mark_updated()

        from ..events.device_events import DeviceUpdated
        self.add_domain_event(DeviceUpdated(device_id=self.id))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize device to dictionary."""
        return {
            'id': str(self.id),
            'site_id': str(self.site_id),
            'organization_id': str(self.organization_id),
            'device_type': self.device_type.value,
            'name': self.name,
            'display_name': self.display_name,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'serial_number': self.serial_number,
            'firmware_version': self.firmware_version,
            'status': self.status.value,
            'is_online': self.is_online,
            'connection_config': self.connection_config.to_dict() if self.connection_config else None,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'last_error_at': self.last_error_at.isoformat() if self.last_error_at else None,
            'last_error_message': self.last_error_message,
            'latest_metrics': self.latest_metrics.to_dict() if self.latest_metrics else None,
            'metadata': self.metadata,
            'tags': self.tags,
            'total_messages_received': self.total_messages_received,
            'total_errors': self.total_errors,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @classmethod
    def create(
        cls,
        site_id: UUID,
        organization_id: UUID,
        device_type: DeviceType,
        name: str,
        manufacturer: str,
        model: str,
        serial_number: str,
        firmware_version: Optional[str] = None,
        connection_config: Optional[ConnectionConfig] = None
    ) -> 'Device':
        """
        Factory method to create a new device.

        Args:
            site_id: ID of the site this device belongs to
            organization_id: ID of the organization
            device_type: Type of device
            name: Device name
            manufacturer: Device manufacturer
            model: Device model
            serial_number: Device serial number
            firmware_version: Optional firmware version
            connection_config: Optional connection configuration

        Returns:
            New Device instance with DeviceRegistered event
        """
        device = cls(
            site_id=site_id,
            organization_id=organization_id,
            device_type=device_type,
            name=name.strip(),
            manufacturer=manufacturer.strip(),
            model=model.strip(),
            serial_number=serial_number.strip(),
            firmware_version=firmware_version,
            connection_config=connection_config
        )

        from ..events.device_events import DeviceRegistered
        device.add_domain_event(DeviceRegistered(
            device_id=device.id,
            site_id=site_id,
            organization_id=organization_id,
            device_type=device_type.value,
            serial_number=serial_number
        ))

        return device
