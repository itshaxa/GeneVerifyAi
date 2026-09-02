"""Tests for the secure document upload pipeline (Step 6).

Covers upload validation, identifier generation, secure storage, ownership
protection, metadata listing, download/delete and response hygiene. Runs on
the isolated in-memory database fixtures and the throwaway document storage
directory configured in conftest.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User, UserRole
from app.models.verification_document import (
    DocumentType,
    ProcessingStatus,
    VerificationDocument,
)
from app.services import document_storage_service, security_service

BASE_URL = "/api/v1/verifications"
CREATE_URL = BASE_URL
DEMO_MATCH_CNIC = "99900-0000001-1"
OTHER_PASSWORD = "OtherOfficerPass1!"

#: Minimal binaries with real magic bytes for each supported format.
MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\r\xe1\xa5\x00\x00\x00\x00IEND\xaeB`\x82"
)
MINIMAL_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


def _create_case(client: TestClient, headers: dict, cnic: str = DEMO_MATCH_CNIC) -> str:
    response = client.post(CREATE_URL, json={"cnic": cnic}, headers=headers)
    assert response.status_code == 201
    return response.json()["verification_id"]


def _documents_url(verification_id: str) -> str:
    return f"{BASE_URL}/{verification_id}/documents"


def _upload_pdf(
    client: TestClient,
    headers: dict,
    verification_id: str,
    filename: str = "dna_report.pdf",
    content_type: str = "application/pdf",
    data: bytes = MINIMAL_PDF,
    extra_form: dict | None = None,
):
    # Extra multipart form fields go through ``data`` so they stay real form
    # parts (values inside ``files`` would become file uploads themselves).
    return client.post(
        _documents_url(verification_id),
        files={"file": (filename, data, content_type)},
        data=extra_form or {},
        headers=headers,
    )


def _make_officer(db_session: Session, username: str) -> dict[str, str]:
    user = User(
        username=username,
        password_hash=security_service.hash_password(OTHER_PASSWORD),
        role=UserRole.OFFICER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return {"Authorization": f"Bearer {security_service.create_access_token(user)}"}


def _make_admin(db_session: Session, username: str = "root_admin") -> dict[str, str]:
    user = User(
        username=username,
        password_hash=security_service.hash_password("AdminPassw0rd!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return {"Authorization": f"Bearer {security_service.create_access_token(user)}"}


@pytest.fixture()
def small_size_limit():
    """Temporarily lower the upload limit so oversize behaviour is testable.

    Mutates the cached settings instance in place (no cache clearing), so the
    running application sees the lowered limit; restored afterwards.
    """
    settings = get_settings()
    original = settings.max_document_size_mb
    settings.max_document_size_mb = 1
    try:
        yield
    finally:
        settings.max_document_size_mb = original


# ---------------------------------------------------------------------------
# Successful uploads (one per supported format)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("filename", "content_type", "data"),
    [
        ("dna_report.pdf", "application/pdf", MINIMAL_PDF),
        ("sample.png", "image/png", MINIMAL_PNG),
        ("sample.jpg", "image/jpeg", MINIMAL_JPEG),
        ("sample.jpeg", "image/jpeg", MINIMAL_JPEG),
    ],
)
def test_authenticated_user_can_upload_supported_formats(
    seeded_client: TestClient,
    auth_headers: dict,
    test_user: User,
    filename: str,
    content_type: str,
    data: bytes,
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)

    response = _upload_pdf(
        seeded_client, auth_headers, verification_id,
        filename=filename, content_type=content_type, data=data,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["document_id"].startswith("GVD-")
    assert body["original_filename"] == filename
    assert body["document_type"] == DocumentType.DNA_REPORT.value
    assert body["content_type"] == content_type
    assert body["file_size"] == len(data)
    assert body["processing_status"] == ProcessingStatus.UPLOADED.value
    assert body["uploaded_by"] == test_user.username
    assert "created_at" in body and "updated_at" in body


def test_upload_accepts_alternative_document_type(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    response = _upload_pdf(
        seeded_client, auth_headers, verification_id,
        extra_form={"document_type": "BLOOD_TEST"},
    )
    assert response.status_code == 201
    assert response.json()["document_type"] == DocumentType.BLOOD_TEST.value


# ---------------------------------------------------------------------------
# Authentication and case access
# ---------------------------------------------------------------------------
def test_unauthenticated_upload_returns_401(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    response = seeded_client.post(
        _documents_url(verification_id),
        files={"file": ("report.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert response.status_code == 401


def test_upload_to_unknown_case_returns_404(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    response = _upload_pdf(seeded_client, auth_headers, "GV-2026-999999")
    assert response.status_code == 404


def test_upload_to_foreign_case_is_rejected_and_stores_nothing(
    seeded_client: TestClient,
    auth_headers: dict,
    seeded_session: Session,
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    other_headers = _make_officer(seeded_session, "other_officer")

    response = _upload_pdf(seeded_client, other_headers, verification_id)

    assert response.status_code == 404
    assert seeded_session.execute(select(VerificationDocument)).scalars().all() == []


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------
def test_unsupported_extension_is_rejected(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    response = _upload_pdf(
        seeded_client, auth_headers, verification_id,
        filename="notes.txt", content_type="text/plain", data=b"plain text",
    )
    assert response.status_code == 422
    assert "Unsupported file type" in response.json()["detail"]


def test_spoofed_content_is_rejected_by_magic_bytes(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    # A .pdf whose bytes are not a PDF must never reach storage.
    response = _upload_pdf(
        seeded_client, auth_headers, verification_id,
        filename="fake.pdf", content_type="application/pdf", data=b"not a pdf at all",
    )
    assert response.status_code == 422
    assert "does not match" in response.json()["detail"]


def test_declared_content_type_mismatch_is_rejected(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    response = _upload_pdf(
        seeded_client, auth_headers, verification_id,
        filename="report.pdf", content_type="image/png", data=MINIMAL_PDF,
    )
    assert response.status_code == 422


def test_oversized_file_is_rejected_with_413(
    seeded_client: TestClient, auth_headers: dict, small_size_limit
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    oversized = b"%PDF-1.4\n" + b"X" * (1024 * 1024)

    response = _upload_pdf(seeded_client, auth_headers, verification_id, data=oversized)

    assert response.status_code == 413
    assert "limit" in response.json()["detail"]


def test_empty_file_is_rejected(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    response = _upload_pdf(seeded_client, auth_headers, verification_id, data=b"")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Identifiers, storage and metadata
# ---------------------------------------------------------------------------
def test_document_ids_are_generated_and_unique(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    first = _upload_pdf(seeded_client, auth_headers, verification_id).json()["document_id"]
    second = _upload_pdf(seeded_client, auth_headers, verification_id).json()["document_id"]

    assert first == "GVD-2026-000001"
    assert second == "GVD-2026-000002"
    assert first != second


def test_stored_filename_is_server_generated_and_traversal_is_neutralised(
    seeded_client: TestClient,
    auth_headers: dict,
    seeded_session: Session,
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    hostile_name = "../../evil report.pdf"

    response = _upload_pdf(seeded_client, auth_headers, verification_id, filename=hostile_name)

    assert response.status_code == 201
    document = seeded_session.execute(select(VerificationDocument)).scalar_one()
    # Server-generated uuid hex name — no user input, no separators.
    assert len(document.stored_filename) == 36
    assert "/" not in document.stored_filename and "\\" not in document.stored_filename
    assert document.stored_filename.endswith(".pdf")
    # Display name keeps only the basename.
    assert document.original_filename == "evil report.pdf"
    # Nothing escaped the storage root.
    root = Path(get_settings().document_storage_path).resolve()
    assert not (root.parent / "evil report.pdf").exists()
    assert (root / document.stored_filename).is_file()


def test_metadata_is_persisted_and_bound_to_case_and_authenticated_user(
    seeded_client: TestClient,
    auth_headers: dict,
    seeded_session: Session,
    test_user: User,
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    uploaded = _upload_pdf(
        seeded_client, auth_headers, verification_id,
        # Trying to spoof the uploader id in the multipart form has no effect.
        extra_form={"uploaded_by_user_id": "999"},
    ).json()

    document = seeded_session.execute(select(VerificationDocument)).scalar_one()
    assert document.document_id == uploaded["document_id"]
    assert document.verification_case.verification_id == verification_id
    assert document.uploaded_by_user_id == test_user.id
    assert document.processing_status is ProcessingStatus.UPLOADED
    assert document.document_type is DocumentType.DNA_REPORT
    assert document.file_size == len(MINIMAL_PDF)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------
def test_listing_only_exposes_documents_of_accessible_cases(
    seeded_client: TestClient, auth_headers: dict, seeded_session: Session
) -> None:
    own_case = _create_case(seeded_client, auth_headers)
    other_headers = _make_officer(seeded_session, "other_officer")
    foreign_case = _create_case(seeded_client, other_headers)
    _upload_pdf(seeded_client, auth_headers, own_case)
    _upload_pdf(seeded_client, other_headers, foreign_case)

    own_list = seeded_client.get(_documents_url(own_case), headers=auth_headers)
    foreign_list = seeded_client.get(_documents_url(foreign_case), headers=auth_headers)

    assert own_list.status_code == 200
    assert own_list.json()["total"] == 1
    assert own_list.json()["verification_id"] == own_case
    assert foreign_list.status_code == 404


def test_admin_can_list_documents_of_any_case(
    seeded_client: TestClient, auth_headers: dict, seeded_session: Session
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    _upload_pdf(seeded_client, auth_headers, verification_id)
    admin_headers = _make_admin(seeded_session)

    response = seeded_client.get(_documents_url(verification_id), headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def test_download_requires_authentication(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id).json()["document_id"]

    response = seeded_client.get(
        f"{_documents_url(verification_id)}/{document_id}/file"
    )
    assert response.status_code == 401


def test_download_returns_the_uploaded_bytes_with_correct_content_type(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id).json()["document_id"]

    response = seeded_client.get(
        f"{_documents_url(verification_id)}/{document_id}/file", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content == MINIMAL_PDF


def test_download_respects_case_ownership(
    seeded_client: TestClient, auth_headers: dict, seeded_session: Session
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id).json()["document_id"]
    other_headers = _make_officer(seeded_session, "other_officer")

    response = seeded_client.get(
        f"{_documents_url(verification_id)}/{document_id}/file", headers=other_headers
    )
    assert response.status_code == 404


def test_download_unknown_document_returns_404(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    response = seeded_client.get(
        f"{_documents_url(verification_id)}/GVD-2026-999999/file", headers=auth_headers
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
def test_delete_removes_metadata_and_stored_file(
    seeded_client: TestClient,
    auth_headers: dict,
    seeded_session: Session,
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id).json()["document_id"]
    stored = seeded_session.execute(select(VerificationDocument)).scalar_one().stored_filename
    root = Path(get_settings().document_storage_path).resolve()

    response = seeded_client.delete(
        f"{_documents_url(verification_id)}/{document_id}", headers=auth_headers
    )

    assert response.status_code == 204
    assert seeded_session.execute(select(VerificationDocument)).scalars().all() == []
    assert not (root / stored).exists()


def test_delete_is_ownership_protected(
    seeded_client: TestClient, auth_headers: dict, seeded_session: Session
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    document_id = _upload_pdf(seeded_client, auth_headers, verification_id).json()["document_id"]
    other_headers = _make_officer(seeded_session, "other_officer")

    response = seeded_client.delete(
        f"{_documents_url(verification_id)}/{document_id}", headers=other_headers
    )

    assert response.status_code == 404
    # Document survives the foreign attempt.
    assert seeded_client.get(
        _documents_url(verification_id), headers=auth_headers
    ).json()["total"] == 1


# ---------------------------------------------------------------------------
# Storage-service path hardening (crafted metadata)
# ---------------------------------------------------------------------------
def test_storage_service_refuses_to_leave_the_storage_root() -> None:
    root = Path(get_settings().document_storage_path).resolve()

    for crafted in ("../escape.pdf", "..\\escape.pdf", "nested/deep.pdf", ".."):
        with pytest.raises(document_storage_service.DocumentStorageError):
            document_storage_service.save(crafted, b"x")
        with pytest.raises(document_storage_service.DocumentStorageError):
            document_storage_service.resolve(crafted)
        with pytest.raises(document_storage_service.DocumentStorageError):
            document_storage_service.delete(crafted)

    assert not (root.parent / "escape.pdf").exists()


# ---------------------------------------------------------------------------
# Response hygiene
# ---------------------------------------------------------------------------
def test_document_responses_never_expose_storage_or_sensitive_data(
    seeded_client: TestClient, auth_headers: dict, seeded_session: Session, test_user: User
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    uploaded = _upload_pdf(seeded_client, auth_headers, verification_id)
    listing = seeded_client.get(_documents_url(verification_id), headers=auth_headers)

    stored = seeded_session.execute(select(VerificationDocument)).scalar_one().stored_filename
    for raw_text in (uploaded.text, listing.text):
        # Internal storage details never leave the server.
        assert stored not in raw_text
        assert "storage_path" not in raw_text
        assert "stored_filename" not in raw_text
        # No DNA content or credentials in document metadata.
        for forbidden in ("markers", "alleles", "dna_profile", "password", "token"):
            assert forbidden not in raw_text.lower()
        assert test_user.password_hash not in raw_text
