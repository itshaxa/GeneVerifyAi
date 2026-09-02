"""Persisted result of one deterministic STR comparison for a case.

One row is written per comparison run (re-runs are allowed and kept for
auditability). The raw submitted profile is stored alongside the aggregate
numbers: the prototype has no document/lab-report source for it yet, so the
stored copy is the only audit trail of what evidence was compared. It is
internal-only and is never exposed through case list/detail endpoints.

Reference DNA is deliberately NOT duplicated here — it stays reachable only
through the linked identity's ``dna_profiles`` row.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.services.str_engine.comparison import ComparisonClassification


class DnaComparisonResult(Base):
    """Aggregate + marker-level outcome of comparing submitted vs reference."""

    __tablename__ = "dna_comparison_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    verification_case_id: Mapped[int] = mapped_column(
        ForeignKey("verification_cases.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    classification: Mapped[ComparisonClassification] = mapped_column(
        Enum(ComparisonClassification, native_enum=False, length=20),
        nullable=False,
    )
    total_markers: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_markers: Mapped[int] = mapped_column(Integer, nullable=False)
    mismatched_markers: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_markers: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_markers: Mapped[int] = mapped_column(Integer, nullable=False)
    match_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    #: Per-marker breakdown: [{"marker", "status", "reference_alleles", ...}].
    marker_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    #: Submitted evidence as received (audit trail; never served in lists).
    submitted_markers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    verification_case: Mapped["VerificationCase"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<DnaComparisonResult case_id={self.verification_case_id} "
            f"classification={self.classification.value}>"
        )
