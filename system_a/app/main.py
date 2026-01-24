"""
FastAPI application entry point for System A (Platform & Monitoring).

This is the main backend for:
- User management and authentication
- Organization and site management
- Dashboard and reporting
- Billing simulation
- AI-powered analytics
"""
import json
import logging
import sys
import time
import traceback
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .infrastructure.database.connection import DatabaseManager, init_db
from .infrastructure.cache.redis_cache import RedisManager

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger("system_a")


class RequestLoggingMiddleware:
    """Middleware to log request details including body."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        # Skip logging for health checks and static files
        if path in ["/health", "/", "/docs", "/openapi.json", "/redoc"]:
            await self.app(scope, receive, send)
            return

        # Capture request details
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        query_params = dict(request.query_params)

        # Read body and create a new receive function that returns cached body
        body = b""
        body_for_log = None

        async def receive_wrapper():
            nonlocal body
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
            return message

        # For methods with body, read it first
        if method in ["POST", "PUT", "PATCH"]:
            # Consume the body
            chunks = []
            while True:
                message = await receive()
                chunk = message.get("body", b"")
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)

            if body:
                try:
                    body_for_log = json.loads(body.decode("utf-8"))
                    if isinstance(body_for_log, dict):
                        body_for_log = mask_sensitive_fields(body_for_log.copy())
                except json.JSONDecodeError:
                    body_for_log = body.decode("utf-8")[:500]

            # Store body in scope for later access
            scope["_body"] = body

            # Create new receive that returns cached body
            body_sent = False

            async def cached_receive():
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return {"type": "http.request", "body": b"", "more_body": False}

            receive = cached_receive

        # Log request
        logger.info("=" * 60)
        logger.info(f"REQUEST: {method} {path}")
        logger.info(f"Client: {client_ip}")
        if query_params:
            logger.info(f"Query params: {query_params}")
        if body_for_log:
            logger.info(f"Request body: {json.dumps(body_for_log, indent=2, default=str)}")

        # Track response status
        response_status = [None]

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_status[0] = message["status"]
            await send(message)

        # Process request
        await self.app(scope, receive, send_wrapper)

        # Log response
        duration = time.time() - start_time
        status_code = response_status[0] or "unknown"
        logger.info(f"RESPONSE: {status_code} ({duration:.3f}s)")
        logger.info("=" * 60)


def mask_sensitive_fields(data: dict) -> dict:
    """Mask sensitive fields in request data for logging."""
    sensitive_fields = ["password", "password_hash", "token", "secret", "api_key", "credit_card"]
    for field in sensitive_fields:
        if field in data:
            data[field] = "***MASKED***"
        # Check nested with common patterns
        for key in list(data.keys()):
            if any(s in key.lower() for s in sensitive_fields):
                data[key] = "***MASKED***"
    return data


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan handler.

    Manages startup and shutdown tasks.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"CORS allowed origins: {settings.cors.allowed_origins}")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.error(traceback.format_exc())
        raise

    # Test Redis connection
    try:
        client = await RedisManager.get_client()
        await client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        # Redis failure is not fatal for now
        pass

    yield

    # Shutdown
    logger.info("Shutting down application...")
    await DatabaseManager.close()
    await RedisManager.close()
    logger.info("Shutdown complete")


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

    # Add request logging middleware (raw ASGI middleware for proper body caching)
    app.add_middleware(RequestLoggingMiddleware)

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

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError):
        """Handle Pydantic validation errors with detailed logging."""
        errors = exc.errors()

        # Log detailed validation errors
        logger.error("=" * 60)
        logger.error(f"VALIDATION ERROR on {request.method} {request.url.path}")
        logger.error(f"Client: {request.client.host if request.client else 'unknown'}")

        # Try to get cached body from scope (set by middleware)
        cached_body = request.scope.get("_body")
        if cached_body:
            try:
                body_json = json.loads(cached_body.decode("utf-8"))
                masked_body = mask_sensitive_fields(body_json.copy()) if isinstance(body_json, dict) else body_json
                logger.error(f"Request body received: {json.dumps(masked_body, indent=2, default=str)}")
            except:
                logger.error(f"Request body (raw): {cached_body.decode('utf-8')[:1000]}")

        logger.error(f"Validation errors ({len(errors)} total):")
        for i, error in enumerate(errors, 1):
            field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
            error_type = error.get("type", "unknown")
            error_msg = error.get("msg", "no message")
            error_input = error.get("input", "N/A")

            logger.error(f"  [{i}] Field: {field_path}")
            logger.error(f"      Type: {error_type}")
            logger.error(f"      Message: {error_msg}")
            if "password" not in str(field_path).lower():
                logger.error(f"      Input value: {error_input}")
            else:
                logger.error(f"      Input value: ***MASKED***")
        logger.error("=" * 60)

        # Return user-friendly error response
        formatted_errors = []
        for error in errors:
            field_path = ".".join(str(loc) for loc in error.get("loc", []) if loc != "body")
            formatted_errors.append({
                "field": field_path,
                "message": error.get("msg", "Validation error"),
                "type": error.get("type", "unknown"),
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": formatted_errors,
            },
        )

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        logger.warning(f"Domain exception on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=exc.to_dict(),
        )

    @app.exception_handler(EntityNotFoundException)
    async def not_found_handler(request: Request, exc: EntityNotFoundException):
        logger.info(f"Not found on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=exc.to_dict(),
        )

    @app.exception_handler(ValidationException)
    async def validation_handler(request: Request, exc: ValidationException):
        logger.warning(f"Validation error on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=exc.to_dict(),
        )

    @app.exception_handler(AuthorizationException)
    async def authorization_handler(request: Request, exc: AuthorizationException):
        logger.warning(f"Authorization denied on {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        # Log detailed exception info
        error_id = id(exc)  # Simple error tracking ID
        logger.error("=" * 60)
        logger.error(f"UNHANDLED EXCEPTION [ID: {error_id}]")
        logger.error(f"Request: {request.method} {request.url.path}")
        logger.error(f"Query params: {dict(request.query_params)}")
        logger.error(f"Client: {request.client.host if request.client else 'unknown'}")
        logger.error(f"Exception type: {type(exc).__name__}")
        logger.error(f"Exception message: {exc}")
        logger.error("Stack trace:")
        logger.error(traceback.format_exc())
        logger.error("=" * 60)

        if settings.debug:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    'error': 'INTERNAL_ERROR',
                    'message': str(exc),
                    'type': type(exc).__name__,
                    'error_id': error_id,
                    'path': request.url.path,
                    'traceback': traceback.format_exc().split('\n'),
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'error': 'INTERNAL_ERROR',
                'message': 'An internal error occurred',
                'error_id': error_id,
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
