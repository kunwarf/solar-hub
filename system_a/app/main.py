"""
FastAPI application entry point for System A (Platform & Monitoring).

This is the main backend for:
- User management and authentication
- Organization and site management
- Dashboard and reporting
- Billing simulation
- AI-powered analytics
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .infrastructure.database.connection import DatabaseManager, init_db
from .infrastructure.cache.redis_cache import RedisManager

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

    # Initialize database
    try:
        await init_db()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise

    # Test Redis connection
    try:
        client = await RedisManager.get_client()
        await client.ping()
        print("Redis connection established")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        # Redis failure is not fatal for now
        pass

    yield

    # Shutdown
    print("Shutting down application...")
    await DatabaseManager.close()
    await RedisManager.close()
    print("Shutdown complete")


def create_app() -> FastAPI:
    """
    Application factory.

    Creates and configures the FastAPI application.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Solar Hub Platform API - Solar monitoring and management system",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors.allowed_origins,
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.allowed_methods,
        allow_headers=settings.cors.allowed_headers,
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register routes
    register_routes(app)

    return app


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    from .domain.exceptions import (
        DomainException,
        EntityNotFoundException,
        ValidationException,
        AuthorizationException,
    )

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=exc.to_dict(),
        )

    @app.exception_handler(EntityNotFoundException)
    async def not_found_handler(request: Request, exc: EntityNotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=exc.to_dict(),
        )

    @app.exception_handler(ValidationException)
    async def validation_handler(request: Request, exc: ValidationException):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=exc.to_dict(),
        )

    @app.exception_handler(AuthorizationException)
    async def authorization_handler(request: Request, exc: AuthorizationException):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        # Log the exception
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

    # Health check endpoint (always available)
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Check application health."""
        from .infrastructure.database.connection import health_check as db_health
        from .infrastructure.cache.redis_cache import health_check as redis_health

        db_ok = await db_health()
        redis_ok = await redis_health()

        return {
            'status': 'healthy' if db_ok and redis_ok else 'degraded',
            'services': {
                'database': 'up' if db_ok else 'down',
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

    # Import and register API v1 router
    from .api.v1 import api_router

    # Mount API under /api prefix
    from fastapi import APIRouter
    main_router = APIRouter(prefix=settings.api_prefix)
    main_router.include_router(api_router)

    app.include_router(main_router)


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "system_a.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers,
    )
