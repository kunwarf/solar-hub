"""
Configuration for the Device Server.

Provides settings for TCP server, connection handling,
device identification, polling, and storage integration.
"""
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TCPServerSettings(BaseSettings):
    """TCP server configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DEVICE_SERVER_",
        env_file=".env",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="Server bind address")
    port: int = Field(default=8502, description="Server port for data loggers")
    max_connections: int = Field(default=1000, description="Maximum concurrent connections")
    backlog: int = Field(default=100, description="Connection backlog size")


class ConnectionSettings(BaseSettings):
    """Connection handling configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DEVICE_CONNECTION_",
        env_file=".env",
        extra="ignore",
    )

    timeout: float = Field(default=30.0, description="Connection timeout in seconds")
    keepalive: float = Field(default=60.0, description="Keepalive interval in seconds")
    read_timeout: float = Field(default=10.0, description="Read timeout in seconds")
    write_timeout: float = Field(default=10.0, description="Write timeout in seconds")
    reconnect_delay: float = Field(default=5.0, description="Delay before reconnection attempt")
    max_reconnect_attempts: int = Field(default=10, description="Maximum reconnection attempts")


class IdentificationSettings(BaseSettings):
    """Device identification configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DEVICE_IDENTIFICATION_",
        env_file=".env",
        extra="ignore",
    )

    timeout: float = Field(default=10.0, description="Timeout per protocol attempt")
    max_retries: int = Field(default=3, description="Maximum identification retries")
    retry_delay: float = Field(default=1.0, description="Delay between retries")


class PollingSettings(BaseSettings):
    """Telemetry polling configuration."""

    model_config = SettingsConfigDict(
        env_prefix="DEVICE_POLLING_",
        env_file=".env",
        extra="ignore",
    )

    default_interval: int = Field(default=10, description="Default poll interval (seconds)")
    min_interval: int = Field(default=5, description="Minimum poll interval (seconds)")
    max_interval: int = Field(default=300, description="Maximum poll interval (seconds)")
    failure_backoff: bool = Field(default=True, description="Enable exponential backoff on failure")
    max_consecutive_failures: int = Field(default=5, description="Failures before device goes offline")
    backoff_multiplier: float = Field(default=2.0, description="Backoff multiplier")
    max_backoff: float = Field(default=60.0, description="Maximum backoff time (seconds)")


class SystemAClientSettings(BaseSettings):
    """System A API client configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SYSTEM_A_",
        env_file=".env",
        extra="ignore",
    )

    base_url: str = Field(default="http://localhost:8000/api/v1", description="System A API URL")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    timeout: float = Field(default=10.0, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Delay between retries")


class StorageSettings(BaseSettings):
    """Storage configuration for telemetry data."""

    model_config = SettingsConfigDict(
        env_prefix="DEVICE_STORAGE_",
        env_file=".env",
        extra="ignore",
    )

    batch_size: int = Field(default=100, description="Batch size for bulk writes")
    flush_interval: float = Field(default=1.0, description="Flush interval in seconds")
    buffer_max_size: int = Field(default=10000, description="Maximum buffer size before force flush")


class DeviceServerSettings(BaseSettings):
    """Main configuration for Device Server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Solar Hub Device Server")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # Paths
    config_dir: Path = Field(
        default=Path(__file__).parent.parent / "config",
        description="Path to config directory",
    )
    register_maps_dir: Path = Field(
        default=Path(__file__).parent.parent.parent / "register_maps",
        description="Path to register maps directory",
    )

    # Sub-settings
    server: TCPServerSettings = Field(default_factory=TCPServerSettings)
    connection: ConnectionSettings = Field(default_factory=ConnectionSettings)
    identification: IdentificationSettings = Field(default_factory=IdentificationSettings)
    polling: PollingSettings = Field(default_factory=PollingSettings)
    system_a: SystemAClientSettings = Field(default_factory=SystemAClientSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)

    @property
    def protocols_file(self) -> Path:
        """Path to protocols.yaml configuration file."""
        return self.config_dir / "protocols.yaml"

    def validate_paths(self) -> List[str]:
        """
        Validate that required paths exist.

        Returns:
            List of error messages for missing paths.
        """
        errors = []

        if not self.config_dir.exists():
            errors.append(f"Config directory not found: {self.config_dir}")

        if not self.register_maps_dir.exists():
            errors.append(f"Register maps directory not found: {self.register_maps_dir}")

        if not self.protocols_file.exists():
            errors.append(f"Protocols file not found: {self.protocols_file}")

        return errors


@lru_cache()
def get_device_server_settings() -> DeviceServerSettings:
    """
    Get cached device server settings.

    Uses LRU cache to avoid re-reading environment variables on every access.
    """
    return DeviceServerSettings()


# Convenience accessor
settings = get_device_server_settings()
