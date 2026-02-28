"""
Tests for SQLAgent.fetch_schema() — database schema retrieval.
Target: backend.py lines 65-82.

Coverage intent:
- Returns dict with 'schema' key
- Schema string contains all table names
- Schema string contains all column names with types
- Schema format matches f-string template on line 81
- Returns only 'schema' key (no side effects on other state keys)
"""
import pytest


class TestFetchSchemaReturnStructure:
    """Verify the return value contract."""

    def test_returns_dict_with_schema_key(self, agent, make_state):
        """fetch_schema must return {'schema': <str>}."""
        result = agent.fetch_schema(make_state())
        assert "schema" in result
        assert isinstance(result["schema"], str)

    def test_returns_only_schema_key(self, agent, make_state):
        """fetch_schema must not return other state keys."""
        result = agent.fetch_schema(make_state())
        assert list(result.keys()) == ["schema"]

    def test_schema_is_nonempty(self, agent, make_state):
        """With seeded DB, schema must not be empty."""
        result = agent.fetch_schema(make_state())
        assert len(result["schema"]) > 0


class TestFetchSchemaContent:
    """Verify schema string contains expected table and column info."""

    def test_contains_departments_table(self, agent, make_state):
        result = agent.fetch_schema(make_state())
        assert "departments" in result["schema"]

    def test_contains_employees_table(self, agent, make_state):
        result = agent.fetch_schema(make_state())
        assert "employees" in result["schema"]

    def test_contains_department_columns(self, agent, make_state):
        """backend.py:80 — col format is 'col_name (col_type)'."""
        schema = agent.fetch_schema(make_state())["schema"]
        for col in ["dept_id (INTEGER)", "dept_name (TEXT)", "location (TEXT)"]:
            assert col in schema, f"Missing '{col}' in schema"

    def test_contains_employee_columns(self, agent, make_state):
        schema = agent.fetch_schema(make_state())["schema"]
        for col in ["emp_id (INTEGER)", "name (TEXT)", "salary (REAL)", "dept_id (INTEGER)"]:
            assert col in schema, f"Missing '{col}' in schema"

    def test_schema_format_per_table(self, agent, make_state):
        """
        backend.py:81 — format is: Table '<name>': col1 (type1), col2 (type2)\\n
        Verify at least one line matches this pattern.
        """
        schema = agent.fetch_schema(make_state())["schema"]
        assert "Table '" in schema
        assert "':" in schema


class TestFetchSchemaEmptyDb:
    """Verify behavior when the database has no tables."""

    def test_empty_db_returns_empty_schema(self, tmp_db_dir):
        """If DB has no tables, schema string should be empty."""
        import sqlite3
        from unittest.mock import MagicMock
        from backend import SQLAgent

        # Create an empty database (no tables)
        conn = sqlite3.connect("company.db")
        conn.execute("DROP TABLE IF EXISTS departments")
        conn.execute("DROP TABLE IF EXISTS employees")
        conn.commit()
        conn.close()

        mock_llm = MagicMock()
        # Bypass setup_db by directly creating agent and overriding DB
        agent = SQLAgent(mock_llm)
        # After SQLAgent.__init__, setup_db recreates tables.
        # So we need to drop them again after init.
        conn = sqlite3.connect("company.db")
        conn.execute("DROP TABLE IF EXISTS departments")
        conn.execute("DROP TABLE IF EXISTS employees")
        conn.commit()
        conn.close()

        state = {"question": "", "schema": "", "sql_query": "",
                 "sql_safe": False, "result": "", "error": "", "retry_count": 0}
        result = agent.fetch_schema(state)
        assert result["schema"] == ""
