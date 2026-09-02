"""Schemas for the safe CNIC identity lookup response.

The lookup response exposes ONLY the synthetic identity fields an operator
needs. The raw DNA profile is deliberately absent — it stays accessible only
to internal services (future verification workflow), never through this API.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.models.identity import Gender, IdentityStatus


class IdentityLookupResponse(BaseModel):
    """Safe, bounded view of a single synthetic identity record."""

    model_config = ConfigDict(from_attributes=True)

    cnic: str = Field(description="Canonical demo CNIC (NNNNN-NNNNNN-N)")
    name: str
    father_name: str
    date_of_birth: date
    gender: Gender
    address: str
    photo_reference: str | None = None
    status: IdentityStatus
