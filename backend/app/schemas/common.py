"""Shared response schemas used across endpoints."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Uniform error envelope returned by every failure path."""

    detail: str = Field(description="Human-readable description of the error")
    code: str | None = Field(default=None, description="Stable machine-readable error code")
