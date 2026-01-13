"""
FastAPI application entry point for System B (Communication & Telemetry).

This is the backend for:
- Device registration and authentication
- Telemetry data ingestion
- Protocol handling (MQTT, Modbus, HTTP)
- Real-time data streaming
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .infrastructure.database.timescale_connection import TimescaleDBManager, init_db
from .infrastructure.messaging.redis_streams import RedisStreamManager

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan handler.

    Manages startup and shutdown tasks.
    """
    # Startup
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"Environment: {settings.environment}")

    # Initialize TimescaleDB
    try:
        await init_db()
        print("TimescaleDB initialized successfully")
    except Exception as e:
        print(f"TimescaleDB initialization failed: {e}")
        raise

    # Test Redis connection
    try:
        client = await RedisStreamManager.get_client()
        await client.ping()
        print("Redis connection established")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        raise  # Redis is critical for System B

    yield

    # Shutdown
    print("Shutting down application...")
    await TimescaleDBManager.close()
    await RedisStreamManager.close()
    print("Shutdown complete")


def create_app() -> FastAPI:
    """
    Application factory.

    Creates and configures the FastAPI application.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Solar Hub Telemetry API - Device communication and data ingestion",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Configure CORS (limited for device API)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Devices can connect from anywhere
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register routes
    register_routes(app)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        print(f"Unhandled exception: {exc}")

        if settings.debug:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    'error': 'INTERNAL_ERROR',
                    'message': str(exc),
                    'type': type(exc).__name__,
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'error': 'INTERNAL_ERROR',
                'message': 'An internal error occurred',
            },
        )


def register_routes(app: FastAPI) -> None:
    """Register API routes."""

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Check application health."""
        from .infrastructure.database.timescale_connection import health_check as db_health
        from .infrastructure.messaging.redis_streams import health_check as redis_health

        db_ok = await db_health()
        redis_ok = await redis_health()

        return {
            'status': 'healthy' if db_ok and redis_ok else 'unhealthy',
            'services': {
                'timescaledb': 'up' if db_ok else 'down',
                'redis': 'up' if redis_ok else 'down',
            },
            'version': settings.app_version,
            'environment': settings.environment,
        }

    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint."""
        return {
            'name': settings.app_name,
            'version': settings.app_version,
            'api_docs': '/docs' if settings.debug else None,
        }

    # Import and register API routers
    from fastapi import APIRouter

    api_router = APIRouter(prefix=f"{settings.api_prefix}/{settings.api_version}")

    # Device registration endpoints
    @api_router.post("/devices/register")
    async def register_device():
        """Register a new device."""
        return {"message": "Device registration endpoint coming soon"}

    @api_router.post("/devices/{device_id}/authenticate")
    async def authenticate_device(device_id: str):
        """Authenticate a device."""
        return {"message": "Device authentication endpoint coming soon"}

    # Telemetry endpoints
    @api_router.post("/telemetry")
    async def ingest_telemetry():
        """Ingest telemetry data (batch)."""
        return {"message": "Telemetry ingestion endpoint coming soon"}

    @api_router.post("/telemetry/stream")
    async def stream_telemetry():
        """Stream telemetry data (real-time)."""
        return {"message": "Telemetry streaming endpoint coming soon"}

    # Device commands
    @api_router.get("/devices/{device_id}/commands")
    async def get_device_commands(device_id: str):
        """Get pending commands for device."""
        return {"commands": []}

    @api_router.post("/devices/{device_id}/commands/{command_id}/result")
    async def submit_command_result(device_id: str, command_id: str):
        """Submit command execution result."""
        return {"message": "Command result endpoint coming soon"}

    # Stats endpoint (for monitoring)
    @api_router.get("/stats")
    async def get_stats():
        """Get telemetry statistics."""
        from .infrastructure.database.timescale_connection import get_database_stats
        from .infrastructure.messaging.redis_streams import get_stream_info, TELEMETRY_STREAM

        try:
            db_stats = await get_database_stats()
        except Exception:
            db_stats = None

        try:
            stream_stats = await get_stream_info(TELEMETRY_STREAM)
        except Exception:
            stream_stats = None

        return {
            'database': db_stats,
            'streams': {TELEMETRY_STREAM: stream_stats}
        }

    app.include_router(api_router)


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "system_b.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers,
    )
