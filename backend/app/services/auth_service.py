"""Authentication business logic (credential verification).

Security rules:
- Error messages are generic to avoid user enumeration.
- A dummy hash is verified when the username is unknown so response timing
  does not reveal whether an account exists.
- Passwords and tokens are never logged.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.services import security_service

logger = logging.getLogger(__name__)

# Verified once at import so unknown-username lookups cost the same time.
_DUMMY_PASSWORD_HASH = security_service.hash_password("dummy-password-for-timing-only")


class AuthenticationError(Exception):
    """Raised for any failed login attempt (bad credentials or inactive user)."""


def authenticate_user(db: Session, username: str, password: str) -> User:
    """Return the active user matching the credentials.

    Raises:
        AuthenticationError: on any failed login, with a uniform message.
    """
    user = db.execute(
        select(User).where(User.username == username.strip())
    ).scalar_one_or_none()

    password_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = security_service.verify_password(password, password_hash)

    if user is None or not password_ok or not user.is_active:
        logger.info("Failed login attempt for username=%r", username)
        raise AuthenticationError("Incorrect username or password.")
    return user
