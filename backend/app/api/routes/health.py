"""Health / liveness endpoint used by the frontend shell and future probes."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse, summary="Service health check")
def health_check() -> HealthResponse:
    """Return basic service status. No database or external dependency needed."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
    )
