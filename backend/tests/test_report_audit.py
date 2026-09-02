"""Step 9 tests — Verification Report & Audit Trail.

Covers the 25 items required by the Step 9 brief plus extra audit-trail
guarantees. Everything runs on the isolated in-memory database from
``conftest.py`` and the deterministic mock AI provider — no network access,
no dev database, no real credentials.

The report is a *read-only projection*: these tests also prove that building
or downloading a report never creates, duplicates or mutates evidence.
"""

from __future__ import annotations

import json
import re
import zlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.dna_comparison import DnaComparisonResult
from app.models.dna_profile import DnaProfile
from app.models.document_extraction import DocumentExtraction
from app.models.identity import IdentityRecord
from app.models.user import User, UserRole
from app.models.verification_audit import AuditEventType, VerificationAuditEvent
from app.models.verification_case import VerificationCase
from app.models.verification_decision import VerificationDecision
from app.models.verification_document import VerificationDocument
from app.services import security_service
from app.services.str_engine.panel import ALLELE_RANGES, STR_PANEL

DEMO_CNIC = "99900-0000001-1"  # the seeded demo identity used across Steps 5-8

#: Exact-match profile for DEMO_CNIC (same fixture data as the Step 8 tests).
REFERENCE_PROFILE = {
    "D3S1358": [15, 16], "vWA": [17, 18], "FGA": [21, 24],
    "D8S1179": [12, 13], "D21S11": [29, 30], "D18S51": [14, 16],
    "D5S818": [10, 11], "D13S317": [9, 11], "D7S820": [9, 10],
    "CSF1PO": [10, 11], "TH01": [7, 9], "TPOX": [8, 11],
    "D16S539": [11, 12], "D2S1338": [19, 21], "D19S433": [13, 14],
    "D12S391": [20, 22], "D10S1248": [14, 15], "D1S1656": [13, 16],
    "D22S1045": [16, 17], "SE33": [22, 24],
}

REPORT_URL = "/api/v1/verifications/{vid}/report"
DOWNLOAD_URL = "/api/v1/verifications/{vid}/report/download"


# --- Helpers ------------------------------------------------------------------


def _pdf_with(content: bytes) -> bytes:
    return b"%PDF-1.4\n" + content + b"\n%%EOF"


def _create_case(client: TestClient, headers: dict[str, str], cnic: str = DEMO_CNIC) -> str:
    response = client.post("/api/v1/verifications", json={"cnic": cnic}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["verification_id"]


def _upload_pdf(
    client: TestClient,
    headers: dict[str, str],
    vid: str,
    payload: bytes | None = None,
    filename: str = "dna report 2026.pdf",
) -> str:
    response = client.post(
        f"/api/v1/verifications/{vid}/documents",
        files={"file": (filename, payload or _pdf_with(b"GV-SAMPLE"), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


def _process(client: TestClient, headers: dict[str, str], vid: str, doc_id: str) -> dict:
    response = client.post(
        f"/api/v1/verifications/{vid}/documents/{doc_id}/process", headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def _compare(client: TestClient, headers: dict[str, str], vid: str) -> dict:
    response = client.post(
        f"/api/v1/verifications/{vid}/dna/compare",
        json={"submitted_profile": REFERENCE_PROFILE},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _decide(client: TestClient, headers: dict[str, str], vid: str) -> dict:
    response = client.post(f"/api/v1/verifications/{vid}/decision", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _full_pipeline(client: TestClient, headers: dict[str, str], vid: str) -> dict:
    """Upload -> process -> compare -> decide, mirroring the Step 1-8 flow."""
    doc_id = _upload_pdf(client, headers, vid)
    _process(client, headers, vid, doc_id)
    _compare(client, headers, vid)
    return _decide(client, headers, vid)


def _get_report(client: TestClient, headers: dict[str, str] | None, vid: str):
    return client.get(REPORT_URL.format(vid=vid), headers=headers)


def _report_json(client: TestClient, headers: dict[str, str], vid: str) -> dict:
    response = _get_report(client, headers, vid)
    assert response.status_code == 200, response.text
    return response.json()


def _events(db: Session, vid: str) -> list[VerificationAuditEvent]:
    """Audit rows of one case in insertion order (id asc)."""
    return list(
        db.execute(
            select(VerificationAuditEvent)
            .join(VerificationCase, VerificationCase.id == VerificationAuditEvent.verification_case_id)
            .where(VerificationCase.verification_id == vid)
            .order_by(VerificationAuditEvent.id.asc())
        ).scalars().all()
    )


def _event_types(db: Session, vid: str) -> list[AuditEventType]:
    return [event.event_type for event in _events(db, vid)]


def _table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def _count(db: Session, model) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


def _inflate(chunk: bytes) -> bytes | None:
    """Inflate one content stream.

    The EOL before ``endstream`` is ambiguous in the PDF grammar — fpdf2 emits
    stream data that may itself end with ``\n`` — so both readings are tried
    rather than silently falling back to raw bytes (which loses the page).
    """
    candidates = [chunk]
    if chunk.endswith(b"\n"):
        candidates.append(chunk[:-1])
    for candidate in candidates:
        try:
            return zlib.decompress(candidate)
        except zlib.error:
            try:
                partial = zlib.decompressobj().decompress(candidate)
            except zlib.error:
                continue
            if partial:
                return partial
    return None


def _pdf_text(data: bytes) -> str:
    """Extract the visible text of the generated PDF using only the stdlib.

    fpdf2 writes zlib-compressed content streams whose show-text operators
    carry latin-1 parenthesised literals — enough to prove what the printed
    report does (and does not) contain.

    The trailing positive control matters for the "must not contain"
    assertions: without it, a failed extraction would make them pass
    vacuously.
    """
    parts: list[str] = []
    for match in re.finditer(rb"stream\r?\n", data):
        stop = data.find(b"endstream", match.end())
        if stop == -1:
            continue
        decoded = _inflate(data[match.end():stop])
        if decoded is None:
            continue
        for literal in re.findall(rb"\(((?:\\.|[^\\()])*)\)", decoded, re.S):
            literal = literal.replace(b"\\(", b"(").replace(b"\\)", b")")
            literal = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8)]), literal)
            parts.append(literal.decode("latin-1"))
    text = "\n".join(parts)
    assert "GeneVerify AI - Verification Report" in text, (
        "PDF text extraction recovered no readable page content"
    )
    return text


# --- Fixtures (isolated per test through conftest) -----------------------------


@pytest.fixture()
def other_user(db_session: Session) -> User:
    user = User(
        username="officer-z",
        password_hash=security_service.hash_password("OtherPass99!"),
        role=UserRole.OFFICER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def other_headers(other_user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {security_service.create_access_token(other_user)}"}


@pytest.fixture()
def admin_user(seeded_session: Session) -> User:
    admin = User(
        username="root_admin",
        password_hash=security_service.hash_password("AdminPassw0rd!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    seeded_session.add(admin)
    seeded_session.commit()
    seeded_session.refresh(admin)
    return admin


@pytest.fixture()
def admin_headers(admin_user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {security_service.create_access_token(admin_user)}"}


@pytest.fixture()
def completed_case(seeded_client: TestClient, auth_headers: dict[str, str]) -> str:
    """A case that has been through the entire Step 4-8 pipeline."""
    vid = _create_case(seeded_client, auth_headers)
    _full_pipeline(seeded_client, auth_headers, vid)
    return vid


# =================================================================================
# 1-4. Access control
# =================================================================================


def test_01_authenticated_user_can_retrieve_own_report(
    seeded_client, auth_headers, completed_case, db_session
):
    body = _report_json(seeded_client, auth_headers, completed_case)
    assert body["verification_id"] == completed_case
    assert body["decision"]["decision"] == "VERIFIED"
    # The audit trail of the case is fully visible to its creator.
    assert len(body["audit_timeline"]) == len(_events(db_session, completed_case))


def test_02_unauthenticated_report_request_returns_401(seeded_client, auth_headers, completed_case):
    assert _get_report(seeded_client, None, completed_case).status_code == 401


def test_03_another_user_cannot_access_report(
    seeded_client, auth_headers, other_headers, completed_case
):
    """Existing safe 404 semantics: existence is never disclosed."""
    mine = _report_json(seeded_client, auth_headers, completed_case)
    response = _get_report(seeded_client, other_headers, completed_case)
    assert response.status_code == 404

    # The refusal carries no case content at all.
    text = response.text
    for secret in (
        mine["identity"]["cnic"],
        mine["identity"]["name"],
        mine["identity"]["father_name"],
        mine["document"]["document_id"],
        mine["decision"]["explanation"],
        "audit_timeline",
        "evidence_score",
        "dna_analysis",
    ):
        if secret:
            assert secret not in text

    # ... and an unknown id answers in exactly the same shape.
    unknown = _get_report(seeded_client, other_headers, "GV-2026-999999")
    assert unknown.status_code == 404
    assert response.json().keys() == unknown.json().keys()
    assert response.json()["detail"].split("'")[0] == unknown.json()["detail"].split("'")[0]


def test_04_admin_access_follows_existing_policy(
    seeded_client, auth_headers, admin_headers, completed_case
):
    body = _report_json(seeded_client, admin_headers, completed_case)
    assert body["verification_id"] == completed_case
    assert body["identity"]["cnic"] == DEMO_CNIC


# =================================================================================
# 5-12. Report content
# =================================================================================


def test_05_report_contains_verification_id_and_status(
    seeded_client, auth_headers, completed_case
):
    body = _report_json(seeded_client, auth_headers, completed_case)
    assert body["verification_id"] == completed_case
    assert body["status"] == "completed"
    assert body["generated_at"]


def test_06_report_contains_safe_identity_information(
    seeded_client, auth_headers, completed_case
):
    identity = _report_json(seeded_client, auth_headers, completed_case)["identity"]
    assert set(identity) == {
        "cnic", "name", "father_name", "date_of_birth", "gender", "identity_status"
    }
    assert identity["cnic"] == DEMO_CNIC
    assert identity["name"]
    assert identity["father_name"]
    assert identity["date_of_birth"]
    assert identity["gender"]


def test_07_report_contains_document_metadata(seeded_client, auth_headers, completed_case):
    document = _report_json(seeded_client, auth_headers, completed_case)["document"]
    assert document["available"] is True
    assert document["document_id"].startswith("GVD-")
    assert document["original_filename"] == "dna report 2026.pdf"
    assert document["document_type"] == "DNA_REPORT"
    assert document["processing_status"] == "PROCESSED"
    assert document["file_size"] > 0
    assert document["uploaded_by"] == "operator"
    assert document["uploaded_at"]


def test_08_report_contains_extraction_summary(seeded_client, auth_headers, completed_case):
    extraction = _report_json(seeded_client, auth_headers, completed_case)["ai_extraction"]
    assert extraction["available"] is True
    assert extraction["extraction_status"] == "SUCCEEDED"
    assert extraction["extracted_name"]
    assert extraction["extracted_cnic"]
    assert extraction["identity_consistency"] == "CONSISTENT"
    assert extraction["extracted_marker_count"] == 20
    # AI output is always labelled as AI output.
    assert extraction["label"] == "AI-extracted information \u2014 validated before use."


def test_09_report_contains_dna_comparison_summary(seeded_client, auth_headers, completed_case):
    dna = _report_json(seeded_client, auth_headers, completed_case)["dna_analysis"]
    assert dna["available"] is True
    assert dna["classification"] == "EXACT_MATCH"
    assert dna["match_percentage"] == 100.0
    assert (dna["total_markers"], dna["matched_markers"]) == (20, 20)
    assert dna["mismatched_markers"] == 0
    assert dna["missing_markers"] == 0
    assert dna["engine_note"] == (
        "DNA comparison was performed using the deterministic STR matching engine."
    )


def test_10_report_contains_evidence_score(seeded_client, auth_headers, completed_case):
    evidence = _report_json(seeded_client, auth_headers, completed_case)["evidence"]
    assert evidence["available"] is True
    assert (evidence["dna_score"], evidence["identity_score"], evidence["document_score"]) == (70, 20, 10)
    assert evidence["total_score"] == 100
    assert evidence["max_score"] == 100
    # Guardrail wording from Step 8 is carried into the report.
    assert evidence["score_label"] == "Prototype Evidence Score"
    assert "not a forensic probability" in evidence["score_note"]


def test_11_report_contains_final_decision_and_explanation(
    seeded_client, auth_headers, completed_case
):
    decision = _report_json(seeded_client, auth_headers, completed_case)["decision"]
    assert decision["available"] is True
    assert decision["decision"] == "VERIFIED"
    assert "20 STR markers" in decision["explanation"]
    assert decision["decided_at"]


def test_12_report_contains_audit_timeline(seeded_client, auth_headers, completed_case):
    timeline = _report_json(seeded_client, auth_headers, completed_case)["audit_timeline"]
    assert [entry["event_type"] for entry in timeline] == [
        "CASE_CREATED",
        "DOCUMENT_UPLOADED",
        "DOCUMENT_PROCESSED",
        "DNA_COMPARED",
        "DECISION_GENERATED",
    ]
    for entry in timeline:
        assert entry["timestamp"] and entry["event"] and entry["actor"] == "operator"
        assert entry["description"]
    # Chronological order.
    stamps = [entry["timestamp"] for entry in timeline]
    assert stamps == sorted(stamps)


# =================================================================================
# 13-17. Nothing sensitive leaks
# =================================================================================


def test_13_raw_dna_markers_are_not_exposed(seeded_client, auth_headers, completed_case):
    response = _get_report(seeded_client, auth_headers, completed_case)
    text = response.text
    for marker in STR_PANEL:
        assert marker not in text, f"marker {marker} leaked into the report"
    assert "str_profile" not in text
    assert "extracted_str_profile" not in text
    assert "allele" not in text.lower()


def test_14_password_hashes_are_not_exposed(seeded_client, auth_headers, completed_case, db_session):
    body = _report_json(seeded_client, auth_headers, completed_case)
    text = json.dumps(body)
    stored_hash = db_session.execute(
        select(User.password_hash).where(User.username == "operator")
    ).scalar_one()
    assert "password" not in text.lower()
    assert "password_hash" not in text
    assert "argon2" not in text
    assert stored_hash not in text


def test_15_jwts_are_not_exposed(seeded_client, auth_headers, completed_case):
    response = _get_report(seeded_client, auth_headers, completed_case)
    token = auth_headers["Authorization"].split(" ", 1)[1]
    assert "eyJ" not in response.text  # base64 JWT body prefix
    assert token not in response.text
    assert "bearer" not in response.text.lower()
    assert "access_token" not in response.text
    assert get_settings().jwt_secret_key not in response.text


def test_16_api_keys_are_not_exposed(seeded_client, auth_headers, completed_case, monkeypatch):
    settings = get_settings()
    fake_key = "sk-test-supersecret-0123456789"
    monkeypatch.setattr(settings, "qwen_api_key", fake_key, raising=False)
    body = _report_json(seeded_client, auth_headers, completed_case)
    text = json.dumps(body)
    assert fake_key not in text
    assert "api_key" not in text.lower()
    assert "secret" not in text.lower()
    # Only the model *name* may be mentioned, never provider credentials.
    assert "sk-" not in text


def test_17_storage_paths_are_not_exposed(
    seeded_client, auth_headers, other_headers, completed_case, db_session
):
    case_id = db_session.execute(
        select(VerificationCase.id).where(VerificationCase.verification_id == completed_case)
    ).scalar_one()
    stored = db_session.execute(
        select(VerificationDocument).where(VerificationDocument.verification_case_id == case_id)
    ).scalar_one()
    text = _get_report(seeded_client, auth_headers, completed_case).text
    assert stored.stored_filename not in text
    assert stored.storage_path not in text
    assert get_settings().document_storage_path not in text
    assert "storage_path" not in text
    assert "stored_filename" not in text
    assert ".db" not in text
    assert not re.search(r"[A-Za-z]:[\\/]|/home/|/tmp/", text)


# =================================================================================
# 18. Incomplete evidence
# =================================================================================


def test_18_incomplete_case_produces_safe_report(seeded_client, auth_headers, db_session):
    # (a) draft case: no document at all
    draft = _create_case(seeded_client, auth_headers)
    body = _report_json(seeded_client, auth_headers, draft)
    assert body["document"]["message"] == "No document submitted."
    assert body["ai_extraction"]["message"] == "Document has not been processed."
    assert body["dna_analysis"]["message"] == "DNA comparison not available."
    assert body["evidence"]["message"] == "Verification decision not available."
    assert body["decision"]["message"] == "Verification decision not available."
    assert body["evidence"]["available"] is False and body["decision"]["available"] is False
    assert body["evidence"]["total_score"] == 0
    assert [e["event_type"] for e in body["audit_timeline"]] == ["CASE_CREATED"]

    # (b) document uploaded but never processed
    _upload_pdf(seeded_client, auth_headers, draft)
    body = _report_json(seeded_client, auth_headers, draft)
    assert body["document"]["available"] is True
    assert body["document"]["processing_status"] == "UPLOADED"
    assert body["ai_extraction"]["message"] == "Document has not been processed."
    assert body["dna_analysis"]["available"] is False

    # (c) processed but no DNA comparison
    doc_id = body["document"]["document_id"]
    _process(seeded_client, auth_headers, draft, doc_id)
    body = _report_json(seeded_client, auth_headers, draft)
    assert body["ai_extraction"]["available"] is True
    assert body["dna_analysis"]["message"] == "DNA comparison not available."
    assert body["decision"]["available"] is False

    # (d) no crash, no fabricated results: every unavailable section stayed zeroed
    assert body["evidence"]["total_score"] == 0
    assert body["decision"]["decision"] is None
    assert body["dna_analysis"]["classification"] is None


def test_18b_partial_evidence_is_reported_without_overclaiming(
    seeded_client, auth_headers
):
    """An extraction that misses markers lowers document/identity scores — no invention."""
    vid = _create_case(seeded_client, auth_headers)
    doc_id = _upload_pdf(seeded_client, auth_headers, vid, payload=_pdf_with(b"GV-PARTIAL"))
    _process(seeded_client, auth_headers, vid, doc_id)
    _compare(seeded_client, auth_headers, vid)
    _decide(seeded_client, auth_headers, vid)
    body = _report_json(seeded_client, auth_headers, vid)
    assert body["ai_extraction"]["extracted_marker_count"] == 18
    assert body["evidence"]["total_score"] <= 100
    assert body["decision"]["decision"] in ("VERIFIED", "REVIEW_REQUIRED", "MISMATCH")


# =================================================================================
# 19-23. Download + report generation event
# =================================================================================


def test_19_report_download_requires_authentication(seeded_client, completed_case):
    response = seeded_client.get(DOWNLOAD_URL.format(vid=completed_case))
    assert response.status_code == 401


def test_20_unauthorized_report_download_is_rejected(
    seeded_client, auth_headers, other_headers, completed_case
):
    assert seeded_client.get(
        DOWNLOAD_URL.format(vid=completed_case), headers=other_headers
    ).status_code == 404
    assert seeded_client.get(
        DOWNLOAD_URL.format(vid="GV-2026-999999"), headers=auth_headers
    ).status_code == 404


def test_21_pdf_generation_succeeds(seeded_client, auth_headers, completed_case):
    response = seeded_client.get(DOWNLOAD_URL.format(vid=completed_case), headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="GeneVerify-Report-{completed_case}.pdf"'
    )
    data = response.content
    assert data.startswith(b"%PDF-")
    assert data.rstrip().endswith(b"%%EOF")
    assert len(data) > 1500  # a real multi-section document, not an empty page

    text = _pdf_text(data)
    # All brief-mandated sections are present.
    for fragment in (
        "DNA Identity Verification Report",
        "1. Case and Subject Identity",
        "2. Submitted Document",
        "3. AI Document Intelligence",
        "4. DNA / STR Analysis",
        "5. Evidence Assessment",
        "6. Verification Decision",
        "7. Audit Trail",
        "Disclaimer",
    ):
        assert fragment in text, fragment
    assert completed_case in text
    assert "100 / 100" in text
    assert "Verified" in text
    assert "Actor: operator" in text


def test_22_pdf_does_not_contain_raw_dna_markers(seeded_client, auth_headers, completed_case):
    response = seeded_client.get(DOWNLOAD_URL.format(vid=completed_case), headers=auth_headers)
    text = _pdf_text(response.content)
    for marker in STR_PANEL:
        assert marker not in text, f"marker {marker} printed in the PDF"
    assert "15, 16" not in text  # an allele pair of the reference profile
    assert "stored_filename" not in text
    assert not re.search(r"[A-Za-z]:[\\/]|/tmp/|storage[\\/]documents", text)
    # No certainty claims; the required disclaimers are printed instead.
    assert "not a legally valid forensic identification system" in text
    assert "not a forensic probability or match probability" in text
    assert "deterministic STR matching engine" in text
    assert "AI-extracted information - validated before use." in text


def test_23_audit_event_is_created_for_report_generation(
    seeded_client, auth_headers, completed_case, db_session
):
    before = _event_types(db_session, completed_case)
    assert AuditEventType.REPORT_GENERATED not in before

    assert seeded_client.get(
        DOWNLOAD_URL.format(vid=completed_case), headers=auth_headers
    ).status_code == 200

    after = _events(db_session, completed_case)
    assert [event.event_type for event in after] == before + [AuditEventType.REPORT_GENERATED]
    event = after[-1]
    assert event.actor_user_id == db_session.execute(
        select(User.id).where(User.username == "operator")
    ).scalar_one()
    assert "report generated" in event.event_description.lower()
    assert len(event.event_description) <= 255


def test_23b_report_generated_event_uses_the_authenticated_actor(
    seeded_client, auth_headers, admin_headers, completed_case, db_session, admin_user
):
    """The actor always comes from the JWT, never from request data."""
    assert seeded_client.get(
        DOWNLOAD_URL.format(vid=completed_case), headers=admin_headers
    ).status_code == 200
    event = _events(db_session, completed_case)[-1]
    assert event.actor_user_id == admin_user.id
    body = _report_json(seeded_client, auth_headers, completed_case)
    assert body["audit_timeline"][-1]["actor"] == "root_admin"


def test_24_duplicate_get_requests_do_not_create_audit_events(
    seeded_client, auth_headers, completed_case, db_session
):
    expected = _event_types(db_session, completed_case)
    for _ in range(5):
        assert _get_report(seeded_client, auth_headers, completed_case).status_code == 200
    # Ordinary GETs of the whole pipeline are read-only too.
    for url in (
        f"/api/v1/verifications/{completed_case}",
        f"/api/v1/verifications/{completed_case}/documents",
        f"/api/v1/verifications/{completed_case}/decision",
        DOWNLOAD_URL.format(vid=completed_case),
    ):
        seeded_client.get(url, headers=auth_headers)

    # Only the explicit download appended exactly one event.
    assert _event_types(db_session, completed_case) == expected + [AuditEventType.REPORT_GENERATED]


def test_24b_report_generation_never_duplicates_evidence(
    seeded_client, auth_headers, completed_case, db_session
):
    before = (
        _count(db_session, VerificationCase),
        _count(db_session, DnaComparisonResult),
        _count(db_session, DocumentExtraction),
        _count(db_session, VerificationDecision),
    )
    first = _report_json(seeded_client, auth_headers, completed_case)
    second = _report_json(seeded_client, auth_headers, completed_case)
    after = (
        _count(db_session, VerificationCase),
        _count(db_session, DnaComparisonResult),
        _count(db_session, DocumentExtraction),
        _count(db_session, VerificationDecision),
    )
    assert before == after
    # The report is a projection: no dedicated report storage table exists.
    assert "verification_reports" not in _table_names(db_session.get_bind())
    # Deterministic content for unchanged evidence (only the clock may differ).
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


# =================================================================================
# 25. Steps 1-8 remain intact
# =================================================================================


def test_25_existing_pipeline_still_works_end_to_end(
    seeded_client, auth_headers, seeded_session
):
    """Regression guard: Step 9 instrumentation did not alter Steps 1-8 behaviour."""
    # Step 2-3: exact-CNIC identity lookup still returns the safe record.
    lookup = seeded_client.get(f"/api/v1/identity/{DEMO_CNIC}", headers=auth_headers)
    assert lookup.status_code == 200, lookup.text
    assert lookup.json()["cnic"] == DEMO_CNIC
    assert "password" not in lookup.text.lower()

    # Step 5: STR comparison response shape unchanged (per-marker detail present)
    vid = _create_case(seeded_client, auth_headers)
    comparison = _compare(seeded_client, auth_headers, vid)
    assert comparison["classification"] == "EXACT_MATCH"
    assert len(comparison["markers"]) == 20
    assert comparison["markers"][0]["marker"] in STR_PANEL

    # Step 6-7: upload + AI extraction still behave as before
    doc_id = _upload_pdf(seeded_client, auth_headers, vid)
    processed = _process(seeded_client, auth_headers, vid, doc_id)
    assert processed["processing_status"] == "PROCESSED"
    assert processed["extracted_marker_count"] == 20

    # Step 8: scoring formula unchanged (100 -> VERIFIED for exact + consistent)
    decision = _decide(seeded_client, auth_headers, vid)
    assert decision["decision"] == "VERIFIED"
    assert decision["evidence_score"] == 100

    # Case status transition still applies
    case = seeded_client.get(f"/api/v1/verifications/{vid}", headers=auth_headers).json()
    assert case["status"] == "completed"


def test_25b_existing_seeded_data_is_untouched(seeded_session):
    assert _count(seeded_session, IdentityRecord) == 123
    assert _count(seeded_session, DnaProfile) == 123


# =================================================================================
# Extra audit-trail guarantees
# =================================================================================


def test_audit_table_schema_matches_the_brief(test_engine: Engine):
    inspector = inspect(test_engine)
    columns = {
        column["name"]: column for column in inspector.get_columns("verification_audit_events")
    }
    assert set(columns) == {
        "id",
        "verification_case_id",
        "actor_user_id",
        "event_type",
        "event_description",
        "created_at",
    }
    indexes = {
        tuple(index["column_names"]) for index in inspector.get_indexes("verification_audit_events")
    }
    assert ("verification_case_id",) in indexes
    assert ("actor_user_id",) in indexes
    assert ("created_at",) in indexes
    assert ("verification_case_id", "created_at") in indexes  # timeline lookup
    references = {
        foreign_key["constrained_columns"][0]: foreign_key["referred_table"]
        for foreign_key in inspector.get_foreign_keys("verification_audit_events")
    }
    assert references == {
        "verification_case_id": "verification_cases",
        "actor_user_id": "users",
    }
    assert "verification_audit_events" in _table_names(test_engine)


def test_every_pipeline_step_records_its_event(seeded_client, auth_headers, db_session):
    vid = _create_case(seeded_client, auth_headers)
    assert _event_types(db_session, vid) == [AuditEventType.CASE_CREATED]

    doc_id = _upload_pdf(seeded_client, auth_headers, vid)
    assert _event_types(db_session, vid)[1] is AuditEventType.DOCUMENT_UPLOADED

    _process(seeded_client, auth_headers, vid, doc_id)
    assert _event_types(db_session, vid)[2] is AuditEventType.DOCUMENT_PROCESSED

    _compare(seeded_client, auth_headers, vid)
    assert _event_types(db_session, vid)[3] is AuditEventType.DNA_COMPARED

    _decide(seeded_client, auth_headers, vid)
    assert _event_types(db_session, vid)[4] is AuditEventType.DECISION_GENERATED

    events = _events(db_session, vid)
    assert {event.actor_user_id for event in events} == {events[0].actor_user_id}
    assert all(event.event_description for event in events)


def test_read_requests_never_record_events(seeded_client, auth_headers, completed_case, db_session):
    expected = _event_types(db_session, completed_case)
    for url in (
        f"/api/v1/verifications/{completed_case}",
        "/api/v1/verifications",
        f"/api/v1/verifications/{completed_case}/documents",
        f"/api/v1/verifications/{completed_case}/decision",
    ):
        assert seeded_client.get(url, headers=auth_headers).status_code == 200
    assert _event_types(db_session, completed_case) == expected


def test_failed_operations_record_no_success_event(seeded_client, auth_headers, db_session):
    vid = _create_case(seeded_client, auth_headers)

    # (a) document that the AI provider cannot analyse -> no DOCUMENT_PROCESSED
    doc_id = _upload_pdf(seeded_client, auth_headers, vid, payload=_pdf_with(b"GV-FAIL"))
    failure = seeded_client.post(
        f"/api/v1/verifications/{vid}/documents/{doc_id}/process", headers=auth_headers
    )
    assert failure.status_code == 502
    types = _event_types(db_session, vid)
    assert AuditEventType.DOCUMENT_PROCESSED not in types

    # (b) rejected STR profile -> no DNA_COMPARED
    bad = seeded_client.post(
        f"/api/v1/verifications/{vid}/dna/compare",
        json={"submitted_profile": {"D3S1358": [1, 2]}},
        headers=auth_headers,
    )
    assert bad.status_code == 422
    assert AuditEventType.DNA_COMPARED not in _event_types(db_session, vid)

    # (c) decision without required evidence -> no DECISION_GENERATED
    premature = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert premature.status_code == 409
    assert AuditEventType.DECISION_GENERATED not in _event_types(db_session, vid)

    # (d) an unknown case records nothing at all
    assert _get_report(seeded_client, auth_headers, "GV-2026-999999").status_code == 404
    assert _event_types(db_session, vid) == [
        AuditEventType.CASE_CREATED,
        AuditEventType.DOCUMENT_UPLOADED,
    ]


def test_audit_descriptions_are_safe_summaries(seeded_client, auth_headers, completed_case, db_session):
    """Event text is human-readable and free of DNA/credentials/paths."""
    events = _events(db_session, completed_case)
    assert events
    blob = json.dumps([event.event_description for event in events])
    for marker in STR_PANEL:
        assert marker not in blob
    for forbidden in ("password", "argon2", "eyJ", "Bearer", "sk-", "storage", "stored_filename", ".db"):
        assert forbidden.lower() not in blob.lower(), forbidden
    assert re.search(r"\[\s*\d+", blob) is None  # no allele lists


def test_events_are_scoped_to_their_own_case(seeded_client, auth_headers, db_session):
    first = _create_case(seeded_client, auth_headers)
    second = _create_case(seeded_client, auth_headers)
    assert [event.event_type for event in _events(db_session, first)] == [AuditEventType.CASE_CREATED]
    assert len(_events(db_session, second)) == 1

    timeline = _report_json(seeded_client, auth_headers, second)["audit_timeline"]
    assert len(timeline) == 1
    assert timeline[0]["event_type"] == "CASE_CREATED"


def test_report_reflects_the_current_state_of_the_case(
    seeded_client, auth_headers, completed_case
):
    before = _report_json(seeded_client, auth_headers, completed_case)
    assert before["status"] == "completed"
    assert before["decision"]["decision"] == "VERIFIED"

    # A new comparison with in-range alternative alleles changes the aggregate
    # DNA evidence in the report immediately - the report is never cached.
    shifted: dict[str, list[float]] = {}
    for marker, alleles in REFERENCE_PROFILE.items():
        low, high = ALLELE_RANGES[marker]
        shifted[marker] = [
            min(max(alleles[0] + 3, low), high),
            min(max(alleles[1] + 3, low), high),
        ]
    response = seeded_client.post(
        f"/api/v1/verifications/{completed_case}/dna/compare",
        json={"submitted_profile": shifted},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    after = _report_json(seeded_client, auth_headers, completed_case)
    assert after["dna_analysis"]["classification"] != before["dna_analysis"]["classification"]
    assert after["audit_timeline"][-1]["event_type"] == "DNA_COMPARED"


def test_report_isolation_between_cases(seeded_client, auth_headers, db_session):
    """Each report carries only its own case's evidence and timeline."""
    first = _create_case(seeded_client, auth_headers)
    _full_pipeline(seeded_client, auth_headers, first)
    second = _create_case(seeded_client, auth_headers)

    body = _report_json(seeded_client, auth_headers, second)
    assert body["verification_id"] == second
    assert body["document"]["available"] is False
    assert len(body["audit_timeline"]) == 1
    assert _report_json(seeded_client, auth_headers, first)["decision"]["decision"] == "VERIFIED"
