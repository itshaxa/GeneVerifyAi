"""Non-destructive database initialization.

``create_all`` only creates tables that do not exist yet; it never drops or
truncates existing data. The seed script (``python -m app.database.seed``) is
the explicit developer command for populating demo data.
"""

import logging

from sqlalchemy import Engine

from app.database.base import Base
from app.database.session import engine

logger = logging.getLogger(__name__)


def init_db(bind: Engine | None = None) -> None:
    """Ensure all registered tables exist (no data is deleted)."""
    import app.models  # noqa: F401 — import registers models with Base.metadata

    Base.metadata.create_all(bind=bind or engine)
    logger.info("Database schema ensured (non-destructive create_all).")
