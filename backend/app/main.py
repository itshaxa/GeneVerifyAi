"""GeneVerify AI backend entry point.

Run locally (development):
    uvicorn app.main:app --reload

Run behind a deployment platform (PORT/HOST come from the environment):
    python run.py
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Ensure the schema exists at startup (non-destructive create_all).

    Demo data is only ever written by the explicit seed command:
        python -m app.database.seed
    """
    from app.database.init import init_db

    init_db()
    yield


def _register_exception_handlers(app: FastAPI) -> None:
    """Attach uniform JSON error handling for every failure path."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        payload = ErrorResponse(detail=str(exc.detail)).model_dump()
        # Preserve security headers such as WWW-Authenticate for 401 responses.
        return JSONResponse(status_code=exc.status_code, content=payload, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first_error.get("loc", []))
        message = first_error.get("msg", "Invalid request payload")
        detail = f"Validation failed for '{location}': {message}" if location else str(message)
        payload = ErrorResponse(detail=detail, code="validation_error").model_dump()
        return JSONResponse(status_code=422, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        payload = ErrorResponse(detail="Internal server error", code="internal_error").model_dump()
        return JSONResponse(status_code=500, content=payload)


def _production_startup_checks(settings: Settings) -> None:
    """Refuse to start a production instance that is still configured for dev.

    Step 11 (deployment): these checks exist so a misconfigured environment is
    loud at boot time instead of silently insecure. They never print secret
    values, and they only apply when ``APP_ENV=production``.
    """
    if settings.app_env != "production":
        return

    if settings.using_insecure_dev_jwt_secret:
        raise RuntimeError(
            "Refusing to start in production with the insecure development "
            "JWT_SECRET_KEY. Set a strong, randomly generated secret."
        )

    if settings.debug:
        raise RuntimeError(
            "Refusing to start in production with DEBUG enabled: debug responses "
            "can expose internals. Set DEBUG=false."
        )

    loopback = [origin for origin in settings.cors_origin_list if _is_loopback_origin(origin)]
    if loopback:
        logger.warning(
            "CORS_ORIGINS still lists development loopback origin(s) in production: %s",
            ", ".join(loopback),
        )

    if settings.ai_provider == "mock":
        logger.warning(
            "AI_PROVIDER=mock is disabled in production; document extraction "
            "will answer 503 until a real provider is configured."
        )


def _is_loopback_origin(origin: str) -> bool:
    """True for ``http(s)://localhost`` / ``127.0.0.1`` / ``0.0.0.0`` origins."""
    lowered = origin.strip().lower()
    return "//localhost" in lowered or "//127.0.0.1" in lowered or "//0.0.0.0" in lowered


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory used both by the server and by tests."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    if settings.using_insecure_dev_jwt_secret and settings.app_env != "production":
        logger.warning("Using the insecure development JWT secret — never do this in production.")

    _production_startup_checks(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Prototype API for biological-sample substitution prevention through "
            "identity-linked DNA/STR verification. Uses synthetic data only."
        ),
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)
    _register_exception_handlers(app)

    logger.info("GeneVerify AI API initialised (env=%s)", settings.app_env)
    return app


app = create_app()
