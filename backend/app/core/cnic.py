"""CNIC format helpers for the synthetic demonstration dataset.

Pakistan-style demo format: ``NNNNN-NNNNNN-N`` (5-7-1 digits, 13 digits total).
Only format validation happens here — no check-digit or registry logic, and
never any lookup against real government data.
"""

import re

CANONICAL_CNIC_PATTERN = re.compile(r"^\d{5}-\d{7}-\d$")
_DIGITS_ONLY_PATTERN = re.compile(r"^\d{13}$")


class InvalidCnicError(ValueError):
    """Raised when a CNIC does not match the demonstration format."""


def normalize_cnic(raw: str) -> str:
    """Trim, strip separators and return the canonical ``NNNNN-NNNNNN-N`` form.

    Raises:
        InvalidCnicError: if the value cannot be normalized to 13 digits.
    """
    cleaned = raw.strip().replace("-", "").replace(" ", "")
    if not _DIGITS_ONLY_PATTERN.fullmatch(cleaned):
        raise InvalidCnicError(
            "CNIC must contain exactly 13 digits, e.g. 99900-0000001-1"
        )
    return f"{cleaned[0:5]}-{cleaned[5:12]}-{cleaned[12]}"


def is_valid_cnic(raw: str) -> bool:
    """Return True when the value can be normalized to a valid demo CNIC."""
    try:
        normalize_cnic(raw)
    except InvalidCnicError:
        return False
    return True
