"""Filesystem storage for uploaded documents (Step 6).

Design rules:
- Files live under ``DOCUMENT_STORAGE_PATH`` (gitignored, outside source
  trees, never mounted as static content).
- Stored filenames are generated server-side (uuid hex + extension); a
  user-provided filename is never used as a filesystem name.
- Every resolved path must stay inside the storage root — anything else is
  rejected, so even crafted metadata cannot escape the directory.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.core.config import get_settings


class DocumentStorageError(RuntimeError):
    """Raised when a storage operation would leave the storage root."""


def _storage_root() -> Path:
    root = Path(get_settings().document_storage_path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(stored_filename: str) -> Path:
    """Resolve ``stored_filename`` inside the root, refusing any escape."""
    root = _storage_root()
    candidate = (root / stored_filename).resolve()
    if candidate.parent != root or not candidate.name:
        raise DocumentStorageError("Refusing path outside the document storage root")
    return candidate


def generate_stored_filename(extension: str) -> str:
    """Server-generated filename: random, unique, no user input."""
    return f"{uuid.uuid4().hex}{extension.lower()}"


def sanitize_original_filename(raw: str | None) -> str:
    """Reduce a user-supplied filename to a safe display name.

    Only the basename survives (both path flavours), control characters and
    path separators are stripped, and length is bounded. Used for metadata
    display only — never as a filesystem name.
    """
    name = (raw or "").strip()
    name = PureWindowsPath(name).name if "\\" in name else PurePosixPath(name).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip(" .")
    if len(name) > 200:
        name = name[:200]
    return name or "uploaded-document"


def save(stored_filename: str, data: bytes) -> None:
    """Write file bytes inside the storage root."""
    _safe_path(stored_filename).write_bytes(data)


def resolve(stored_filename: str) -> Path:
    """Return the on-disk path for a stored file (still inside the root)."""
    path = _safe_path(stored_filename)
    if not path.is_file():
        raise DocumentStorageError("Stored document file is missing")
    return path


def delete(stored_filename: str) -> None:
    """Remove the stored file; a missing file is not an error."""
    try:
        _safe_path(stored_filename).unlink(missing_ok=True)
    except DocumentStorageError:
        # Crafted metadata cannot take deletions outside the root either.
        raise
