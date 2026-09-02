"""Schemas for verification case endpoints.

Responses expose only safe case information: the linked identity is rendered
as a bounded summary and DNA data is never reachable through these contracts.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.identity import Gender, IdentityStatus
from app.models.verification_case import CaseStatus


class CreateVerificationRequest(BaseModel):
    """Case creation is driven by CNIC only; the creator comes from the JWT."""

    cnic: str = Field(min_length=1, max_length=20, description="Synthetic demo CNIC")

    @field_validator("cnic")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("cnic must not be blank")
        return stripped


class CaseIdentitySummary(BaseModel):
    """Safe identity reference for the verification workflow (no DNA)."""

    model_config = ConfigDict(from_attributes=True)

    cnic: str
    name: str
    father_name: str
    date_of_birth: date
    gender: Gender
    status: IdentityStatus


class VerificationCaseResponse(BaseModel):
    verification_id: str
    status: CaseStatus
    identity: CaseIdentitySummary
    created_by_user_id: int
    created_by_username: str
    created_at: datetime
    updated_at: datetime


class VerificationCaseListResponse(BaseModel):
    items: list[VerificationCaseResponse]
    total: int
