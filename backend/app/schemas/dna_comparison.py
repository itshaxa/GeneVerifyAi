"""Schemas for the DNA comparison endpoint.

The client supplies ONLY the submitted STR profile. The reference profile is
always resolved server-side (case -> identity -> dna_profile), so the request
model forbids any extra field — a smuggled ``reference_profile`` is rejected
with a 422 instead of silently ignored.

Responses expose only the comparison outcome; reference DNA is revealed only
as the alleles of each marker alongside the submitted alleles (the point of
the comparison), never as a raw downloadable profile.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.str_engine.comparison import ComparisonClassification, MarkerStatus


class CompareDnaRequest(BaseModel):
    """Only the submitted evidence comes from the client."""

    model_config = ConfigDict(extra="forbid")

    submitted_profile: dict[str, Any] = Field(
        min_length=1,
        description='STR markers as {"MARKER": [allele_a, allele_b]}',
    )


class MarkerComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    marker: str
    status: MarkerStatus
    reference_alleles: list[float] | None = None
    submitted_alleles: list[float] | None = None
    reason: str | None = None


class ComparisonSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_markers: int
    matched: int
    mismatched: int
    missing: int
    invalid: int
    match_percentage: float


class DnaComparisonResponse(BaseModel):
    """Deterministic STR comparison outcome for one verification case."""

    model_config = ConfigDict(from_attributes=True)

    verification_id: str
    classification: ComparisonClassification
    summary: ComparisonSummaryResponse
    markers: list[MarkerComparisonResponse]
    compared_at: datetime
