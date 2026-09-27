"""Disposable PostgreSQL 17 fixture, enabled only with an explicit test DSN."""

import os
from unittest.mock import MagicMock

import psycopg
import pytest
from langchain_core.messages import AIMessage
from psycopg.conninfo import make_conninfo

from nl2sql_agent.agent import NL2SQLAgent
from nl2sql_agent.config import Settings
from nl2sql_agent.db import DatabaseError, PostgresDatabase

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def postgres_db():
    dsn = os.environ.get("NL2SQL_TEST_POSTGRES_ADMIN_DSN")
    if not dsn:
        pytest.skip("Disposable PostgreSQL test DSN not configured")
    # The explicit DSN must identify a disposable test database, never an app DB.
    from psycopg.conninfo import conninfo_to_dict

    if conninfo_to_dict(dsn).get("dbname") != "nl2sql_test":
        pytest.fail("Use the disposable nl2sql_test database")
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "CREATE ROLE nl2sql_reader LOGIN PASSWORD 'test-reader-only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
        )
        conn.execute("CREATE TABLE departments(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute(
            "CREATE TABLE employees(id INTEGER PRIMARY KEY, department_id INTEGER REFERENCES departments(id), name TEXT)"
        )
        conn.execute("INSERT INTO departments VALUES (1, 'Engineering')")
        conn.execute("INSERT INTO employees VALUES (1, 1, 'Alice'), (2, 1, 'Bob')")
        conn.execute("CREATE TABLE regions(country TEXT, city TEXT, PRIMARY KEY(country, city))")
        conn.execute(
            "CREATE TABLE offices(id INTEGER PRIMARY KEY, country TEXT, city TEXT, "
            "FOREIGN KEY(country, city) REFERENCES regions(country, city))"
        )
        conn.execute("GRANT USAGE ON SCHEMA public TO nl2sql_reader")
        conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO nl2sql_reader")
    return PostgresDatabase(
        make_conninfo(
            dsn,
            user="nl2sql_reader",
            password="test-reader-only",  # pragma: allowlist secret
        )
    )
    # The service container is disposed by CI; no broad cleanup on a user's DB.


def test_real_postgres_schema_plan_and_execution(postgres_db):
    assert postgres_db.get_schema_text(allowed_tables=set()) == "(no tables)"
    schema = postgres_db.get_schema_text(allowed_tables={"employees", "departments"})
    assert "employees.department_id" in schema
    model = MagicMock()
    model.invoke.return_value = AIMessage(
        content='{"action":"sql","sql":"SELECT COUNT(*) AS total FROM employees"}'
    )
    agent = NL2SQLAgent(model, settings=Settings(audit_enabled=False), database=postgres_db)
    prepared = agent.prepare("Count employees")
    assert prepared["outcome"] == "prepared"
    assert not prepared["executed"]
    result = agent.execute_prepared(prepared)
    assert result["raw_rows"] == [(2,)]
    assert result["executed"] is True


def test_readonly_role_cannot_write(postgres_db):
    with pytest.raises(DatabaseError):
        postgres_db.execute("DELETE FROM employees")
    assert postgres_db.execute("SELECT COUNT(*) FROM employees").rows == ((2,),)


def test_readonly_role_sees_correct_composite_foreign_key_pairs(postgres_db):
    schema = postgres_db.get_schema_text(allowed_tables={"regions", "offices"})
    assert "offices.country → regions.country" in schema
    assert "offices.city → regions.city" in schema
    assert "offices.country → regions.city" not in schema
    assert "employees" not in schema
