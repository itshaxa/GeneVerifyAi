"""Synthetic STR panel definition and marker-data validation.

This module holds the shared *data definition* of the demonstration STR panel.
Matching/comparison logic is added later in this package and stays pure and
deterministic; nothing here depends on AI code.
"""

from collections.abc import Mapping, Sequence

#: The 20 demonstration STR markers, in canonical panel order.
STR_PANEL: tuple[str, ...] = (
    "D3S1358",
    "vWA",
    "FGA",
    "D8S1179",
    "D21S11",
    "D18S51",
    "D5S818",
    "D13S317",
    "D7S820",
    "CSF1PO",
    "TH01",
    "TPOX",
    "D16S539",
    "D2S1338",
    "D19S433",
    "D12S391",
    "D10S1248",
    "D1S1656",
    "D22S1045",
    "SE33",
)

#: Plausible synthetic allele value ranges per marker (demo purposes only).
ALLELE_RANGES: dict[str, tuple[int, int]] = {
    "D3S1358": (14, 18),
    "vWA": (14, 20),
    "FGA": (18, 26),
    "D8S1179": (9, 15),
    "D21S11": (28, 34),
    "D18S51": (12, 20),
    "D5S818": (8, 13),
    "D13S317": (8, 13),
    "D7S820": (8, 12),
    "CSF1PO": (9, 13),
    "TH01": (6, 10),
    "TPOX": (8, 12),
    "D16S539": (9, 13),
    "D2S1338": (18, 24),
    "D19S433": (12, 16),
    "D12S391": (18, 25),
    "D10S1248": (13, 16),
    "D1S1656": (12, 18),
    "D22S1045": (15, 19),
    "SE33": (18, 30),
}

_ALLELES_PER_MARKER = 2


class InvalidStrProfileError(ValueError):
    """Raised when STR marker data is malformed."""


def validate_str_markers(markers: Mapping[str, Sequence[float]]) -> dict[str, list[float]]:
    """Validate marker data against the panel and return a normalized copy.

    Rules:
    - exactly the markers of ``STR_PANEL`` must be present (no extras, none missing)
    - every marker has exactly two allele values
    - every allele is a positive number

    Raises:
        InvalidStrProfileError: on any violation.
    """
    missing = [marker for marker in STR_PANEL if marker not in markers]
    if missing:
        raise InvalidStrProfileError(f"Missing STR markers: {', '.join(missing)}")

    unknown = [marker for marker in markers if marker not in STR_PANEL]
    if unknown:
        raise InvalidStrProfileError(f"Unknown STR markers: {', '.join(unknown)}")

    normalized: dict[str, list[float]] = {}
    for marker in STR_PANEL:
        alleles = markers[marker]
        if not isinstance(alleles, Sequence) or isinstance(alleles, str):
            raise InvalidStrProfileError(f"Marker {marker} must be a list of allele values")
        if len(alleles) != _ALLELES_PER_MARKER:
            raise InvalidStrProfileError(
                f"Marker {marker} must have exactly {_ALLELES_PER_MARKER} allele values"
            )
        cleaned: list[float] = []
        for allele in alleles:
            if isinstance(allele, bool) or not isinstance(allele, (int, float)):
                raise InvalidStrProfileError(f"Marker {marker} has a non-numeric allele: {allele!r}")
            value = float(allele)
            if value <= 0:
                raise InvalidStrProfileError(f"Marker {marker} has a non-positive allele: {value}")
            cleaned.append(value)
        normalized[marker] = cleaned
    return normalized
