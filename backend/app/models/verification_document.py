"""Metadata for documents uploaded to a verification case (Step 6).

File binaries live on the local filesystem (``DOCUMENT_STORAGE_PATH``,
gitignored, never served statically) — SQLite stores metadata and the
server-generated stored filename only.

Step 6 performs no AI/OCR/extraction: documents start in ``UPLOADED`` and
wait for the Step 7 document-intelligence pipeline.
"""

from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DocumentType(str, enum.Enum):
    """Kind of uploaded evidence. Extensible in later stages."""

    DNA_REPORT = "DNA_REPORT"
    BLOOD_TEST = "BLOOD_TEST"
    OTHER = "OTHER"


class ProcessingStatus(str, enum.Enum):
    """Document pipeline state. Step 6 only ever writes UPLOADED."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class VerificationDocument(Base):
    """One uploaded DNA/blood-test document bound to a verification case."""

    __tablename__ = "verification_documents"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_verification_documents_document_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    #: Public identifier (GVD-YYYY-NNNNNN); internal PK is never exposed.
    document_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    verification_case_id: Mapped[int] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    #: Sanitized display name supplied by the uploader (never used on disk).
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Server-generated filename (uuid hex + extension) inside the storage root.
    stored_filename: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Storage location relative to the configured storage root (internal).
    storage_path: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False, length=20),
        nullable=False,
        default=DocumentType.DNA_REPORT,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, native_enum=False, length=20),
        nullable=False,
        default=ProcessingStatus.UPLOADED,
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    verification_case: Mapped["VerificationCase"] = relationship()  # noqa: F821
    uploader: Mapped["User"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<VerificationDocument id={self.document_id!r} case_id={self.verification_case_id}>"
