"""Privacy-preserving append-only audit events."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import expressions as exp

_WRITE_LOCK = threading.Lock()
_ALLOWED_FIELDS = {
    "database",
    "duration_ms",
    "error_type",
    "model",
    "provider",
    "retries",
    "row_count",
    "truncated",
    "validation",
}


def hash_text(value: str) -> str:
    """Return a stable SHA-256 digest without retaining the source text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redact_sql(sql: str) -> str:
    """Remove literal values from parseable SQL, or retain only a digest."""
    try:
        statements = sqlglot.parse(sql, dialect="sqlite")
        if len(statements) != 1 or statements[0] is None:
            raise ValueError("not one statement")
        redacted = statements[0].transform(
            lambda node: exp.Placeholder() if isinstance(node, exp.Literal) else node
        )
        return redacted.sql(dialect="sqlite", comments=False)
    except (sqlglot.errors.ParseError, ValueError):
        return f"<unparseable:{hash_text(sql)}>"


class AuditLogger:
    """Write sanitized operational events to a local JSONL file."""

    def __init__(self, path: str | Path, *, enabled: bool = True) -> None:
        self.path = Path(path)
        self.enabled = enabled

    def write(self, *, event: str, run_id: str, **fields: Any) -> None:
        if not self.enabled:
            return
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "run_id": run_id,
        }
        question = fields.pop("question", None)
        if isinstance(question, str):
            payload["question_hash"] = hash_text(question)
            payload["question_length"] = len(question)
        sql = fields.pop("sql", None)
        if isinstance(sql, str):
            payload["sql"] = redact_sql(sql)
        unsupported = fields.keys() - _ALLOWED_FIELDS
        if unsupported:
            raise ValueError(f"unsupported audit fields: {', '.join(sorted(unsupported))}")
        payload.update(fields)

        with _WRITE_LOCK:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
