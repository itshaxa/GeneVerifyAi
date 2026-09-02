"""Deployment startup for the GeneVerify API (Step 11).

The canonical command is still the plain ASGI one, and it works anywhere a shell
command can be configured::

    uvicorn app.main:app --host 0.0.0.0 --port 8000

This wrapper exists for the cases where a single ``python run.py`` is easier:
platforms that inject a ``PORT`` environment variable (Alibaba Cloud App Service,
Render, Fly.io, Cloud Run, ...), and local runs where you do not want to remember
the flags. Nothing about the application changes - it serves the same
``app.main:app`` object that ``uvicorn`` and the tests use.

    Development :  python run.py
    Production  :  APP_ENV=production DEBUG=false JWT_SECRET_KEY=... python run.py

Environment variables understood here (none of them are read anywhere else):

* ``PORT`` - TCP port to bind (defaults to 8000). Set automatically by most PaaS.
* ``HOST`` - interface to bind. Defaults to ``0.0.0.0`` in production (required
  inside a container) and ``127.0.0.1`` otherwise (so a dev run is not exposed).

Run this file from ``backend/`` - that is where the ``app`` package lives.
"""

from __future__ import annotations

import os

import uvicorn

from app.core.config import get_settings


def _port(default: int = 8000) -> int:
    """Resolve the bind port, honouring the platform-injected ``PORT``."""
    raw = (os.environ.get("PORT") or "").strip()
    if not raw:
        return default
    try:
        port = int(raw)
    except ValueError:
        raise RuntimeError(f"PORT must be a number, got {raw!r}") from None
    if not 1 <= port <= 65535:
        raise RuntimeError("PORT must be between 1 and 65535")
    return port


def main() -> None:
    """Start the ASGI server with environment-driven host/port."""
    settings = get_settings()
    host = (os.environ.get("HOST") or "").strip() or (
        "0.0.0.0" if settings.app_env == "production" else "127.0.0.1"
    )
    # The import string (not the object) keeps this identical to
    # `uvicorn app.main:app`, so production and dev serve the same app.
    uvicorn.run("app.main:app", host=host, port=_port(), log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
