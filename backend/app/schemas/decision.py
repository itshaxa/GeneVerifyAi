"""Step 8 schemas: verification decision API contracts.

Safe response model — never exposes raw DNA profiles, reference markers,
password hashes, JWTs, API keys, filesystem paths or raw provider responses.
"""

from datetime import datetime

from pydantic import BaseModel

from app.models.verification_decision import ConsistencyLevel, DecisionOutcome


class DecisionResponse(BaseModel):
    """GET/POST /api/v1/verifications/{id}/decision — safe result."""

    verification_id: str
    decision: DecisionOutcome
    evidence_score: int
    dna_classification: str | None
    dna_match_percentage: float | None
    identity_consistency: ConsistencyLevel
    document_consistency: ConsistencyLevel
    explanation: str
    created_at: datetime
    updated_at: datetime
