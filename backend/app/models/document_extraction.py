"""Persistence model for AI document extraction results (Step 7).

One extraction per document (1:1). Stores audit-grade metadata: which model
produced the extraction, when, how many markers survived validation, and a
safe validation note. Never stores API keys or raw provider payloads.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ExtractionStatus(str, enum.Enum):
    """Outcome of one AI extraction attempt for a document."""

    #: Extraction ran and the STR profile (full or partial) passed validation.
    SUCCEEDED = "SUCCEEDED"
    #: Provider/parsing/validation failure — no usable STR profile.
    FAILED = "FAILED"


class DocumentExtraction(Base):
    """Structured result of the AI document-intelligence pipeline."""

    __tablename__ = "document_extractions"
    __table_args__ = (
        UniqueConstraint(
            "verification_document_id", name="uq_document_extractions_document"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    verification_document_id: Mapped[int] = mapped_column(
        ForeignKey("verification_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, native_enum=False, length=20),
        default=ExtractionStatus.FAILED,
        nullable=False,
    )

    #: Safe, validated identity fields (or null). No raw document content.
    extracted_identity_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: Validated STR markers against the canonical panel; null when unusable.
    extracted_str_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extracted_marker_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    #: Audit trail: which model produced the extraction.
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    #: User-safe summary of why validation failed (never a stack trace).
    validation_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentExtraction document_pk={self.verification_document_id} "
            f"status={self.extraction_status.value}>"
        )
