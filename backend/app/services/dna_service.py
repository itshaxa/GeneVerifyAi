"""Internal access to reference DNA profiles.

These functions are meant for internal workflows (future verification
service) and tests — NOT for direct exposure through operator-facing API
responses.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dna_profile import DnaProfile
from app.services.str_engine.panel import validate_str_markers


def get_profile_by_identity_id(db: Session, identity_id: int) -> DnaProfile | None:
    """Return the reference DNA profile linked to an identity, if any."""
    return db.execute(
        select(DnaProfile).where(DnaProfile.identity_record_id == identity_id)
    ).scalar_one_or_none()


def get_reference_markers_by_identity_id(db: Session, identity_id: int) -> dict[str, list[float]] | None:
    """Return validated STR marker data ready for the deterministic STR engine."""
    profile = get_profile_by_identity_id(db, identity_id)
    if profile is None:
        return None
    return validate_str_markers(profile.markers)
