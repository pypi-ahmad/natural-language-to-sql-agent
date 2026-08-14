"""Tests for SQLite upload validation and storage."""

from __future__ import annotations

import sqlite3

import pytest

from nl2sql_agent.ui.database_upload import (
    SQLiteUploadError,
    save_sqlite_upload,
    validate_sqlite_upload,
    validate_upload_metadata,
)


def _sqlite_bytes(tmp_path):
    path = tmp_path / "source.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO items(name) VALUES ('one')")
    return path.read_bytes()


def test_valid_sqlite_upload(tmp_path):
    data = _sqlite_bytes(tmp_path)
    digest = validate_sqlite_upload("source.sqlite", data, max_mb=1)
    assert len(digest) == 64


def test_rejects_wrong_extension(tmp_path):
    with pytest.raises(SQLiteUploadError, match="extension"):
        validate_sqlite_upload("source.txt", _sqlite_bytes(tmp_path), max_mb=1)


def test_rejects_wrong_header():
    with pytest.raises(SQLiteUploadError, match="SQLite database"):
        validate_sqlite_upload("source.db", b"not sqlite", max_mb=1)


def test_rejects_oversized_upload():
    data = b"SQLite format 3\x00" + b"x" * 1024
    with pytest.raises(SQLiteUploadError, match="larger"):
        validate_sqlite_upload("source.db", data, max_mb=0.0001)


def test_rejects_oversized_upload_from_metadata():
    with pytest.raises(SQLiteUploadError, match="larger"):
        validate_upload_metadata("source.db", size=51 * 1024 * 1024, max_mb=50)


def test_save_uses_digest_not_uploaded_filename(tmp_path):
    data = _sqlite_bytes(tmp_path)
    digest = validate_sqlite_upload("../../secret.sqlite", data, max_mb=1)
    saved = save_sqlite_upload(tmp_path / "uploads", data, digest)
    assert saved.parent == tmp_path / "uploads"
    assert saved.name == f"{digest}.sqlite3"
    assert saved.read_bytes() == data
