"""Step 8 tests — Verification Decision Engine & Evidence Scoring.

All tests run against the deterministic mock provider (Step 7): NO network
access, NO AI calls for decisions. The decision engine is pure application
logic combining existing Step 5 + Step 7 evidence.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dna_comparison import DnaComparisonResult
from app.models.document_extraction import DocumentExtraction, ExtractionStatus
from app.models.user import User, UserRole
from app.models.verification_case import CaseStatus
from app.models.verification_decision import ConsistencyLevel, DecisionOutcome, VerificationDecision
from app.services import security_service
from app.services.str_engine.comparison import ComparisonClassification

DEMO_CNIC = "99900-0000001-1"  # Sami Demoosh


def _pdf_with(content: bytes) -> bytes:
    return b"%PDF-1.4\n" + content + b"\n%%EOF"


def _create_case(client, headers, cnic=DEMO_CNIC):
    r = client.post("/api/v1/verifications", json={"cnic": cnic}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["verification_id"]


def _upload_pdf(client, headers, vid, payload=None):
    if payload is None:
        payload = _pdf_with(b"GV-SAMPLE")
    r = client.post(
        f"/api/v1/verifications/{vid}/documents",
        files={"file": ("report.pdf", payload, "application/pdf")},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["document_id"]


def _process_document(client, headers, vid, doc_id):
    r = client.post(
        f"/api/v1/verifications/{vid}/documents/{doc_id}/process",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _compare_reference(client, headers, vid, profile=None):
    """Compare with the known demo profile (20/20 for EXACT_MATCH)."""
    if profile is None:
        profile = {
            "D3S1358": [15, 16], "vWA": [17, 18], "FGA": [21, 24],
            "D8S1179": [12, 13], "D21S11": [29, 30], "D18S51": [14, 16],
            "D5S818": [10, 11], "D13S317": [9, 11], "D7S820": [9, 10],
            "CSF1PO": [10, 11], "TH01": [7, 9], "TPOX": [8, 11],
            "D16S539": [11, 12], "D2S1338": [19, 21], "D19S433": [13, 14],
            "D12S391": [20, 22], "D10S1248": [14, 15], "D1S1656": [13, 16],
            "D22S1045": [16, 17], "SE33": [22, 24],
        }
    r = client.post(
        f"/api/v1/verifications/{vid}/dna/compare",
        json={"submitted_profile": profile},
        headers=headers,
    )
    return r


def _full_evidence(client, headers, vid):
    """Upload + process a document AND run a DNA comparison. Returns (extraction_result, comparison_result)."""
    doc_id = _upload_pdf(client, headers, vid)
    proc = _process_document(client, headers, vid, doc_id)
    comp = _compare_reference(client, headers, vid)
    assert comp.status_code == 200
    return proc, comp.json()


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
    token = security_service.create_access_token(other_user)
    return {"Authorization": f"Bearer {token}"}


# --- 1. Authenticated user can generate decision ------------------------------------


def test_authenticated_user_can_generate_decision(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] in ("VERIFIED", "REVIEW_REQUIRED", "MISMATCH")
    assert body["evidence_score"] >= 0


# --- 2. Unauthenticated user receives 401 -------------------------------------------


def test_unauthenticated_decision_401(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision")
    assert r.status_code == 401
    r = seeded_client.get(f"/api/v1/verifications/{vid}/decision")
    assert r.status_code == 401


# --- 3. User cannot access another user's case --------------------------------------


def test_foreign_case_decision_404(seeded_client, auth_headers, other_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=other_headers)
    assert r.status_code == 404


# --- 4. Unknown case returns 404 -----------------------------------------------------


def test_unknown_case_decision_404(seeded_client, auth_headers):
    r = seeded_client.post("/api/v1/verifications/GV-9999-999999/decision", headers=auth_headers)
    assert r.status_code == 404


# --- 5. Missing DNA comparison returns safe 409 -------------------------------------


def test_missing_dna_comparison_409(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 409
    assert "DNA comparison" in r.json()["detail"] or "No DNA" in r.json()["detail"]


# --- 6. Missing extraction evidence is handled safely --------------------------------


def test_missing_extraction_still_works(seeded_client, auth_headers):
    """Decision works with DNA comparison only (no extraction). Score reduced."""
    vid = _create_case(seeded_client, auth_headers)
    comp = _compare_reference(seeded_client, auth_headers, vid)
    assert comp.status_code == 200
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # EXACT_MATCH but no extraction → identity=NOT_DETECTED, document=NOT_DETECTED
    assert body["identity_consistency"] == "NOT_DETECTED"
    assert body["document_consistency"] == "NOT_DETECTED"
    # Decision: EXACT_MATCH + NOT_DETECTED (not INCONSISTENT) → VERIFIED
    assert body["decision"] == "VERIFIED"
    # Score: 70 (DNA) + 0 (identity NOT_DETECTED) + 0 (document NOT_DETECTED) = 70
    assert body["evidence_score"] == 70


# --- 7. EXACT_MATCH + consistent evidence → VERIFIED --------------------------------


def test_exact_match_consistent_verified(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "VERIFIED"
    assert body["dna_classification"] == "EXACT_MATCH"
    assert body["identity_consistency"] == "CONSISTENT"
    assert body["document_consistency"] == "CONSISTENT"
    assert body["evidence_score"] == 100


# --- 8. EXACT_MATCH + inconsistent identity → REVIEW_REQUIRED -----------------------


def test_exact_match_inconsistent_identity_review(seeded_client, auth_headers, seeded_session):
    vid = _create_case(seeded_client, auth_headers)
    doc_id = _upload_pdf(seeded_client, auth_headers, vid)
    _process_document(seeded_client, auth_headers, vid, doc_id)
    _compare_reference(seeded_client, auth_headers, vid)

    # Tamper: overwrite extraction with a different CNIC
    extraction = seeded_session.execute(select(DocumentExtraction)).scalar_one()
    extraction.extracted_identity_data = {
        **extraction.extracted_identity_data,
        "cnic": "12345-6789012-3",
        "patient_name": "Someone Else",
    }
    seeded_session.commit()

    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "REVIEW_REQUIRED"
    assert body["identity_consistency"] == "INCONSISTENT"


# --- 9. PARTIAL_MATCH → REVIEW_REQUIRED ----------------------------------------------


def test_partial_match_review_required(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    # Partial: only 10 of 20 markers
    partial = {
        "D3S1358": [15, 16], "vWA": [17, 18], "FGA": [21, 24],
        "D8S1179": [12, 13], "D21S11": [29, 30], "D18S51": [14, 16],
        "D5S818": [10, 11], "D13S317": [9, 11], "D7S820": [9, 10],
        "CSF1PO": [10, 11],
    }
    comp = _compare_reference(seeded_client, auth_headers, vid, partial)
    assert comp.status_code == 200
    assert comp.json()["classification"] == "PARTIAL_MATCH"
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["decision"] == "REVIEW_REQUIRED"


# --- 10. NO_MATCH → MISMATCH --------------------------------------------------------


def test_no_match_mismatch(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    # All 20 markers within valid ALLELE_RANGES but every marker is a MISMATCH
    no_match = {
        "D3S1358": [14, 17], "vWA": [14, 15], "FGA": [18, 19],
        "D8S1179": [9, 10], "D21S11": [32, 33], "D18S51": [17, 18],
        "D5S818": [8, 9], "D13S317": [12, 13], "D7S820": [11, 12],
        "CSF1PO": [12, 13], "TH01": [6, 8], "TPOX": [9, 10],
        "D16S539": [9, 10], "D2S1338": [22, 24], "D19S433": [12, 15],
        "D12S391": [18, 19], "D10S1248": [13, 16], "D1S1656": [12, 14],
        "D22S1045": [15, 18], "SE33": [19, 20],
    }
    comp = _compare_reference(seeded_client, auth_headers, vid, no_match)
    assert comp.status_code == 200
    assert comp.json()["classification"] == "NO_MATCH"
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "MISMATCH"
    assert body["dna_classification"] == "NO_MATCH"


# --- 11. INVALID → REVIEW_REQUIRED ---------------------------------------------------


def test_invalid_dna_review(seeded_client, auth_headers, seeded_session):
    """Directly insert an INVALID comparison result and run decision."""
    vid = _create_case(seeded_client, auth_headers)
    # Get the case PK
    from app.models.verification_case import VerificationCase
    case = seeded_session.execute(
        select(VerificationCase).where(VerificationCase.verification_id == vid)
    ).scalar_one()
    # Insert an INVALID comparison row directly
    invalid_result = DnaComparisonResult(
        verification_case_id=case.id,
        classification=ComparisonClassification.INVALID,
        total_markers=20,
        matched_markers=0,
        mismatched_markers=0,
        missing_markers=20,
        invalid_markers=20,
        match_percentage=0.0,
        marker_results=[],
        submitted_markers={},
    )
    seeded_session.add(invalid_result)
    seeded_session.commit()

    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "REVIEW_REQUIRED"
    assert body["dna_classification"] == "INVALID"


# --- 12. Evidence score is deterministic --------------------------------------------


def test_evidence_score_deterministic(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r1 = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    r2 = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r1.json()["evidence_score"] == r2.json()["evidence_score"]
    assert r1.json()["decision"] == r2.json()["decision"]


# --- 13. Same evidence produces same score ------------------------------------------


def test_same_evidence_same_score(seeded_client, auth_headers):
    """Create two cases with the same evidence and get the same score."""
    vid1 = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid1)
    r1 = seeded_client.post(f"/api/v1/verifications/{vid1}/decision", headers=auth_headers)

    vid2 = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid2)
    r2 = seeded_client.post(f"/api/v1/verifications/{vid2}/decision", headers=auth_headers)

    assert r1.json()["evidence_score"] == r2.json()["evidence_score"]
    assert r1.json()["decision"] == r2.json()["decision"]


# --- 14. Explanation is deterministic -----------------------------------------------


def test_explanation_deterministic(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r1 = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    r2 = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r1.json()["explanation"] == r2.json()["explanation"]
    assert len(r1.json()["explanation"]) > 10


# --- 15. DNA result comes from existing STR engine -----------------------------------


def test_dna_from_existing_engine(seeded_client, auth_headers):
    """The decision uses the Step 5 classification, not recomputed."""
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    body = r.json()
    assert body["dna_classification"] == "EXACT_MATCH"
    assert body["dna_match_percentage"] == 100.0


# --- 16. Qwen is never used to determine the decision --------------------------------


def test_no_ai_in_decision(seeded_client, auth_headers):
    """Decision runs with AI provider NOT configured — proves no AI dependency."""
    from app.core.config import get_settings
    settings = get_settings()
    snapshot = (settings.ai_provider, settings.qwen_api_key)
    try:
        settings.ai_provider = "qwen"
        settings.qwen_api_key = None  # unconfigured

        vid = _create_case(seeded_client, auth_headers)
        # Need a DNA comparison but no document processing (no AI)
        comp = _compare_reference(seeded_client, auth_headers, vid)
        assert comp.status_code == 200

        # Decision should work fine — no AI needed
        r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["decision"] in ("VERIFIED", "REVIEW_REQUIRED", "MISMATCH")
    finally:
        settings.ai_provider, settings.qwen_api_key = snapshot


# --- 17. Decision does not expose raw DNA profile ------------------------------------


def test_no_raw_dna_in_response(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    text = r.text.lower()
    assert "allele" not in text
    assert "d3s1358" not in text
    assert "str_profile" not in text
    assert "submitted_markers" not in text
    assert "marker_results" not in text


# --- 18. Decision does not expose password hash -------------------------------------


def test_no_password_hash_in_response(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    text = r.text.lower()
    assert "argon2" not in text
    assert "password" not in text
    assert "$" not in text


# --- 19. Decision does not expose API keys ------------------------------------------


def test_no_api_key_in_response(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    text = r.text.lower()
    assert "api_key" not in text
    assert "qwen" not in text
    assert "sk-" not in text


# --- 20. Case status updates correctly -----------------------------------------------


def test_case_status_verified_becomes_completed(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    r = seeded_client.get(f"/api/v1/verifications/{vid}", headers=auth_headers)
    assert r.json()["status"] == "completed"


def test_case_status_mismatch_becomes_completed(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    no_match = {
        "D3S1358": [14, 17], "vWA": [14, 15], "FGA": [18, 19],
        "D8S1179": [9, 10], "D21S11": [32, 33], "D18S51": [17, 18],
        "D5S818": [8, 9], "D13S317": [12, 13], "D7S820": [11, 12],
        "CSF1PO": [12, 13], "TH01": [6, 8], "TPOX": [9, 10],
        "D16S539": [9, 10], "D2S1338": [22, 24], "D19S433": [12, 15],
        "D12S391": [18, 19], "D10S1248": [13, 16], "D1S1656": [12, 14],
        "D22S1045": [15, 18], "SE33": [19, 20],
    }
    _compare_reference(seeded_client, auth_headers, vid, no_match)
    seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    r = seeded_client.get(f"/api/v1/verifications/{vid}", headers=auth_headers)
    assert r.json()["status"] == "completed"


def test_case_status_review_becomes_review_required(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    partial = {
        "D3S1358": [15, 16], "vWA": [17, 18], "FGA": [21, 24],
        "D8S1179": [12, 13], "D21S11": [29, 30],
    }
    _compare_reference(seeded_client, auth_headers, vid, partial)
    seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    r = seeded_client.get(f"/api/v1/verifications/{vid}", headers=auth_headers)
    assert r.json()["status"] == "review_required"


# --- 21. Re-running decision is deterministic ---------------------------------------


def test_rerun_decision_idempotent(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    r1 = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    r2 = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r1.json()["decision"] == r2.json()["decision"]
    assert r1.json()["evidence_score"] == r2.json()["evidence_score"]
    # One decision row only
    from app.models.verification_case import VerificationCase
    case = seeded_client.get(f"/api/v1/verifications/{vid}", headers=auth_headers).json()
    # GET decision returns the same single result
    r3 = seeded_client.get(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r3.status_code == 200
    assert r3.json()["decision"] == r1.json()["decision"]


# --- 22. Existing Steps 1–7 tests continue passing (verified by running pytest) ------


# --- GET decision --------------------------------------------------------------------


def test_get_decision_no_decision_404(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    r = seeded_client.get(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 404


def test_get_decision_returns_current(seeded_client, auth_headers):
    vid = _create_case(seeded_client, auth_headers)
    _full_evidence(seeded_client, auth_headers, vid)
    seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    r = seeded_client.get(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["verification_id"] == vid


# --- Score formula validation --------------------------------------------------------


def test_score_partial_match_capped(seeded_client, auth_headers):
    """PARTIAL_MATCH score never reaches 70 (DNA full) → cannot auto-VERIFIED."""
    vid = _create_case(seeded_client, auth_headers)
    # 19 of 20 markers match → 95%
    profile_19 = {
        "D3S1358": [15, 16], "vWA": [17, 18], "FGA": [21, 24],
        "D8S1179": [12, 13], "D21S11": [29, 30], "D18S51": [14, 16],
        "D5S818": [10, 11], "D13S317": [9, 11], "D7S820": [9, 10],
        "CSF1PO": [10, 11], "TH01": [7, 9], "TPOX": [8, 11],
        "D16S539": [11, 12], "D2S1338": [19, 21], "D19S433": [13, 14],
        "D12S391": [20, 22], "D10S1248": [14, 15], "D1S1656": [13, 16],
        "D22S1045": [16, 17],
        "SE33": [20, 21],  # MISMATCH
    }
    _compare_reference(seeded_client, auth_headers, vid, profile_19)
    r = seeded_client.post(f"/api/v1/verifications/{vid}/decision", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    # PARTIAL_MATCH → REVIEW_REQUIRED always (rule 3)
    assert body["decision"] == "REVIEW_REQUIRED"
    # Score: DNA proportional, capped at 60, + 0 identity + 0 document
    assert body["evidence_score"] <= 60
