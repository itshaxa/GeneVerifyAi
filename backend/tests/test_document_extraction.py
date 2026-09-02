"""Step 7 tests — AI document intelligence & STR extraction pipeline.

All tests run against the deterministic mock provider: NO network access,
NO Alibaba Cloud calls. Covers the processing pipeline, strict extraction
schema validation, persistence, consistency checks, and security hygiene
(no API keys, no reference DNA, no password hashes, no storage paths).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.identity import IdentityRecord
from app.models.user import User, UserRole
from app.models.verification_document import ProcessingStatus, VerificationDocument
from app.schemas.extraction import (
    CnicConsistency,
    DocumentExtractionResult,
    ExtractedStrProfile,
    NameConsistency,
)
from app.services import (
    dna_service,
    document_extraction_service,
    document_storage_service,
    security_service,
)
from app.services.ai import (
    AIProviderError,
    AiProviderNotConfiguredError,
    create_document_intelligence_service,
)
from app.services.ai.mock import MockDocumentIntelligenceService
from app.services.ai.qwen import QwenDocumentIntelligenceService
from app.services.str_engine.panel import ALLELE_RANGES

DEMO_CNIC = "99900-0000001-1"  # Sami Demoosh — synthetic demo identity


def _pdf_with(content: bytes) -> bytes:
    """A minimal valid PDF whose payload carries a mock-provider trigger."""
    return b"%PDF-1.4\n" + content + b"\n%%EOF"


def _pdf_printing(markers: dict, *, extra: bytes = b"") -> bytes:
    """An uncompressed-style PDF whose text stream prints a ``NAME | a, b`` table.

    This is the shape the demonstration reports are generated in (and the only
    shape the network-free mock can read), so the marker values a document
    carries are genuinely inside the uploaded bytes.
    """
    chunks = [b"%PDF-1.4\n", b"(SYNTHETIC DNA REPORT) Tj\n", b"(Marker | Alleles) Tj\n"]
    for name, alleles in markers.items():
        chunks.append(f"({name} | {alleles[0]:g}, {alleles[1]:g}) Tj\n".encode())
    if extra:
        chunks.append(extra + b"\n")
    chunks.append(b"%%EOF")
    return b"".join(chunks)


def _different_pair(marker: str, reference: list) -> list[int]:
    """A homozygous in-range pair that differs from the stored one."""
    low, high = ALLELE_RANGES[marker]
    for candidate in (14, 18, 12, 16, 20, 10):
        if low <= candidate <= high and sorted(reference) != [candidate, candidate]:
            return [candidate, candidate]
    raise AssertionError(f"no in-range substitute pair for {marker}")


def _reference_markers(db: Session, cnic: str = DEMO_CNIC) -> dict[str, list[float]]:
    """Internal test access to the registered reference profile."""
    identity = db.execute(
        select(IdentityRecord).where(IdentityRecord.cnic == cnic)
    ).scalar_one()
    markers = dna_service.get_reference_markers_by_identity_id(db, identity.id)
    assert markers is not None
    return markers


def _create_case(client, headers: dict[str, str], cnic: str = DEMO_CNIC) -> str:
    response = client.post("/api/v1/verifications", json={"cnic": cnic}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["verification_id"]


def _upload_pdf(client, headers: dict[str, str], verification_id: str, payload: bytes) -> str:
    response = client.post(
        f"/api/v1/verifications/{verification_id}/documents",
        files={"file": ("report.pdf", payload, "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


@pytest.fixture()
def other_officer(db_session: Session) -> User:
    user = User(
        username="officer-b",
        password_hash=security_service.hash_password("OtherPassw0rd!"),
        role=UserRole.OFFICER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def other_officer_headers(other_officer: User) -> dict[str, str]:
    token = security_service.create_access_token(other_officer)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def ai_settings():
    """In-place mutation of the cached settings instance (never cache_clear)."""
    settings = get_settings()
    snapshot = (
        settings.ai_provider,
        settings.qwen_api_key,
        settings.qwen_model,
        settings.qwen_base_url,
        settings.app_env,
    )
    yield settings
    (
        settings.ai_provider,
        settings.qwen_api_key,
        settings.qwen_model,
        settings.qwen_base_url,
        settings.app_env,
    ) = snapshot


# --- Pipeline: success path --------------------------------------------------


def test_process_document_success(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == document_id
    assert body["processing_status"] == "PROCESSED"
    assert body["extraction_status"] == "SUCCEEDED"
    assert body["extracted_marker_count"] == 20

    document = seeded_session.execute(
        select(VerificationDocument).where(VerificationDocument.document_id == document_id)
    ).scalar_one()
    assert document.processing_status is ProcessingStatus.PROCESSED


def test_extraction_persisted(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )

    extraction = seeded_session.execute(select(DocumentExtraction)).scalar_one()
    assert extraction.extraction_status is ExtractionStatus.SUCCEEDED
    assert extraction.model_name == "mock-document-intelligence"
    assert extraction.extracted_marker_count == 20
    assert extraction.extracted_str_profile is not None
    assert len(extraction.extracted_str_profile) == 20
    assert extraction.extracted_identity_data["patient_name"] == "Sami Demoosh"
    assert extraction.extracted_identity_data["cnic"] == DEMO_CNIC


def test_extraction_retrievable(seeded_client, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )

    response = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["processing_status"] == "PROCESSED"
    assert body["extraction_status"] == "SUCCEEDED"
    assert body["patient_name"] == "Sami Demoosh"
    assert body["cnic"] == DEMO_CNIC
    assert body["extracted_marker_count"] == 20
    assert len(body["str_profile"]) == 20
    assert body["str_profile"]["D3S1358"] == [15, 16]
    assert body["cnic_consistency"] == "CONSISTENT"
    assert body["name_consistency"] == "CONSISTENT"
    assert body["model_name"] == "mock-document-intelligence"
    assert body["extracted_at"] is not None


def test_extraction_before_processing_is_empty(seeded_client, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))

    response = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["processing_status"] == "UPLOADED"
    assert body["extraction_status"] is None
    assert body["str_profile"] is None
    assert body["extracted_marker_count"] == 0


def test_no_invented_marker_values(seeded_client, auth_headers):
    """Extracted markers must be exactly the canonical ones present — none invented."""
    from app.services.str_engine.panel import STR_PANEL

    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    response = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    markers = set(response.json()["str_profile"].keys())
    assert markers <= set(STR_PANEL)
    assert markers == set(STR_PANEL)  # full panel, nothing added, nothing lost


def test_partial_extraction_handled(seeded_client, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-PARTIAL"))

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["processing_status"] == "PROCESSED"
    assert response.json()["extracted_marker_count"] == 18

    extraction = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    assert "D22S1045" not in extraction.json()["str_profile"]
    assert "SE33" not in extraction.json()["str_profile"]


# --- Pipeline: authorization -------------------------------------------------


def test_process_requires_authentication(seeded_client, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process"
    )
    assert response.status_code == 401


def test_extraction_requires_authentication(seeded_client, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    response = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction"
    )
    assert response.status_code == 401


def test_process_foreign_case_rejected(
    seeded_client, seeded_session, auth_headers, other_officer_headers
):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=other_officer_headers,
    )
    assert response.status_code == 404

    document = seeded_session.execute(
        select(VerificationDocument).where(VerificationDocument.document_id == document_id)
    ).scalar_one()
    assert document.processing_status is ProcessingStatus.UPLOADED  # never processed


def test_process_foreign_document_rejected(seeded_client, auth_headers, other_officer_headers):
    case_a = _create_case(seeded_client, auth_headers)
    document_a = _upload_pdf(seeded_client, auth_headers, case_a, _pdf_with(b"GV-SAMPLE"))
    case_b = _create_case(seeded_client, other_officer_headers)

    response = seeded_client.post(
        f"/api/v1/verifications/{case_b}/documents/{document_a}/process",
        headers=auth_headers,
    )
    assert response.status_code == 404

    response = seeded_client.get(
        f"/api/v1/verifications/{case_b}/documents/{document_a}/extraction",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_process_unknown_document_rejected(seeded_client, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/GVD-2026-999999/process",
        headers=auth_headers,
    )
    assert response.status_code == 404


# --- Pipeline: failure paths ---------------------------------------------------


def test_ai_failure_transitions_to_failed(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-FAIL"))

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "AI provider" in detail

    document = seeded_session.execute(
        select(VerificationDocument).where(VerificationDocument.document_id == document_id)
    ).scalar_one()
    assert document.processing_status is ProcessingStatus.FAILED
    extraction = seeded_session.execute(select(DocumentExtraction)).scalar_one()
    assert extraction.extraction_status is ExtractionStatus.FAILED
    assert extraction.extracted_marker_count == 0
    assert extraction.validation_note  # audit trail present


def test_malformed_ai_output_fails_safely(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-BADJSON"))

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "AI output failed validation."

    document = seeded_session.execute(
        select(VerificationDocument).where(VerificationDocument.document_id == document_id)
    ).scalar_one()
    assert document.processing_status is ProcessingStatus.FAILED


def test_unknown_marker_from_ai_fails(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-BADSTR"))

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 502
    document = seeded_session.execute(
        select(VerificationDocument).where(VerificationDocument.document_id == document_id)
    ).scalar_one()
    assert document.processing_status is ProcessingStatus.FAILED


def test_missing_stored_file_reports_404(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    document = seeded_session.execute(
        select(VerificationDocument).where(VerificationDocument.document_id == document_id)
    ).scalar_one()
    document_storage_service.resolve(document.stored_filename).unlink()

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 404
    assert "could not be found" in response.json()["detail"]


# --- Status lifecycle / cost control --------------------------------------------


def test_reprocess_is_blocked(seeded_client, auth_headers):
    """Cost control: a PROCESSED document must not be analyzed again."""
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    url = f"/api/v1/verifications/{verification_id}/documents/{document_id}/process"
    assert seeded_client.post(url, headers=auth_headers).status_code == 200
    response = seeded_client.post(url, headers=auth_headers)
    assert response.status_code == 409
    assert "already been processed" in response.json()["detail"]


def test_processing_state_blocks_concurrent_run(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    document = seeded_session.execute(
        select(VerificationDocument).where(VerificationDocument.document_id == document_id)
    ).scalar_one()
    document.processing_status = ProcessingStatus.PROCESSING
    seeded_session.commit()

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 409


# --- Mock provider (network-free) -----------------------------------------------


def test_mock_provider_works_without_network():
    mock = MockDocumentIntelligenceService()
    result = mock.extract_dna_report(
        b"%PDF-1.4 content",
        content_type="application/pdf",
        context={
            "reference_markers": {"D3S1358": [15, 16]},
            "patient_name": "Test Person",
            "cnic": "99900-0000001-1",
        },
    )
    parsed = DocumentExtractionResult.model_validate(result)
    assert parsed.str_profile is not None
    assert parsed.str_profile.root == {"D3S1358": [15.0, 16.0]}
    assert parsed.identity.patient_name == "Test Person"


def test_mock_provider_reads_markers_printed_in_the_document():
    """The document is the source of truth for alleles - not the database."""
    printed = {"D3S1358": [16.0, 17.0], "vWA": [17.5, 18.0]}
    result = MockDocumentIntelligenceService().extract_dna_report(
        _pdf_printing(printed),
        content_type="application/pdf",
        context={
            "reference_markers": {"D3S1358": [14, 14], "vWA": [18, 19]},
            "patient_name": "Test Person",
            "cnic": DEMO_CNIC,
        },
    )
    parsed = DocumentExtractionResult.model_validate(result)
    assert parsed.str_profile.root == printed
    # Identity fields are still taken from the case, never from the document.
    assert parsed.identity.cnic == DEMO_CNIC
    assert parsed.identity.patient_name == "Test Person"


def test_mock_provider_falls_back_only_when_the_text_is_unreadable():
    """Compressed/scanned/bare payloads keep using the registered reference."""
    result = MockDocumentIntelligenceService().extract_dna_report(
        _pdf_with(b"GV-SAMPLE"),
        content_type="application/pdf",
        context={"reference_markers": {"D3S1358": [15, 16]}, "cnic": DEMO_CNIC},
    )
    assert DocumentExtractionResult.model_validate(result).str_profile.root == {
        "D3S1358": [15.0, 16.0]
    }


def test_mock_provider_partial_marker_subtracts_from_the_printed_profile():
    """GV-PARTIAL drops markers from whatever was read, exactly as before."""
    printed = {"D3S1358": [16.0, 17.0], "D22S1045": [17, 18], "SE33": [19, 20]}
    result = MockDocumentIntelligenceService().extract_dna_report(
        _pdf_printing(printed, extra=b"GV-PARTIAL"),
        content_type="application/pdf",
        context={"reference_markers": printed, "cnic": DEMO_CNIC},
    )
    profile = DocumentExtractionResult.model_validate(result).str_profile.root
    assert set(profile) == {"D3S1358"}
    assert profile["D3S1358"] == [16.0, 17.0]


def test_behaviour_markers_still_short_circuit_on_a_readable_document():
    """GV-FAIL / GV-BADJSON / GV-BADSTR win over a printed marker table."""
    printed = {"D3S1358": [16.0, 17.0], "vWA": [17.5, 18.0]}
    mock = MockDocumentIntelligenceService()
    context = {"reference_markers": printed, "cnic": DEMO_CNIC}

    with pytest.raises(AIProviderError, match="failed to analyze"):
        mock.extract_dna_report(
            _pdf_printing(printed, extra=b"GV-FAIL"),
            content_type="application/pdf",
            context=context,
        )

    for marker, expected in (
        (b"GV-BADJSON", {"D3S1358": [15, "not-a-number"], "EXTRA_FIELD": "oops"}),
        (b"GV-BADSTR", {"NOT_A_REAL_MARKER": [10, 11]}),
    ):
        result = mock.extract_dna_report(
            _pdf_printing(printed, extra=marker),
            content_type="application/pdf",
            context=context,
        )
        assert result["str_profile"] == expected
        with pytest.raises(ValueError):
            DocumentExtractionResult.model_validate(result)


def test_document_that_disagrees_with_the_reference_is_not_repaired(
    seeded_client, seeded_session, auth_headers
):
    """End to end: printed alleles survive extraction and drive the STR engine."""
    reference = _reference_markers(seeded_session)
    printed = {marker: list(alleles) for marker, alleles in reference.items()}
    for marker in ("D3S1358", "vWA"):
        printed[marker] = _different_pair(marker, reference[marker])

    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(
        seeded_client, auth_headers, verification_id, _pdf_printing(printed)
    )
    processed = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert processed.status_code == 200, processed.text
    assert processed.json()["extracted_marker_count"] == 20

    extraction = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    ).json()
    assert extraction["str_profile"] == printed
    assert extraction["str_profile"] != {k: list(v) for k, v in reference.items()}

    comparison = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/dna/compare",
        json={"submitted_profile": extraction["str_profile"]},
        headers=auth_headers,
    )
    assert comparison.status_code == 200, comparison.text
    body = comparison.json()
    assert body["classification"] == "PARTIAL_MATCH"
    assert body["summary"]["matched"] == 18
    assert body["summary"]["mismatched"] == 2


def test_default_dependency_resolves_to_mock(seeded_client, seeded_session, auth_headers):
    """With AI_PROVIDER=mock (dev default) the app works end-to-end offline."""
    settings = get_settings()
    assert settings.ai_provider == "mock"
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 200


# --- Provider configurability ---------------------------------------------------


def test_factory_selects_qwen_when_configured(ai_settings):
    ai_settings.ai_provider = "qwen"
    ai_settings.qwen_api_key = "sk-test-1234567890"
    service = create_document_intelligence_service(ai_settings)
    assert isinstance(service, QwenDocumentIntelligenceService)
    assert service.model_name == ai_settings.qwen_model


def test_factory_rejects_unconfigured_qwen(ai_settings):
    ai_settings.ai_provider = "qwen"
    ai_settings.qwen_api_key = None
    with pytest.raises(AiProviderNotConfiguredError):
        create_document_intelligence_service(ai_settings)


def test_factory_rejects_mock_in_production(ai_settings):
    ai_settings.ai_provider = "mock"
    ai_settings.app_env = "production"
    with pytest.raises(AiProviderNotConfiguredError):
        create_document_intelligence_service(ai_settings)


def test_unconfigured_provider_returns_503(seeded_client, auth_headers, ai_settings):
    """The app stays alive; processing reports 'AI provider is not configured.'"""
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))

    ai_settings.ai_provider = "qwen"
    ai_settings.qwen_api_key = None
    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "AI provider is not configured."


# --- Security hygiene -------------------------------------------------------------


def test_api_key_never_in_responses_or_database(
    seeded_client, seeded_session, auth_headers, ai_settings
):
    secret = "sk-live-DO-NOT-LEAK-1234567890"
    ai_settings.qwen_api_key = secret

    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    process = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    extraction = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    documents = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents", headers=auth_headers
    )
    for response in (process, extraction, documents):
        assert secret not in response.text
        assert "api_key" not in response.text.lower()

    row = seeded_session.execute(select(DocumentExtraction)).scalar_one()
    assert secret not in str(row.__dict__)


def test_reference_dna_never_exposed_by_extraction(seeded_client, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    response = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    body = response.json()
    # Structural guarantee: no comparison/reference internals leak here.
    assert "reference_alleles" not in response.text
    assert "reference_profile" not in response.text.lower()
    assert "dna_profiles" not in response.text.lower()
    assert "reference_alleles" not in body
    assert "submitted_alleles" not in body


def test_password_hash_never_exposed(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    response = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    assert "$argon2" not in response.text
    assert "password" not in response.text.lower()


def test_storage_paths_never_exposed(seeded_client, seeded_session, auth_headers):
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    response = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    document = seeded_session.execute(
        select(VerificationDocument).where(VerificationDocument.document_id == document_id)
    ).scalar_one()
    assert document.stored_filename not in response.text
    assert "storage" not in response.text.lower()


# --- Extraction schema strictness --------------------------------------------------


def _valid_payload() -> dict:
    return {
        "identity": {
            "patient_name": "Sami Demoosh",
            "cnic": "99900-0000001-1",
            "date_of_birth": "1990-05-20",
            "report_date": "2026-08-01",
            "laboratory_reference": "LAB-001",
        },
        "str_profile": {"D3S1358": [15, 16], "vWA": [17, 18]},
    }


def test_schema_accepts_valid_output():
    parsed = DocumentExtractionResult.model_validate(_valid_payload())
    assert parsed.str_profile is not None
    assert parsed.str_profile.root["vWA"] == [17.0, 18.0]
    assert parsed.identity.cnic == DEMO_CNIC


def test_schema_rejects_unknown_marker():
    payload = _valid_payload()
    payload["str_profile"]["FAKE_MARKER"] = [10, 11]
    with pytest.raises(ValueError, match="Unknown STR marker"):
        DocumentExtractionResult.model_validate(payload)


def test_schema_rejects_non_numeric_allele():
    payload = _valid_payload()
    payload["str_profile"]["D3S1358"] = [15, "sixteen"]
    with pytest.raises(ValueError, match="non-numeric"):
        DocumentExtractionResult.model_validate(payload)


def test_schema_rejects_null_allele():
    payload = _valid_payload()
    payload["str_profile"]["D3S1358"] = [15, None]
    with pytest.raises(ValueError, match="null allele"):
        DocumentExtractionResult.model_validate(payload)


def test_schema_rejects_three_alleles():
    payload = _valid_payload()
    payload["str_profile"]["D3S1358"] = [15, 16, 17]
    with pytest.raises(ValueError, match="two alleles"):
        DocumentExtractionResult.model_validate(payload)


def test_schema_rejects_single_allele():
    payload = _valid_payload()
    payload["str_profile"]["D3S1358"] = [15]
    with pytest.raises(ValueError, match="two alleles"):
        DocumentExtractionResult.model_validate(payload)


def test_schema_rejects_out_of_range_allele():
    payload = _valid_payload()
    payload["str_profile"]["D3S1358"] = [15, 999]
    with pytest.raises(ValueError, match="outside the allowed range"):
        DocumentExtractionResult.model_validate(payload)


def test_schema_rejects_arbitrary_extra_fields():
    payload = _valid_payload()
    payload["extra_field"] = "should not be here"
    with pytest.raises(ValueError):
        DocumentExtractionResult.model_validate(payload)
    payload = _valid_payload()
    payload["identity"]["arbitrary"] = "nope"
    with pytest.raises(ValueError):
        DocumentExtractionResult.model_validate(payload)


def test_schema_accepts_missing_markers_but_not_empty_profile():
    payload = _valid_payload()
    payload["str_profile"] = {"D3S1358": [15, 16]}
    parsed = DocumentExtractionResult.model_validate(payload)
    assert len(parsed.str_profile.root) == 1

    payload["str_profile"] = {}
    with pytest.raises(ValueError):
        DocumentExtractionResult.model_validate(payload)


def test_profile_standalone_validation():
    profile = ExtractedStrProfile.model_validate({"CSF1PO": [10, 12]})
    assert profile.root == {"CSF1PO": [10.0, 12.0]}


# --- Deterministic consistency helpers ----------------------------------------------


def test_cnic_consistency_rules():
    cnic_consistency = document_extraction_service.cnic_consistency
    assert cnic_consistency("99900-0000001-1", DEMO_CNIC) is CnicConsistency.CONSISTENT
    assert cnic_consistency("9990000000011", DEMO_CNIC) is CnicConsistency.CONSISTENT
    assert cnic_consistency("12345-6789012-3", DEMO_CNIC) is CnicConsistency.INCONSISTENT
    assert cnic_consistency(None, DEMO_CNIC) is CnicConsistency.NOT_DETECTED
    assert cnic_consistency("", DEMO_CNIC) is CnicConsistency.NOT_DETECTED


def test_name_consistency_rules():
    name_consistency = document_extraction_service.name_consistency
    assert name_consistency("Sami Demoosh", "Sami Demoosh") is NameConsistency.CONSISTENT
    assert name_consistency("demoosh  sami ", "Sami Demoosh") is NameConsistency.CONSISTENT
    assert name_consistency("Somebody Else", "Sami Demoosh") is NameConsistency.INCONSISTENT
    assert name_consistency(None, "Sami Demoosh") is NameConsistency.NOT_DETECTED


def test_inconsistent_cnic_detected_via_api(seeded_client, seeded_session, auth_headers):
    """Overwrite the stored extraction CNIC to simulate a different document."""
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    extraction = seeded_session.execute(select(DocumentExtraction)).scalar_one()
    extraction.extracted_identity_data = {
        **extraction.extracted_identity_data,
        "cnic": "12345-6789012-3",
    }
    seeded_session.commit()

    response = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    )
    assert response.json()["cnic_consistency"] == "INCONSISTENT"


# --- Seam into the deterministic Step 5 engine ---------------------------------------


def test_extracted_profile_feeds_step5_engine(seeded_client, auth_headers):
    """Extraction -> Step 5 deterministic comparison (no duplicated engine)."""
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    extraction = seeded_client.get(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/extraction",
        headers=auth_headers,
    ).json()

    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/dna/compare",
        json={"submitted_profile": extraction["str_profile"]},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["classification"] == "EXACT_MATCH"
    assert response.json()["summary"]["match_percentage"] == 100.0


# --- Deletion integrity ------------------------------------------------------


def test_deleting_document_cascades_extraction(seeded_client, seeded_session, auth_headers):
    """Regression: document deletion must remove its extraction row.

    Without FK enforcement, orphaned ``document_extractions`` rows survive
    document deletion and collide with the unique constraint when SQLite
    reuses the document primary key for a later upload (500 IntegrityError).
    """
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert seeded_session.execute(select(DocumentExtraction)).scalar_one() is not None

    response = seeded_client.delete(
        f"/api/v1/verifications/{verification_id}/documents/{document_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204, response.text
    assert seeded_session.execute(select(DocumentExtraction)).scalar_one_or_none() is None

    # A new document must process cleanly — no leftover unique-constraint row.
    next_document_id = _upload_pdf(seeded_client, auth_headers, verification_id, _pdf_with(b"GV-SAMPLE"))
    response = seeded_client.post(
        f"/api/v1/verifications/{verification_id}/documents/{next_document_id}/process",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
