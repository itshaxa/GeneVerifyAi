"""Security service: password hashing and JWT handling.

All cryptography is delegated to well-maintained libraries (argon2-cffi for
password hashing, PyJWT for tokens). No passwords or tokens are ever logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

from app.core.config import get_settings

if TYPE_CHECKING:  # avoid circular import at runtime
    from app.models.user import User

# Argon2id with the library's current secure defaults.
_password_hasher = PasswordHasher()


class InvalidTokenError(Exception):
    """Raised when a JWT is missing, malformed, expired or fails validation."""


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2. Never store the plaintext."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True when the password matches the stored Argon2 hash.

    InvalidHashError does not subclass Argon2Error, so both are caught.
    """
    try:
        return _password_hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        return False


@dataclass(frozen=True)
class TokenPayload:
    """Decoded JWT identity claims (no personal/DNA data ever included)."""

    subject: str
    username: str
    role: str


def create_access_token(user: "User", expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT for the user with sub/username/role/exp claims."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    claims = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "iat": now,
        "exp": expires,
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    """Validate signature and expiry; raise InvalidTokenError on any failure."""
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Invalid or expired access token") from exc

    subject = str(claims.get("sub", ""))
    username = str(claims.get("username", ""))
    role = str(claims.get("role", ""))
    if not subject or not role:
        raise InvalidTokenError("Token payload is incomplete")
    return TokenPayload(subject=subject, username=username, role=role)
