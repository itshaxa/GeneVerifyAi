"""Persistence model for verification decisions (Step 8).

One decision per case at a time (unique FK). The decision engine combines
the existing deterministic STR comparison result and AI document-extraction
consistency signals into a transparent, deterministic Prototype Evidence Score
and a final VERIFIED / REVIEW_REQUIRED / MISMATCH decision.

This model does NOT store raw DNA profiles, reference markers, passwords,
API keys or raw provider payloads.
"""

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DecisionOutcome(str, enum.Enum):
    """Final verification decision — deterministic, never AI-driven."""

    VERIFIED = "VERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    MISMATCH = "MISMATCH"


class ConsistencyLevel(str, enum.Enum):
    """Deterministic consistency assessment of one evidence dimension."""

    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"
    NOT_DETECTED = "NOT_DETECTED"


class VerificationDecision(Base):
    """The current (or historical) verification assessment for a case."""

    __tablename__ = "verification_decisions"
    __table_args__ = (
        UniqueConstraint(
            "verification_case_id", name="uq_verification_decisions_case"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    verification_case_id: Mapped[int] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Evidence inputs (safe summary only — never raw DNA) ---
    dna_classification: Mapped[str | None] = mapped_column(String(20), nullable=True)
    dna_match_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    identity_consistency: Mapped[ConsistencyLevel] = mapped_column(
        Enum(ConsistencyLevel, native_enum=False, length=20),
        default=ConsistencyLevel.NOT_DETECTED,
        nullable=False,
    )
    document_consistency: Mapped[ConsistencyLevel] = mapped_column(
        Enum(ConsistencyLevel, native_enum=False, length=20),
        default=ConsistencyLevel.NOT_DETECTED,
        nullable=False,
    )

    # --- Outcome ---
    evidence_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision: Mapped[DecisionOutcome] = mapped_column(
        Enum(DecisionOutcome, native_enum=False, length=20),
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(String(1000), nullable=False, default="")

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    verification_case: Mapped["VerificationCase"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<VerificationDecision case_id={self.verification_case_id} "
            f"decision={self.decision.value} score={self.evidence_score}>"
        )
