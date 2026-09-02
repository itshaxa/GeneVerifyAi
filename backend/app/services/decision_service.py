"""Step 8: Verification Decision Engine — deterministic evidence scoring.

Combines existing evidence from Step 5 (deterministic STR comparison) and
Step 7 (AI document extraction + consistency checks) into a transparent
Prototype Evidence Score and final decision.

NEVER uses an LLM/AI to decide whether DNA matches — the STR engine is the
authoritative component for DNA comparison. This module only aggregates
already-computed results.

Scoring (simple, documented, deterministic):
  DNA STR comparison:   70 points
  Identity consistency: 20 points
  Document consistency: 10 points
  Total:               100 points

Decision rules:
  1. EXACT_MATCH + consistent identity/document        → VERIFIED
  2. EXACT_MATCH + significant inconsistency           → REVIEW_REQUIRED
  3. PARTIAL_MATCH                                     → REVIEW_REQUIRED
  4. NO_MATCH                                          → MISMATCH
  5. INVALID DNA                                       → REVIEW_REQUIRED
  6. Missing required DNA evidence                      → REVIEW_REQUIRED

The numeric score NEVER determines the outcome alone — classification and
evidence availability are always considered.

The evidence score is a deterministic prototype scoring mechanism and is not
a forensic probability or legally valid identity determination.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dna_comparison import DnaComparisonResult
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.user import User
from app.models.verification_audit import AuditEventType
from app.models.verification_case import CaseStatus, VerificationCase
from app.models.verification_decision import (
    ConsistencyLevel,
    DecisionOutcome,
    VerificationDecision,
)
from app.models.verification_document import VerificationDocument
from app.services import audit_service, verification_case_service
from app.services.str_engine.comparison import ComparisonClassification

logger = logging.getLogger(__name__)

# --- Weighting constants (documented, simple) ---------------------------------

DNA_WEIGHT = 70
IDENTITY_WEIGHT = 20
DOCUMENT_WEIGHT = 10

# --- Exception -----------------------------------------------------------------


class InsufficientEvidenceError(RuntimeError):
    """Raised when required evidence is not yet available (maps to HTTP 409)."""


# --- Evidence loading helpers ---------------------------------------------------


def latest_comparison(db: Session, case_id: int) -> DnaComparisonResult | None:
    """Fetch the most recent DNA comparison result for a case."""
    return db.execute(
        select(DnaComparisonResult)
        .where(DnaComparisonResult.verification_case_id == case_id)
        .order_by(DnaComparisonResult.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def latest_successful_extraction(db: Session, case_id: int) -> DocumentExtraction | None:
    """Fetch the most recent successful extraction across all documents in a case."""
    return db.execute(
        select(DocumentExtraction)
        .join(VerificationDocument, DocumentExtraction.verification_document_id == VerificationDocument.id)
        .where(
            VerificationDocument.verification_case_id == case_id,
            DocumentExtraction.extraction_status == ExtractionStatus.SUCCEEDED,
        )
        .order_by(DocumentExtraction.id.desc())
        .limit(1)
    ).scalar_one_or_none()


# --- Consistency evaluation ------------------------------------------------------


def compute_identity_consistency(
    case: VerificationCase, extraction: DocumentExtraction | None
) -> ConsistencyLevel:
    """Compute identity-field consistency (CNIC + name) between extraction and case."""
    if extraction is None or extraction.extracted_identity_data is None:
        return ConsistencyLevel.NOT_DETECTED

    from app.services.document_extraction_service import cnic_consistency, name_consistency

    identity_data = extraction.extracted_identity_data
    identity = case.identity_record

    cnic_result = cnic_consistency(identity_data.get("cnic"), identity.cnic)
    name_result = name_consistency(identity_data.get("patient_name"), identity.name)

    # Overall identity: if either is INCONSISTENT → INCONSISTENT;
    # both CONSISTENT → CONSISTENT; else NOT_DETECTED.
    levels = (cnic_result.value, name_result.value)
    if "INCONSISTENT" in levels:
        return ConsistencyLevel.INCONSISTENT
    if levels == ("CONSISTENT", "CONSISTENT"):
        return ConsistencyLevel.CONSISTENT
    return ConsistencyLevel.NOT_DETECTED


def compute_document_consistency(
    extraction: DocumentExtraction | None,
) -> ConsistencyLevel:
    """Document consistency: whether the extracted STR profile is complete.

    CONSISTENT = extraction succeeded with a full 20-marker profile.
    INCONSISTENT = extraction failed or produced no usable STR profile.
    NOT_DETECTED = no extraction exists.
    """
    if extraction is None:
        return ConsistencyLevel.NOT_DETECTED
    if extraction.extraction_status == ExtractionStatus.FAILED:
        return ConsistencyLevel.INCONSISTENT
    # SUCCEEDED — check if STR profile was present
    if extraction.extracted_str_profile and extraction.extracted_marker_count > 0:
        return ConsistencyLevel.CONSISTENT
    return ConsistencyLevel.INCONSISTENT


# --- Scoring ---------------------------------------------------------------------


def _dna_score_with_percentage(
    classification: str | None, match_percentage: float | None
) -> int:
    """Score DNA evidence out of 70 points based on the Step 5 result."""
    if classification is None:
        return 0
    match classification:
        case "EXACT_MATCH":
            return DNA_WEIGHT
        case "PARTIAL_MATCH":
            pct = match_percentage or 0.0
            # Proportional, capped at 60 to prevent auto-VERIFIED on partial.
            return min(int(DNA_WEIGHT * pct / 100.0), DNA_WEIGHT - 10)
        case "NO_MATCH":
            return 0
        case _:
            return 0


def _identity_score(level: ConsistencyLevel) -> int:
    if level == ConsistencyLevel.CONSISTENT:
        return IDENTITY_WEIGHT
    # INCONSISTENT or NOT_DETECTED get 0
    return 0


def _document_score(level: ConsistencyLevel) -> int:
    if level == ConsistencyLevel.CONSISTENT:
        return DOCUMENT_WEIGHT
    return 0


def evidence_breakdown(
    dna_classification: str | None,
    dna_match_percentage: float | None,
    identity_consistency: ConsistencyLevel,
    document_consistency: ConsistencyLevel,
) -> dict[str, int]:
    """Per-component points of the documented 70/20/10 weighting.

    Exposed read-only for the Step 9 report so the breakdown shown to an
    operator always comes from the very same formula the decision used —
    it never recomputes or alters a stored decision.
    """
    dna = _dna_score_with_percentage(dna_classification, dna_match_percentage)
    identity = _identity_score(identity_consistency)
    document = _document_score(document_consistency)
    return {
        "dna": dna,
        "identity": identity,
        "document": document,
        "total": dna + identity + document,
    }


# --- Decision rules ----------------------------------------------------------------


def _determine_decision(
    dna_classification: str | None,
    identity_consistency: ConsistencyLevel,
    document_consistency: ConsistencyLevel,
) -> DecisionOutcome:
    """Apply explicit deterministic rules.

    The numeric score never determines the result alone — classification and
    evidence availability are always considered.
    """
    if dna_classification is None:
        # Missing required evidence
        return DecisionOutcome.REVIEW_REQUIRED

    match dna_classification:
        case "EXACT_MATCH":
            if identity_consistency == ConsistencyLevel.INCONSISTENT or document_consistency == ConsistencyLevel.INCONSISTENT:
                return DecisionOutcome.REVIEW_REQUIRED
            return DecisionOutcome.VERIFIED
        case "PARTIAL_MATCH":
            return DecisionOutcome.REVIEW_REQUIRED
        case "NO_MATCH":
            return DecisionOutcome.MISMATCH
        case "INVALID":
            return DecisionOutcome.REVIEW_REQUIRED
        case _:
            return DecisionOutcome.REVIEW_REQUIRED


# --- Explanation generation ----------------------------------------------------------


def _build_explanation(
    dna_classification: str | None,
    dna_match_percentage: float | None,
    identity_consistency: ConsistencyLevel,
    document_consistency: ConsistencyLevel,
    matched_markers: int | None,
    total_markers: int | None,
) -> str:
    """Deterministic explanation from actual evidence. Never invents facts."""
    if dna_classification is None:
        return "No DNA comparison evidence is available yet. Manual review is required."

    parts: list[str] = []

    if dna_classification == "EXACT_MATCH":
        n = total_markers or 20
        parts.append(
            f"All {n} STR markers are consistent with the registered reference profile."
        )
    elif dna_classification == "PARTIAL_MATCH":
        pct = dna_match_percentage or 0.0
        m = matched_markers or 0
        n = total_markers or 20
        parts.append(
            f"The submitted STR profile is partially consistent ({m}/{n} markers, {pct:.1f}%). "
            "This result requires manual review and is not an identity confirmation."
        )
    elif dna_classification == "NO_MATCH":
        parts.append(
            "The submitted STR profile does not match the registered reference profile."
        )
    elif dna_classification == "INVALID":
        parts.append(
            "The submitted DNA profile could not be validated against the canonical STR panel. "
            "Manual review is required."
        )

    # Identity consistency note
    if identity_consistency == ConsistencyLevel.CONSISTENT:
        parts.append(
            "Identity information extracted from the submitted document is also consistent "
            "with the selected record."
        )
    elif identity_consistency == ConsistencyLevel.INCONSISTENT:
        parts.append(
            "Identity information extracted from the document is INCONSISTENT with the "
            "selected record — manual review is needed."
        )

    # Document consistency note
    if document_consistency == ConsistencyLevel.INCONSISTENT:
        parts.append("The document extraction indicates potential issues.")

    return " ".join(parts)


# --- Public API ---------------------------------------------------------------------


def calculate_decision(
    db: Session, user: User, verification_id: str
) -> tuple[VerificationCase, VerificationDecision]:
    """Evaluate evidence, score, decide, persist, and update case status.

    Raises VerificationCaseNotFoundError (404) or InsufficientEvidenceError (409).
    """
    case = verification_case_service.get_case(db, user, verification_id)

    # Load existing evidence
    comparison = latest_comparison(db, case.id)
    extraction = latest_successful_extraction(db, case.id)

    # Require at least a DNA comparison to produce a decision
    if comparison is None:
        raise InsufficientEvidenceError(
            "No DNA comparison result is available for this case. "
            "Please complete a STR comparison before running the assessment."
        )

    # Extract safe summary fields from evidence
    dna_classification = comparison.classification.value
    dna_match_percentage = comparison.match_percentage
    matched_markers = comparison.matched_markers
    total_markers = comparison.total_markers

    # Compute consistency levels from extraction
    identity_consistency = compute_identity_consistency(case, extraction)
    document_consistency = compute_document_consistency(extraction)

    # Score
    scores = evidence_breakdown(
        dna_classification, dna_match_percentage, identity_consistency, document_consistency
    )
    evidence_score = scores["total"]

    # Decision (classification-driven, never score-alone)
    decision = _determine_decision(dna_classification, identity_consistency, document_consistency)

    # Explanation
    explanation = _build_explanation(
        dna_classification,
        dna_match_percentage,
        identity_consistency,
        document_consistency,
        matched_markers,
        total_markers,
    )

    # Upsert: one decision per case (unique constraint)
    existing = db.execute(
        select(VerificationDecision).where(
            VerificationDecision.verification_case_id == case.id
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.dna_classification = dna_classification
        existing.dna_match_percentage = dna_match_percentage
        existing.identity_consistency = identity_consistency
        existing.document_consistency = document_consistency
        existing.evidence_score = evidence_score
        existing.decision = decision
        existing.explanation = explanation
        db.commit()
        db.refresh(existing)
        result = existing
    else:
        result = VerificationDecision(
            verification_case_id=case.id,
            dna_classification=dna_classification,
            dna_match_percentage=dna_match_percentage,
            identity_consistency=identity_consistency,
            document_consistency=document_consistency,
            evidence_score=evidence_score,
            decision=decision,
            explanation=explanation,
        )
        db.add(result)
        db.commit()
        db.refresh(result)

    # Update case status based on decision
    _update_case_status(db, case, decision)

    audit_service.record_event(
        db,
        case,
        user,
        AuditEventType.DECISION_GENERATED,
        f"Verification decision generated: {decision.value} "
        f"(prototype evidence score {evidence_score}/100).",
    )

    logger.info(
        "Decision for case %s: %s (score=%d, dna=%s, identity=%s, document=%s)",
        verification_id,
        decision.value,
        evidence_score,
        dna_classification,
        identity_consistency.value,
        document_consistency.value,
    )
    return case, result


def get_current_decision(
    db: Session, user: User, verification_id: str
) -> tuple[VerificationCase, VerificationDecision | None]:
    """Return the current decision for a case, if one exists."""
    case = verification_case_service.get_case(db, user, verification_id)
    decision = db.execute(
        select(VerificationDecision).where(
            VerificationDecision.verification_case_id == case.id
        )
    ).scalar_one_or_none()
    return case, decision


def _update_case_status(
    db: Session, case: VerificationCase, decision: DecisionOutcome
) -> None:
    """Map the decision to a case status. No complex state machine."""
    match decision:
        case DecisionOutcome.VERIFIED:
            case.status = CaseStatus.COMPLETED
        case DecisionOutcome.MISMATCH:
            case.status = CaseStatus.COMPLETED
        case DecisionOutcome.REVIEW_REQUIRED:
            case.status = CaseStatus.REVIEW_REQUIRED
    db.commit()
