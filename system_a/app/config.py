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
        default=[
            'http://localhost:3000',
            'http://localhost:5173',
            'http://127.0.0.1:3000',
            'http://127.0.0.1:5173',
            'http://localhost:8080',
            'http://localhost:8081',
            'http://localhost:8082',
            'http://localhost:8083',
            'http://localhost:8084',
            'http://localhost:8085',
            'http://127.0.0.1:8080',
            'http://127.0.0.1:8081',
            'http://127.0.0.1:8082',
            'http://127.0.0.1:8083',
            'http://127.0.0.1:8084',
            'http://127.0.0.1:8085',
        ],
        description='Allowed origins for CORS'
    )
    allow_credentials: bool = Field(default=True)
    allowed_methods: List[str] = Field(default=['*'])
    allowed_headers: List[str] = Field(default=['*'])

    @field_validator('allowed_origins', mode='before')
    @classmethod
    def parse_origins(cls, v):
        """Parse origins from environment variable (JSON array or comma-separated)."""
        import json
        if isinstance(v, str):
            v = v.strip()
            # Try JSON format first: ["http://...", "http://..."]
            if v.startswith('['):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            # Handle comma-separated string
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v

    @field_validator('allowed_methods', 'allowed_headers', mode='before')
    @classmethod
    def parse_list(cls, v):
        """Parse list from environment variable (JSON array or comma-separated)."""
        import json
        if isinstance(v, str):
            v = v.strip()
            if v.startswith('['):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in v.split(',') if item.strip()]
        return v


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
    provider: str = Field(default='anthropic', description='AI provider (anthropic or openai)')
    api_key: Optional[str] = Field(default=None)
    model: str = Field(default='claude-haiku-4-5-20251001', description='Model to use')
    anomaly_detection_enabled: bool = Field(default=True)
    forecasting_enabled: bool = Field(default=True)


class WeatherSettings(BaseSettings):
    """Weather API configuration."""

    model_config = SettingsConfigDict(
        env_prefix='WEATHER_',
        env_file='.env',
        extra='ignore'
    )

    enabled: bool = Field(default=True, description='Enable external weather API')
    provider: str = Field(default='openweathermap', description='Weather provider')
    api_key: Optional[str] = Field(default=None, description='Weather API key')
    cache_ttl_seconds: int = Field(default=1800, description='Cache TTL for weather data (30 minutes)')
    timeout_seconds: float = Field(default=10.0, description='API request timeout')
    fallback_to_telemetry: bool = Field(default=True, description='Use telemetry if API fails')


class SystemBSettings(BaseSettings):
    """System B (Telemetry Service) connection settings."""

    model_config = SettingsConfigDict(
        env_prefix='SYSTEM_B_',
        env_file='.env',
        extra='ignore'
    )

    url: str = Field(
        default='http://localhost:8001',
        description='System B API base URL'
    )
    api_key: Optional[str] = Field(
        default=None,
        description='API key for System B authentication'
    )
    timeout: float = Field(
        default=30.0,
        description='Request timeout in seconds'
    )


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

    # Billing Migration Feature Flags
    use_system_b_for_billing: bool = Field(
        default=False,
        description='Use System B (TimescaleDB) for billing telemetry instead of System A (PostgreSQL)'
    )
    validate_system_b_data: bool = Field(
        default=False,
        description='Enable dual-read validation: compare System A and System B data for consistency'
    )
    system_b_rollout_percentage: int = Field(
        default=100,
        ge=0,
        le=100,
        description='Percentage of sites to use System B for billing (0-100%). Used for gradual rollout.'
    )

    # Pakistan-specific
    default_timezone: str = Field(default='Asia/Karachi')
    default_currency: str = Field(default='PKR')

    # Frontend URL (for email links like verification, password reset)
    frontend_url: str = Field(
        default='http://182.180.150.107:8080',
        description='Frontend application URL for email links'
    )

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    ai: AISettings = Field(default_factory=AISettings)
    weather: WeatherSettings = Field(default_factory=WeatherSettings)
    system_b: SystemBSettings = Field(default_factory=SystemBSettings)

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
