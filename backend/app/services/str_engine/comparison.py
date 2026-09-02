"""Deterministic STR profile comparison (pure application logic).

This module compares two STR marker profiles against the canonical panel
from :mod:`app.services.str_engine.panel`. It is intentionally boring:

- Same two inputs ALWAYS produce the same result (no RNG, no clock use).
- No network, no database, no AI/LLM calls — fully offline.
- Never repairs malformed data; invalid input raises a structured error.

A PARTIAL_MATCH is NOT an identity confirmation. The final verification
engine (a later stage) will combine STR evidence with other evidence; this
module only reports what the marker data says.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum

from app.services.str_engine.panel import ALLELE_RANGES, STR_PANEL

_ALLELES_PER_MARKER = 2


class MarkerStatus(str, Enum):
    """Per-marker comparison outcome."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    MISSING_REFERENCE = "MISSING_REFERENCE"
    MISSING_SUBMITTED = "MISSING_SUBMITTED"
    INVALID = "INVALID"


class ComparisonClassification(str, Enum):
    """Overall deterministic classification of one comparison.

    - EXACT_MATCH: every marker of the canonical panel matches.
    - PARTIAL_MATCH: at least one marker matches but not all required
      markers match (including when submitted markers are missing).
      A partial match is NOT identity confirmation.
    - NO_MATCH: zero markers match.
    - INVALID: the comparison cannot be evaluated deterministically.
    """

    EXACT_MATCH = "EXACT_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    NO_MATCH = "NO_MATCH"
    INVALID = "INVALID"


class StrProfileValidationError(ValueError):
    """Raised when an STR profile cannot be validly compared.

    ``issues`` carries every detected problem so callers can surface
    structured validation errors instead of failing one issue at a time.
    """

    def __init__(self, issues: list[str]):
        self.issues = list(issues)
        super().__init__("; ".join(self.issues))


@dataclass(frozen=True)
class MarkerResult:
    """Structured outcome for a single marker (safe for API exposure)."""

    marker: str
    status: MarkerStatus
    reference_alleles: tuple[float, ...] | None = None
    submitted_alleles: tuple[float, ...] | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ComparisonSummary:
    """Aggregate counts derived strictly from the marker results."""

    total_markers: int
    matched: int
    mismatched: int
    missing: int
    invalid: int
    match_percentage: float


@dataclass(frozen=True)
class ComparisonResult:
    """Complete deterministic outcome of one profile comparison."""

    classification: ComparisonClassification
    summary: ComparisonSummary
    markers: list[MarkerResult] = field(default_factory=list)


def validate_profile(
    raw: object, *, require_complete: bool
) -> dict[str, tuple[float, float]]:
    """Validate one STR profile and return a normalized copy.

    Detected problems (reported together, never silently repaired):
    - non-object / completely empty profiles
    - unexpected or malformed marker names (only canonical panel markers)
    - missing alleles, more than two alleles, non-numeric or null alleles
    - alleles outside the marker's demonstration range

    ``require_complete=True`` additionally rejects profiles that are missing
    canonical markers (reference profiles); submitted profiles may be partial
    so that missing data is reported as MISSING_SUBMITTED, not as an error.

    Duplicate allele values (e.g. ``[15, 15]``) are technically valid
    homozygous calls and are accepted.
    """
    if not isinstance(raw, Mapping):
        raise StrProfileValidationError(
            ["STR profile must be a JSON object mapping marker names to allele lists"]
        )
    if not raw:
        raise StrProfileValidationError(["STR profile is empty"])

    issues: list[str] = []
    normalized: dict[str, tuple[float, float]] = {}

    for name, alleles in raw.items():
        if not isinstance(name, str) or name not in STR_PANEL:
            issues.append(f"Unexpected or malformed STR marker: {name!r}")
            continue
        if isinstance(alleles, str) or not isinstance(alleles, Sequence):
            issues.append(f"Marker {name} must be a list of allele values")
            continue
        if len(alleles) != _ALLELES_PER_MARKER:
            issues.append(
                f"Marker {name} must have exactly {_ALLELES_PER_MARKER} allele values "
                f"(got {len(alleles)})"
            )
            continue

        low, high = ALLELE_RANGES[name]
        pair: list[float] = []
        for allele in alleles:
            if allele is None or isinstance(allele, bool) or not isinstance(allele, (int, float)):
                issues.append(f"Marker {name} has a non-numeric allele: {allele!r}")
                break
            value = float(allele)
            if not low <= value <= high:
                issues.append(
                    f"Marker {name} allele {value:g} is outside the allowed "
                    f"demonstration range {low}-{high}"
                )
                break
            pair.append(value)
        else:
            normalized[name] = (pair[0], pair[1])

    if require_complete:
        missing = [marker for marker in STR_PANEL if marker not in raw]
        if missing:
            issues.append(f"Missing STR markers: {', '.join(missing)}")

    if issues:
        raise StrProfileValidationError(issues)
    return normalized


def compare_profiles(reference: Mapping[str, object], submitted: Mapping[str, object]) -> ComparisonResult:
    """Deterministically compare two STR profiles marker by marker.

    Both profiles are validated first; malformed data raises
    :class:`StrProfileValidationError` and is never repaired. Allele order
    does not matter (pairs are compared as sorted multisets). Missing
    markers are reported explicitly and are NOT treated as mismatches.

    The reference is validated leniently about completeness so a degraded
    reference reports MISSING_REFERENCE per marker; production reference
    profiles are already completeness-checked when stored (panel validation).
    """
    clean_reference = validate_profile(reference, require_complete=False)
    clean_submitted = validate_profile(submitted, require_complete=False)

    marker_results: list[MarkerResult] = []
    for marker in STR_PANEL:
        ref_pair = clean_reference.get(marker)
        sub_pair = clean_submitted.get(marker)

        if ref_pair is None and sub_pair is None:
            marker_results.append(
                MarkerResult(
                    marker=marker,
                    status=MarkerStatus.INVALID,
                    reason="Marker missing from both profiles",
                )
            )
        elif ref_pair is None:
            marker_results.append(
                MarkerResult(
                    marker=marker,
                    status=MarkerStatus.MISSING_REFERENCE,
                    submitted_alleles=tuple(sorted(sub_pair)),  # type: ignore[arg-type]
                    reason="Marker absent from the reference profile",
                )
            )
        elif sub_pair is None:
            marker_results.append(
                MarkerResult(
                    marker=marker,
                    status=MarkerStatus.MISSING_SUBMITTED,
                    reference_alleles=tuple(sorted(ref_pair)),
                    reason="Marker absent from the submitted profile",
                )
            )
        elif sorted(ref_pair) == sorted(sub_pair):
            marker_results.append(
                MarkerResult(
                    marker=marker,
                    status=MarkerStatus.MATCH,
                    reference_alleles=tuple(sorted(ref_pair)),
                    submitted_alleles=tuple(sorted(sub_pair)),
                )
            )
        else:
            marker_results.append(
                MarkerResult(
                    marker=marker,
                    status=MarkerStatus.MISMATCH,
                    reference_alleles=tuple(sorted(ref_pair)),
                    submitted_alleles=tuple(sorted(sub_pair)),
                    reason="Allele sets differ",
                )
            )

    matched = sum(1 for r in marker_results if r.status is MarkerStatus.MATCH)
    mismatched = sum(1 for r in marker_results if r.status is MarkerStatus.MISMATCH)
    invalid = sum(1 for r in marker_results if r.status is MarkerStatus.INVALID)
    missing = sum(
        1
        for r in marker_results
        if r.status in (MarkerStatus.MISSING_REFERENCE, MarkerStatus.MISSING_SUBMITTED)
    )
    total = len(STR_PANEL)
    match_percentage = round(matched / total * 100, 1) if total else 0.0

    if invalid:
        classification = ComparisonClassification.INVALID
    elif matched == total:
        classification = ComparisonClassification.EXACT_MATCH
    elif matched == 0:
        classification = ComparisonClassification.NO_MATCH
    else:
        classification = ComparisonClassification.PARTIAL_MATCH

    return ComparisonResult(
        classification=classification,
        summary=ComparisonSummary(
            total_markers=total,
            matched=matched,
            mismatched=mismatched,
            missing=missing,
            invalid=invalid,
            match_percentage=match_percentage,
        ),
        markers=marker_results,
    )
