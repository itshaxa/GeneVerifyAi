"""Authentication endpoints: login, current user, logout.

Logout is stateless by design: JWTs cannot be revoked server-side without a
token blocklist, so the client discards the (short-lived) token. The endpoint
exists for a uniform frontend flow and future upgrade to server-side sessions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserPublic
from app.services import auth_service, security_service

router = APIRouter()


@router.post("/login", response_model=LoginResponse, summary="Authenticate and receive a JWT")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    """Exchange username/password for a bearer access token."""
    try:
        user = auth_service.authenticate_user(db, payload.username, payload.password)
    except auth_service.AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    access_token = security_service.create_access_token(user)
    return LoginResponse(
        access_token=access_token,
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic, summary="Current authenticated user")
def current_user(current_user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.post("/logout", summary="Log out (client discards the token)")
def logout(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"detail": "Logged out. The access token must be discarded by the client."}
