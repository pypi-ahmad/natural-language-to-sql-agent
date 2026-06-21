"""Tests for the database layer."""

from __future__ import annotations

import sqlite3

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
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        assert "departments" in names
        assert "employees" in names

    def test_departments_columns(self, seeded_db, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(departments)")
            }
        assert {"dept_id", "dept_name", "location"}.issubset(cols)

    def test_employees_columns(self, seeded_db, tmp_db_path):
        with sqlite3.connect(tmp_db_path) as conn:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(employees)")
            }
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
