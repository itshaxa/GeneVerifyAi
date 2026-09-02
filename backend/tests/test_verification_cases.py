"""Tests for the verification case layer (Step 4).

Covers creation flow, verification-ID generation, ownership/access rules and
response hygiene (no DNA, no password data). Runs on the isolated in-memory
database fixtures from conftest.
"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.verification_case import CaseStatus, VerificationCase
from app.schemas.verification import VerificationCaseResponse
from app.services import security_service
from app.services import verification_case_service

CREATE_URL = "/api/v1/verifications"
DEMO_MATCH_CNIC = "99900-0000001-1"
DEMO_REVIEW_CNIC = "99900-0000003-5"
UNKNOWN_CNIC = "99900-9999999-9"
OTHER_PASSWORD = "OtherOfficerPass1!"


def _create_case(client: TestClient, headers: dict, cnic: str = DEMO_MATCH_CNIC):
    return client.post(CREATE_URL, json={"cnic": cnic}, headers=headers)


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
# Creation flow
# ---------------------------------------------------------------------------
def test_authenticated_user_can_create_case_with_valid_cnic(
    seeded_client: TestClient, auth_headers: dict, test_user: User
) -> None:
    response = _create_case(seeded_client, auth_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["verification_id"].startswith("GV-")
    assert body["status"] == "draft"
    assert body["identity"]["cnic"] == DEMO_MATCH_CNIC
    assert body["identity"]["name"] == "Sami Demoosh"
    assert body["created_by_user_id"] == test_user.id
    assert body["created_by_username"] == test_user.username


def test_unauthenticated_user_cannot_create_case(seeded_client: TestClient) -> None:
    response = seeded_client.post(CREATE_URL, json={"cnic": DEMO_MATCH_CNIC})
    assert response.status_code == 401


def test_invalid_cnic_is_rejected(seeded_client: TestClient, auth_headers: dict) -> None:
    response = _create_case(seeded_client, auth_headers, cnic="12345")
    assert response.status_code == 422
    assert "CNIC" in response.json()["detail"]


def test_unknown_cnic_returns_404_and_creates_nothing(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    response = _create_case(seeded_client, auth_headers, cnic=UNKNOWN_CNIC)

    assert response.status_code == 404
    assert seeded_client.get(CREATE_URL, headers=auth_headers).json()["total"] == 0


def test_creator_never_taken_from_request_body(
    seeded_client: TestClient, auth_headers: dict, test_user: User
) -> None:
    # Even if a client tries to spoof another creator id, the JWT wins.
    response = seeded_client.post(
        CREATE_URL,
        json={"cnic": DEMO_MATCH_CNIC, "created_by_user_id": 999},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["created_by_user_id"] == test_user.id


# ---------------------------------------------------------------------------
# Verification IDs
# ---------------------------------------------------------------------------
def test_verification_id_is_generated_and_unique(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    first = _create_case(seeded_client, auth_headers).json()["verification_id"]
    second = _create_case(seeded_client, auth_headers, cnic=DEMO_REVIEW_CNIC).json()[
        "verification_id"
    ]

    assert first != second
    assert first == "GV-2026-000001"  # predictable for demo readability
    assert second == "GV-2026-000002"


def test_verification_id_is_not_derived_from_cnic(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    body = _create_case(seeded_client, auth_headers).json()
    digits = DEMO_MATCH_CNIC.replace("-", "")
    assert digits not in body["verification_id"]


def test_id_generator_survives_existing_counter(
    seeded_session: Session, test_user: User
) -> None:
    seeded_session.add(
        VerificationCase(
            verification_id="GV-2026-000041",
            identity_record_id=1,
            created_by_user_id=test_user.id,
            status=CaseStatus.DRAFT,
        )
    )
    seeded_session.commit()

    assert verification_case_service.VerificationIdGenerator.next(seeded_session) == (
        "GV-2026-000042"
    )


# ---------------------------------------------------------------------------
# Defaults and references
# ---------------------------------------------------------------------------
def test_new_case_defaults_to_draft(seeded_client: TestClient, auth_headers: dict) -> None:
    body = _create_case(seeded_client, auth_headers).json()
    assert body["status"] == CaseStatus.DRAFT.value


def test_case_references_the_correct_identity(
    seeded_client: TestClient, seeded_session: Session, auth_headers: dict, test_user: User
) -> None:
    body = _create_case(seeded_client, auth_headers, cnic=DEMO_REVIEW_CNIC).json()

    case = seeded_session.execute(
        select(VerificationCase).where(
            VerificationCase.verification_id == body["verification_id"]
        )
    ).scalar_one()
    # The case stores a reference only — no duplicated identity columns.
    assert case.identity_record.cnic == DEMO_REVIEW_CNIC
    assert case.created_by_user_id == test_user.id


# ---------------------------------------------------------------------------
# Ownership and access
# ---------------------------------------------------------------------------
def test_user_can_retrieve_their_own_case(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    created = _create_case(seeded_client, auth_headers).json()
    response = seeded_client.get(
        f"{CREATE_URL}/{created['verification_id']}", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["verification_id"] == created["verification_id"]


def test_user_cannot_retrieve_another_users_case(
    seeded_client: TestClient, auth_headers: dict, seeded_session: Session
) -> None:
    created = _create_case(seeded_client, auth_headers).json()
    other_headers = _make_officer(seeded_session, "other_officer")

    # Foreign case answers 404 — its existence is never disclosed.
    response = seeded_client.get(
        f"{CREATE_URL}/{created['verification_id']}", headers=other_headers
    )
    assert response.status_code == 404


def test_user_lists_only_their_own_cases(
    seeded_client: TestClient, auth_headers: dict, seeded_session: Session
) -> None:
    own = _create_case(seeded_client, auth_headers).json()["verification_id"]
    other_headers = _make_officer(seeded_session, "other_officer")
    theirs = _create_case(seeded_client, other_headers).json()["verification_id"]

    listed = seeded_client.get(CREATE_URL, headers=auth_headers).json()

    assert listed["total"] == 1
    ids = [item["verification_id"] for item in listed["items"]]
    assert ids == [own]
    assert theirs not in ids


def test_admin_can_access_all_cases(
    seeded_client: TestClient, auth_headers: dict, seeded_session: Session
) -> None:
    officer_case = _create_case(seeded_client, auth_headers).json()["verification_id"]

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

    detail = seeded_client.get(f"{CREATE_URL}/{officer_case}", headers=admin_headers)
    listed = seeded_client.get(CREATE_URL, headers=admin_headers).json()

    assert detail.status_code == 200
    assert listed["total"] == 1


def test_unknown_verification_id_returns_404(
    seeded_client: TestClient, auth_headers: dict
) -> None:
    response = seeded_client.get(f"{CREATE_URL}/GV-2026-999999", headers=auth_headers)
    assert response.status_code == 404


def test_case_list_requires_authentication(seeded_client: TestClient) -> None:
    assert seeded_client.get(CREATE_URL).status_code == 401
    assert seeded_client.get(f"{CREATE_URL}/GV-2026-000001").status_code == 401


# ---------------------------------------------------------------------------
# Service-level status update (no endpoint yet — by design)
# ---------------------------------------------------------------------------
def test_service_can_update_case_status(
    seeded_client: TestClient,
    seeded_session: Session,
    auth_headers: dict,
    test_user: User,
) -> None:
    created_id = _create_case(seeded_client, auth_headers).json()["verification_id"]

    updated = verification_case_service.update_case_status(
        seeded_session, test_user, created_id, CaseStatus.IN_PROGRESS
    )
    assert updated.status is CaseStatus.IN_PROGRESS


# ---------------------------------------------------------------------------
# Response hygiene
# ---------------------------------------------------------------------------
def test_case_responses_never_expose_dna_or_password_data(
    seeded_client: TestClient, auth_headers: dict, test_user: User
) -> None:
    created = _create_case(seeded_client, auth_headers)
    verification_id = created.json()["verification_id"]
    detail = seeded_client.get(f"{CREATE_URL}/{verification_id}", headers=auth_headers)
    listed = seeded_client.get(CREATE_URL, headers=auth_headers)

    allowed_fields = set(VerificationCaseResponse.model_fields.keys())
    assert set(created.json().keys()) == allowed_fields
    assert set(detail.json().keys()) == allowed_fields

    for raw_text in (created.text, detail.text, listed.text):
        for forbidden in ("markers", "dna_profile", "alleles", "password", "password_hash"):
            assert forbidden not in raw_text
        assert test_user.password_hash not in raw_text
