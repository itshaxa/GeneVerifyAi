"""Step 7 document-processing pipeline (AI extraction orchestration).

    auth/ownership -> metadata -> file on disk -> PROCESSING ->
    AI document-intelligence -> strict Pydantic validation ->
    persisted DocumentExtraction -> PROCESSED

The AI only performs document understanding/extraction. It never decides
whether a DNA profile matches — that stays with the deterministic STR
engine (Step 5), which consumes the extracted profile unchanged.

Failures are controlled and audit-friendly: the document is marked FAILED,
a FAILED extraction row records a user-safe note, and no secrets/stack
traces ever leave the backend.
"""

from __future__ import annotations

import logging
import re

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.user import User
from app.models.verification_audit import AuditEventType
from app.models.verification_case import VerificationCase
from app.models.verification_document import ProcessingStatus, VerificationDocument
from app.schemas.extraction import (
    CnicConsistency,
    DocumentExtractionResult,
    NameConsistency,
)
from app.services import (
    audit_service,
    dna_service,
    document_service,
    document_storage_service,
    verification_case_service,
)
from app.services.ai.base import AIProviderError, DocumentIntelligenceService

logger = logging.getLogger(__name__)


class DocumentNotProcessableError(ValueError):
    """Document status does not allow processing — maps to HTTP 409."""


class DocumentProcessingError(RuntimeError):
    """Controlled processing failure with a user-safe message (HTTP 502)."""


def _first_validation_note(exc: ValidationError) -> str:
    """One concise, user-safe line describing invalid AI output."""
    try:
        error = exc.errors()[0]
        location = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg", "Invalid AI output."))
        note = f"{location}: {message}" if location else message
    except Exception:  # pragma: no cover - defensive
        note = "AI output failed validation."
    return note[:500]


def _mark_failed(
    db: Session,
    document: VerificationDocument,
    note: str,
    model_name: str | None,
) -> DocumentExtraction:
    """Transition the document to FAILED and record an audit row."""
    document.processing_status = ProcessingStatus.FAILED
    extraction = DocumentExtraction(
        verification_document_id=document.id,
        extraction_status=ExtractionStatus.FAILED,
        extracted_marker_count=0,
        model_name=model_name,
        validation_note=note[:500],
    )
    db.add(extraction)
    db.commit()
    db.refresh(document)
    db.refresh(extraction)
    return extraction


def process_document(
    db: Session,
    user: User,
    verification_id: str,
    document_id: str,
    ai_service: DocumentIntelligenceService,
) -> tuple[VerificationDocument, DocumentExtraction]:
    """Run the full extraction pipeline for one accessible document."""
    document = document_service.get_document(db, user, verification_id, document_id)
    case = verification_case_service.get_case(db, user, verification_id)

    if document.processing_status is ProcessingStatus.PROCESSED:
        raise DocumentNotProcessableError("This document has already been processed.")
    if document.processing_status is ProcessingStatus.PROCESSING:
        raise DocumentNotProcessableError("This document is already being processed.")

    # Raises DocumentStorageError when the stored file is missing/escaping.
    path = document_storage_service.resolve(document.stored_filename)
    content = path.read_bytes()

    # Context aids the development mock only; real providers ignore it.
    identity = case.identity_record
    reference_markers = (
        dna_service.get_reference_markers_by_identity_id(db, case.identity_record_id) or {}
    )
    context = {
        "reference_markers": reference_markers,
        "patient_name": identity.name,
        "cnic": identity.cnic,
        "date_of_birth": identity.date_of_birth.isoformat()
        if identity.date_of_birth
        else None,
        "report_date": None,
    }

    document.processing_status = ProcessingStatus.PROCESSING
    db.commit()

    try:
        raw = ai_service.extract_dna_report(
            content, content_type=document.content_type, context=context
        )
        parsed = DocumentExtractionResult.model_validate(raw)
    except AIProviderError as exc:
        logger.warning(
            "AI processing failed for document %s: %s", document.document_id, exc
        )
        _mark_failed(db, document, str(exc), ai_service.model_name)
        raise DocumentProcessingError(str(exc)) from None
    except ValidationError as exc:
        note = _first_validation_note(exc)
        logger.warning(
            "AI output rejected for document %s: %s", document.document_id, note
        )
        _mark_failed(db, document, note, ai_service.model_name)
        raise DocumentProcessingError("AI output failed validation.") from None

    profile = parsed.str_profile.root if parsed.str_profile is not None else None
    validation_note = None if profile else "No STR profile was found in the document."

    extraction = DocumentExtraction(
        verification_document_id=document.id,
        extraction_status=ExtractionStatus.SUCCEEDED,
        extracted_identity_data=parsed.identity.model_dump(mode="json"),
        extracted_str_profile=profile,
        extracted_marker_count=len(profile) if profile else 0,
        model_name=ai_service.model_name,
        validation_note=validation_note,
    )
    db.add(extraction)
    document.processing_status = ProcessingStatus.PROCESSED
    db.commit()
    db.refresh(document)
    db.refresh(extraction)
    logger.info(
        "Document %s processed for case %s: %d STR markers extracted",
        document.document_id,
        case.verification_id,
        extraction.extracted_marker_count,
    )
    audit_service.record_event(
        db,
        case,
        user,
        AuditEventType.DOCUMENT_PROCESSED,
        f"Document {document.document_id} analysed - "
        f"{extraction.extracted_marker_count} STR markers extracted.",
    )
    return document, extraction


def get_extraction(
    db: Session,
    user: User,
    verification_id: str,
    document_id: str,
) -> tuple[VerificationCase, VerificationDocument, DocumentExtraction | None]:
    """Accessible document plus its extraction (None when never processed)."""
    case = verification_case_service.get_case(db, user, verification_id)
    document = document_service.get_document(db, user, verification_id, document_id)
    extraction = db.execute(
        select(DocumentExtraction).where(
            DocumentExtraction.verification_document_id == document.id
        )
    ).scalar_one_or_none()
    return case, document, extraction


# --- Deterministic document/case consistency checks -------------------------
# These are simple equality checks on extracted fields. They NEVER replace
# DNA comparison and the AI never interprets them.


def normalize_cnic(value: str | None) -> str:
    """Reduce a CNIC to its digits so formatting differences don't matter."""
    return re.sub(r"\D", "", value or "")


def cnic_consistency(extracted_cnic: str | None, case_cnic: str) -> CnicConsistency:
    extracted_digits = normalize_cnic(extracted_cnic)
    if not extracted_digits:
        return CnicConsistency.NOT_DETECTED
    if extracted_digits == normalize_cnic(case_cnic):
        return CnicConsistency.CONSISTENT
    return CnicConsistency.INCONSISTENT


def normalize_name(value: str | None) -> str:
    """Case-insensitive, whitespace-insensitive, order-insensitive form."""
    return " ".join(sorted((value or "").strip().lower().split()))


def name_consistency(extracted_name: str | None, case_name: str) -> NameConsistency:
    extracted = normalize_name(extracted_name)
    if not extracted:
        return NameConsistency.NOT_DETECTED
    if extracted == normalize_name(case_name):
        return NameConsistency.CONSISTENT
    return NameConsistency.INCONSISTENT
