"""Verification case business logic.

Ownership model (deliberately simple for the prototype):
- the creator can always access their own cases;
- admins may review all cases (audit/expansion point for role management);
- any other user gets a not-found response — case existence is never leaked.

The creator is ALWAYS taken from the authenticated user, never from the
request body. Verification IDs are generated server-side (GV-YYYY-NNNNNN).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.verification_audit import AuditEventType
from app.models.verification_case import CaseStatus, VerificationCase
from app.services import audit_service, identity_service

logger = logging.getLogger(__name__)

_MAX_ID_RETRIES = 5


class VerificationCaseNotFoundError(LookupError):
    """Raised when a case does not exist or is not visible to the user."""


class VerificationIdGenerator:
    """Sequential per-year identifiers: readable for demos, unique in DB."""

    @staticmethod
    def next(db: Session) -> str:
        year = datetime.now(timezone.utc).year
        prefix = f"GV-{year}-"
        # Zero-padded suffixes make lexical max() equal to numeric max().
        last = db.execute(
            select(func.max(VerificationCase.verification_id)).where(
                VerificationCase.verification_id.like(f"{prefix}%")
            )
        ).scalar_one_or_none()
        next_number = int(last[len(prefix) :]) + 1 if last else 1
        return f"{prefix}{next_number:06d}"


def create_case(db: Session, user: User, raw_cnic: str) -> VerificationCase:
    """Create a DRAFT case linked to the identity for ``raw_cnic``.

    Propagates InvalidCnicError / IdentityNotFoundError from the identity
    service: a case is never created without a valid existing identity.
    """
    identity = identity_service.find_identity_by_cnic(db, raw_cnic)

    for attempt in range(_MAX_ID_RETRIES):
        case = VerificationCase(
            verification_id=VerificationIdGenerator.next(db),
            identity_record_id=identity.id,
            created_by_user_id=user.id,
            status=CaseStatus.DRAFT,
        )
        db.add(case)
        try:
            db.commit()
            break
        except IntegrityError:
            # Concurrent creation raced on the sequential ID — retry.
            db.rollback()
            logger.warning("Verification ID collision (attempt %d)", attempt + 1)
    else:  # pragma: no cover - extremely unlikely with the retry window
        raise RuntimeError("Could not allocate a unique verification ID")

    db.refresh(case)
    logger.info("Verification case %s created by user_id=%d", case.verification_id, user.id)
    audit_service.record_event(
        db,
        case,
        user,
        AuditEventType.CASE_CREATED,
        "Verification case created.",
    )
    return case


def _visible_to(user: User, case: VerificationCase) -> bool:
    return user.role is UserRole.ADMIN or case.created_by_user_id == user.id


def get_case(db: Session, user: User, verification_id: str) -> VerificationCase:
    """Return the case if it exists and is visible to ``user``.

    Foreign cases are reported as not-found so existence is never disclosed.
    """
    case = db.execute(
        select(VerificationCase).where(VerificationCase.verification_id == verification_id.strip())
    ).scalar_one_or_none()
    if case is None or not _visible_to(user, case):
        raise VerificationCaseNotFoundError(
            f"No verification case found for id {verification_id!r}"
        )
    return case


def list_cases_for_user(db: Session, user: User) -> list[VerificationCase]:
    """Owners see their own cases; admins see all (newest first)."""
    query = select(VerificationCase).order_by(VerificationCase.id.desc())
    if user.role is not UserRole.ADMIN:
        query = query.where(VerificationCase.created_by_user_id == user.id)
    return list(db.execute(query).scalars().all())


def update_case_status(
    db: Session, user: User, verification_id: str, new_status: CaseStatus
) -> VerificationCase:
    """Set the status on a visible case. State-machine rules come later."""
    case = get_case(db, user, verification_id)
    case.status = new_status
    db.commit()
    db.refresh(case)
    return case
