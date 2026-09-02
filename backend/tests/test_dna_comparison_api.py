"""API tests for the DNA comparison endpoint (Step 5).

Covers the protected comparison flow, ownership rules, the security boundary
(reference DNA is never client-supplied, no bulk DNA endpoints) and response
hygiene. Runs on the isolated seeded in-memory database fixtures.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.dna_comparison import DnaComparisonResult
from app.models.dna_profile import DnaProfile
from app.models.identity import IdentityRecord
from app.models.user import User, UserRole
from app.services import dna_service, security_service

COMPARE_PATH = "/api/v1/verifications/{vid}/dna/compare"
CREATE_URL = "/api/v1/verifications"
DEMO_MATCH_CNIC = "99900-0000001-1"  # Sami Demoosh
OTHER_PASSWORD = "OtherOfficerPass1!"


def _create_case(client: TestClient, headers: dict, cnic: str = DEMO_MATCH_CNIC) -> str:
    response = client.post(CREATE_URL, json={"cnic": cnic}, headers=headers)
    assert response.status_code == 201
    return response.json()["verification_id"]


def _reference_markers(db: Session, cnic: str) -> dict[str, list[float]]:
    """Internal test access to the reference DNA for a demo identity."""
    identity = db.execute(
        select(IdentityRecord).where(IdentityRecord.cnic == cnic)
    ).scalar_one()
    markers = dna_service.get_reference_markers_by_identity_id(db, identity.id)
    assert markers is not None
    return markers


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


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_owner_can_compare_exact_match_profile(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": reference},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["verification_id"] == verification_id
    assert body["classification"] == "EXACT_MATCH"
    assert body["summary"] == {
        "total_markers": 20,
        "matched": 20,
        "mismatched": 0,
        "missing": 0,
        "invalid": 0,
        "match_percentage": 100.0,
    }
    assert len(body["markers"]) == 20
    assert all(marker["status"] == "MATCH" for marker in body["markers"])


def test_mismatched_profile_is_partial_match(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)
    submitted = {marker: list(alleles) for marker, alleles in reference.items()}
    # Flip one marker to a different, still-in-range pair.
    submitted["D3S1358"] = [14, 14] if sorted(reference["D3S1358"]) != [14, 14] else [18, 18]

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": submitted},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["classification"] == "PARTIAL_MATCH"
    assert body["summary"]["matched"] == 19
    assert body["summary"]["mismatched"] == 1
    assert body["summary"]["match_percentage"] == 95.0


def test_incomplete_submitted_profile_reports_missing(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)
    submitted = {m: a for m, a in reference.items() if m not in ("FGA", "SE33")}

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": submitted},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["matched"] == 18
    assert body["summary"]["missing"] == 2
    assert body["summary"]["mismatched"] == 0
    statuses = {m["marker"]: m["status"] for m in body["markers"]}
    assert statuses["FGA"] == "MISSING_SUBMITTED"
    assert statuses["SE33"] == "MISSING_SUBMITTED"


def test_successful_comparison_moves_draft_case_to_in_progress(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)

    seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": reference},
        headers=auth_headers,
    )

    case = seeded_client.get(f"{CREATE_URL}/{verification_id}", headers=auth_headers)
    assert case.json()["status"] == "in_progress"


def test_comparison_is_persisted_and_deterministic(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)
    url = COMPARE_PATH.format(vid=verification_id)

    first = seeded_client.post(url, json={"submitted_profile": reference}, headers=auth_headers)
    second = seeded_client.post(url, json={"submitted_profile": reference}, headers=auth_headers)

    assert first.json()["classification"] == second.json()["classification"] == "EXACT_MATCH"
    assert first.json()["markers"] == second.json()["markers"]

    rows = seeded_session.execute(
        select(func.count(DnaComparisonResult.id))
    ).scalar_one()
    assert rows == 2  # every run is kept for auditability


# ---------------------------------------------------------------------------
# Security boundary
# ---------------------------------------------------------------------------
def test_reference_profile_cannot_be_client_supplied(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={
            "reference_profile": reference,  # malicious: must be rejected
            "submitted_profile": reference,
        },
        headers=auth_headers,
    )

    assert response.status_code == 422
    stored = seeded_session.execute(
        select(func.count(DnaComparisonResult.id))
    ).scalar_one()
    assert stored == 0  # nothing persisted from the rejected request


def test_unauthenticated_comparison_returns_401(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": {"D3S1358": [15, 16]}},
    )
    assert response.status_code == 401


def test_user_cannot_compare_another_users_case(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    other_headers = _make_officer(seeded_session, "other_officer")
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": reference},
        headers=other_headers,
    )
    # 404, not 403 — foreign case existence is never disclosed.
    assert response.status_code == 404


def test_admin_can_compare_any_case(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    admin = User(
        username="root_admin",
        password_hash=security_service.hash_password("AdminPassw0rd!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    seeded_session.add(admin)
    seeded_session.commit()
    seeded_session.refresh(admin)
    admin_headers = {"Authorization": f"Bearer {security_service.create_access_token(admin)}"}
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": reference},
        headers=admin_headers,
    )
    assert response.status_code == 200


def test_unknown_verification_id_returns_404(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    response = seeded_client.post(
        COMPARE_PATH.format(vid="GV-2026-999999"),
        json={"submitted_profile": {"D3S1358": [15, 16]}},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_missing_reference_dna_is_handled_safely(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    identity = seeded_session.execute(
        select(IdentityRecord).where(IdentityRecord.cnic == DEMO_MATCH_CNIC)
    ).scalar_one()
    seeded_session.execute(
        delete(DnaProfile).where(DnaProfile.identity_record_id == identity.id)
    )
    seeded_session.commit()

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": {"D3S1358": [15, 16]}},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert "reference DNA" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Submitted-profile validation through the API
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("bad_profile", "expected_issue"),
    [
        ({}, "at least 1 item"),  # empty
        ({"D3S1358": [15, 16], "UNKNOWN_MARKER": [10, 11]}, "UNKNOWN_MARKER"),  # extra marker
        ({"D3S1358": [15, 500]}, "outside the allowed demonstration range"),
        ({"D3S1358": ["15", "16"]}, "non-numeric allele"),
        ({"D3S1358": [15, 16, 17]}, "exactly 2 allele values"),  # too many alleles
        ({"D3S1358": [15]}, "exactly 2 allele values"),  # missing allele
        ({"D3S1358": None}, "must be a list of allele values"),  # null value
    ],
)
def test_invalid_submitted_profiles_are_rejected_with_structured_errors(
    seeded_client: TestClient, auth_headers: dict, bad_profile: dict, expected_issue: str
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": bad_profile},
        headers=auth_headers,
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)
    assert expected_issue in detail  # each problem is reported explicitly


# ---------------------------------------------------------------------------
# DNA exposure boundaries
# ---------------------------------------------------------------------------
def test_no_bulk_dna_endpoint_exists(seeded_client: TestClient) -> None:
    paths = set(seeded_client.app.openapi()["paths"])
    dna_paths = {path for path in paths if "dna" in path.lower()}
    # The ONLY dna-related route is the per-case comparison endpoint.
    assert dna_paths == {"/api/v1/verifications/{verification_id}/dna/compare"}
    for forbidden in ("/api/v1/dna", "/api/v1/dna_profiles", "/api/v1/all-dna"):
        assert forbidden not in paths


def test_identity_lookup_still_exposes_no_dna(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    response = seeded_client.get(f"/api/v1/identity/{DEMO_MATCH_CNIC}", headers=auth_headers)
    assert response.status_code == 200
    for forbidden in ("markers", "dna", "alleles"):
        assert forbidden not in response.text.lower()


def test_comparison_response_does_not_leak_internals(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict, test_user: User
) -> None:
    verification_id = _create_case(seeded_client, auth_headers)
    reference = _reference_markers(seeded_session, DEMO_MATCH_CNIC)

    response = seeded_client.post(
        COMPARE_PATH.format(vid=verification_id),
        json={"submitted_profile": reference},
        headers=auth_headers,
    )

    body = response.json()
    assert set(body.keys()) == {"verification_id", "classification", "summary", "markers", "compared_at"}
    for marker in body["markers"]:
        assert set(marker.keys()) == {
            "marker",
            "status",
            "reference_alleles",
            "submitted_alleles",
            "reason",
        }
    assert test_user.password_hash not in response.text
    assert "password" not in response.text
