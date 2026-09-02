"""Step 9: verification report service.

Builds a professional verification report purely from evidence that already
exists — it is a read-only projection over:

    VerificationCase  -> identity summary
    VerificationDocument (metadata only) -> document section
    DocumentExtraction -> AI extraction summary (deterministic consistency)
    DnaComparisonResult -> aggregate STR result (counts, never alleles)
    VerificationDecision -> evidence score breakdown + final decision
    VerificationAuditEvent -> audit timeline

Nothing here computes DNA similarity, re-runs the STR engine, re-scores the
evidence or calls an AI provider. The PDF rendering lives in
:mod:`app.services.report_pdf_service`; this module assembles the data and
owns the report-side audit event.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.verification_audit import AuditEventType
from app.models.verification_case import VerificationCase
from app.models.verification_decision import VerificationDecision
from app.models.verification_document import (
    ProcessingStatus,
    VerificationDocument,
)
from app.schemas.report import (
    REPORT_DISCLAIMER,
    ReportAuditEvent,
    ReportDecisionSection,
    ReportDnaSection,
    ReportDocumentSection,
    ReportEvidenceSection,
    ReportExtractionSection,
    ReportIdentity,
    VerificationReport,
)
from app.services import (
    audit_service,
    decision_service,
    document_extraction_service,
    verification_case_service,
)
from app.services.report_pdf_service import render_pdf

logger = logging.getLogger(__name__)

NO_DOCUMENT_MESSAGE = "No document submitted."
NO_EXTRACTION_MESSAGE = "Document has not been processed."
NO_COMPARISON_MESSAGE = "DNA comparison not available."
NO_DECISION_MESSAGE = "Verification decision not available."


def _now_naive_utc() -> datetime:
    """Timestamp comparable with the naive UTC values the DB layer stores."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _documents_of(db: Session, case_id: int) -> list[VerificationDocument]:
    """All documents of the case, oldest first."""
    return list(
        db.execute(
            select(VerificationDocument)
            .where(VerificationDocument.verification_case_id == case_id)
            .order_by(VerificationDocument.id.asc())
        ).scalars().all()
    )


def _primary_document(
    documents: list[VerificationDocument],
) -> VerificationDocument | None:
    """The report's subject document: newest processed one, else newest upload."""
    if not documents:
        return None
    processed = [d for d in documents if d.processing_status is ProcessingStatus.PROCESSED]
    return (processed or documents)[-1]


def _identity_section(case: VerificationCase) -> ReportIdentity:
    identity = case.identity_record
    return ReportIdentity(
        cnic=identity.cnic,
        name=identity.name,
        father_name=identity.father_name,
        date_of_birth=identity.date_of_birth,
        gender=identity.gender.value,
        identity_status=identity.status.value,
    )


def _document_section(
    documents: list[VerificationDocument], primary: VerificationDocument | None
) -> ReportDocumentSection:
    if primary is None:
        return ReportDocumentSection(
            available=False, message=NO_DOCUMENT_MESSAGE, document_count=0
        )
    return ReportDocumentSection(
        available=True,
        message=None,
        document_count=len(documents),
        document_id=primary.document_id,
        original_filename=primary.original_filename,
        document_type=primary.document_type.value,
        content_type=primary.content_type,
        file_size=primary.file_size,
        processing_status=primary.processing_status.value,
        uploaded_by=primary.uploader.username,
        uploaded_at=primary.created_at,
    )


def _extraction_section(
    case: VerificationCase,
    extraction,
) -> ReportExtractionSection:
    if extraction is None:
        return ReportExtractionSection(available=False, message=NO_EXTRACTION_MESSAGE)

    identity_data = extraction.extracted_identity_data or {}
    identity = case.identity_record
    return ReportExtractionSection(
        available=True,
        message=None,
        extraction_status=extraction.extraction_status.value,
        model_name=extraction.model_name,
        extracted_name=identity_data.get("patient_name"),
        extracted_cnic=identity_data.get("cnic"),
        cnic_consistency=document_extraction_service.cnic_consistency(
            identity_data.get("cnic"), identity.cnic
        ).value,
        name_consistency=document_extraction_service.name_consistency(
            identity_data.get("patient_name"), identity.name
        ).value,
        identity_consistency=decision_service.compute_identity_consistency(
            case, extraction
        ).value,
        extracted_marker_count=extraction.extracted_marker_count,
        validation_note=extraction.validation_note,
        extracted_at=extraction.created_at,
    )


def _dna_section(comparison) -> ReportDnaSection:
    if comparison is None:
        return ReportDnaSection(available=False, message=NO_COMPARISON_MESSAGE)
    return ReportDnaSection(
        available=True,
        message=None,
        classification=comparison.classification.value,
        match_percentage=comparison.match_percentage,
        total_markers=comparison.total_markers,
        matched_markers=comparison.matched_markers,
        mismatched_markers=comparison.mismatched_markers,
        missing_markers=comparison.missing_markers,
        invalid_markers=comparison.invalid_markers,
        compared_at=comparison.created_at,
    )


def _evidence_section(decision: VerificationDecision | None) -> ReportEvidenceSection:
    """Reuse the stored decision and the *same* scoring breakdown — no re-scoring."""
    if decision is None:
        return ReportEvidenceSection(available=False, message=NO_DECISION_MESSAGE)

    identity_consistency = decision.identity_consistency
    document_consistency = decision.document_consistency
    scores = decision_service.evidence_breakdown(
        decision.dna_classification,
        decision.dna_match_percentage,
        identity_consistency,
        document_consistency,
    )
    return ReportEvidenceSection(
        available=True,
        message=None,
        dna_score=scores["dna"],
        identity_score=scores["identity"],
        document_score=scores["document"],
        total_score=decision.evidence_score,
        identity_consistency=identity_consistency.value,
        document_consistency=document_consistency.value,
        dna_classification=decision.dna_classification,
        dna_match_percentage=decision.dna_match_percentage,
    )


def _decision_section(decision: VerificationDecision | None) -> ReportDecisionSection:
    if decision is None:
        return ReportDecisionSection(available=False, message=NO_DECISION_MESSAGE)
    return ReportDecisionSection(
        available=True,
        message=None,
        decision=decision.decision.value,
        explanation=decision.explanation,
        decided_at=decision.updated_at,
    )


def _timeline(events) -> list[ReportAuditEvent]:
    return [
        ReportAuditEvent(
            timestamp=event.created_at,
            event_type=event.event_type.value,
            event=audit_service.event_label(event.event_type),
            description=event.event_description,
            actor=event.actor.username,
        )
        for event in events
    ]


def _assemble(db: Session, case: VerificationCase) -> VerificationReport:
    """Project the case's existing evidence into the report structure."""
    documents = _documents_of(db, case.id)
    primary = _primary_document(documents)

    extraction = decision_service.latest_successful_extraction(db, case.id)
    comparison = decision_service.latest_comparison(db, case.id)
    decision = db.execute(
        select(VerificationDecision).where(
            VerificationDecision.verification_case_id == case.id
        )
    ).scalar_one_or_none()

    report = VerificationReport(
        verification_id=case.verification_id,
        status=case.status.value,
        generated_at=_now_naive_utc(),
        identity=_identity_section(case),
        document=_document_section(documents, primary),
        ai_extraction=_extraction_section(case, extraction),
        dna_analysis=_dna_section(comparison),
        evidence=_evidence_section(decision),
        decision=_decision_section(decision),
        audit_timeline=_timeline(audit_service.get_case_events(db, case)),
        disclaimer=REPORT_DISCLAIMER,
    )
    logger.info(
        "Report assembled for case %s (status=%s)", case.verification_id, case.status.value
    )
    return report


def build_report(db: Session, user: User, verification_id: str) -> VerificationReport:
    """Assemble the current report of an accessible case (read-only, no events).

    Raises VerificationCaseNotFoundError for unknown/foreign cases so the
    route layer keeps its existing safe 404 behaviour.
    """
    case = verification_case_service.get_case(db, user, verification_id)
    return _assemble(db, case)


def generate_report_pdf(
    db: Session, user: User, verification_id: str
) -> tuple[VerificationReport, bytes, str]:
    """Build the report, render the PDF and record the REPORT_GENERATED event.

    Only this explicit generation action writes an audit event — plain report
    reads never do, so refreshing the page cannot inflate the timeline.
    """
    case = verification_case_service.get_case(db, user, verification_id)
    report = _assemble(db, case)
    pdf_bytes = render_pdf(report)

    audit_service.record_event(
        db,
        case,
        user,
        AuditEventType.REPORT_GENERATED,
        f"Verification report generated (PDF, {len(pdf_bytes)} bytes).",
    )
    filename = f"GeneVerify-Report-{case.verification_id}.pdf"
    return report, pdf_bytes, filename
