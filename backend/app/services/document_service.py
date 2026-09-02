"""Verification-document business logic (Step 6).

Secure upload pipeline: case ownership → file validation (extension,
content type, size, magic bytes) → server-generated identifiers and
filenames → metadata persistence. No AI/OCR/extraction happens here —
documents wait in UPLOADED for the Step 7 pipeline.

The uploader is ALWAYS the authenticated user; identity/case/user ids from
the request are never accepted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.models.verification_audit import AuditEventType
from app.models.verification_case import VerificationCase
from app.models.verification_document import (
    DocumentType,
    ProcessingStatus,
    VerificationDocument,
)
from app.services import audit_service, document_storage_service, verification_case_service

logger = logging.getLogger(__name__)

_MAX_ID_RETRIES = 5

#: Safe display labels for document types (audit text only, never paths).
_DOCUMENT_TYPE_LABELS: dict[DocumentType, str] = {
    DocumentType.DNA_REPORT: "DNA report",
    DocumentType.BLOOD_TEST: "blood test",
    DocumentType.OTHER: "supporting document",
}

#: Allowed extension -> canonical content type. The extension alone is never
#: trusted: declared content type and file signature are checked as well.
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

#: Content-type aliases browsers sometimes send (treated as the canonical type).
_CONTENT_TYPE_ALIASES: dict[str, str] = {"image/jpg": "image/jpeg"}

#: Magic-byte signatures per canonical content type (anti-spoofing).
_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


class DocumentValidationError(ValueError):
    """Unsupported/malformed upload — maps to HTTP 422."""


class DocumentTooLargeError(ValueError):
    """Upload exceeds the configured limit — maps to HTTP 413."""


class DocumentNotFoundError(LookupError):
    """Document missing or not visible — maps to HTTP 404."""


class DocumentIdGenerator:
    """Sequential per-year document identifiers: GVD-YYYY-NNNNNN."""

    @staticmethod
    def next(db: Session) -> str:
        year = datetime.now(timezone.utc).year
        prefix = f"GVD-{year}-"
        # Zero-padded suffixes make lexical max() equal to numeric max().
        last = db.execute(
            select(func.max(VerificationDocument.document_id)).where(
                VerificationDocument.document_id.like(f"{prefix}%")
            )
        ).scalar_one_or_none()
        next_number = int(last[len(prefix) :]) + 1 if last else 1
        return f"{prefix}{next_number:06d}"


def _validate_upload(filename: str | None, content_type: str | None, data: bytes) -> tuple[str, str]:
    """Validate extension, declared content type, size and magic bytes.

    Returns (extension, canonical_content_type) or raises.
    """
    settings = get_settings()
    max_bytes = settings.max_document_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise DocumentTooLargeError(
            f"File exceeds the {settings.max_document_size_mb} MB limit."
        )
    if len(data) == 0:
        raise DocumentValidationError("The uploaded file is empty.")

    name = filename or ""
    dot = name.rfind(".")
    extension = name[dot:].lower() if dot > 0 else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError("Unsupported file type. Allowed: PDF, PNG, JPG, JPEG.")

    canonical = ALLOWED_EXTENSIONS[extension]
    declared = _CONTENT_TYPE_ALIASES.get((content_type or "").lower(), (content_type or "").lower())
    if declared and declared != canonical:
        raise DocumentValidationError(
            "Declared content type does not match the file extension."
        )

    if not any(data.startswith(signature) for signature in _MAGIC_BYTES[canonical]):
        raise DocumentValidationError("File content does not match its extension.")

    return extension, canonical


async def store_upload(
    db: Session,
    user: User,
    verification_id: str,
    file: UploadFile,
    document_type: DocumentType = DocumentType.DNA_REPORT,
) -> tuple[VerificationCase, VerificationDocument]:
    """Validate and persist one upload for an accessible case."""
    case = verification_case_service.get_case(db, user, verification_id)

    data = await file.read()
    extension, canonical_type = _validate_upload(file.filename, file.content_type, data)

    stored_filename = document_storage_service.generate_stored_filename(extension)
    document_storage_service.save(stored_filename, data)

    try:
        document = VerificationDocument(
            document_id=DocumentIdGenerator.next(db),
            verification_case_id=case.id,
            original_filename=document_storage_service.sanitize_original_filename(file.filename),
            stored_filename=stored_filename,
            content_type=canonical_type,
            file_size=len(data),
            storage_path=stored_filename,
            document_type=document_type,
            processing_status=ProcessingStatus.UPLOADED,
            uploaded_by_user_id=user.id,
        )
        db.add(document)
        db.commit()
    except IntegrityError:
        # ID collision: roll back and retry; never leave an orphaned file.
        db.rollback()
        document_storage_service.delete(stored_filename)
        raise
    db.refresh(document)
    logger.info(
        "Document %s uploaded to case %s by user_id=%d (%d bytes)",
        document.document_id,
        case.verification_id,
        user.id,
        len(data),
    )
    audit_service.record_event(
        db,
        case,
        user,
        AuditEventType.DOCUMENT_UPLOADED,
        f"Document {document.document_id} uploaded "
        f"({_DOCUMENT_TYPE_LABELS[document.document_type]}).",
    )
    return case, document


def list_documents(db: Session, user: User, verification_id: str) -> tuple[VerificationCase, list[VerificationDocument]]:
    """Documents of an accessible case (oldest first), metadata only."""
    case = verification_case_service.get_case(db, user, verification_id)
    documents = list(
        db.execute(
            select(VerificationDocument)
            .where(VerificationDocument.verification_case_id == case.id)
            .order_by(VerificationDocument.id.asc())
        ).scalars().all()
    )
    return case, documents


def get_document(db: Session, user: User, verification_id: str, document_id: str) -> VerificationDocument:
    """One document of an accessible case; foreign ids answer not-found."""
    case = verification_case_service.get_case(db, user, verification_id)
    document = db.execute(
        select(VerificationDocument).where(
            VerificationDocument.verification_case_id == case.id,
            VerificationDocument.document_id == document_id.strip(),
        )
    ).scalar_one_or_none()
    if document is None:
        raise DocumentNotFoundError(f"No document found for id {document_id!r}")
    return document


def delete_document(db: Session, user: User, verification_id: str, document_id: str) -> None:
    """Remove metadata and stored file (missing files are tolerated)."""
    document = get_document(db, user, verification_id, document_id)
    document_storage_service.delete(document.stored_filename)
    db.delete(document)
    db.commit()
    logger.info("Document %s deleted from case %s", document_id, verification_id)
