"""Tests for CNIC format validation and STR panel marker validation."""

import pytest

from app.core.cnic import InvalidCnicError, is_valid_cnic, normalize_cnic
from app.services.str_engine.panel import STR_PANEL, validate_str_markers


class TestCnicNormalization:
    def test_canonical_form_accepted(self) -> None:
        assert normalize_cnic("99900-0000001-1") == "99900-0000001-1"

    def test_whitespace_trimmed(self) -> None:
        assert normalize_cnic("  99900-0000001-1  ") == "99900-0000001-1"

    def test_digits_only_form_normalized(self) -> None:
        assert normalize_cnic("9990000000011") == "99900-0000001-1"

    @pytest.mark.parametrize(
        "bad_value",
        ["", "1234", "99900-0000001", "99900-0000001-12", "999O0-0000001-1", "99900 0000001 12"],
    )
    def test_malformed_rejected(self, bad_value: str) -> None:
        with pytest.raises(InvalidCnicError):
            normalize_cnic(bad_value)
        assert not is_valid_cnic(bad_value)


def _full_profile() -> dict[str, list[float]]:
    return {marker: [10.0, 12.0] for marker in STR_PANEL}


class TestStrMarkerValidation:
    def test_valid_profile_passes(self) -> None:
        normalized = validate_str_markers(_full_profile())
        assert set(normalized) == set(STR_PANEL)
        assert all(len(alleles) == 2 for alleles in normalized.values())

    def test_missing_marker_rejected(self) -> None:
        profile = _full_profile()
        del profile["SE33"]
        with pytest.raises(ValueError):
            validate_str_markers(profile)

    def test_unknown_marker_rejected(self) -> None:
        profile = _full_profile()
        profile["FAKE01"] = [10, 11]
        with pytest.raises(ValueError):
            validate_str_markers(profile)

    def test_three_alleles_rejected(self) -> None:
        profile = _full_profile()
        profile["vWA"] = [10, 11, 12]
        with pytest.raises(ValueError):
            validate_str_markers(profile)

    def test_one_allele_rejected(self) -> None:
        profile = _full_profile()
        profile["TH01"] = [7]
        with pytest.raises(ValueError):
            validate_str_markers(profile)

    def test_non_numeric_allele_rejected(self) -> None:
        profile = _full_profile()
        profile["FGA"] = [21, "x"]  # type: ignore[list-item]
        with pytest.raises(ValueError):
            validate_str_markers(profile)

    def test_non_positive_allele_rejected(self) -> None:
        profile = _full_profile()
        profile["TPOX"] = [0, 11]
        with pytest.raises(ValueError):
            validate_str_markers(profile)
