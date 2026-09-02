"""Schemas for verification-document endpoints (Step 6).

Responses expose metadata only — never the stored filename, storage path,
internal database ids, or any DNA content.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.verification_document import DocumentType, ProcessingStatus


class VerificationDocumentResponse(BaseModel):
    """Safe metadata view of one uploaded document."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str
    original_filename: str
    document_type: DocumentType
    content_type: str
    file_size: int
    processing_status: ProcessingStatus
    uploaded_by: str
    created_at: datetime
    updated_at: datetime


class VerificationDocumentListResponse(BaseModel):
    verification_id: str
    items: list[VerificationDocumentResponse]
    total: int
