"""
FastAPI application entry point for System B (Communication & Telemetry).

This is the backend for:
- Device registration and authentication
- Telemetry data ingestion
- Protocol handling (MQTT, Modbus, HTTP)
- Real-time data streaming
- Device Server (TCP server for Modbus device connections)
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .infrastructure.database.timescale_connection import TimescaleDBManager, init_db
from .infrastructure.messaging.redis_streams import RedisStreamManager

# Get settings (will use environment variables if available)
settings = get_settings()

# Global reference to Device Server for health checks
_device_server: Optional["DeviceServer"] = None
_device_server_task: Optional[asyncio.Task] = None

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if settings.log_format != 'json' else None,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan handler.

    Manages startup and shutdown tasks.
    """
    global _device_server, _device_server_task

    # Startup
    logger = logging.getLogger(__name__)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")

    # Initialize TimescaleDB
    try:
        await init_db()
        logger.info("TimescaleDB initialized successfully")
    except Exception as e:
        logger.error(f"TimescaleDB initialization failed: {e}")
        raise

    # Test Redis connection
    try:
        client = await RedisStreamManager.get_client()
        await client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise  # Redis is critical for System B

    # Start Device Server (TCP server for Modbus device connections)
    try:
        from ..device_server.main import DeviceServer

        _device_server = DeviceServer()
        await _device_server.start()

        # Run serve_forever in background task
        _device_server_task = asyncio.create_task(
            _device_server.serve_forever(),
            name="device_server"
        )
        logger.info("Device Server started successfully")
    except Exception as e:
        logger.error(f"Device Server startup failed: {e}")
        # Don't raise - allow API to run even if device server fails
        _device_server = None
        _device_server_task = None

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Stop Device Server
    if _device_server:
        try:
            await _device_server.stop()
            if _device_server_task and not _device_server_task.done():
                _device_server_task.cancel()
                try:
                    await _device_server_task
                except asyncio.CancelledError:
                    pass
            logger.info("Device Server stopped")
        except Exception as e:
            logger.error(f"Error stopping Device Server: {e}")

    await TimescaleDBManager.close()
    await RedisStreamManager.close()
    logger.info("Shutdown complete")


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
        logger = logging.getLogger(__name__)
        logger.exception(f"Unhandled exception: {exc}")

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

        # Check Device Server status
        device_server_ok = (
            _device_server is not None
            and _device_server.tcp_server is not None
            and _device_server.tcp_server.is_running
        )

        return {
            'status': 'healthy' if db_ok and redis_ok else 'unhealthy',
            'services': {
                'timescaledb': 'up' if db_ok else 'down',
                'redis': 'up' if redis_ok else 'down',
                'device_server': 'up' if device_server_ok else 'down',
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

    # Import and register API v1 routers
    from .api.v1 import api_router as v1_api_router
    
    # Include the v1 API router (includes devices, telemetry, commands, events)
    app.include_router(v1_api_router)
    
    # Stats endpoint (for monitoring) - keep this as it's not in v1 routers
    from fastapi import APIRouter
    stats_router = APIRouter(prefix=f"{settings.api_prefix}/{settings.api_version}")
    
    @stats_router.get("/stats")
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
    
    app.include_router(stats_router)


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "system_b.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.uvicorn_workers,
    )
