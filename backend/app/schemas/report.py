"""Step 9 schemas: verification report API contracts.

The report is a *read-only projection* of evidence that already exists
(Steps 4-8) plus the audit trail. It never recomputes DNA matching and never
re-derives a decision.

Safety contract: none of these models can carry raw STR allele profiles,
reference DNA, password hashes, JWTs, API keys, filesystem/storage paths or
raw AI provider payloads — the fields below are the complete surface.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field

#: Shown on every report, PDF and frontend view.
REPORT_DISCLAIMER = (
    "GeneVerify AI is a hackathon prototype using synthetic demonstration data. "
    "It is not a legally valid forensic identification system. AI-extracted "
    "information is subject to deterministic validation and should not be "
    "treated as independent proof of identity."
)

#: Label that must always accompany AI-extracted values.
AI_EXTRACTION_LABEL = "AI-extracted information — validated before use."

#: Statement that DNA matching is deterministic (never performed by AI).
DNA_ENGINE_NOTE = (
    "DNA comparison was performed using the deterministic STR matching engine."
)

#: The score is an application-level aid, not a forensic statistic.
EVIDENCE_SCORE_LABEL = "Prototype Evidence Score"
EVIDENCE_SCORE_NOTE = (
    "Prototype evidence score — not a forensic probability or match probability."
)


class ReportIdentity(BaseModel):
    """Safe identity summary (the same fields the case view already exposes)."""

    cnic: str
    name: str
    father_name: str
    date_of_birth: date
    gender: str
    identity_status: str


class ReportDocumentSection(BaseModel):
    """Metadata of the document behind the report — never a storage path."""

    available: bool
    message: str | None = None
    document_count: int = 0
    document_id: str | None = None
    original_filename: str | None = None
    document_type: str | None = None
    content_type: str | None = None
    file_size: int | None = None
    processing_status: str | None = None
    uploaded_by: str | None = None
    uploaded_at: datetime | None = None


class ReportExtractionSection(BaseModel):
    """AI document-intelligence summary, clearly labelled as AI output."""

    available: bool
    message: str | None = None
    label: str = AI_EXTRACTION_LABEL
    extraction_status: str | None = None
    model_name: str | None = None
    extracted_name: str | None = None
    extracted_cnic: str | None = None
    cnic_consistency: str | None = None
    name_consistency: str | None = None
    identity_consistency: str | None = None
    extracted_marker_count: int = 0
    validation_note: str | None = None
    extracted_at: datetime | None = None


class ReportDnaSection(BaseModel):
    """Aggregate STR comparison result — counts only, never allele values."""

    available: bool
    message: str | None = None
    engine_note: str = DNA_ENGINE_NOTE
    classification: str | None = None
    match_percentage: float | None = None
    total_markers: int | None = None
    matched_markers: int | None = None
    mismatched_markers: int | None = None
    missing_markers: int | None = None
    invalid_markers: int | None = None
    compared_at: datetime | None = None


class ReportEvidenceSection(BaseModel):
    """Prototype Evidence Score breakdown (70 DNA / 20 identity / 10 document)."""

    available: bool
    message: str | None = None
    score_label: str = EVIDENCE_SCORE_LABEL
    score_note: str = EVIDENCE_SCORE_NOTE
    dna_score: int = 0
    identity_score: int = 0
    document_score: int = 0
    total_score: int = 0
    max_score: int = Field(default=100, ge=1)
    identity_consistency: str | None = None
    document_consistency: str | None = None
    dna_classification: str | None = None
    dna_match_percentage: float | None = None


class ReportDecisionSection(BaseModel):
    """Final deterministic decision plus the engine's own explanation."""

    available: bool
    message: str | None = None
    decision: str | None = None
    explanation: str | None = None
    decided_at: datetime | None = None


class ReportAuditEvent(BaseModel):
    """One timeline entry: when, what, who."""

    timestamp: datetime
    event_type: str
    event: str
    description: str
    actor: str


class VerificationReport(BaseModel):
    """GET /api/v1/verifications/{verification_id}/report."""

    verification_id: str
    status: str
    generated_at: datetime
    identity: ReportIdentity
    document: ReportDocumentSection
    ai_extraction: ReportExtractionSection
    dna_analysis: ReportDnaSection
    evidence: ReportEvidenceSection
    decision: ReportDecisionSection
    audit_timeline: list[ReportAuditEvent]
    disclaimer: str = REPORT_DISCLAIMER
