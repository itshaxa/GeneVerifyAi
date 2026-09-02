"""Step 9: verification audit trail service.

Append-only recording of the meaningful actions performed on a case:

    CASE_CREATED -> DOCUMENT_UPLOADED -> DOCUMENT_PROCESSED
                 -> DNA_COMPARED -> DECISION_GENERATED -> REPORT_GENERATED

Design rules
------------
* The actor is ALWAYS the authenticated :class:`~app.models.user.User`
  object handed down by the route layer — a client-supplied user id is never
  accepted, and this module has no way to read one from a request.
* Events are recorded only *after* the operation they describe has
  successfully committed, so a failed operation never leaves a misleading
  "completed" entry behind.
* Audit writing can never break business flow: a failure is logged and
  swallowed (the primary transaction is already committed).
* Descriptions are short, safe summaries: no DNA markers, no file contents,
  no filesystem paths, no credentials, no raw provider responses.

This module deliberately depends only on the ORM models, never on other
service modules, so any service can call it without import cycles.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.verification_audit import (
    AUDIT_EVENT_LABELS,
    AuditEventType,
    VerificationAuditEvent,
)
from app.models.verification_case import VerificationCase

logger = logging.getLogger(__name__)

_MAX_DESCRIPTION_LENGTH = 255


def record_event(
    db: Session,
    case: VerificationCase,
    actor: User,
    event_type: AuditEventType,
    description: str | None = None,
) -> VerificationAuditEvent | None:
    """Append one audit event to an accessible case.

    Returns the persisted row, or ``None`` when recording failed (the error
    is logged; the caller's completed business operation is never undone).
    """
    text = (description or AUDIT_EVENT_LABELS.get(event_type, event_type.value))
    event = VerificationAuditEvent(
        verification_case_id=case.id,
        actor_user_id=actor.id,
        event_type=event_type,
        event_description=text[:_MAX_DESCRIPTION_LENGTH],
    )
    db.add(event)
    try:
        db.commit()
    except SQLAlchemyError:  # pragma: no cover - defensive
        db.rollback()
        logger.exception(
            "Could not record audit event %s for case %s",
            event_type.value,
            case.verification_id,
        )
        return None
    db.refresh(event)
    logger.info(
        "Audit: case %s event=%s actor_user_id=%d",
        case.verification_id,
        event_type.value,
        actor.id,
    )
    return event


def get_case_events(db: Session, case: VerificationCase) -> list[VerificationAuditEvent]:
    """Chronological events of one case (already-authorized caller supplies it)."""
    return list(
        db.execute(
            select(VerificationAuditEvent)
            .where(VerificationAuditEvent.verification_case_id == case.id)
            .order_by(
                VerificationAuditEvent.created_at.asc(),
                VerificationAuditEvent.id.asc(),
            )
        ).scalars().all()
    )


def event_label(event_type: AuditEventType) -> str:
    """Safe display label for an event type."""
    return AUDIT_EVENT_LABELS.get(event_type, event_type.value)
