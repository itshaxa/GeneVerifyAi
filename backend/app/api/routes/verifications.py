"""Verification case endpoints (all require authentication).

POST /api/v1/verifications                 create a case for a CNIC
GET  /api/v1/verifications                 current user's cases (all for admin)
GET  /api/v1/verifications/{verification_id} one accessible case
POST /api/v1/verifications/{verification_id}/dna/compare
                                           deterministic STR comparison
POST /api/v1/verifications/{verification_id}/documents
                                           upload a DNA/blood-test document
GET  /api/v1/verifications/{verification_id}/documents
                                           list a case's document metadata
GET  /api/v1/verifications/{verification_id}/documents/{document_id}/file
                                           download a stored document
DELETE /api/v1/verifications/{verification_id}/documents/{document_id}
                                           remove a document + stored file
POST /api/v1/verifications/{verification_id}/documents/{document_id}/process
                                           AI document intelligence (Step 7)
GET  /api/v1/verifications/{verification_id}/documents/{document_id}/extraction
                                           safe AI extraction result
POST /api/v1/verifications/{verification_id}/decision
                                           calculate verification decision (Step 8)
GET  /api/v1/verifications/{verification_id}/decision
                                           retrieve current decision (Step 8)
GET  /api/v1/verifications/{verification_id}/report
                                           structured verification report (Step 9)
GET  /api/v1/verifications/{verification_id}/report/download
                                           PDF verification report (Step 9)
"""

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_document_intelligence_service
from app.core.cnic import InvalidCnicError
from app.database.session import get_db
from app.models.user import User
from app.models.verification_case import VerificationCase
from app.models.verification_document import DocumentType, VerificationDocument
from app.schemas.document import (
    VerificationDocumentListResponse,
    VerificationDocumentResponse,
)
from app.schemas.dna_comparison import (
    CompareDnaRequest,
    ComparisonSummaryResponse,
    DnaComparisonResponse,
    MarkerComparisonResponse,
)
from app.schemas.decision import DecisionResponse
from app.schemas.extraction import (
    DocumentExtractionResponse,
    ProcessDocumentResponse,
)
from app.schemas.report import VerificationReport
from app.schemas.verification import (
    CaseIdentitySummary,
    CreateVerificationRequest,
    VerificationCaseListResponse,
    VerificationCaseResponse,
)
from app.services import (
    decision_service,
    dna_comparison_service,
    document_extraction_service,
    document_service,
    document_storage_service,
    identity_service,
    report_service,
    verification_case_service,
)
from app.services.ai import AiProviderNotConfiguredError, DocumentIntelligenceService
from app.services.str_engine.comparison import StrProfileValidationError

router = APIRouter()


def _to_response(case: VerificationCase) -> VerificationCaseResponse:
    """Map the ORM graph to the safe response — DNA is not part of it."""
    return VerificationCaseResponse(
        verification_id=case.verification_id,
        status=case.status,
        identity=CaseIdentitySummary.model_validate(case.identity_record),
        created_by_user_id=case.created_by_user_id,
        created_by_username=case.creator.username,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.post(
    "",
    response_model=VerificationCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a verification case for a CNIC",
    responses={
        404: {"description": "No synthetic identity record with this CNIC"},
        422: {"description": "Malformed CNIC format"},
    },
)
def create_verification(
    payload: CreateVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationCaseResponse:
    """Create a DRAFT case owned by the authenticated user (never by request data)."""
    try:
        case = verification_case_service.create_case(db, current_user, payload.cnic)
    except InvalidCnicError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except identity_service.IdentityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(case)


@router.get(
    "",
    response_model=VerificationCaseListResponse,
    summary="List verification cases accessible to the current user",
)
def list_verifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationCaseListResponse:
    """Officers see only their own cases; admins see all."""
    cases = verification_case_service.list_cases_for_user(db, current_user)
    items = [_to_response(case) for case in cases]
    return VerificationCaseListResponse(items=items, total=len(items))


@router.get(
    "/{verification_id}",
    response_model=VerificationCaseResponse,
    summary="Retrieve one accessible verification case",
    responses={404: {"description": "Case not found or not visible to this user"}},
)
def get_verification(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationCaseResponse:
    """Foreign cases answer with a plain 404 — existence is never disclosed."""
    try:
        case = verification_case_service.get_case(db, current_user, verification_id)
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(case)


@router.post(
    "/{verification_id}/dna/compare",
    response_model=DnaComparisonResponse,
    summary="Compare a submitted STR profile against the case's reference DNA",
    responses={
        404: {"description": "Case not found or not visible to this user"},
        409: {"description": "Case's identity has no reference DNA profile"},
        422: {"description": "Submitted STR profile is malformed"},
    },
)
def compare_dna(
    verification_id: str,
    payload: CompareDnaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DnaComparisonResponse:
    """Deterministic STR comparison for an accessible case.

    The reference profile is resolved server-side (case -> identity ->
    dna_profile); the request may only carry the submitted profile.
    """
    try:
        case, result, _stored = dna_comparison_service.compare_for_case(
            db, current_user, verification_id, payload.submitted_profile
        )
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except dna_comparison_service.ReferenceProfileUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except StrProfileValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid submitted STR profile: " + "; ".join(exc.issues),
        ) from exc

    return DnaComparisonResponse(
        verification_id=case.verification_id,
        classification=result.classification,
        summary=ComparisonSummaryResponse.model_validate(result.summary),
        markers=[MarkerComparisonResponse.model_validate(marker) for marker in result.markers],
        compared_at=_stored.created_at,
    )


def _document_response(document: VerificationDocument) -> VerificationDocumentResponse:
    """Metadata-only view — storage paths and internal ids never leave here."""
    return VerificationDocumentResponse(
        document_id=document.document_id,
        original_filename=document.original_filename,
        document_type=document.document_type,
        content_type=document.content_type,
        file_size=document.file_size,
        processing_status=document.processing_status,
        uploaded_by=document.uploader.username,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post(
    "/{verification_id}/documents",
    response_model=VerificationDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a DNA/blood-test document to a verification case",
    responses={
        404: {"description": "Case not found or not visible to this user"},
        413: {"description": "File exceeds the configured size limit"},
        422: {"description": "Unsupported or spoofed file"},
    },
)
async def upload_document(
    verification_id: str,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.DNA_REPORT),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationDocumentResponse:
    """Secure multipart upload for an accessible case.

    The uploader is always the authenticated user; identity/case/user ids
    from the request are never accepted. Files are validated (extension,
    declared content type, size, magic bytes) and stored under a
    server-generated filename outside any static/web path.
    """
    try:
        _case, document = await document_service.store_upload(
            db, current_user, verification_id, file, document_type
        )
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except document_service.DocumentTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    except document_service.DocumentValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return _document_response(document)


@router.get(
    "/{verification_id}/documents",
    response_model=VerificationDocumentListResponse,
    summary="List document metadata of an accessible case",
    responses={404: {"description": "Case not found or not visible to this user"}},
)
def list_documents(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationDocumentListResponse:
    """Metadata only — never file binaries, storage paths or DNA content."""
    try:
        case, documents = document_service.list_documents(db, current_user, verification_id)
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    items = [_document_response(document) for document in documents]
    return VerificationDocumentListResponse(
        verification_id=case.verification_id, items=items, total=len(items)
    )


@router.get(
    "/{verification_id}/documents/{document_id}/file",
    summary="Download a document of an accessible case",
    responses={404: {"description": "Case/document not found or not visible"}},
)
def download_document(
    verification_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Serve the stored file via server-side metadata only.

    The path is resolved inside the storage root (path traversal is
    rejected); there is no public/static download URL.
    """
    try:
        document = document_service.get_document(db, current_user, verification_id, document_id)
        path = document_storage_service.resolve(document.stored_filename)
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (document_service.DocumentNotFoundError, document_storage_service.DocumentStorageError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type=document.content_type,
        filename=document.original_filename,
    )


@router.delete(
    "/{verification_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document of an accessible case",
    responses={404: {"description": "Case/document not found or not visible"}},
)
def delete_document(
    verification_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove metadata and the stored file (a missing file is tolerated)."""
    try:
        document_service.delete_document(db, current_user, verification_id, document_id)
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return None


@router.post(
    "/{verification_id}/documents/{document_id}/process",
    response_model=ProcessDocumentResponse,
    summary="Analyze an uploaded document with the AI document-intelligence service",
    responses={
        404: {"description": "Case/document not found or not visible"},
        409: {"description": "Document status does not allow processing"},
        502: {"description": "Controlled AI processing failure"},
        503: {"description": "AI provider is not configured"},
    },
)
def process_document(
    verification_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_service: DocumentIntelligenceService = Depends(get_document_intelligence_service),
) -> ProcessDocumentResponse:
    """Run the AI extraction pipeline for one accessible document.

    The AI only EXTRACTS structured data; it never decides whether a DNA
    profile matches. Comparison remains with the deterministic STR engine.
    """
    try:
        document, extraction = document_extraction_service.process_document(
            db, current_user, verification_id, document_id, ai_service
        )
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except document_storage_service.DocumentStorageError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The stored document file could not be found.",
        ) from None
    except document_extraction_service.DocumentNotProcessableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except document_extraction_service.DocumentProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except AiProviderNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider is not configured.",
        ) from None
    return ProcessDocumentResponse(
        document_id=document.document_id,
        processing_status=document.processing_status,
        extraction_status=extraction.extraction_status,
        extracted_marker_count=extraction.extracted_marker_count,
    )


@router.get(
    "/{verification_id}/documents/{document_id}/extraction",
    response_model=DocumentExtractionResponse,
    summary="Retrieve the AI extraction result of a document",
    responses={404: {"description": "Case/document not found or not visible"}},
)
def get_document_extraction(
    verification_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentExtractionResponse:
    """AI-extracted data — requires deterministic validation.

    Returns extracted identity fields, the extracted STR profile and
    deterministic CNIC/name consistency checks. Never returns the reference
    profile, storage paths, raw provider responses or credentials.
    """
    try:
        case, document, extraction = document_extraction_service.get_extraction(
            db, current_user, verification_id, document_id
        )
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except document_service.DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if extraction is None:
        return DocumentExtractionResponse(
            document_id=document.document_id,
            processing_status=document.processing_status,
        )

    identity_data = extraction.extracted_identity_data or {}
    identity = case.identity_record
    return DocumentExtractionResponse(
        document_id=document.document_id,
        processing_status=document.processing_status,
        extraction_status=extraction.extraction_status,
        model_name=extraction.model_name,
        patient_name=identity_data.get("patient_name"),
        cnic=identity_data.get("cnic"),
        date_of_birth=_safe_date(identity_data.get("date_of_birth")),
        report_date=_safe_date(identity_data.get("report_date")),
        laboratory_reference=identity_data.get("laboratory_reference"),
        str_profile=extraction.extracted_str_profile,
        extracted_marker_count=extraction.extracted_marker_count,
        cnic_consistency=document_extraction_service.cnic_consistency(
            identity_data.get("cnic"), identity.cnic
        ),
        name_consistency=document_extraction_service.name_consistency(
            identity_data.get("patient_name"), identity.name
        ),
        validation_note=extraction.validation_note,
        extracted_at=extraction.created_at,
    )


# --- Step 8: Verification Decision Engine -------------------------------------------


@router.post(
    "/{verification_id}/decision",
    response_model=DecisionResponse,
    summary="Calculate and persist the verification decision",
    responses={
        404: {"description": "Case not found or not visible"},
        409: {"description": "Required evidence is not available"},
    },
)
def create_decision(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DecisionResponse:
    """Run the deterministic evidence assessment for an accessible case.

    Requires an existing DNA comparison (Step 5). Optionally incorporates AI
    document extraction (Step 7) for identity/document consistency scoring.
    The decision engine NEVER uses an LLM to determine whether DNA matches.
    """
    try:
        case, decision = decision_service.calculate_decision(
            db, current_user, verification_id
        )
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except decision_service.InsufficientEvidenceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _decision_response(case, decision)


@router.get(
    "/{verification_id}/decision",
    response_model=DecisionResponse,
    summary="Retrieve the current verification decision",
    responses={404: {"description": "Case not found or no decision exists"}},
)
def get_decision(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DecisionResponse:
    """Return the latest/current verification decision for an accessible case."""
    try:
        case, decision = decision_service.get_current_decision(
            db, current_user, verification_id
        )
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No decision has been recorded for this case yet.",
        )
    return _decision_response(case, decision)


def _decision_response(case: VerificationCase, decision) -> DecisionResponse:
    """Map a decision ORM row to the safe response (no internals)."""
    return DecisionResponse(
        verification_id=case.verification_id,
        decision=decision.decision,
        evidence_score=decision.evidence_score,
        dna_classification=decision.dna_classification,
        dna_match_percentage=decision.dna_match_percentage,
        identity_consistency=decision.identity_consistency,
        document_consistency=decision.document_consistency,
        explanation=decision.explanation,
        created_at=decision.created_at,
        updated_at=decision.updated_at,
    )


def _safe_date(value: object) -> date | None:
    """Parse an ISO date coming from stored JSON; tolerate absent values."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# --- Step 9: Verification Report & Audit Trail --------------------------------------


@router.get(
    "/{verification_id}/report",
    response_model=VerificationReport,
    summary="Build the verification report of an accessible case",
    responses={404: {"description": "Case not found or not visible to this user"}},
)
def get_report(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationReport:
    """Read-only projection of the evidence already stored for this case.

    Nothing is recomputed and no audit event is written, so refreshing the
    report page can never change the audit trail. Incomplete cases still get
    a full report whose sections say what is missing.
    """
    try:
        return report_service.build_report(db, current_user, verification_id)
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/{verification_id}/report/download",
    summary="Download the verification report as a PDF document",
    response_class=Response,
    responses={
        200: {
            "description": "PDF report",
            "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        },
        404: {"description": "Case not found or not visible to this user"},
    },
)
def download_report(
    verification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Explicitly generate the report: render a PDF and record REPORT_GENERATED.

    The audit event is written only here (never on plain report reads), and
    the download itself is deterministic for unchanged evidence.
    """
    try:
        _report, pdf_bytes, filename = report_service.generate_report_pdf(
            db, current_user, verification_id
        )
    except verification_case_service.VerificationCaseNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
