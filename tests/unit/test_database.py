"""Tests for the database layer."""

from __future__ import annotations

import re
import sqlite3
from csv import reader
from io import StringIO
from unittest.mock import patch

import pytest

from nl2sql_agent.db import (
    SEED_DEPARTMENTS,
    SEED_EMPLOYEES,
    Database,
    QueryResult,
    render_table,
    setup_db,
)


class TestSetup:
    def test_creates_database_file(self, tmp_db_path):
        assert not tmp_db_path.exists()
        Database(tmp_db_path).ensure_schema(seed=True)
        assert tmp_db_path.exists()

    def test_creates_parent_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        nested = tmp_path / "a" / "b" / "company.db"
        Database(nested).ensure_schema(seed=True)
        assert nested.exists()

    def test_tables_created(self, seeded_db, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            names = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        assert "departments" in names
        assert "employees" in names

    def test_departments_columns(self, seeded_db, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(departments)")}
        assert {"dept_id", "dept_name", "location"}.issubset(cols)

    def test_employees_columns(self, seeded_db, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(employees)")}
        assert {"emp_id", "name", "salary", "dept_id"}.issubset(cols)

    def test_seed_data_inserted(self, seeded_db, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            dept_count = conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
            emp_count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        assert dept_count == len(SEED_DEPARTMENTS)
        assert emp_count == len(SEED_EMPLOYEES)

    def test_seed_data_actual_values(self, seeded_db, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            alice = conn.execute(
                "SELECT name, salary FROM employees WHERE name = 'Alice'"
            ).fetchone()
        assert alice == ("Alice", 120_000.0)

    def test_idempotent(self, seeded_db, tmp_db_path):
        # Run setup_db a second time; should not duplicate rows.
        Database(tmp_db_path).ensure_schema(seed=True)
        with sqlite3.connect(tmp_db_path) as conn:
            n = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        assert n == len(SEED_EMPLOYEES)

    def test_no_seed_when_disabled(self, tmp_db_path):
        Database(tmp_db_path).ensure_schema(seed=False)
        with sqlite3.connect(tmp_db_path) as conn:
            n = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        assert n == 0

    def test_setup_module_helper(self, tmp_db_path):
        setup_db(tmp_db_path, seed=True)
        assert tmp_db_path.exists()


class TestQueryResult:
    def test_to_markdown_includes_header(self):
        qr = QueryResult(columns=("a", "b"), rows=((1, 2),), row_count=1)
        md = qr.to_markdown()
        assert "| a | b |" in md
        assert "| --- | --- |" in md
        assert "| 1 | 2 |" in md

    def test_to_markdown_truncates(self):
        rows = tuple((i,) for i in range(50))
        qr = QueryResult(columns=("x",), rows=rows, row_count=50)
        md = qr.to_markdown(max_rows=10)
        assert "more rows truncated" in md
        # Header + separator + 10 rows + truncation footer = 13 lines
        assert len(md.splitlines()) == 13

    def test_to_markdown_empty(self):
        qr = QueryResult(columns=("a",), rows=(), row_count=0)
        assert qr.to_markdown() == "_No rows returned._"

    def test_to_markdown_escapes_pipe(self):
        qr = QueryResult(columns=("a",), rows=(("a|b",),), row_count=1)
        assert "a\\|b" in qr.to_markdown()

    def test_to_csv(self):
        qr = QueryResult(columns=("a", "b"), rows=((1, 2), (3, 4)), row_count=2)
        csv = qr.to_csv()
        # csv.writer uses \r\n line terminator (RFC 4180)
        assert csv.replace("\r\n", "\n") == "a,b\n1,2\n3,4\n"

    def test_to_csv_neutralizes_spreadsheet_formulas(self):
        qr = QueryResult(
            columns=("=header", "safe"),
            rows=(("=1+1", "  @SUM(A1:A2)"), ("ordinary", -5)),
            row_count=2,
        )

        parsed = list(reader(StringIO(qr.to_csv())))

        assert parsed == [
            ["'=header", "safe"],
            ["'=1+1", "'  @SUM(A1:A2)"],
            ["ordinary", "-5"],
        ]
        assert qr.rows[0][0] == "=1+1"

    def test_truncation_is_reported(self):
        qr = QueryResult(columns=("a",), rows=((1,),), row_count=1, truncated=True)
        assert qr.truncated is True

    def test_render_table_helper(self):
        out = render_table([(1, "x")], ["a", "b"])
        assert "| a | b |" in out


class TestDatabaseExecute:
    def test_basic_select(self, seeded_db):
        qr = seeded_db.execute("SELECT name, salary FROM employees ORDER BY name LIMIT 1")
        assert qr.columns == ("name", "salary")
        assert qr.rows == (("Alice", 120_000.0),)
        assert qr.row_count == 1

    def test_no_rows(self, seeded_db):
        qr = seeded_db.execute("SELECT * FROM employees WHERE name = 'Nobody'")
        assert qr.row_count == 0
        assert qr.rows == ()

    def test_max_rows_enforced(self, seeded_db):
        qr = seeded_db.execute("SELECT * FROM employees")
        assert qr.row_count == len(SEED_EMPLOYEES)

    def test_aggregation(self, seeded_db):
        qr = seeded_db.execute("SELECT COUNT(*) AS n FROM employees")
        assert qr.rows == ((len(SEED_EMPLOYEES),),)

    def test_invalid_sql_raises(self, seeded_db):
        with pytest.raises(sqlite3.Error):
            seeded_db.execute("SELECT * FROM no_such_table")

    def test_syntax_error_raises(self, seeded_db):
        with pytest.raises(sqlite3.Error):
            seeded_db.execute("SELECT FROM WHERE")

    def test_query_connection_is_read_only(self, seeded_db):
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            seeded_db.execute("DELETE FROM employees")

    def test_preflight_validates_columns_without_running_query(self, seeded_db):
        plan = seeded_db.preflight("SELECT name FROM employees")
        assert plan.backend == "sqlite"
        assert plan.nodes
        with pytest.raises(sqlite3.OperationalError, match="no such column"):
            seeded_db.preflight("SELECT missing FROM employees")

    def test_execution_records_runtime_and_work_units(self, seeded_db):
        result = seeded_db.execute("SELECT name FROM employees")
        assert result.metrics.duration_ms >= 0
        assert result.metrics.work_units is not None

    def test_result_cap_sets_truncation_flag(self, tmp_db_path):
        db = Database(tmp_db_path, max_rows=2)
        db.ensure_schema(seed=True)
        result = db.execute("SELECT * FROM employees")
        assert result.row_count == 2
        assert result.truncated is True

    def test_vm_step_budget_interrupts_expensive_query(self, tmp_db_path):
        db = Database(tmp_db_path, max_vm_steps=10_000)
        db.ensure_schema(seed=True)
        with pytest.raises(sqlite3.OperationalError, match="interrupted"):
            db.execute(
                "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL "
                "SELECT x + 1 FROM n WHERE x < 1000000) SELECT SUM(x) FROM n"
            )


class TestDatabaseSchema:
    def test_get_schema_text(self, seeded_db):
        text = seeded_db.get_schema_text()
        assert "Table departments" in text
        assert "Table employees" in text
        assert "dept_id" in text
        assert "salary" in text

    def test_get_schema_text_includes_foreign_key(self, seeded_db):
        text = seeded_db.get_schema_text()
        # FK from employees.dept_id to departments.dept_id
        assert "→" in text

    def test_get_schema_empty_db(self, empty_db):
        text = empty_db.get_schema_text()
        # Empty DB still has the tables (just no rows)
        assert "Table departments" in text

    def test_lists_user_tables(self, seeded_db):
        assert seeded_db.list_tables() == ("departments", "employees")

    def test_schema_reuses_one_query_connection(self, seeded_db):
        with patch.object(seeded_db, "connect", wraps=seeded_db.connect) as connect:
            seeded_db.get_schema_text(question="employee salary", max_tables=1)

        assert connect.call_count == 1

    def test_schema_honors_allowlist(self, seeded_db):
        text = seeded_db.get_schema_text(allowed_tables={"employees"})
        assert "Table employees" in text
        assert "Table departments" not in text

    def test_schema_ranking_prefers_matching_columns(self, seeded_db):
        text = seeded_db.get_schema_text(
            allowed_tables={"employees", "departments"},
            question="employee salary",
            max_tables=1,
        )
        assert "Table employees" in text
        assert "Table departments" not in text

    def test_schema_ranking_evaluates_each_identifier_once(self, seeded_db):
        tables = seeded_db.list_tables()
        with sqlite3.connect(seeded_db.path) as conn:
            identifier_count = sum(
                1 + len(conn.execute("SELECT name FROM pragma_table_info(?)", (table,)).fetchall())
                for table in tables
            )

        with patch("nl2sql_agent.db.database.re.findall", wraps=re.findall) as findall:
            seeded_db.get_schema_text(question="employee salary", max_tables=1)

        assert findall.call_count == 1 + identifier_count

    def test_sample_rows_are_opt_in(self, seeded_db):
        without = seeded_db.get_schema_text(include_sample_values=False)
        with_samples = seeded_db.get_schema_text(include_sample_values=True)
        assert "Sample rows:" not in without
        assert "Sample rows:" in with_samples
