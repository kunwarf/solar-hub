"""
Configuration management for System B (Communication & Telemetry).

Uses Pydantic settings for validation and environment variable support.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TimescaleDBSettings(BaseSettings):
    """TimescaleDB configuration for telemetry storage."""

    model_config = SettingsConfigDict(
        env_prefix='TIMESCALE_',
        env_file='.env',
        extra='ignore'
    )

    host: str = Field(default='localhost', description='Database host')
    port: int = Field(default=5432, description='Database port')
    name: str = Field(default='solar_hub_telemetry', description='Database name')
    user: str = Field(default='postgres', description='Database user')
    password: str = Field(default='postgres', description='Database password')
    pool_size: int = Field(default=10, description='Connection pool size')
    max_overflow: int = Field(default=20, description='Max overflow connections')
    echo_sql: bool = Field(default=False, description='Echo SQL queries')

    # TimescaleDB-specific settings
    chunk_time_interval: str = Field(default='1 day', description='Hypertable chunk interval')
    retention_days: int = Field(default=90, description='Data retention in days')
    compression_after_days: int = Field(default=7, description='Compress data after days')

    @property
    def url(self) -> str:
        """Build database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        """Build synchronous database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis configuration for messaging and caching."""

    model_config = SettingsConfigDict(
        env_prefix='REDIS_',
        env_file='.env',
        extra='ignore'
    )

    host: str = Field(default='localhost', description='Redis host')
    port: int = Field(default=6379, description='Redis port')
    db: int = Field(default=1, description='Redis database number (separate from System A)')
    password: Optional[str] = Field(default=None, description='Redis password')
    ssl: bool = Field(default=False, description='Use SSL connection')

    # Stream settings
    stream_max_len: int = Field(default=100000, description='Max stream length')
    consumer_group: str = Field(default='telemetry_processors', description='Consumer group name')

    @property
    def url(self) -> str:
        """Build Redis URL."""
        auth = f":{self.password}@" if self.password else ""
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


class ProtocolSettings(BaseSettings):
    """Protocol handler configuration."""

    model_config = SettingsConfigDict(
        env_prefix='PROTOCOL_',
        env_file='.env',
        extra='ignore'
    )

    # MQTT Settings
    mqtt_enabled: bool = Field(default=True)
    mqtt_broker_host: str = Field(default='localhost')
    mqtt_broker_port: int = Field(default=1883)
    mqtt_username: Optional[str] = Field(default=None)
    mqtt_password: Optional[str] = Field(default=None)
    mqtt_client_id: str = Field(default='solar_hub_system_b')
    mqtt_topic_prefix: str = Field(default='solarhub/')

    # Modbus Settings
    modbus_enabled: bool = Field(default=True)
    modbus_tcp_port: int = Field(default=502)
    modbus_timeout: float = Field(default=5.0, description='Timeout in seconds')

    # HTTP Settings
    http_enabled: bool = Field(default=True)
    http_timeout: float = Field(default=30.0, description='HTTP timeout in seconds')


class DeviceAuthSettings(BaseSettings):
    """Device authentication configuration."""

    model_config = SettingsConfigDict(
        env_prefix='DEVICE_AUTH_',
        env_file='.env',
        extra='ignore'
    )

    token_validity_minutes: int = Field(default=5, description='Token validity window')
    secret_key: str = Field(
        default='device-secret-key-change-in-production',
        description='Secret for device token generation'
    )
    algorithm: str = Field(default='HS256')


class TelemetrySettings(BaseSettings):
    """Telemetry processing configuration."""

    model_config = SettingsConfigDict(
        env_prefix='TELEMETRY_',
        env_file='.env',
        extra='ignore'
    )

    # Batch processing
    batch_size: int = Field(default=100, description='Batch size for bulk inserts')
    flush_interval_seconds: float = Field(default=1.0, description='Flush interval')

    # Validation
    max_metric_value: float = Field(default=1000000, description='Max allowed metric value')
    min_metric_value: float = Field(default=-1000000, description='Min allowed metric value')

    # Aggregation
    aggregate_intervals: List[str] = Field(
        default=['5min', '15min', '1hour', '1day'],
        description='Aggregation intervals'
    )

    # Rate limiting per device
    max_messages_per_minute: int = Field(default=120, description='Max messages per device per minute')


class WorkerSettings(BaseSettings):
    """Background worker configuration."""

    model_config = SettingsConfigDict(
        env_prefix='WORKER_',
        env_file='.env',
        extra='ignore'
    )

    telemetry_processor_workers: int = Field(default=4, description='Number of telemetry processors')
    aggregation_worker_interval: int = Field(default=60, description='Aggregation interval in seconds')
    alert_checker_interval: int = Field(default=10, description='Alert check interval in seconds')


class AppSettings(BaseSettings):
    """Main application settings for System B."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    # Application
    app_name: str = Field(default='Solar Hub Telemetry')
    app_version: str = Field(default='1.0.0')
    debug: bool = Field(default=False)
    environment: str = Field(default='development')

    # Server
    host: str = Field(default='0.0.0.0')
    port: int = Field(default=8001)  # Different from System A
    workers: int = Field(default=2)
    reload: bool = Field(default=False)

    # API
    api_prefix: str = Field(default='/api')
    api_version: str = Field(default='v1')

    # Logging
    log_level: str = Field(default='INFO')
    log_format: str = Field(default='json')

    # System A Integration
    system_a_url: str = Field(default='http://localhost:8000', description='System A base URL')
    system_a_api_key: Optional[str] = Field(default=None, description='API key for System A')

    # Timezone
    default_timezone: str = Field(default='Asia/Karachi')

    # Sub-settings
    database: TimescaleDBSettings = Field(default_factory=TimescaleDBSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    protocols: ProtocolSettings = Field(default_factory=ProtocolSettings)
    device_auth: DeviceAuthSettings = Field(default_factory=DeviceAuthSettings)
    telemetry: TelemetrySettings = Field(default_factory=TelemetrySettings)
    workers: WorkerSettings = Field(default_factory=WorkerSettings)

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == 'production'

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == 'development'


@lru_cache()
def get_settings() -> AppSettings:
    """
    Get cached application settings.

    Uses LRU cache to avoid re-reading environment variables on every access.
    """
    return AppSettings()


# Convenience accessor
settings = get_settings()
