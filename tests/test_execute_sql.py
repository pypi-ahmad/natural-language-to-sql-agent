"""
Tests for SQLAgent.execute_sql() — SQL query execution.
Target: backend.py lines 128-146.

Coverage intent:
- Successful SELECT with results
- Successful SELECT with no results (empty result set)
- Failed SQL (syntax error, missing table)
- Return contract on success: {result, error}
- Return contract on failure: {error} only (Bug C-01)
- Result format (str(rows))
- Connection cleanup (finally block)
"""
import pytest
from unittest.mock import MagicMock
from backend import SQLAgent


class TestExecuteSqlSuccess:
    """Verify successful query execution."""

    def test_select_all_returns_results(self, agent, make_state):
        """Valid SELECT must return non-empty result string."""
        result = agent.execute_sql(make_state(sql_query="SELECT * FROM employees"))
        assert "result" in result
        assert len(result["result"]) > 0

    def test_select_all_contains_names(self, agent, make_state):
        """Result must contain all seeded employee names."""
        result = agent.execute_sql(make_state(sql_query="SELECT * FROM employees ORDER BY emp_id"))
        for name in ["Alice", "Bob", "Charlie", "Diana", "Eve"]:
            assert name in result["result"], f"Missing '{name}' in result"

    def test_success_clears_error(self, agent, make_state):
        """On success, error must be '' (line 139, 140)."""
        result = agent.execute_sql(make_state(sql_query="SELECT * FROM employees"))
        assert result["error"] == ""

    def test_select_with_where(self, agent, make_state):
        result = agent.execute_sql(
            make_state(sql_query="SELECT name FROM employees WHERE salary > 100000")
        )
        assert "Alice" in result["result"]
        assert "Charlie" in result["result"]
        assert "Bob" not in result["result"]

    def test_aggregate_count(self, agent, make_state):
        result = agent.execute_sql(make_state(sql_query="SELECT COUNT(*) FROM employees"))
        assert "5" in result["result"]

    def test_aggregate_sum(self, agent, make_state):
        result = agent.execute_sql(
            make_state(sql_query="SELECT SUM(salary) FROM employees WHERE dept_id = 101")
        )
        # Alice=120000 + Charlie=115000 = 235000
        assert "235000" in result["result"]

    def test_join_query(self, agent, make_state):
        result = agent.execute_sql(make_state(sql_query=(
            "SELECT e.name, d.dept_name FROM employees e "
            "JOIN departments d ON e.dept_id = d.dept_id ORDER BY e.emp_id"
        )))
        assert "Alice" in result["result"]
        assert "Engineering" in result["result"]

    def test_result_is_str_of_rows(self, agent, make_state):
        """Result format is str(rows) per backend.py:140."""
        result = agent.execute_sql(
            make_state(sql_query="SELECT emp_id FROM employees WHERE emp_id = 1")
        )
        assert result["result"] == "[(1,)]"

    def test_returns_result_and_error_keys(self, agent, make_state):
        """Success returns both 'result' and 'error' keys."""
        result = agent.execute_sql(make_state(sql_query="SELECT 1"))
        assert "result" in result
        assert "error" in result


class TestExecuteSqlNoResults:
    """Verify empty result set handling (backend.py:139)."""

    def test_no_matching_rows(self, agent, make_state):
        result = agent.execute_sql(
            make_state(sql_query="SELECT * FROM employees WHERE salary > 999999")
        )
        assert result["result"] == "No data found."

    def test_no_results_clears_error(self, agent, make_state):
        result = agent.execute_sql(
            make_state(sql_query="SELECT * FROM employees WHERE salary > 999999")
        )
        assert result["error"] == ""


class TestExecuteSqlFailure:
    """Verify error handling on invalid SQL."""

    def test_syntax_error_returns_error(self, agent, make_state):
        result = agent.execute_sql(make_state(sql_query="INVALID SQL QUERY"))
        assert "error" in result
        assert len(result["error"]) > 0

    def test_missing_table_returns_error(self, agent, make_state):
        result = agent.execute_sql(make_state(sql_query="SELECT * FROM nonexistent_table"))
        assert "error" in result
        assert "nonexistent_table" in result["error"]

    def test_missing_column_returns_error(self, agent, make_state):
        result = agent.execute_sql(
            make_state(sql_query="SELECT nonexistent_col FROM employees")
        )
        assert "error" in result

    def test_error_is_string(self, agent, make_state):
        result = agent.execute_sql(make_state(sql_query="INVALID"))
        assert isinstance(result["error"], str)

    def test_error_includes_result_key(self, agent, make_state):
        """
        FIX VERIFICATION (Phase 2: C-01 — now fixed):
        On exception, execute_sql now returns {"result": "", "error": str(e)}.
        The 'result' key IS included to prevent downstream KeyError.
        """
        result = agent.execute_sql(make_state(sql_query="INVALID SQL"))
        assert "error" in result
        assert "result" in result
        assert result["result"] == ""
