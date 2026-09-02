"""API tests for the CNIC identity lookup endpoint.

Covers the security requirements: single-record lookup only, no browsing,
no DNA profile leakage in the operator-facing response.
"""

from fastapi.testclient import TestClient

from app.schemas.identity import IdentityLookupResponse

LOOKUP_URL = "/api/v1/identity/{cnic}"
DEMO_MATCH_CNIC = "99900-0000001-1"
DEMO_REVIEW_CNIC = "99900-0000003-5"

#: Fields the safe lookup response may contain — nothing else.
ALLOWED_FIELDS = set(IdentityLookupResponse.model_fields.keys())


def test_valid_cnic_returns_exactly_one_identity(seeded_client: TestClient, auth_headers: dict) -> None:
    response = seeded_client.get(f"/api/v1/identity/{DEMO_MATCH_CNIC}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["cnic"] == DEMO_MATCH_CNIC
    assert body["name"] == "Sami Demoosh"
    assert body["father_name"] == "Kamal Demoosh"
    assert body["gender"] == "male"
    assert body["status"] == "active"
    assert body["date_of_birth"]


def test_lookup_accepts_unformatted_and_padded_cnic(seeded_client: TestClient, auth_headers: dict) -> None:
    digits_only = seeded_client.get("/api/v1/identity/9990000000011", headers=auth_headers)
    assert digits_only.status_code == 200
    assert digits_only.json()["cnic"] == DEMO_MATCH_CNIC


def test_review_demo_record_is_returned(seeded_client: TestClient, auth_headers: dict) -> None:
    response = seeded_client.get(f"/api/v1/identity/{DEMO_REVIEW_CNIC}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "under_review"


def test_unknown_cnic_returns_404(seeded_client: TestClient, auth_headers: dict) -> None:
    response = seeded_client.get("/api/v1/identity/99900-9999999-9", headers=auth_headers)

    assert response.status_code == 404
    assert "detail" in response.json()


def test_invalid_cnic_returns_422(seeded_client: TestClient, auth_headers: dict) -> None:
    for bad_cnic in ("12345", "99900-0000001-12", "ABCDEFGHIJKLM", "999000000001"):
        response = seeded_client.get(f"/api/v1/identity/{bad_cnic}", headers=auth_headers)
        assert response.status_code == 422, f"{bad_cnic} should be rejected"
        assert "CNIC" in response.json()["detail"]


def test_response_does_not_expose_dna_profile(seeded_client: TestClient, auth_headers: dict) -> None:
    body = seeded_client.get(f"/api/v1/identity/{DEMO_MATCH_CNIC}", headers=auth_headers).json()

    assert set(body.keys()) == ALLOWED_FIELDS
    for forbidden_key in ("markers", "dna_profile", "str_profile", "alleles"):
        assert forbidden_key not in body


def test_no_endpoint_exposes_the_full_identity_database(seeded_client: TestClient, auth_headers: dict) -> None:
    # Guessable bulk/export paths must never return data.
    for path in (
        "/api/v1/identities",
        "/api/v1/identity",
        "/api/v1/database/export",
        "/api/v1/dna-profiles",
    ):
        assert seeded_client.get(path).status_code in {404, 405}, f"{path} must not exist"

    # '/identity/all' is not a list endpoint: when authenticated it is treated
    # as an invalid CNIC by the single-lookup route and rejected.
    assert seeded_client.get("/api/v1/identity/all", headers=auth_headers).status_code == 422

    # And the registered API surface contains no identity list/export route.
    api_paths = set(seeded_client.app.openapi()["paths"].keys())
    identity_paths = [path for path in api_paths if "identit" in path]
    assert identity_paths == [LOOKUP_URL]


def test_lookup_on_empty_database_returns_404(client: TestClient, auth_headers: dict) -> None:
    # Unseeded isolated database: well-formed CNIC simply does not exist.
    response = client.get(f"/api/v1/identity/{DEMO_MATCH_CNIC}", headers=auth_headers)
    assert response.status_code == 404
