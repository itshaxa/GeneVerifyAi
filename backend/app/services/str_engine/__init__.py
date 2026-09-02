"""Deterministic STR comparison engine.

Pure, offline, deterministic STR/DNA profile comparison against the canonical
demonstration panel. Guarantees:

- Same inputs ALWAYS produce the same result (no RNG, no clock dependence).
- No dependency on AI/LLM code in any direction — an LLM never decides
  whether two DNA profiles match.
- Unit-testable without network, database, or external services.

Public API lives in :mod:`app.services.str_engine.comparison`; the shared
panel definition and marker validation rules live in
:mod:`app.services.str_engine.panel`.
"""

from app.services.str_engine.comparison import (
    ComparisonClassification,
    ComparisonResult,
    ComparisonSummary,
    MarkerResult,
    MarkerStatus,
    StrProfileValidationError,
    compare_profiles,
    validate_profile,
)
from app.services.str_engine.panel import ALLELE_RANGES, STR_PANEL, validate_str_markers

__all__ = [
    "ALLELE_RANGES",
    "ComparisonClassification",
    "ComparisonResult",
    "ComparisonSummary",
    "MarkerResult",
    "MarkerStatus",
    "STR_PANEL",
    "StrProfileValidationError",
    "compare_profiles",
    "validate_profile",
    "validate_str_markers",
]
