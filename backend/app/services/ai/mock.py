"""Deterministic mock document-intelligence provider.

Used ONLY in development and automated tests — it never touches the
network. It reads the STR marker table printed in the document itself, so
the whole Step 7 pipeline (process -> extract -> validate -> persist) can be
exercised deterministically without an Alibaba Cloud API key, including with
reports whose alleles deliberately differ from the registered profile.

When the document text cannot be read (compressed streams, scans, or the
bare byte payloads the test suite uploads) it falls back to the case's
reference profile from ``context`` — the original "perfectly scanned report"
simulation, now kept as a fallback only.

Behaviour is controlled by byte markers inside the document content:
* ``GV-FAIL``    -> simulated provider failure (document ends FAILED)
* ``GV-BADJSON`` -> returns output that violates the extraction schema
* ``GV-BADSTR``  -> returns an STR profile with an unknown marker
* ``GV-PARTIAL`` -> returns the resulting profile minus two markers

Identity fields always come from ``context``: this provider simulates reading
the marker table, not the whole form, so CNIC/name consistency keeps being
assessed against the case the document was uploaded to.

In production this provider is refused by the factory unless the
environment explicitly opts into development mode.

The AI still never decides anything: it only produces the profile that the
deterministic STR engine then compares.
"""

import logging
from typing import Any

from app.services.ai.base import AIProviderError, DocumentIntelligenceService
from app.services.ai.document_text import str_markers_from_document

logger = logging.getLogger(__name__)

_FAIL_MARKER = b"GV-FAIL"
_BAD_JSON_MARKER = b"GV-BADJSON"
_BAD_STR_MARKER = b"GV-BADSTR"
_PARTIAL_MARKER = b"GV-PARTIAL"

# Markers dropped when a partial extraction is simulated.
_PARTIAL_DROPS = ("D22S1045", "SE33")


class MockDocumentIntelligenceService(DocumentIntelligenceService):
    """Network-free, deterministic extraction provider for dev/tests."""

    @property
    def model_name(self) -> str:
        return "mock-document-intelligence"

    def extract_structured_fields(
        self,
        file_content: bytes,
        *,
        content_type: str,
        document_kind: str,
    ) -> dict[str, Any]:
        result = self.extract_dna_report(file_content, content_type=content_type)
        fields: dict[str, Any] = dict(result.get("identity") or {})
        fields["document_kind"] = document_kind
        return fields

    def extract_dna_report(
        self,
        file_content: bytes,
        *,
        content_type: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        context = context or {}

        if _FAIL_MARKER in file_content:
            logger.warning("Mock AI provider simulated a failure marker.")
            raise AIProviderError("AI provider failed to analyze the document.")

        if _BAD_JSON_MARKER in file_content:
            # Structurally invalid AI output: alleles must be numeric pairs.
            return {
                "identity": {"patient_name": context.get("patient_name")},
                "str_profile": {"D3S1358": [15, "not-a-number"], "EXTRA_FIELD": "oops"},
            }

        if _BAD_STR_MARKER in file_content:
            # Unknown marker name — the schema must reject this.
            return {
                "identity": {"patient_name": context.get("patient_name")},
                "str_profile": {"NOT_A_REAL_MARKER": [10, 11]},
            }

        str_profile, source = self._read_str_profile(file_content, context)
        if _PARTIAL_MARKER in file_content:
            for marker in _PARTIAL_DROPS:
                str_profile.pop(marker, None)

        logger.info(
            "Mock provider returned %d STR markers read from %s.", len(str_profile), source
        )
        return {
            "identity": {
                "patient_name": context.get("patient_name"),
                "cnic": context.get("cnic"),
                "date_of_birth": context.get("date_of_birth"),
                "report_date": context.get("report_date"),
                "laboratory_reference": "MOCK-LAB-0001",
            },
            "str_profile": str_profile,
        }

    @staticmethod
    def _read_str_profile(
        file_content: bytes, context: dict[str, Any]
    ) -> tuple[dict[str, list[float]], str]:
        """The profile printed in the document, reference data only as fallback.

        Returns ``(profile, source)`` where ``source`` is audit-friendly text
        only - marker values are never logged.
        """
        printed = str_markers_from_document(file_content)
        if printed:
            return printed, "the document's own marker table"
        return (
            dict(context.get("reference_markers") or {}),
            "the registered reference (document text unreadable)",
        )
