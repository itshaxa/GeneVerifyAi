"""Reusable authentication dependencies for protected routes.

Any future route (verification, documents, reports, analytics, admin) can be
protected by adding ``Depends(get_current_user)`` — or ``Depends(require_role(...))``
for role-restricted endpoints. Error responses are generic on purpose.
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db
from app.models.user import User, UserRole
from app.services import security_service
from app.services.ai import (
    AiProviderNotConfiguredError,
    DocumentIntelligenceService,
    create_document_intelligence_service,
)

#: auto_error=False so missing credentials yield a clean 401 envelope.
bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=_UNAUTHENTICATED_HEADERS,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Extract the bearer token, validate the JWT and return the active user."""
    if credentials is None:
        raise _unauthorized("Not authenticated")

    try:
        payload = security_service.decode_access_token(credentials.credentials)
    except security_service.InvalidTokenError:
        raise _unauthorized("Invalid or expired credentials") from None

    if not payload.subject.isdigit():
        raise _unauthorized("Invalid or expired credentials")

    user = db.get(User, int(payload.subject))
    # Uniform 401 whether the user is missing or deactivated.
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired credentials")
    return user


#: Explicit alias for readability in protected routes.
require_authenticated_user = get_current_user


def require_role(*roles: UserRole) -> Callable[..., User]:
    """Dependency factory enforcing that the current user has one of the roles."""

    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this resource",
            )
        return current_user

    return checker


def get_document_intelligence_service(
    settings: Settings = Depends(get_settings),
) -> DocumentIntelligenceService:
    """Resolve the configured AI document-intelligence provider.

    An unconfigured provider becomes a clean 503 "AI provider is not
    configured." response — dependency errors are raised before the route
    body runs, so they must be translated here. Tests override this
    dependency to inject the deterministic mock.
    """
    try:
        return create_document_intelligence_service(settings)
    except AiProviderNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider is not configured.",
        ) from None
