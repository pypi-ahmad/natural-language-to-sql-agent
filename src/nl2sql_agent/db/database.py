"""SQLite database layer.

Provides:
- :class:`Database`: a thin, thread-safe wrapper around ``sqlite3.Connection``
  with context-manager semantics, row factory, and a query timeout.
- :func:`setup_db`: idempotent seed routine for the demo company database.
- :func:`render_table`: pretty-printer for query results.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ..utils import get_logger
from .base import QueryMetrics, QueryPlan, QueryPlanNode
from .seed import SEED_DEPARTMENTS, SEED_EMPLOYEES

logger = get_logger(__name__)

DDL_DEPARTMENTS = (
    "CREATE TABLE IF NOT EXISTS departments ("
    "dept_id INTEGER PRIMARY KEY,"
    "dept_name TEXT NOT NULL UNIQUE,"
    "location TEXT"
    ")"
)
DDL_EMPLOYEES = (
    "CREATE TABLE IF NOT EXISTS employees ("
    "emp_id INTEGER PRIMARY KEY,"
    "name TEXT NOT NULL,"
    "salary REAL NOT NULL CHECK (salary >= 0),"
    "dept_id INTEGER NOT NULL,"
    "FOREIGN KEY (dept_id) REFERENCES departments(dept_id)"
    ")"
)


@dataclass(frozen=True, slots=True)
class QueryResult:
    """A successful SQL execution result."""

    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    row_count: int
    truncated: bool = False
    metrics: QueryMetrics = field(default_factory=QueryMetrics)

    def to_markdown(self, *, max_rows: int = 100) -> str:
        """Render the result as a Markdown table."""
        if not self.rows:
            return "_No rows returned._"
        shown = self.rows[:max_rows]
        lines = [
            "| " + " | ".join(self.columns) + " |",
            "| " + " | ".join("---" for _ in self.columns) + " |",
        ]
        for row in shown:
            lines.append("| " + " | ".join(_fmt_cell(c) for c in row) + " |")
        if self.row_count > len(shown):
            lines.append(f"_… {self.row_count - len(shown)} more rows truncated._")
        return "\n".join(lines)

    def to_csv(self) -> str:
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_csv_cell(value) for value in self.columns)
        writer.writerows(tuple(_csv_cell(value) for value in row) for row in self.rows)
        return buf.getvalue()


def _fmt_cell(value: object) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _csv_cell(value: object) -> object:
    """Neutralize string cells that spreadsheet programs may execute."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


class Database:
    """A small wrapper around :mod:`sqlite3` for the agent's database.

    The class is **stateless across threads** by design. Each call creates a
    short-lived connection via :meth:`connect` (a context manager), so we
    don't share connections across threads (sqlite3 connections are
    thread-local by default).
    """

    def __init__(
        self,
        path: str | Path,
        *,
        timeout_seconds: float = 15.0,
        max_rows: int = 1000,
        max_vm_steps: int = 5_000_000,
    ) -> None:
        self.path = Path(path)
        self.timeout_seconds = float(timeout_seconds)
        self.max_rows = int(max_rows)
        self.max_vm_steps = int(max_vm_steps)
        self._init_lock = threading.Lock()
        self._initialized = False

    kind = "sqlite"
    dialect = "sqlite"

    @property
    def display_name(self) -> str:
        """Return a non-sensitive database label."""
        return self.path.name

    @property
    def fingerprint(self) -> str:
        """Return a stable identity without reading database contents."""
        import hashlib

        return hashlib.sha256(str(self.path.resolve()).encode()).hexdigest()

    # ---- Connection management ----

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a hardened read-only query connection.

        The connection is closed when the block exits, even on exceptions.
        Row factory is :class:`sqlite3.Row` so callers can access columns
        by name.
        """
        if not self.path.exists():
            raise sqlite3.OperationalError(f"Database does not exist: {self.path.name}")
        uri = self.path.resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=self.timeout_seconds,
            isolation_level=None,
            check_same_thread=True,
        )
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA query_only = ON")
            conn.execute("PRAGMA trusted_schema = OFF")
            conn.enable_load_extension(False)
            yield conn
        finally:
            try:
                conn.close()
            except sqlite3.Error:  # pragma: no cover - defensive
                logger.warning("Failed to close connection cleanly")

    @contextmanager
    def _writable_connection(self) -> Iterator[sqlite3.Connection]:
        """Yield the narrowly scoped connection used only for demo setup."""
        conn = sqlite3.connect(
            str(self.path),
            timeout=self.timeout_seconds,
            isolation_level=None,
            check_same_thread=True,
        )
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.enable_load_extension(False)
            yield conn
        finally:
            conn.close()

    # ---- Schema operations ----

    def ensure_schema(self, *, seed: bool = True) -> None:
        """Create the demo tables and (optionally) seed sample data.

        Idempotent: ``CREATE IF NOT EXISTS`` + ``INSERT OR IGNORE``.
        """
        with self._init_lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._writable_connection() as conn:
                conn.executescript(f"{DDL_DEPARTMENTS};\n{DDL_EMPLOYEES};")
                if seed:
                    conn.executemany(
                        "INSERT OR IGNORE INTO departments VALUES (?, ?, ?)",
                        SEED_DEPARTMENTS,
                    )
                    conn.executemany(
                        "INSERT OR IGNORE INTO employees VALUES (?, ?, ?, ?)",
                        SEED_EMPLOYEES,
                    )
            self._initialized = True
            logger.info("Database ready at {path}", path=str(self.path))

    def reset(self) -> None:
        """Drop the database file (use only in tests or interactive reset)."""
        with self._init_lock:
            if self.path.exists():
                self.path.unlink()
            self._initialized = False
            logger.warning("Database reset at {path}", path=str(self.path))

    # ---- Querying ----

    def list_tables(self) -> tuple[str, ...]:
        """Return ordinary user tables in deterministic order."""
        with self.connect() as conn:
            return _list_tables(conn)

    def get_schema_text(
        self,
        *,
        allowed_tables: set[str] | frozenset[str] | None = None,
        question: str = "",
        max_tables: int | None = None,
        include_sample_values: bool = False,
    ) -> str:
        """Return ranked schema context for the LLM prompt."""
        with self.connect() as conn:
            all_tables = _list_tables(conn)
            allowed = (
                {name.casefold() for name in allowed_tables} if allowed_tables is not None else None
            )
            tables = [name for name in all_tables if allowed is None or name.casefold() in allowed]
            if not tables:
                return "(no tables)"

            metadata: dict[str, list[sqlite3.Row]] = {}
            for table in tables:
                metadata[table] = conn.execute(
                    "SELECT name, type, [notnull], dflt_value, pk "
                    "FROM pragma_table_info(?) ORDER BY pk DESC, cid",
                    (table,),
                ).fetchall()

            selected = self._rank_tables(tables, metadata, question=question, max_tables=max_tables)
            parts: list[str] = []
            if selected != tables:
                parts.append("Available tables: " + ", ".join(tables))
            for table in selected:
                cols = metadata[table]
                col_descr = ", ".join(
                    f"{c['name']} {c['type']}"
                    + (" PRIMARY KEY" if c["pk"] else "")
                    + (" NOT NULL" if c["notnull"] else "")
                    for c in cols
                )
                parts.append(f"Table {table}({col_descr})")

                fks = conn.execute("SELECT * FROM pragma_foreign_key_list(?)", (table,)).fetchall()
                for fk in fks:
                    parts.append(f"  └─ {table}.{fk['from']} → {fk['table']}.{fk['to']}")
                if include_sample_values:
                    quoted = _quote_identifier(table)
                    rows = conn.execute(
                        f"SELECT * FROM {quoted} LIMIT 3"  # noqa: S608 - strictly quoted
                    ).fetchall()
                    if rows:
                        samples = [tuple(_sample_cell(value) for value in row) for row in rows]
                        parts.append(f"  Sample rows: {samples}")

            return "\n".join(parts)

    @staticmethod
    def _rank_tables(
        tables: list[str],
        metadata: dict[str, list[sqlite3.Row]],
        *,
        question: str,
        max_tables: int | None,
    ) -> list[str]:
        if max_tables is None or len(tables) <= max_tables:
            return tables
        tokens = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", question)}

        def score(table: str) -> int:
            names = [table, *(str(col["name"]) for col in metadata[table])]
            value = 0
            for index, name in enumerate(names):
                normalized = name.casefold()
                pieces = set(re.findall(r"[A-Za-z0-9]+", normalized.replace("_", " ")))
                matches = tokens & pieces
                value += len(matches) * (5 if index == 0 else 2)
                if any(token in normalized or normalized in token for token in tokens):
                    value += 1
            return value

        ranked = sorted(tables, key=lambda name: (-score(name), name.casefold()))
        selected = ranked[:max_tables]
        return sorted(dict.fromkeys(selected))[:max_tables]

    def execute(self, sql: str) -> QueryResult:
        """Execute a single SELECT and return its result.

        Enforces ``max_rows`` by appending ``LIMIT`` when missing. The
        caller is responsible for having validated ``sql`` for safety.
        """
        started = time.perf_counter()
        with self.connect() as conn:
            step_count = self._install_progress_guard(conn)
            cur = conn.execute(sql)
            cols = tuple(d[0] for d in cur.description) if cur.description else ()
            raw_rows = cur.fetchmany(self.max_rows + 1)
            truncated = len(raw_rows) > self.max_rows
            if truncated:
                raw_rows = raw_rows[: self.max_rows]
            # Convert sqlite3.Row -> tuple so the consumer can hash / JSON-serialize.
            rows = tuple(tuple(r) for r in raw_rows)
            return QueryResult(
                columns=cols,
                rows=rows,
                row_count=len(rows),
                truncated=truncated,
                metrics=QueryMetrics(
                    duration_ms=round((time.perf_counter() - started) * 1000, 3),
                    work_units=step_count(),
                    row_count=len(rows),
                    truncated=truncated,
                ),
            )

    def preflight(self, sql: str) -> QueryPlan:
        """Compile and normalize a query plan without executing the SELECT."""
        with self.connect() as conn:
            self._install_progress_guard(conn)
            rows = conn.execute("EXPLAIN QUERY PLAN " + sql).fetchall()
        nodes: list[QueryPlanNode] = []
        scans: list[str] = []
        for row in rows:
            detail = str(row[3])
            operation = detail.split(maxsplit=1)[0] if detail else "PLAN"
            relation = ""
            match = re.search(r"\b(?:SCAN|SEARCH)\s+([\w.]+)", detail, re.IGNORECASE)
            if match:
                relation = match.group(1)
            if operation.upper() == "SCAN" and "USING INDEX" not in detail.upper() and relation:
                scans.append(relation)
            nodes.append(QueryPlanNode(operation=operation, relation=relation, detail=detail))
        warnings = tuple(f"Full table scan: {name}" for name in dict.fromkeys(scans))
        return QueryPlan(
            backend=self.kind,
            nodes=tuple(nodes),
            full_scan_relations=tuple(dict.fromkeys(scans)),
            warnings=warnings,
        )

    def _install_progress_guard(self, conn: sqlite3.Connection):
        deadline = time.monotonic() + self.timeout_seconds
        steps = 0
        interval = 1000

        def progress() -> int:
            nonlocal steps
            steps += interval
            return int(steps > self.max_vm_steps or time.monotonic() > deadline)

        conn.set_progress_handler(progress, interval)
        return lambda: steps


# ---- Module-level helpers ----------------------------------------------------


def _list_tables(conn: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    )


def setup_db(path: str | Path, *, seed: bool = True) -> None:
    """Backward-compatible module-level setup helper."""
    Database(path).ensure_schema(seed=seed)


def render_table(
    rows: list[tuple[object, ...]] | tuple[tuple[object, ...], ...],
    columns: list[str] | tuple[str, ...],
) -> str:
    """Standalone pretty-printer used by tests and CLI."""
    return QueryResult(columns=tuple(columns), rows=tuple(rows), row_count=len(rows)).to_markdown()


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sample_cell(value: object) -> object:
    if isinstance(value, bytes):
        return "<blob>"
    if isinstance(value, str) and len(value) > 64:
        return value[:61] + "..."
    return value
