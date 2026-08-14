"""Local persistence for saved sessions, pricing, costs, and query insights."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import threading
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Any
from uuid import uuid4

from .llm.pricing import DEFAULT_PRICING_RULES, PricingRule

_SAFE_MESSAGE_FIELDS = frozenset(
    {
        "sql",
        "error",
        "trace",
        "run_id",
        "model",
        "provider",
        "token_usage",
        "usage_records",
        "cost_breakdown",
        "query_plan",
        "query_metrics",
        "warnings",
        "approved",
        "approved_at",
        "result_not_stored",
    }
)
_SAFE_PENDING_FIELDS = frozenset(
    {
        "run_id",
        "question",
        "sql_query",
        "sql_safe",
        "allowed_tables",
        "retry_count",
        "max_retries",
        "trace",
        "token_usage",
        "usage_records",
        "query_plan",
        "warnings",
        "provider",
        "model",
        "database_kind",
        "database_fingerprint",
    }
)


@dataclass(frozen=True, slots=True)
class SavedSession:
    """One persisted conversation summary."""

    session_id: str
    title: str
    created_at: str
    updated_at: str
    database_kind: str
    database_label: str
    database_fingerprint: str
    provider: str
    model: str


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, default=str)


def _safe_mapping(value: Mapping[str, Any], fields: frozenset[str]) -> dict[str, Any]:
    return {key: value[key] for key in fields if key in value}


def title_from_question(question: str) -> str:
    """Create a deterministic, compact session title without another LLM call."""
    compact = " ".join(question.split()).strip()
    if not compact:
        return "New session"
    return compact if len(compact) <= 80 else compact[:77].rstrip() + "..."


def _csv_cell(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def cost_rows_to_csv(rows: Iterable[Mapping[str, object]]) -> str:
    """Export privacy-safe cost rows and neutralize spreadsheet formulas."""
    columns = (
        "created_at",
        "session_id",
        "session_title",
        "run_id",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "request_mode",
        "estimated_cost_usd",
        "pricing_rule_id",
        "query_duration_ms",
        "total_duration_ms",
        "warnings",
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(_csv_cell(row.get(column, "")) for column in columns)
    return buffer.getvalue()


class StateStore:
    """Thread-safe local SQLite store with an explicit privacy allowlist."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self._migration_lock = threading.Lock()
        self._initialize()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 10000")
            yield conn
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._migration_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as conn:
                version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                if version > 1:
                    raise RuntimeError("State database was created by a newer app version")
                if version == 0:
                    conn.executescript(
                        """
                        BEGIN;
                        CREATE TABLE sessions (
                            id TEXT PRIMARY KEY,
                            title TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            database_kind TEXT NOT NULL,
                            database_label TEXT NOT NULL,
                            database_fingerprint TEXT NOT NULL,
                            provider TEXT NOT NULL,
                            model TEXT NOT NULL
                        );
                        CREATE TABLE messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                            position INTEGER NOT NULL,
                            role TEXT NOT NULL CHECK (role IN ('user','assistant')),
                            content TEXT NOT NULL,
                            payload_json TEXT NOT NULL DEFAULT '{}',
                            created_at TEXT NOT NULL,
                            UNIQUE(session_id, position)
                        );
                        CREATE TABLE pending_queries (
                            session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
                            payload_json TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );
                        CREATE TABLE pricing_rules (
                            rule_id TEXT PRIMARY KEY,
                            model TEXT NOT NULL,
                            display_name TEXT NOT NULL,
                            effective_from TEXT NOT NULL,
                            effective_to TEXT,
                            standard_input TEXT NOT NULL,
                            standard_output TEXT NOT NULL,
                            cache_read_input TEXT,
                            cache_creation_input TEXT,
                            batch_input TEXT,
                            batch_output TEXT,
                            fast_input TEXT,
                            fast_output TEXT,
                            long_context_threshold INTEGER,
                            long_context_input TEXT,
                            long_context_output TEXT,
                            notes TEXT NOT NULL DEFAULT ''
                        );
                        CREATE INDEX pricing_model_dates
                            ON pricing_rules(model, effective_from, effective_to);
                        CREATE TABLE runs (
                            run_id TEXT PRIMARY KEY,
                            session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                            created_at TEXT NOT NULL,
                            provider TEXT NOT NULL,
                            model TEXT NOT NULL,
                            database_kind TEXT NOT NULL,
                            database_fingerprint TEXT NOT NULL,
                            approved_sql TEXT NOT NULL DEFAULT '',
                            approved_at TEXT,
                            query_fingerprint TEXT NOT NULL DEFAULT '',
                            input_tokens INTEGER NOT NULL DEFAULT 0,
                            output_tokens INTEGER NOT NULL DEFAULT 0,
                            cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                            request_mode TEXT NOT NULL DEFAULT 'standard',
                            estimated_cost_usd TEXT,
                            pricing_rule_id TEXT,
                            pricing_snapshot_json TEXT NOT NULL DEFAULT '{}',
                            query_duration_ms REAL,
                            total_duration_ms REAL,
                            plan_json TEXT NOT NULL DEFAULT '{}',
                            metrics_json TEXT NOT NULL DEFAULT '{}',
                            warnings_json TEXT NOT NULL DEFAULT '[]',
                            status TEXT NOT NULL
                        );
                        CREATE INDEX runs_created_at ON runs(created_at);
                        CREATE INDEX runs_session ON runs(session_id, created_at);
                        CREATE INDEX runs_model ON runs(model, created_at);
                        CREATE INDEX runs_query_fingerprint
                            ON runs(query_fingerprint, created_at);
                        CREATE TABLE preferences (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL
                        );
                        PRAGMA user_version = 1;
                        COMMIT;
                        """
                    )
                self._seed_pricing(conn)

    @staticmethod
    def _seed_pricing(conn: sqlite3.Connection) -> None:
        for rule in DEFAULT_PRICING_RULES:
            conn.execute(
                """INSERT OR IGNORE INTO pricing_rules VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                StateStore._rule_values(rule),
            )

    @staticmethod
    def _rule_values(rule: PricingRule) -> tuple[object, ...]:
        def value(number: Decimal | None) -> str | None:
            return str(number) if number is not None else None

        return (
            rule.rule_id,
            rule.model,
            rule.display_name,
            rule.effective_from.astimezone(UTC).isoformat(),
            rule.effective_to.astimezone(UTC).isoformat() if rule.effective_to else None,
            str(rule.standard_input),
            str(rule.standard_output),
            value(rule.cache_read_input),
            value(rule.cache_creation_input),
            value(rule.batch_input),
            value(rule.batch_output),
            value(rule.fast_input),
            value(rule.fast_output),
            rule.long_context_threshold,
            value(rule.long_context_input),
            value(rule.long_context_output),
            rule.notes,
        )

    def create_session(
        self,
        *,
        database_kind: str,
        database_label: str,
        database_fingerprint: str,
        provider: str,
        model: str,
        title: str = "New session",
    ) -> str:
        session_id = str(uuid4())
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    title,
                    now,
                    now,
                    database_kind,
                    Path(database_label).name,
                    database_fingerprint,
                    provider,
                    model,
                ),
            )
        return session_id

    def list_sessions(self, *, limit: int = 200) -> list[SavedSession]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (max(limit, 1),)
            ).fetchall()
        return [SavedSession(row["id"], *tuple(row)[1:]) for row in rows]

    def get_session(self, session_id: str) -> SavedSession | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return SavedSession(row["id"], *tuple(row)[1:]) if row else None

    def rename_session(self, session_id: str, title: str) -> None:
        normalized = " ".join(title.split()).strip()
        if not normalized:
            raise ValueError("Session title must not be empty")
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (normalized[:120], _utc_now(), session_id),
            )

    def delete_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("Unsupported message role")
        safe_payload = _safe_mapping(payload or {}, _SAFE_MESSAGE_FIELDS)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            position = int(
                conn.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 FROM messages WHERE session_id = ?",
                    (session_id,),
                ).fetchone()[0]
            )
            conn.execute(
                "INSERT INTO messages(session_id, position, role, content, payload_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, position, role, content, _json(safe_payload), _utc_now()),
            )
            if position == 0 and role == "user":
                conn.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                    (title_from_question(content), _utc_now(), session_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?", (_utc_now(), session_id)
                )
            conn.execute("COMMIT")

    def load_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, payload_json FROM messages "
                "WHERE session_id = ? ORDER BY position",
                (session_id,),
            ).fetchall()
        messages = []
        for row in rows:
            message = {"role": row["role"], "content": row["content"]}
            message.update(json.loads(row["payload_json"]))
            messages.append(message)
        return messages

    def save_pending(self, session_id: str, state: Mapping[str, Any]) -> None:
        safe = _safe_mapping(state, _SAFE_PENDING_FIELDS)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO pending_queries VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET payload_json=excluded.payload_json, "
                "updated_at=excluded.updated_at",
                (session_id, _json(safe), _utc_now()),
            )

    def load_pending(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM pending_queries WHERE session_id = ?", (session_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def clear_pending(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM pending_queries WHERE session_id = ?", (session_id,))

    def save_run(
        self,
        session_id: str,
        state: Mapping[str, Any],
        *,
        provider: str,
        model: str,
        database_kind: str,
        database_fingerprint: str,
        approved: bool,
    ) -> None:
        usage = dict(state.get("token_usage", {}))
        usage_records = list(state.get("usage_records", []))
        cache_read = sum(max(int(item.get("cache_read_tokens", 0)), 0) for item in usage_records)
        modes = {str(item.get("request_mode", "standard")) for item in usage_records}
        request_mode = modes.pop() if len(modes) == 1 else "mixed"
        cost = state.get("cost_breakdown") or {}
        metrics = state.get("query_metrics") or {}
        plan = state.get("query_plan") or {}
        trace = list(state.get("trace", []))
        total_duration = sum(
            float(item.get("duration_ms", 0))
            for item in trace
            if isinstance(item.get("duration_ms", 0), (int, float))
        )
        warnings = list(state.get("warnings", []))
        sql = str(state.get("sql_query", "")) if approved else ""
        fingerprint = hashlib.sha256(" ".join(sql.split()).encode()).hexdigest() if sql else ""
        run_id = str(state.get("run_id") or uuid4())
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO runs VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    session_id,
                    _utc_now(),
                    provider,
                    model,
                    database_kind,
                    database_fingerprint,
                    sql,
                    _utc_now() if approved else None,
                    fingerprint,
                    max(int(usage.get("input_tokens", 0)), 0),
                    max(int(usage.get("output_tokens", 0)), 0),
                    cache_read,
                    request_mode,
                    str(cost.get("total_cost")) if cost.get("total_cost") is not None else None,
                    cost.get("pricing_rule_id"),
                    _json(cost),
                    metrics.get("duration_ms"),
                    round(total_duration, 3),
                    _json(plan),
                    _json(metrics),
                    _json(warnings),
                    "blocked" if state.get("error") else "completed",
                ),
            )

    def list_pricing_rules(self) -> list[PricingRule]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pricing_rules ORDER BY model, effective_from"
            ).fetchall()
        return [self._row_to_rule(row) for row in rows]

    @staticmethod
    def _row_to_rule(row: sqlite3.Row) -> PricingRule:
        def decimal(name: str) -> Decimal | None:
            value = row[name]
            return Decimal(value) if value is not None else None

        return PricingRule(
            rule_id=row["rule_id"],
            model=row["model"],
            display_name=row["display_name"],
            effective_from=datetime.fromisoformat(row["effective_from"]).astimezone(UTC),
            effective_to=(
                datetime.fromisoformat(row["effective_to"]).astimezone(UTC)
                if row["effective_to"]
                else None
            ),
            standard_input=Decimal(row["standard_input"]),
            standard_output=Decimal(row["standard_output"]),
            cache_read_input=decimal("cache_read_input"),
            cache_creation_input=decimal("cache_creation_input"),
            batch_input=decimal("batch_input"),
            batch_output=decimal("batch_output"),
            fast_input=decimal("fast_input"),
            fast_output=decimal("fast_output"),
            long_context_threshold=row["long_context_threshold"],
            long_context_input=decimal("long_context_input"),
            long_context_output=decimal("long_context_output"),
            notes=row["notes"],
        )

    def replace_pricing_rules(self, rules: list[PricingRule]) -> None:
        self._validate_rules(rules)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM pricing_rules")
            conn.executemany(
                "INSERT INTO pricing_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [self._rule_values(rule) for rule in rules],
            )
            conn.execute("COMMIT")

    @staticmethod
    def _validate_rules(rules: list[PricingRule]) -> None:
        seen_ids: set[str] = set()
        by_model: dict[str, list[PricingRule]] = {}
        for rule in rules:
            if not rule.rule_id.strip() or rule.rule_id in seen_ids:
                raise ValueError("Pricing rule IDs must be non-empty and unique")
            seen_ids.add(rule.rule_id)
            if not rule.model.strip() or not rule.display_name.strip():
                raise ValueError("Pricing model and display name are required")
            if rule.effective_to is not None and rule.effective_to <= rule.effective_from:
                raise ValueError("Pricing end must be after its start")
            numeric = [
                rule.standard_input,
                rule.standard_output,
                rule.cache_read_input,
                rule.cache_creation_input,
                rule.batch_input,
                rule.batch_output,
                rule.fast_input,
                rule.fast_output,
                rule.long_context_input,
                rule.long_context_output,
            ]
            if any(value is not None and value < 0 for value in numeric):
                raise ValueError("Pricing values cannot be negative")
            by_model.setdefault(rule.model, []).append(rule)
        for model, model_rules in by_model.items():
            ordered = sorted(model_rules, key=lambda item: item.effective_from)
            for previous, current in pairwise(ordered):
                if previous.effective_to is None or current.effective_from < previous.effective_to:
                    raise ValueError(f"Pricing windows overlap for {model}")

    def get_preference_decimal(self, key: str) -> Decimal:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
        return Decimal(row[0]) if row else Decimal(0)

    def set_preference_decimal(self, key: str, value: Decimal) -> None:
        if value < 0:
            raise ValueError("Preference cannot be negative")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO preferences VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(value)),
            )

    def cost_rows(
        self,
        *,
        start_at: str | None = None,
        end_at: str | None = None,
        session_id: str | None = None,
        model: str | None = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[object] = []
        for value, clause in (
            (start_at, "r.created_at >= ?"),
            (end_at, "r.created_at < ?"),
            (session_id, "r.session_id = ?"),
            (model, "r.model = ?"),
        ):
            if value:
                clauses.append(clause)
                params.append(value)
        params.append(max(1, min(limit, 20_000)))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT r.*, s.title AS session_title FROM runs r "  # noqa: S608
                "JOIN sessions s ON s.id = r.session_id WHERE "
                + " AND ".join(clauses)
                + " ORDER BY r.created_at DESC LIMIT ?",
                params,
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["warnings"] = "; ".join(json.loads(item.pop("warnings_json")))
            result.append(item)
        return result

    def cost_total(self, *, start_at: str | None = None, session_id: str | None = None) -> Decimal:
        """Return an indexed aggregate without loading individual run records."""
        clauses = ["estimated_cost_usd IS NOT NULL"]
        params: list[object] = []
        if start_at:
            clauses.append("created_at >= ?")
            params.append(start_at)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        with self._connect() as conn:
            value = conn.execute(
                "SELECT COALESCE(SUM(CAST(estimated_cost_usd AS REAL)), 0) FROM runs WHERE "  # noqa: S608
                + " AND ".join(clauses),
                params,
            ).fetchone()[0]
        return Decimal(str(value))

    def runtime_rows(self, *, limit: int = 5000) -> list[dict[str, Any]]:
        rows = self.cost_rows(limit=limit)
        for row in rows:
            row["plan"] = json.loads(row.pop("plan_json"))
            row["metrics"] = json.loads(row.pop("metrics_json"))
        return rows
