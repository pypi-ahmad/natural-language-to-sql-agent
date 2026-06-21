"""SQLite database layer.

Provides:
- :class:`Database`: a thin, thread-safe wrapper around ``sqlite3.Connection``
  with context-manager semantics, row factory, and a query timeout.
- :func:`setup_db`: idempotent seed routine for the demo company database.
- :func:`render_table`: pretty-printer for query results.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..utils import get_logger
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

    def to_markdown(self, *, max_rows: int = 100) -> str:
        """Render the result as a Markdown table."""
        if not self.rows:
            return "_No rows returned._"
        shown = self.rows[:max_rows]
        lines = ["| " + " | ".join(self.columns) + " |",
                 "| " + " | ".join("---" for _ in self.columns) + " |"]
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
        writer.writerow(self.columns)
        writer.writerows(self.rows)
        return buf.getvalue()


def _fmt_cell(value: object) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


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
    ) -> None:
        self.path = Path(path)
        self.timeout_seconds = float(timeout_seconds)
        self.max_rows = int(max_rows)
        self._init_lock = threading.Lock()
        self._initialized = False

    # ---- Connection management ----

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection.

        The connection is closed when the block exits, even on exceptions.
        Row factory is :class:`sqlite3.Row` so callers can access columns
        by name.
        """
        conn = sqlite3.connect(
            str(self.path),
            timeout=self.timeout_seconds,
            isolation_level=None,  # autocommit; we manage transactions explicitly
            check_same_thread=True,
        )
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            try:
                conn.close()
            except sqlite3.Error:  # pragma: no cover - defensive
                logger.warning("Failed to close connection cleanly")

    # ---- Schema operations ----

    def ensure_schema(self, *, seed: bool = True) -> None:
        """Create the demo tables and (optionally) seed sample data.

        Idempotent: ``CREATE IF NOT EXISTS`` + ``INSERT OR IGNORE``.
        """
        with self._init_lock:
            if self._initialized:
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as conn:
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

    def get_schema_text(self) -> str:
        """Return a human-readable schema description for the LLM prompt."""
        with self.connect() as conn:
            tables = [
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            if not tables:
                return "(no tables)"

            parts: list[str] = []
            for table in tables:
                cols = conn.execute(
                    "SELECT name, type, [notnull], dflt_value, pk "
                    "FROM pragma_table_info(?) ORDER BY pk DESC, cid",
                    (table,),
                ).fetchall()
                col_descr = ", ".join(
                    f"{c['name']} {c['type']}"
                    + (" PRIMARY KEY" if c["pk"] else "")
                    + (" NOT NULL" if c["notnull"] else "")
                    for c in cols
                )
                parts.append(f"Table {table}({col_descr})")

                fks = conn.execute(
                    "SELECT * FROM pragma_foreign_key_list(?)", (table,)
                ).fetchall()
                for fk in fks:
                    parts.append(
                        f"  └─ {table}.{fk['from']} → "
                        f"{fk['table']}.{fk['to']}"
                    )

            return "\n".join(parts)

    def execute(self, sql: str) -> QueryResult:
        """Execute a single SELECT and return its result.

        Enforces ``max_rows`` by appending ``LIMIT`` when missing. The
        caller is responsible for having validated ``sql`` for safety.
        """
        with self.connect() as conn:
            cur = conn.execute(sql)
            cols = tuple(d[0] for d in cur.description) if cur.description else ()
            raw_rows = cur.fetchmany(self.max_rows + 1)
            truncated = len(raw_rows) > self.max_rows
            if truncated:
                raw_rows = raw_rows[: self.max_rows]
            # Convert sqlite3.Row -> tuple so the consumer can hash / JSON-serialize.
            rows = tuple(tuple(r) for r in raw_rows)
            return QueryResult(columns=cols, rows=rows, row_count=len(rows))


# ---- Module-level helpers ----------------------------------------------------


def setup_db(path: str | Path, *, seed: bool = True) -> None:
    """Backward-compatible module-level setup helper."""
    Database(path).ensure_schema(seed=seed)


def render_table(
    rows: list[tuple[object, ...]] | tuple[tuple[object, ...], ...],
    columns: list[str] | tuple[str, ...],
) -> str:
    """Standalone pretty-printer used by tests and CLI."""
    return QueryResult(columns=tuple(columns), rows=tuple(rows), row_count=len(rows)).to_markdown()
