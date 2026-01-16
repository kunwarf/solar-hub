"""
Telemetry domain entities for System B.

These entities represent raw telemetry data stored in TimescaleDB.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID


class DataQuality(str, Enum):
    """Data quality indicators for telemetry readings."""
    GOOD = "good"                   # Normal reading
    INTERPOLATED = "interpolated"   # Interpolated from nearby values
    ESTIMATED = "estimated"         # Estimated value
    SUSPECT = "suspect"             # Suspicious reading (out of range)
    MISSING = "missing"             # Gap marker
    INVALID = "invalid"             # Invalid/corrupt data


class DeviceType(str, Enum):
    """Types of devices supported."""
    INVERTER = "inverter"
    METER = "meter"
    BATTERY = "battery"
    WEATHER_STATION = "weather_station"
    SENSOR = "sensor"
    GATEWAY = "gateway"


class ConnectionStatus(str, Enum):
    """Device connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class TelemetryPoint:
    """
    A single telemetry data point.

    Represents one metric reading from a device at a specific time.
    """
    time: datetime
    device_id: UUID
    site_id: UUID
    metric_name: str
    metric_value: Optional[float] = None
    metric_value_str: Optional[str] = None  # For string/enum values
    quality: DataQuality = DataQuality.GOOD
    unit: Optional[str] = None
    source: Optional[str] = None  # 'device', 'calculated', 'manual'
    tags: Optional[Dict[str, Any]] = None
    raw_value: Optional[bytes] = None
    received_at: datetime = field(default_factory=datetime.utcnow)
    processed: bool = False

    def __post_init__(self):
        if self.metric_value is None and self.metric_value_str is None:
            raise ValueError("Either metric_value or metric_value_str must be provided")


@dataclass
class TelemetryBatch:
    """
    A batch of telemetry points for efficient ingestion.
    """
    points: List[TelemetryPoint]
    source_type: str  # 'mqtt', 'http', 'modbus', 'file'
    source_identifier: Optional[str] = None
    batch_id: Optional[UUID] = None

    @property
    def device_count(self) -> int:
        return len(set(p.device_id for p in self.points))

    @property
    def record_count(self) -> int:
        return len(self.points)

    def group_by_device(self) -> Dict[UUID, List[TelemetryPoint]]:
        """Group points by device ID."""
        grouped: Dict[UUID, List[TelemetryPoint]] = {}
        for point in self.points:
            if point.device_id not in grouped:
                grouped[point.device_id] = []
            grouped[point.device_id].append(point)
        return grouped


@dataclass
class TelemetryAggregate:
    """
    Aggregated telemetry data for a time bucket.

    Used for continuous aggregates (5-min, hourly, daily).
    """
    bucket: datetime
    device_id: UUID
    site_id: UUID
    metric_name: str
    avg_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    first_value: Optional[float] = None
    last_value: Optional[float] = None
    delta_value: Optional[float] = None  # For cumulative metrics
    sample_count: int = 0
    good_count: int = 0

    @property
    def data_quality_percent(self) -> float:
        """Percentage of good quality readings."""
        if self.sample_count == 0:
            return 0.0
        return (self.good_count / self.sample_count) * 100.0


@dataclass
class MetricDefinition:
    """
    Definition of a standard metric.
    """
    metric_name: str
    display_name: str
    unit: str
    data_type: str  # 'float', 'integer', 'string', 'boolean'
    device_types: List[DeviceType]
    description: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    aggregation_method: str = "avg"  # 'avg', 'sum', 'min', 'max', 'last'
    is_cumulative: bool = False  # True for counters like energy_total

    def validate_value(self, value: float) -> bool:
        """Check if a value is within valid range."""
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        return True


# Standard metric names as constants
class Metrics:
    """Standard metric name constants."""
    # Power
    POWER_AC = "power_ac"
    POWER_DC = "power_dc"
    POWER_ACTIVE = "power_active"
    POWER_REACTIVE = "power_reactive"
    POWER_APPARENT = "power_apparent"

    # Voltage
    VOLTAGE_DC = "voltage_dc"
    VOLTAGE_AC = "voltage_ac"
    VOLTAGE_L1 = "voltage_l1"
    VOLTAGE_L2 = "voltage_l2"
    VOLTAGE_L3 = "voltage_l3"

    # Current
    CURRENT_DC = "current_dc"
    CURRENT_AC = "current_ac"
    CURRENT_L1 = "current_l1"
    CURRENT_L2 = "current_l2"
    CURRENT_L3 = "current_l3"

    # Energy (cumulative)
    ENERGY_TOTAL = "energy_total"
    ENERGY_TODAY = "energy_today"
    ENERGY_IMPORT = "energy_import"
    ENERGY_EXPORT = "energy_export"

    # Grid
    FREQUENCY = "frequency"
    POWER_FACTOR = "power_factor"

    # Temperature
    TEMPERATURE_INTERNAL = "temperature_internal"
    TEMPERATURE_AMBIENT = "temperature_ambient"
    TEMPERATURE_MODULE = "temperature_module"
    TEMPERATURE_BATTERY = "temperature_battery"

    # Battery
    BATTERY_SOC = "battery_soc"
    BATTERY_SOH = "battery_soh"
    BATTERY_VOLTAGE = "battery_voltage"
    BATTERY_CURRENT = "battery_current"
    BATTERY_POWER = "battery_power"
    BATTERY_CYCLES = "battery_cycles"

    # Weather
    IRRADIANCE = "irradiance"
    IRRADIANCE_POA = "irradiance_poa"
    WIND_SPEED = "wind_speed"
    WIND_DIRECTION = "wind_direction"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    RAINFALL = "rainfall"

    # Status
    STATUS = "status"
    ERROR_CODE = "error_code"
    WARNING_CODE = "warning_code"

    # MPPT
    MPPT_VOLTAGE = "mppt_voltage"
    MPPT_CURRENT = "mppt_current"
    MPPT_POWER = "mppt_power"
