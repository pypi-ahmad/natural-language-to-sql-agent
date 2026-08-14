"""Tests for privacy-preserving audit events."""

from __future__ import annotations

import json

import pytest

from nl2sql_agent.utils import AuditLogger, hash_text, redact_sql


def test_hash_text_does_not_expose_input():
    digest = hash_text("Alice earns 120000")
    assert "Alice" not in digest
    assert len(digest) == 64


def test_redact_sql_removes_literals():
    redacted = redact_sql("SELECT * FROM employees WHERE name='Alice' AND salary>120000")
    assert "Alice" not in redacted
    assert "120000" not in redacted
    assert "employees" in redacted


def test_invalid_sql_is_not_logged_raw():
    redacted = redact_sql("Alice secret not valid SQL")
    assert redacted.startswith("<unparseable:")
    assert "Alice" not in redacted


def test_audit_logger_writes_jsonl_without_raw_question(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLogger(path, enabled=True)
    audit.write(
        event="executed",
        run_id="run-1",
        question="What does Alice earn?",
        sql="SELECT salary FROM employees WHERE name='Alice'",
        row_count=1,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["event"] == "executed"
    assert payload["question_length"] == len("What does Alice earn?")
    assert "question" not in payload
    assert "Alice" not in path.read_text(encoding="utf-8")


def test_disabled_audit_does_not_create_file(tmp_path):
    path = tmp_path / "audit.jsonl"
    AuditLogger(path, enabled=False).write(event="prepared", run_id="run-1")
    assert not path.exists()


def test_audit_logger_rejects_unapproved_fields(tmp_path):
    audit = AuditLogger(tmp_path / "audit.jsonl")
    with pytest.raises(ValueError, match="unsupported audit fields"):
        audit.write(event="failed", run_id="run-1", exception="secret detail")
