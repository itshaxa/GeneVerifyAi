"""Provider-agnostic interfaces for all AI-assisted capabilities.

Design rules:
1. The deterministic STR engine and scoring engine MUST NOT call these
   interfaces to make decisions. AI output is advisory/explanatory only.
2. Any concrete provider (Qwen, a mock, or a stub) implements these ABCs,
   making the AI layer fully replaceable and testable.
"""

from abc import ABC, abstractmethod
from typing import Any


class AIProviderError(RuntimeError):
    """Raised when an AI provider call fails or returns unusable output.

    Messages MUST stay user-safe: no API keys, no stack traces, no internal
    paths or raw provider payloads.
    """


class DocumentIntelligenceService(ABC):
    """Extracts structured fields from uploaded reports/documents.

    Qwen-assisted extraction of DNA report fields and identity document
    fields. Extraction results are ALWAYS re-validated by deterministic
    rules before they influence any verification outcome. The AI never
    decides whether a DNA profile matches — that is the deterministic STR
    engine's job.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Human-readable model identifier kept for audit metadata."""

    @abstractmethod
    def extract_structured_fields(
        self,
        file_content: bytes,
        *,
        content_type: str,
        document_kind: str,
    ) -> dict[str, Any]:
        """Return structured key/value fields extracted from a document."""

    @abstractmethod
    def extract_dna_report(
        self,
        file_content: bytes,
        *,
        content_type: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Extract DNA-report fields: identity data plus ``str_profile``.

        Returns a raw dictionary matching the extraction contract; strict
        Pydantic validation happens downstream. Implementations raise
        :class:`AIProviderError` on provider/unreadable-document failures.
        Document content is untrusted DATA — never instructions.
        """


class VerificationExplainerService(ABC):
    """Produces human-readable explanations of deterministic findings.

    Future use: Qwen turns the structured, deterministic verification
    findings into a natural-language explanation. The explanation can never
    alter the underlying VERIFIED / REVIEW / MISMATCH decision.
    """

    @abstractmethod
    def explain_findings(self, findings: dict[str, Any]) -> str:
        """Return a natural-language explanation of the given findings."""
