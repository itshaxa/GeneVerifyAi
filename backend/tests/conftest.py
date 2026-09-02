"""Shared pytest fixtures for the backend test suite.

Tests are fully isolated from the development/demo database:
- ``DATABASE_URL`` is pointed at a throwaway in-memory database *before* any
  app module is imported, so the module-level engine never touches the dev
  SQLite file.
- Every test gets a fresh in-memory database through ``test_engine``.
- The API client's ``get_db`` dependency is overridden to use that database.
"""

import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
# Document uploads in tests go to a throwaway directory — never the dev storage.
os.environ.setdefault("DOCUMENT_STORAGE_PATH", tempfile.mkdtemp(prefix="geneverify-test-docs-"))

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401 — register ORM models with Base.metadata
from app.database.base import Base  # noqa: E402
from app.database.seed import seed_database  # noqa: E402
from app.database.session import enable_sqlite_foreign_keys, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services import security_service  # noqa: E402


def _make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


#: Known credential for the test user fixture (test-only, never used outside tests).
TEST_USER_PASSWORD = "TestPassw0rd!"


@pytest.fixture()
def test_engine() -> Generator[Engine, None, None]:
    """Fresh shared in-memory SQLite database with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Mirror production behaviour: FK enforcement (incl. ON DELETE CASCADE).
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Direct ORM session bound to the isolated test database."""
    session = _make_session_factory(test_engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded_session(db_session: Session) -> Session:
    """Test database pre-loaded with the deterministic demo dataset."""
    seed_database(db_session)
    return db_session


@pytest.fixture()
def client(test_engine: Engine) -> Generator[TestClient, None, None]:
    """Test client whose get_db dependency uses the isolated test database."""
    app = create_app()
    testing_session_factory = _make_session_factory(test_engine)

    def override_get_db() -> Generator[Session, None, None]:
        session = testing_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_client(client: TestClient, seeded_session: Session) -> TestClient:
    """API client backed by the seeded demo dataset."""
    return client


@pytest.fixture()
def test_user_password() -> str:
    """The known password of the test_user fixture."""
    return TEST_USER_PASSWORD


@pytest.fixture()
def test_user(db_session: Session, test_user_password: str) -> User:
    """An active officer account with a known password for auth tests."""
    user = User(
        username="operator",
        password_hash=security_service.hash_password(test_user_password),
        role=UserRole.OFFICER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def auth_headers(test_user: User) -> dict[str, str]:
    """Bearer-token headers for an authenticated request as test_user."""
    token = security_service.create_access_token(test_user)
    return {"Authorization": f"Bearer {token}"}
