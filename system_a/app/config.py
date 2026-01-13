"""
Configuration management for System A (Platform & Monitoring).

Uses Pydantic settings for validation and environment variable support.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(
        env_prefix='DB_',
        env_file='.env',
        extra='ignore'
    )

    host: str = Field(default='localhost', description='Database host')
    port: int = Field(default=5432, description='Database port')
    name: str = Field(default='solar_hub', description='Database name')
    user: str = Field(default='postgres', description='Database user')
    password: str = Field(default='postgres', description='Database password')
    pool_size: int = Field(default=5, description='Connection pool size')
    max_overflow: int = Field(default=10, description='Max overflow connections')
    echo_sql: bool = Field(default=False, description='Echo SQL queries')

    @property
    def url(self) -> str:
        """Build database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        """Build synchronous database URL (for migrations)."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(
        env_prefix='REDIS_',
        env_file='.env',
        extra='ignore'
    )

    host: str = Field(default='localhost', description='Redis host')
    port: int = Field(default=6379, description='Redis port')
    db: int = Field(default=0, description='Redis database number')
    password: Optional[str] = Field(default=None, description='Redis password')
    ssl: bool = Field(default=False, description='Use SSL connection')

    @property
    def url(self) -> str:
        """Build Redis URL."""
        auth = f":{self.password}@" if self.password else ""
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


class JWTSettings(BaseSettings):
    """JWT authentication configuration."""

    model_config = SettingsConfigDict(
        env_prefix='JWT_',
        env_file='.env',
        extra='ignore'
    )

    secret_key: str = Field(
        default='change-this-secret-key-in-production',
        description='Secret key for JWT signing'
    )
    algorithm: str = Field(default='HS256', description='JWT algorithm')
    access_token_expire_minutes: int = Field(
        default=15,
        description='Access token expiration in minutes'
    )
    refresh_token_expire_days: int = Field(
        default=7,
        description='Refresh token expiration in days'
    )
    issuer: Optional[str] = Field(
        default='solar-hub',
        description='JWT token issuer'
    )
    audience: Optional[str] = Field(
        default='solar-hub-api',
        description='JWT token audience'
    )


class CORSSettings(BaseSettings):
    """CORS configuration."""

    model_config = SettingsConfigDict(
        env_prefix='CORS_',
        env_file='.env',
        extra='ignore'
    )

    allowed_origins: List[str] = Field(
        default=['http://localhost:3000', 'http://localhost:5173'],
        description='Allowed origins for CORS'
    )
    allow_credentials: bool = Field(default=True)
    allowed_methods: List[str] = Field(default=['*'])
    allowed_headers: List[str] = Field(default=['*'])


class NotificationSettings(BaseSettings):
    """Notification service configuration."""

    model_config = SettingsConfigDict(
        env_prefix='NOTIFICATION_',
        env_file='.env',
        extra='ignore'
    )

    # SMS Settings (for Pakistani SMS gateways)
    sms_enabled: bool = Field(default=False)
    sms_provider: str = Field(default='twilio', description='SMS provider')
    sms_api_key: Optional[str] = Field(default=None)
    sms_api_secret: Optional[str] = Field(default=None)
    sms_sender_id: Optional[str] = Field(default='SOLARHUB')

    # Email Settings
    email_enabled: bool = Field(default=False)
    smtp_host: str = Field(default='smtp.gmail.com')
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    smtp_from_email: str = Field(default='noreply@solarhub.pk')
    smtp_from_name: str = Field(default='Solar Hub')


class AISettings(BaseSettings):
    """AI service configuration."""

    model_config = SettingsConfigDict(
        env_prefix='AI_',
        env_file='.env',
        extra='ignore'
    )

    enabled: bool = Field(default=True)
    provider: str = Field(default='openai', description='AI provider')
    api_key: Optional[str] = Field(default=None)
    model: str = Field(default='gpt-4', description='Model to use')
    anomaly_detection_enabled: bool = Field(default=True)
    forecasting_enabled: bool = Field(default=True)


class AppSettings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore'
    )

    # Application
    app_name: str = Field(default='Solar Hub Platform')
    app_version: str = Field(default='1.0.0')
    debug: bool = Field(default=False)
    environment: str = Field(default='development')  # development, staging, production

    # Server
    host: str = Field(default='0.0.0.0')
    port: int = Field(default=8000)
    workers: int = Field(default=1)
    reload: bool = Field(default=False)

    # API
    api_prefix: str = Field(default='/api')
    api_version: str = Field(default='v1')

    # Logging
    log_level: str = Field(default='INFO')
    log_format: str = Field(default='json')  # json or text

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests: int = Field(default=100)
    rate_limit_period: int = Field(default=60)  # seconds

    # Feature Flags
    feature_billing_simulation: bool = Field(default=True)
    feature_ai_analysis: bool = Field(default=True)
    feature_load_shedding_tracking: bool = Field(default=True)

    # Pakistan-specific
    default_timezone: str = Field(default='Asia/Karachi')
    default_currency: str = Field(default='PKR')

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    ai: AISettings = Field(default_factory=AISettings)

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
