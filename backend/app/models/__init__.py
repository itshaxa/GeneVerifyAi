"""SQLAlchemy ORM models.

Importing this package registers every model with ``Base.metadata`` so that
``Base.metadata.create_all`` picks them all up.
"""

from app.models.dna_comparison import DnaComparisonResult
from app.models.dna_profile import DnaProfile
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.identity import Gender, IdentityRecord, IdentityStatus
from app.models.user import User, UserRole
from app.models.verification_audit import (
    AUDIT_EVENT_LABELS,
    AuditEventType,
    VerificationAuditEvent,
)
from app.models.verification_case import CaseStatus, VerificationCase
from app.models.verification_decision import (
    ConsistencyLevel,
    DecisionOutcome,
    VerificationDecision,
)
from app.models.verification_document import (
    DocumentType,
    ProcessingStatus,
    VerificationDocument,
)

__all__ = [
    "AUDIT_EVENT_LABELS",
    "AuditEventType",
    "CaseStatus",
    "ConsistencyLevel",
    "DecisionOutcome",
    "DnaComparisonResult",
    "DnaProfile",
    "DocumentExtraction",
    "DocumentType",
    "ExtractionStatus",
    "Gender",
    "IdentityRecord",
    "IdentityStatus",
    "ProcessingStatus",
    "User",
    "UserRole",
    "VerificationAuditEvent",
    "VerificationCase",
    "VerificationDecision",
    "VerificationDocument",
]
