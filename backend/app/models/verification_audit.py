"""Persistence model for the verification audit trail (Step 9).

One row per meaningful, completed action on a verification case. The trail is
append-only from the application's point of view: events are written by the
service layer right after the operation they describe has succeeded, and are
never produced from client-supplied data.

A stored event NEVER contains passwords, JWTs, API keys, raw DNA markers,
uploaded document contents, filesystem paths or raw AI provider responses —
only a safe, human-readable summary line suitable for a report.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class AuditEventType(str, enum.Enum):
    """The auditable actions of the verification pipeline (Steps 4-9)."""

    CASE_CREATED = "CASE_CREATED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_PROCESSED = "DOCUMENT_PROCESSED"
    DNA_COMPARED = "DNA_COMPARED"
    DECISION_GENERATED = "DECISION_GENERATED"
    REPORT_GENERATED = "REPORT_GENERATED"


#: Short, safe labels used by the report/timeline rendering.
AUDIT_EVENT_LABELS: dict[AuditEventType, str] = {
    AuditEventType.CASE_CREATED: "Case created",
    AuditEventType.DOCUMENT_UPLOADED: "Document uploaded",
    AuditEventType.DOCUMENT_PROCESSED: "AI extraction completed",
    AuditEventType.DNA_COMPARED: "DNA comparison completed",
    AuditEventType.DECISION_GENERATED: "Verification decision generated",
    AuditEventType.REPORT_GENERATED: "Report generated",
}


class VerificationAuditEvent(Base):
    """One append-only audit entry for a verification case."""

    __tablename__ = "verification_audit_events"
    __table_args__ = (
        # Timeline reads are always "events of one case, in time order".
        Index("ix_audit_events_case_created", "verification_case_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    verification_case_id: Mapped[int] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Derived from the authenticated user only; RESTRICT keeps actors resolvable.
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, native_enum=False, length=32),
        nullable=False,
    )
    event_description: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    verification_case: Mapped["VerificationCase"] = relationship()  # noqa: F821
    actor: Mapped["User"] = relationship(lazy="joined")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<VerificationAuditEvent case_id={self.verification_case_id} "
            f"type={self.event_type.value}>"
        )
