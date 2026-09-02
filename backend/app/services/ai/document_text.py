"""Read a printed STR marker table out of a document's text stream.

The development mock provider needs to be able to read the alleles a report
actually carries, so that a document whose profile differs from the registered
reference can be exercised end-to-end without a Qwen API key.

This is deliberately NOT a PDF library. It recognises only the simplest
uncompressed PDF text form that our generated demonstration documents emit:
``(text) Tj`` text-showing operators written verbatim into the content stream
(fpdf2 with page compression disabled). Compressed streams, font subsetting,
vector drawings and scans are unreadable here - which is exactly why a real
deployment uses the Qwen vision provider instead of this module.

Marker rows are recognised as ``NAME | allele, allele``. Rows are returned in
document order, later duplicates overwrite earlier ones, and NOTHING is
filtered against the canonical panel: whether a marker name or an allele value
is acceptable is decided by the strict ``ExtractedStrProfile`` schema and by
the deterministic STR engine, never by this reader. Silently dropping or
"repairing" a printed value here would defeat that validation.
"""

from __future__ import annotations

import re

#: ``(text) Tj`` - one drawn text string, as written by uncompressed PDF output.
_TEXT_OPERATOR = re.compile(rb"\((.*?)\)\s*Tj", re.DOTALL)
#: PDF string literals escape parens and backslashes: ``\( `` ``\) `` ``\\``.
_ESCAPE = re.compile(rb"\\([()\\])")
#: A printed marker row: ``D3S1358    |  15,  16`` (also covers micro-variants).
_MARKER_ROW = re.compile(r"^([A-Za-z0-9]+)\s*\|\s*([0-9.]+)\s*,\s*([0-9.]+)\s*$")


def _unescape(raw: bytes) -> str:
    return _ESCAPE.sub(rb"\1", raw).decode("latin-1", errors="replace")


def text_strings(content: bytes) -> list[str]:
    """Every text string drawn by an uncompressed PDF, in document order."""
    return [_unescape(match) for match in _TEXT_OPERATOR.findall(content)]


def str_markers_from_text(lines: list[str]) -> dict[str, list[float]]:
    """Collect ``{marker: [allele, allele]}`` from ``NAME | a, b`` lines."""
    markers: dict[str, list[float]] = {}
    for line in lines:
        match = _MARKER_ROW.match(line.strip())
        if not match:
            continue
        marker, first, second = match.groups()
        try:
            markers[marker] = [float(first), float(second)]
        except ValueError:  # e.g. "1..5" - not a number, so not a marker row
            continue
    return markers


def str_markers_from_document(content: bytes) -> dict[str, list[float]]:
    """Read the printed marker table of a document; ``{}`` when unreadable.

    An empty result means "this provider could not read the document", and the
    caller decides what to fall back to.
    """
    if not content:
        return {}
    return str_markers_from_text(text_strings(content))
