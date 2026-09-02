"""Unit tests for the deterministic STR comparison engine (Step 5).

The engine is pure application logic: no database, no network, no AI. These
tests pin down matching semantics, missing-data handling, validation and
determinism against the canonical 20-marker panel.
"""

import pytest

from app.services.str_engine.comparison import (
    ComparisonClassification,
    MarkerStatus,
    StrProfileValidationError,
    compare_profiles,
    validate_profile,
)
from app.services.str_engine.panel import ALLELE_RANGES, STR_PANEL


def _make_profile(offset: int = 0) -> dict[str, list[int]]:
    """Build a full valid profile; alleles stay inside the panel ranges."""
    profile: dict[str, list[int]] = {}
    for index, marker in enumerate(STR_PANEL):
        low, high = ALLELE_RANGES[marker]
        a = low + (index + offset) % (high - low + 1)
        b = low + (index + offset + 1) % (high - low + 1)
        profile[marker] = [a, b]
    return profile


def _mismatched_pair(reference: list[int], marker: str) -> list[int]:
    """Pick an in-range allele pair that definitely differs from reference."""
    low, high = ALLELE_RANGES[marker]
    for candidate in ([low, high], [low, low], [high, high]):
        if sorted(candidate) != sorted(reference):
            return candidate
    raise AssertionError("panel range too narrow to build a mismatch")  # pragma: no cover


REFERENCE = _make_profile()


# ---------------------------------------------------------------------------
# Matching semantics
# ---------------------------------------------------------------------------
def test_identical_profiles_are_exact_match() -> None:
    result = compare_profiles(REFERENCE, dict(REFERENCE))

    assert result.classification is ComparisonClassification.EXACT_MATCH
    assert result.summary.total_markers == 20
    assert result.summary.matched == 20
    assert result.summary.mismatched == 0
    assert result.summary.missing == 0
    assert result.summary.invalid == 0
    assert result.summary.match_percentage == 100.0


def test_allele_order_does_not_affect_matching() -> None:
    submitted = {marker: list(reversed(alleles)) for marker, alleles in REFERENCE.items()}

    result = compare_profiles(REFERENCE, submitted)

    assert result.classification is ComparisonClassification.EXACT_MATCH
    assert result.summary.matched == 20


def test_one_mismatch_is_partial_match() -> None:
    marker = "D3S1358"
    submitted = {m: list(a) for m, a in REFERENCE.items()}
    submitted[marker] = _mismatched_pair(REFERENCE[marker], marker)

    result = compare_profiles(REFERENCE, submitted)

    assert result.classification is ComparisonClassification.PARTIAL_MATCH
    assert result.summary.matched == 19
    assert result.summary.mismatched == 1
    assert result.summary.match_percentage == 95.0
    flagged = next(r for r in result.markers if r.marker == marker)
    assert flagged.status is MarkerStatus.MISMATCH
    assert flagged.reason == "Allele sets differ"


def test_all_markers_mismatched_is_no_match() -> None:
    submitted = {
        marker: _mismatched_pair(alleles, marker) for marker, alleles in REFERENCE.items()
    }

    result = compare_profiles(REFERENCE, submitted)

    assert result.classification is ComparisonClassification.NO_MATCH
    assert result.summary.matched == 0
    assert result.summary.mismatched == 20
    assert result.summary.match_percentage == 0.0


def test_duplicate_alleles_are_valid_homozygous_calls() -> None:
    marker = "vWA"
    submitted = {m: list(a) for m, a in REFERENCE.items()}
    low, _ = ALLELE_RANGES[marker]
    submitted[marker] = [low, low]
    reference = {m: list(a) for m, a in REFERENCE.items()}
    reference[marker] = [low, low]

    result = compare_profiles(reference, submitted)

    assert next(r for r in result.markers if r.marker == marker).status is MarkerStatus.MATCH


# ---------------------------------------------------------------------------
# Missing data is reported, never treated as mismatch
# ---------------------------------------------------------------------------
def test_missing_submitted_marker_is_missing_not_mismatch() -> None:
    dropped = ["FGA", "SE33"]
    submitted = {m: list(a) for m, a in REFERENCE.items() if m not in dropped}

    result = compare_profiles(REFERENCE, submitted)

    assert result.summary.matched == 18
    assert result.summary.mismatched == 0
    assert result.summary.missing == 2
    # Not all required markers match -> partial, never identity confirmation.
    assert result.classification is ComparisonClassification.PARTIAL_MATCH
    assert result.summary.match_percentage == 90.0
    for marker in dropped:
        entry = next(r for r in result.markers if r.marker == marker)
        assert entry.status is MarkerStatus.MISSING_SUBMITTED
        assert entry.submitted_alleles is None
        assert entry.reference_alleles is not None


def test_missing_reference_marker_is_detected() -> None:
    reference = {m: list(a) for m, a in REFERENCE.items() if m != "TPOX"}

    result = compare_profiles(reference, dict(REFERENCE))

    entry = next(r for r in result.markers if r.marker == "TPOX")
    assert entry.status is MarkerStatus.MISSING_REFERENCE
    assert entry.reference_alleles is None
    assert result.summary.missing == 1
    assert result.classification is ComparisonClassification.PARTIAL_MATCH


# ---------------------------------------------------------------------------
# Validation rejects malformed input with structured errors
# ---------------------------------------------------------------------------
def test_invalid_allele_value_is_rejected() -> None:
    submitted = {m: list(a) for m, a in REFERENCE.items()}
    submitted["TH01"] = [7, 999]  # outside the marker's demonstration range

    with pytest.raises(StrProfileValidationError) as excinfo:
        compare_profiles(REFERENCE, submitted)
    assert any("TH01" in issue for issue in excinfo.value.issues)


def test_unknown_marker_is_rejected() -> None:
    submitted = {m: list(a) for m, a in REFERENCE.items()}
    submitted["UNKNOWN_MARKER"] = [10, 11]

    with pytest.raises(StrProfileValidationError) as excinfo:
        compare_profiles(REFERENCE, submitted)
    assert any("UNKNOWN_MARKER" in issue for issue in excinfo.value.issues)


def test_empty_profile_is_rejected() -> None:
    with pytest.raises(StrProfileValidationError):
        compare_profiles(REFERENCE, {})


def test_non_numeric_and_null_alleles_are_rejected() -> None:
    with pytest.raises(StrProfileValidationError):
        compare_profiles(REFERENCE, {**REFERENCE, "D5S818": ["x", 10]})
    with pytest.raises(StrProfileValidationError):
        compare_profiles(REFERENCE, {**REFERENCE, "D5S818": [None, 10]})
    # Booleans are not numbers here.
    with pytest.raises(StrProfileValidationError):
        compare_profiles(REFERENCE, {**REFERENCE, "D5S818": [True, 10]})


def test_three_alleles_are_rejected() -> None:
    with pytest.raises(StrProfileValidationError) as excinfo:
        compare_profiles(REFERENCE, {**REFERENCE, "CSF1PO": [10, 11, 12]})
    assert any("exactly 2" in issue for issue in excinfo.value.issues)


def test_single_allele_is_rejected() -> None:
    with pytest.raises(StrProfileValidationError):
        compare_profiles(REFERENCE, {**REFERENCE, "CSF1PO": [10]})


def test_wrong_container_type_is_rejected() -> None:
    with pytest.raises(StrProfileValidationError):
        compare_profiles(REFERENCE, {**REFERENCE, "CSF1PO": "10,11"})
    with pytest.raises(StrProfileValidationError):
        compare_profiles(REFERENCE, [15, 16])  # not a mapping at all


def test_validation_collects_all_issues_without_repairing() -> None:
    bad = {"BOGUS": [1, 2], "D3S1358": [500, 501]}
    with pytest.raises(StrProfileValidationError) as excinfo:
        validate_profile(bad, require_complete=False)
    assert len(excinfo.value.issues) >= 2


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_results_are_deterministic() -> None:
    submitted = {m: list(a) for m, a in REFERENCE.items()}
    submitted["D8S1179"] = _mismatched_pair(REFERENCE["D8S1179"], "D8S1179")
    del submitted["SE33"]

    first = compare_profiles(REFERENCE, submitted)
    second = compare_profiles(REFERENCE, submitted)

    assert first == second
    assert [r.marker for r in first.markers] == list(STR_PANEL)  # canonical order


def test_marker_results_carry_safe_structured_fields() -> None:
    result = compare_profiles(REFERENCE, dict(REFERENCE))
    for entry in result.markers:
        assert entry.marker in STR_PANEL
        assert isinstance(entry.status, MarkerStatus)
        assert entry.reference_alleles is not None
        assert entry.submitted_alleles is not None
        # Alleles are always reported sorted — order-independent by design.
        assert list(entry.reference_alleles) == sorted(entry.reference_alleles)
