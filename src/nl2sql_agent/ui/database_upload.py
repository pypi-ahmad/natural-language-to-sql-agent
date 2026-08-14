"""Validation and session-local storage for untrusted SQLite uploads."""

from __future__ import annotations

import hashlib
from pathlib import Path

SQLITE_HEADER = b"SQLite format 3\x00"
ALLOWED_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}


class SQLiteUploadError(ValueError):
    """Raised when an uploaded file cannot be accepted as SQLite."""


def validate_upload_metadata(name: str, *, size: int, max_mb: float) -> None:
    """Reject unsupported or oversized uploads before reading their contents."""
    if Path(name).suffix.casefold() not in ALLOWED_EXTENSIONS:
        raise SQLiteUploadError("Use a .db, .sqlite, or .sqlite3 extension.")
    if size > max_mb * 1024 * 1024:
        raise SQLiteUploadError(f"The upload is larger than the {max_mb:g} MB limit.")


def validate_sqlite_upload(name: str, data: bytes, *, max_mb: float) -> str:
    """Validate filename, size, and SQLite magic header; return SHA-256."""
    validate_upload_metadata(name, size=len(data), max_mb=max_mb)
    if not data.startswith(SQLITE_HEADER):
        raise SQLiteUploadError("The file is not a SQLite database.")
    return hashlib.sha256(data).hexdigest()


def save_sqlite_upload(directory: Path, data: bytes, digest: str) -> Path:
    """Store validated bytes under a content-derived session-local name."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.sqlite3"
    if not path.exists():
        path.write_bytes(data)
    return path
