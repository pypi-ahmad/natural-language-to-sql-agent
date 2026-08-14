"""Tests for PostgreSQL read-only connection and plan behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nl2sql_agent.db import DatabaseError, PostgresDatabase


def _cursor(*, one=None, all_rows=None):
    cursor = MagicMock()
    cursor.fetchone.return_value = one
    cursor.fetchall.return_value = all_rows or []
    return cursor


def _safe_connection(final_cursor):
    conn = MagicMock()
    conn.execute.side_effect = [
        _cursor(one={"transaction_read_only": "on"}),
        _cursor(
            one={
                "rolsuper": False,
                "rolcreatedb": False,
                "rolcreaterole": False,
                "rolbypassrls": False,
            }
        ),
        _cursor(),
        _cursor(),
        _cursor(),
        final_cursor,
    ]
    return conn


def test_connection_is_read_only_parameterized_and_rolled_back():
    conn = _safe_connection(_cursor(all_rows=[{"table_name": "employees"}]))
    with patch("nl2sql_agent.db.postgres.psycopg.connect", return_value=conn) as connect:
        database = PostgresDatabase("postgresql://operator@db/app", schema="analytics")
        assert database.list_tables() == ("employees",)

    assert connect.call_args.kwargs["autocommit"] is False
    assert conn.read_only is True
    assert conn.execute.call_args_list[2].args[1] == ("15000ms",)
    assert conn.execute.call_args_list[4].args[1] == ("analytics,pg_catalog",)
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_privileged_postgres_role_is_rejected():
    conn = MagicMock()
    conn.execute.side_effect = [
        _cursor(one={"transaction_read_only": "on"}),
        _cursor(
            one={
                "rolsuper": True,
                "rolcreatedb": False,
                "rolcreaterole": False,
                "rolbypassrls": False,
            }
        ),
    ]
    with (
        patch("nl2sql_agent.db.postgres.psycopg.connect", return_value=conn),
        pytest.raises(DatabaseError, match="non-privileged"),
    ):
        PostgresDatabase("postgresql://admin@db/app").list_tables()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_preflight_uses_json_explain_without_analyze():
    plan = [
        {
            "Plan": {
                "Node Type": "Seq Scan",
                "Relation Name": "employees",
                "Plan Rows": 120000,
                "Total Cost": 12001.5,
            }
        }
    ]
    conn = _safe_connection(_cursor(one={"QUERY PLAN": plan}))
    with patch("nl2sql_agent.db.postgres.psycopg.connect", return_value=conn):
        result = PostgresDatabase("postgresql://reader@db/app").preflight("SELECT * FROM employees")
    rendered = repr(conn.execute.call_args_list[-1].args[0])
    assert "EXPLAIN" in rendered
    assert "ANALYZE" not in rendered
    assert result.estimated_rows == 120000
    assert result.estimated_total_cost == 12001.5
    assert result.full_scan_relations == ("employees",)


def test_fingerprint_never_contains_dsn():
    dsn = "postgresql://reader:top-secret@db/app"  # pragma: allowlist secret
    fingerprint = PostgresDatabase(dsn).fingerprint
    assert "reader" not in fingerprint
    assert "top-secret" not in fingerprint
    assert len(fingerprint) == 64
