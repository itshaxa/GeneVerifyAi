"""Verification case model.

A verification case is the central container that will later connect an
identity, submitted DNA, STR comparison, documents, AI analysis, scoring and
the final result. Identity information is NEVER duplicated here — the case
references the ``identity_records`` row instead.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.identity import IdentityRecord
from app.models.user import User


class CaseStatus(str, enum.Enum):
    """Case lifecycle states. Transition rules arrive with later stages."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEW_REQUIRED = "review_required"
    CANCELLED = "cancelled"


class VerificationCase(Base):
    """One verification workflow instance owned by the operator who created it."""

    __tablename__ = "verification_cases"
    __table_args__ = (
        UniqueConstraint("verification_id", name="uq_verification_cases_verification_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    #: Human-readable, report-safe identifier (GV-YYYY-NNNNNN) — never the PK,
    #: never derived from the CNIC.
    verification_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    identity_record_id: Mapped[int] = mapped_column(
        ForeignKey("identity_records.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, native_enum=False, length=20),
        nullable=False,
        default=CaseStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    #: Ownership references only; parents are never cascade-deleted (RESTRICT).
    identity_record: Mapped[IdentityRecord] = relationship(lazy="joined")
    creator: Mapped[User] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<VerificationCase {self.verification_id} status={self.status.value}>"
