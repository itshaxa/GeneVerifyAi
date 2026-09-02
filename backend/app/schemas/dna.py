"""Schemas for DNA/STR profile data.

``DnaProfileResponse`` is used internally (e.g. by the future verification
service and tests). It is intentionally NOT returned by the public identity
lookup endpoint.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.str_engine.panel import STR_PANEL, validate_str_markers


class StrMarkerProfile(BaseModel):
    """Validated STR marker set: panel marker -> exactly two allele values."""

    markers: dict[str, list[float]] = Field(
        description='e.g. {"D3S1358": [15, 16], "vWA": [17, 18], ...}'
    )

    @field_validator("markers")
    @classmethod
    def _validate_markers(cls, value: dict[str, list[float]]) -> dict[str, list[float]]:
        return validate_str_markers(value)


class DnaProfileResponse(BaseModel):
    """Internal representation of a reference DNA profile."""

    model_config = ConfigDict(from_attributes=True)

    profile_code: str
    markers: dict[str, list[float]]

    @field_validator("markers")
    @classmethod
    def _validate_markers(cls, value: dict[str, list[float]]) -> dict[str, list[float]]:
        return validate_str_markers(value)

    @property
    def panel_markers(self) -> tuple[str, ...]:
        return STR_PANEL
