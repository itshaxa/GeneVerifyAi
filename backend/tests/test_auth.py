"""Authentication tests: users, password hashing, JWT, protected routes.

All tests run against the isolated in-memory database fixtures from conftest.
"""

from datetime import timedelta

import jwt as pyjwt
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User, UserRole
from app.schemas.auth import UserPublic
from app.services import security_service

LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"
DEMO_MATCH_CNIC = "99900-0000001-1"


# ---------------------------------------------------------------------------
# 1-4. User model + password hashing
# ---------------------------------------------------------------------------
def test_user_creation_persists_username_and_role(db_session: Session) -> None:
    db_session.add(
        User(
            username="new_officer",
            password_hash=security_service.hash_password("SomePassw0rd!"),
            role=UserRole.OFFICER,
        )
    )
    db_session.commit()

    fetched = db_session.execute(select(User).where(User.username == "new_officer")).scalar_one()
    assert fetched.role is UserRole.OFFICER
    assert fetched.is_active is True


def test_password_hash_is_not_plaintext(test_user: User, test_user_password: str) -> None:
    assert test_user.password_hash != test_user_password
    assert test_user_password not in test_user.password_hash
    assert test_user.password_hash.startswith("$argon2")


def test_correct_password_verifies(test_user: User, test_user_password: str) -> None:
    assert security_service.verify_password(test_user_password, test_user.password_hash)


def test_incorrect_password_is_rejected(test_user: User, test_user_password: str) -> None:
    assert not security_service.verify_password("WrongPassword!", test_user.password_hash)
    # Garbage hashes must fail safely rather than raising.
    assert not security_service.verify_password(test_user_password, "not-a-valid-hash")


# ---------------------------------------------------------------------------
# 5-6. Login endpoint
# ---------------------------------------------------------------------------
def test_login_with_valid_credentials(client: TestClient, test_user: User, test_user_password: str) -> None:
    response = client.post(
        LOGIN_URL, json={"username": test_user.username, "password": test_user_password}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == test_user.username
    assert body["user"]["role"] == "officer"


def test_login_with_invalid_credentials_is_rejected(client: TestClient, test_user: User, test_user_password: str) -> None:
    wrong_password = client.post(
        LOGIN_URL, json={"username": test_user.username, "password": "WrongPassword!"}
    )
    unknown_user = client.post(
        LOGIN_URL, json={"username": "ghost", "password": test_user_password}
    )

    # Uniform generic message — no hint which part was wrong (anti-enumeration).
    for response in (wrong_password, unknown_user):
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password."


def test_login_validates_payload_shape(client: TestClient) -> None:
    response = client.post(LOGIN_URL, json={"username": "admin"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 7-8. JWT creation and validation
# ---------------------------------------------------------------------------
def test_jwt_contains_identity_claims(test_user: User) -> None:
    token = security_service.create_access_token(test_user)
    payload = security_service.decode_access_token(token)

    assert payload.subject == str(test_user.id)
    assert payload.username == test_user.username
    assert payload.role == "officer"

    # Standard claims are present and the token is not valid forever.
    settings = get_settings()
    raw = pyjwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert raw["exp"] > raw["iat"]
    assert raw["sub"] == str(test_user.id)


def test_expired_token_is_rejected(client: TestClient, test_user: User) -> None:
    expired = security_service.create_access_token(test_user, expires_delta=timedelta(minutes=-1))
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired credentials"


def test_malformed_or_tampered_tokens_are_rejected(client: TestClient, test_user: User) -> None:
    tampered = security_service.create_access_token(test_user) + "x"

    for bad_token in ("not-a-jwt", tampered, "a.b.c"):
        response = client.get(ME_URL, headers={"Authorization": f"Bearer {bad_token}"})
        assert response.status_code == 401


def test_token_signed_with_wrong_secret_is_rejected(client: TestClient, test_user: User) -> None:
    settings = get_settings()
    forged = pyjwt.encode(
        {"sub": str(test_user.id), "username": test_user.username, "role": "officer", "exp": 9_999_999_999},
        "forged-secret-key-for-tests-0123456789abcdef",
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 9-12. Current user + auth dependency
# ---------------------------------------------------------------------------
def test_missing_credentials_are_rejected(client: TestClient) -> None:
    response = client.get(ME_URL)
    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_authenticated_request_is_accepted(client: TestClient, auth_headers: dict, test_user: User) -> None:
    response = client.get(ME_URL, headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == test_user.id


def test_inactive_user_cannot_login_or_use_tokens(client: TestClient, db_session: Session) -> None:
    inactive = User(
        username="suspended",
        password_hash=security_service.hash_password("StillValidPass1!"),
        role=UserRole.OFFICER,
        is_active=False,
    )
    db_session.add(inactive)
    db_session.commit()
    db_session.refresh(inactive)

    login = client.post(LOGIN_URL, json={"username": "suspended", "password": "StillValidPass1!"})
    assert login.status_code == 401

    # Even a token minted before deactivation must be refused.
    stale_token = security_service.create_access_token(inactive)
    me = client.get(ME_URL, headers={"Authorization": f"Bearer {stale_token}"})
    assert me.status_code == 401


def test_token_for_deleted_user_is_rejected(client: TestClient, db_session: Session) -> None:
    ghost = User(
        username="ghost",
        password_hash=security_service.hash_password("GhostPassw0rd!"),
        role=UserRole.ADMIN,
    )
    db_session.add(ghost)
    db_session.commit()
    token = security_service.create_access_token(ghost)
    db_session.delete(ghost)
    db_session.commit()

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_current_user_endpoint_returns_safe_fields(client: TestClient, auth_headers: dict) -> None:
    response = client.get(ME_URL, headers=auth_headers)

    assert response.status_code == 200
    assert set(response.json().keys()) == set(UserPublic.model_fields.keys())


def test_logout_endpoint_requires_and_accepts_auth(client: TestClient, auth_headers: dict) -> None:
    assert client.post(LOGOUT_URL).status_code == 401
    assert client.post(LOGOUT_URL, headers=auth_headers).status_code == 200


# ---------------------------------------------------------------------------
# 13-15. Protected identity lookup + response hygiene
# ---------------------------------------------------------------------------
def test_identity_lookup_requires_authentication(seeded_client: TestClient) -> None:
    response = seeded_client.get(f"/api/v1/identity/{DEMO_MATCH_CNIC}")
    assert response.status_code == 401


def test_identity_lookup_works_when_authenticated(seeded_client: TestClient, auth_headers: dict) -> None:
    response = seeded_client.get(f"/api/v1/identity/{DEMO_MATCH_CNIC}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Sami Demoosh"


def test_password_hash_never_appears_in_api_responses(
    client: TestClient, test_user: User, test_user_password: str
) -> None:
    login = client.post(
        LOGIN_URL, json={"username": test_user.username, "password": test_user_password}
    )
    token = login.json()["access_token"]
    me = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    for raw_text in (login.text, me.text):
        assert test_user.password_hash not in raw_text
        assert "password_hash" not in raw_text


def test_role_dependency_enforces_roles(client: TestClient, db_session: Session) -> None:
    from fastapi import APIRouter

    from app.api.deps import require_role

    officer = User(
        username="role_check",
        password_hash=security_service.hash_password("RoleCheckPass1!"),
        role=UserRole.OFFICER,
    )
    db_session.add(officer)
    db_session.commit()
    db_session.refresh(officer)

    guard = APIRouter()

    @guard.get("/admin-only")
    def admin_only(user: User = Depends(require_role(UserRole.ADMIN))) -> dict:
        del user
        return {"ok": True}

    client.app.include_router(guard, prefix="/api/v1")
    token = {"Authorization": f"Bearer {security_service.create_access_token(officer)}"}

    assert client.get("/api/v1/admin-only", headers=token).status_code == 403
