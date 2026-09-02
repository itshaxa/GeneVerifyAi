"""Synthetic reference DNA/STR profile model.

Marker data is stored as structured JSON: ``{"D3S1358": [15, 16], ...}`` with
exactly the markers of the demonstration panel and two allele values each.
The representation can be passed directly to the deterministic STR engine.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DnaProfile(Base):
    """Reference STR profile bound one-to-one to a synthetic identity record."""

    __tablename__ = "dna_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    identity_record_id: Mapped[int] = mapped_column(
        ForeignKey("identity_records.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    profile_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    #: {"marker": [allele_a, allele_b]} for every marker in the STR panel.
    markers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    identity_record: Mapped["IdentityRecord"] = relationship(  # noqa: F821
        back_populates="dna_profile"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<DnaProfile code={self.profile_code!r} identity_id={self.identity_record_id}>"
