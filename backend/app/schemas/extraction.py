"""Step 7 schemas: strict validation of AI extraction output + safe API models.

AI output is NEVER repaired silently. Anything that violates the contract
(unknown markers, non-numeric/null alleles, wrong arity, out-of-range
values, arbitrary extra fields) is rejected and surfaced as a controlled
processing failure. Canonical marker names and allele ranges come from the
single source of truth: ``app/services/str_engine/panel.py``.
"""

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

from app.models.document_extraction import ExtractionStatus
from app.models.verification_document import ProcessingStatus
from app.services.str_engine.panel import ALLELE_RANGES, STR_PANEL


class CnicConsistency(str, Enum):
    """Deterministic document/case CNIC consistency — NOT identity proof."""

    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"
    NOT_DETECTED = "NOT_DETECTED"


class NameConsistency(str, Enum):
    """Deterministic normalized name comparison — NOT identity proof."""

    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"
    NOT_DETECTED = "NOT_DETECTED"


def _validate_alleles(marker: str, alleles: Any) -> list[float]:
    if not isinstance(alleles, (list, tuple)):
        raise ValueError(f"{marker}: alleles must be a list of two numbers.")
    if len(alleles) != 2:
        raise ValueError(f"{marker}: exactly two alleles are required.")
    values: list[float] = []
    for allele in alleles:
        if allele is None:
            raise ValueError(f"{marker}: null allele values are not allowed.")
        if isinstance(allele, bool) or not isinstance(allele, (int, float)):
            raise ValueError(f"{marker}: non-numeric allele values are not allowed.")
        values.append(float(allele))
    low, high = ALLELE_RANGES[marker]
    for allele in values:
        if not low <= allele <= high:
            raise ValueError(
                f"{marker}: allele {allele:g} is outside the allowed range {low}-{high}."
            )
    return values


class ExtractedStrProfile(RootModel):
    """Canonical-panel STR profile: only known markers, strict allele rules.

    Missing markers are permitted (partial extraction); a missing marker is
    never guessed or invented downstream.
    """

    root: dict[str, Any] = Field(min_length=1)

    @field_validator("root")
    @classmethod
    def _validate_panel(cls, value: dict[str, Any]) -> dict[str, Any]:
        validated: dict[str, Any] = {}
        for marker, alleles in value.items():
            if marker not in STR_PANEL:
                raise ValueError(f"Unknown STR marker: {marker}")
            validated[marker] = _validate_alleles(marker, alleles)
        return validated


class ExtractedIdentityData(BaseModel):
    """Identity fields read from the document; anything absent stays null."""

    model_config = ConfigDict(extra="forbid")

    patient_name: str | None = None
    cnic: str | None = None
    date_of_birth: date | None = None
    report_date: date | None = None
    laboratory_reference: str | None = None


class DocumentExtractionResult(BaseModel):
    """Top-level AI extraction contract (strict: no arbitrary extra fields)."""

    model_config = ConfigDict(extra="forbid")

    identity: ExtractedIdentityData = Field(default_factory=ExtractedIdentityData)
    str_profile: ExtractedStrProfile | None = None


# --- Safe API response models ----------------------------------------------


class ProcessDocumentResponse(BaseModel):
    """Result of POST .../documents/{document_id}/process — no internals."""

    document_id: str
    processing_status: ProcessingStatus
    extraction_status: ExtractionStatus | None = None
    extracted_marker_count: int | None = None


class DocumentExtractionResponse(BaseModel):
    """GET .../documents/{document_id}/extraction — AI data, clearly labelled.

    Never contains the reference profile, storage paths or provider secrets.
    """

    document_id: str
    processing_status: ProcessingStatus
    extraction_status: ExtractionStatus | None = None
    model_name: str | None = None
    patient_name: str | None = None
    cnic: str | None = None
    date_of_birth: date | None = None
    report_date: date | None = None
    laboratory_reference: str | None = None
    str_profile: dict[str, list[float]] | None = None
    extracted_marker_count: int = 0
    cnic_consistency: CnicConsistency | None = None
    name_consistency: NameConsistency | None = None
    validation_note: str | None = None
    extracted_at: datetime | None = None
