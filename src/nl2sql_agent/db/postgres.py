"""Strictly read-only PostgreSQL backend."""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, LiteralString, cast

import psycopg
from psycopg import sql as psycopg_sql
from psycopg.rows import dict_row

from .base import DatabaseError, QueryMetrics, QueryPlan, QueryPlanNode
from .database import QueryResult, _sample_cell


class PostgresDatabase:
    """PostgreSQL access constrained by role checks and read-only transactions."""

    kind = "postgres"
    dialect = "postgres"
    display_name = "PostgreSQL"

    def __init__(
        self,
        dsn: str,
        *,
        schema: str = "public",
        timeout_seconds: float = 15.0,
        lock_timeout_seconds: float = 5.0,
        max_rows: int = 1000,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", schema):
            raise ValueError("PostgreSQL schema must be an unquoted identifier")
        self._dsn = dsn
        self.schema = schema
        self.timeout_seconds = float(timeout_seconds)
        self.lock_timeout_seconds = float(lock_timeout_seconds)
        self.max_rows = int(max_rows)

    @property
    def fingerprint(self) -> str:
        """Return a stable opaque connection identity without exposing the DSN."""
        return hashlib.sha256(f"{self._dsn}\0{self.schema}".encode()).hexdigest()

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection[dict[str, Any]]]:
        """Yield a verified read-only transaction and always roll it back."""
        conn: psycopg.Connection[dict[str, Any]] | None = None
        try:
            conn = cast(
                "psycopg.Connection[dict[str, Any]]",
                psycopg.connect(
                    self._dsn,
                    autocommit=False,
                    connect_timeout=max(1, int(self.timeout_seconds)),
                    row_factory=cast(Any, dict_row),
                ),
            )
            conn.read_only = True
            read_only = conn.execute("SHOW transaction_read_only").fetchone()
            if not read_only or str(read_only["transaction_read_only"]).casefold() != "on":
                raise DatabaseError("PostgreSQL did not enable a read-only transaction")
            role = conn.execute(
                "SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
            if role is None or any(bool(role[field]) for field in role):
                raise DatabaseError("PostgreSQL requires a non-privileged read-only role")
            conn.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (f"{max(1, int(self.timeout_seconds * 1000))}ms",),
            )
            conn.execute(
                "SELECT set_config('lock_timeout', %s, true)",
                (f"{max(1, int(self.lock_timeout_seconds * 1000))}ms",),
            )
            conn.execute(
                "SELECT set_config('search_path', %s, true)",
                (f"{self.schema},pg_catalog",),
            )
            yield conn
        except psycopg.Error as exc:
            raise DatabaseError("PostgreSQL operation failed") from exc
        finally:
            if conn is not None:
                try:
                    conn.rollback()
                finally:
                    conn.close()

    def list_tables(self) -> tuple[str, ...]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
                "ORDER BY table_name",
                (self.schema,),
            ).fetchall()
        return tuple(str(row["table_name"]) for row in rows)

    def get_schema_text(
        self,
        *,
        allowed_tables: set[str] | frozenset[str] | None = None,
        question: str = "",
        max_tables: int | None = None,
        include_sample_values: bool = False,
    ) -> str:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns WHERE table_schema = %s "
                "ORDER BY table_name, ordinal_position",
                (self.schema,),
            ).fetchall()
            metadata: dict[str, list[dict[str, object]]] = {}
            allowed = {name.casefold() for name in allowed_tables} if allowed_tables else None
            for row in rows:
                table = str(row["table_name"])
                if allowed is None or table.casefold() in allowed:
                    metadata.setdefault(table, []).append(row)
            tables = self._rank_tables(list(metadata), metadata, question, max_tables)
            if not tables:
                return "(no tables)"
            parts: list[str] = []
            for table in tables:
                columns = ", ".join(
                    f"{row['column_name']} {row['data_type']}"
                    + (" NOT NULL" if row["is_nullable"] == "NO" else "")
                    for row in metadata[table]
                )
                parts.append(f"Table {table}({columns})")
                if include_sample_values:
                    query = psycopg_sql.SQL("SELECT * FROM {}.{} LIMIT 3").format(
                        psycopg_sql.Identifier(self.schema), psycopg_sql.Identifier(table)
                    )
                    samples = conn.execute(query).fetchall()
                    if samples:
                        parts.append(
                            "  Sample rows: "
                            + str(
                                [
                                    tuple(_sample_cell(value) for value in row.values())
                                    for row in samples
                                ]
                            )
                        )
        return "\n".join(parts)

    @staticmethod
    def _rank_tables(
        tables: list[str],
        metadata: dict[str, list[dict[str, object]]],
        question: str,
        max_tables: int | None,
    ) -> list[str]:
        if max_tables is None or len(tables) <= max_tables:
            return sorted(tables)
        tokens = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+", question)}

        def score(table: str) -> int:
            names = [table, *(str(row["column_name"]) for row in metadata[table])]
            return sum(
                5 if index == 0 else 2
                for index, name in enumerate(names)
                if tokens & set(re.findall(r"[A-Za-z0-9]+", name.casefold().replace("_", " ")))
            )

        return sorted(tables, key=lambda name: (-score(name), name.casefold()))[:max_tables]

    def execute(self, sql: str) -> QueryResult:
        started = time.perf_counter()
        with self.connect() as conn:
            cursor = conn.execute(psycopg_sql.SQL(cast(LiteralString, sql)))
            columns = tuple(column.name for column in cursor.description or ())
            raw_rows = cursor.fetchmany(self.max_rows + 1)
        truncated = len(raw_rows) > self.max_rows
        if truncated:
            raw_rows = raw_rows[: self.max_rows]
        rows = tuple(tuple(row[column] for column in columns) for row in raw_rows)
        duration = round((time.perf_counter() - started) * 1000, 3)
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            metrics=QueryMetrics(
                duration_ms=duration,
                row_count=len(rows),
                truncated=truncated,
            ),
        )

    def preflight(self, sql: str) -> QueryPlan:
        with self.connect() as conn:
            explain = psycopg_sql.SQL("EXPLAIN (FORMAT JSON, COSTS TRUE) ") + psycopg_sql.SQL(
                cast(LiteralString, sql)
            )
            row = conn.execute(explain).fetchone()
        if not row:
            raise DatabaseError("PostgreSQL returned no query plan")
        raw = next(iter(row.values()))
        root = raw[0]["Plan"] if isinstance(raw, list) else raw["Plan"]
        nodes: list[QueryPlanNode] = []
        scans: list[str] = []

        def visit(node: dict[str, Any]) -> None:
            operation = str(node.get("Node Type", "Plan"))
            relation = str(node.get("Relation Name", ""))
            estimated_rows = int(node["Plan Rows"]) if node.get("Plan Rows") is not None else None
            total_cost = float(node["Total Cost"]) if node.get("Total Cost") is not None else None
            if operation == "Seq Scan" and relation:
                scans.append(relation)
            nodes.append(
                QueryPlanNode(
                    operation=operation,
                    relation=relation,
                    detail=operation + (f" on {relation}" if relation else ""),
                    estimated_rows=estimated_rows,
                    total_cost=total_cost,
                )
            )
            for child in node.get("Plans", []) if isinstance(node.get("Plans"), list) else []:
                if isinstance(child, dict):
                    visit(child)

        visit(cast(dict[str, Any], root))
        warnings = tuple(f"Sequential scan: {name}" for name in dict.fromkeys(scans))
        return QueryPlan(
            backend=self.kind,
            nodes=tuple(nodes),
            estimated_rows=int(root.get("Plan Rows", 0)),
            estimated_total_cost=float(root.get("Total Cost", 0.0)),
            full_scan_relations=tuple(dict.fromkeys(scans)),
            warnings=warnings,
        )
