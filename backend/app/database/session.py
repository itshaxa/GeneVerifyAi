"""Engine and session management.

The engine is built from ``DATABASE_URL`` so the same code runs against
SQLite locally and against a managed PostgreSQL/RDS instance on Alibaba
Cloud later, without code changes.
"""

from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def ensure_sqlite_database_directory(database_url: str) -> Path | None:
    """Create the parent directory of a file-based SQLite database.

    Deployment step (Step 11): a container or PaaS volume often mounts an empty
    directory such as ``/data``, and SQLite refuses to create
    ``/data/geneverify.db`` when ``/data`` does not exist yet. This only ever
    mkdirs a missing directory - it never touches an existing database file.

    Returns the directory (for logging) or ``None`` for in-memory URLs.
    """
    url = make_url(database_url)
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        return None
    directory = Path(url.database).expanduser().resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Enforce foreign keys on every SQLite connection.

    SQLite enforces foreign keys only when this pragma is enabled per
    connection; without it, ON DELETE CASCADE rules (e.g. documents ->
    extractions) silently never fire.
    """

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def build_engine() -> Engine:
    """Create the SQLAlchemy engine for the configured database URL."""
    settings = get_settings()
    connect_args: dict[str, Any] = {}
    is_sqlite = settings.database_url.startswith("sqlite")
    if is_sqlite:
        # Make sure a file-based SQLite database has somewhere to live.
        ensure_sqlite_database_directory(settings.database_url)
        # Required for SQLite with FastAPI's threaded request handling.
        connect_args["check_same_thread"] = False
    engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
    if is_sqlite:
        enable_sqlite_foreign_keys(engine)
    return engine


engine: Engine = build_engine()

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
