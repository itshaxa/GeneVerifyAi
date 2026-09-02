"""Verification-case orchestration for the deterministic STR engine.

Flow (all authorization from Step 4 rules — never from request data):

    case lookup (ownership) -> internal reference DNA lookup ->
    submitted-profile validation -> deterministic comparison -> persist result

The reference profile ALWAYS comes from the identity linked to the case;
clients can only supply the submitted profile. Invalid submitted data raises
structured errors without touching the database.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.dna_comparison import DnaComparisonResult
from app.models.user import User
from app.models.verification_audit import AuditEventType
from app.models.verification_case import CaseStatus, VerificationCase
from app.services import audit_service, dna_service, verification_case_service
from app.services.str_engine.comparison import ComparisonResult, compare_profiles

logger = logging.getLogger(__name__)


class ReferenceProfileUnavailableError(LookupError):
    """Raised when the case's identity has no reference DNA profile."""


def compare_for_case(
    db: Session,
    user: User,
    verification_id: str,
    submitted_raw: Any,
) -> tuple[VerificationCase, ComparisonResult, DnaComparisonResult]:
    """Run one deterministic comparison for an accessible case.

    Propagates VerificationCaseNotFoundError (404 semantics, ownership
    enforced by the case service) and StrProfileValidationError (malformed
    submitted profile — nothing is persisted in that case).
    """
    case = verification_case_service.get_case(db, user, verification_id)

    reference = dna_service.get_reference_markers_by_identity_id(
        db, case.identity_record_id
    )
    if reference is None:
        raise ReferenceProfileUnavailableError(
            f"No reference DNA profile is linked to the identity of case "
            f"{case.verification_id}"
        )

    # Raises StrProfileValidationError before anything is written.
    result = compare_profiles(reference, submitted_raw)

    stored = DnaComparisonResult(
        verification_case_id=case.id,
        classification=result.classification,
        total_markers=result.summary.total_markers,
        matched_markers=result.summary.matched,
        mismatched_markers=result.summary.mismatched,
        missing_markers=result.summary.missing,
        invalid_markers=result.summary.invalid,
        match_percentage=result.summary.match_percentage,
        marker_results=[
            {
                "marker": marker.marker,
                "status": marker.status.value,
                "reference_alleles": list(marker.reference_alleles)
                if marker.reference_alleles is not None
                else None,
                "submitted_alleles": list(marker.submitted_alleles)
                if marker.submitted_alleles is not None
                else None,
                "reason": marker.reason,
            }
            for marker in result.markers
        ],
        submitted_markers=submitted_raw,
    )
    db.add(stored)

    # A comparison means DNA evidence is being processed: move DRAFT cases on.
    if case.status is CaseStatus.DRAFT:
        case.status = CaseStatus.IN_PROGRESS

    db.commit()
    db.refresh(stored)
    db.refresh(case)
    logger.info(
        "DNA comparison for case %s: %s (%.1f%%)",
        case.verification_id,
        result.classification.value,
        result.summary.match_percentage,
    )
    audit_service.record_event(
        db,
        case,
        user,
        AuditEventType.DNA_COMPARED,
        "Submitted STR profile compared with registered profile "
        f"({result.classification.value}, {result.summary.match_percentage:.1f}%).",
    )
    return case, result, stored
