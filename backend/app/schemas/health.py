"""Schemas for the health endpoint."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness/status contract consumed by the frontend shell."""

    status: str = Field(description="Service status, e.g. 'ok'")
    app: str = Field(description="Application display name")
    environment: str = Field(description="Deployment environment")
    version: str = Field(description="Application version")
