"""Idempotent demo-user seeding for development/hackathon use.

Creates the synthetic demo admin account. The plaintext password is supplied
via the DEMO_ADMIN_PASSWORD environment variable (see backend/.env.example)
and is NEVER stored in source code — only its Argon2 hash is persisted.

Usage:
    python -m app.database.seed_users

Note: the demo credential is for the hackathon prototype only and MUST be
replaced before any production deployment.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User, UserRole
from app.services import security_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UserSeedSummary:
    created: int
    skipped: int
    total: int


def seed_users(session: Session) -> UserSeedSummary:
    """Create the demo admin account if it does not exist (idempotent)."""
    settings = get_settings()

    if not settings.demo_admin_password:
        raise RuntimeError(
            "DEMO_ADMIN_PASSWORD is not set. Configure it in backend/.env before "
            "running the user seed command."
        )

    username = settings.demo_admin_username.strip()
    existing = session.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()

    if existing is not None:
        logger.info("Demo user %r already exists — skipping", username)
        created, skipped = 0, 1
    else:
        session.add(
            User(
                username=username,
                password_hash=security_service.hash_password(settings.demo_admin_password),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        created, skipped = 1, 0

    session.commit()
    total = session.execute(select(User)).scalars().all()
    return UserSeedSummary(created=created, skipped=skipped, total=len(total))


def main() -> None:
    from app.database.init import init_db
    from app.database.session import SessionLocal

    init_db()
    with SessionLocal() as session:
        summary = seed_users(session)
        print(
            f"User seed complete: created={summary.created} "
            f"skipped={summary.skipped} total_users={summary.total}"
        )


if __name__ == "__main__":
    main()
