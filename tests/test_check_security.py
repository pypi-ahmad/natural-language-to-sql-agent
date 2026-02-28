"""
Tests for SQLAgent.check_security() — SQL safety validation.
Target: backend.py lines 111-126.

Coverage intent:
- All 6 forbidden keywords detected (DROP, DELETE, TRUNCATE, INSERT, UPDATE, ALTER)
- Case insensitivity via .upper() (line 120)
- Safe queries pass validation
- Return contract: unsafe returns {sql_safe, error}, safe returns {sql_safe} only
- False positive documentation (Phase 2 M-01): substring matching in identifiers/values
- Bug documentation (Phase 2 C-02): safe path does not clear error
"""
import pytest
from unittest.mock import MagicMock
from backend import SQLAgent


@pytest.fixture
def security_agent(tmp_db_dir):
    """Lightweight agent for pure-logic security tests."""
    return SQLAgent(MagicMock())


class TestCheckSecuritySafeQueries:
    """Verify safe queries pass validation."""

    def test_simple_select(self, security_agent, make_state):
        result = security_agent.check_security(make_state(sql_query="SELECT * FROM employees"))
        assert result["sql_safe"] is True

    def test_select_with_where(self, security_agent, make_state):
        result = security_agent.check_security(
            make_state(sql_query="SELECT name FROM employees WHERE salary > 100000")
        )
        assert result["sql_safe"] is True

    def test_select_with_join(self, security_agent, make_state):
        result = security_agent.check_security(
            make_state(sql_query=(
                "SELECT e.name, d.dept_name FROM employees e "
                "JOIN departments d ON e.dept_id = d.dept_id"
            ))
        )
        assert result["sql_safe"] is True

    def test_aggregate_query(self, security_agent, make_state):
        result = security_agent.check_security(
            make_state(sql_query="SELECT COUNT(*), AVG(salary) FROM employees")
        )
        assert result["sql_safe"] is True

    def test_subquery(self, security_agent, make_state):
        result = security_agent.check_security(
            make_state(sql_query=(
                "SELECT name FROM employees WHERE dept_id IN "
                "(SELECT dept_id FROM departments WHERE location = 'New York')"
            ))
        )
        assert result["sql_safe"] is True

    def test_select_with_group_by(self, security_agent, make_state):
        result = security_agent.check_security(
            make_state(sql_query="SELECT dept_id, SUM(salary) FROM employees GROUP BY dept_id")
        )
        assert result["sql_safe"] is True


class TestCheckSecurityForbiddenKeywords:
    """Verify each forbidden keyword is blocked (backend.py:121-124)."""

    @pytest.mark.parametrize("keyword,sql", [
        ("DROP", "DROP TABLE employees"),
        ("DELETE", "DELETE FROM employees WHERE emp_id = 1"),
        ("TRUNCATE", "TRUNCATE TABLE employees"),
        ("INSERT", "INSERT INTO employees VALUES (6, 'Frank', 90000, 101)"),
        ("UPDATE", "UPDATE employees SET salary = 0"),
        ("ALTER", "ALTER TABLE employees ADD COLUMN age INTEGER"),
    ])
    def test_blocks_forbidden_keyword(self, security_agent, make_state, keyword, sql):
        result = security_agent.check_security(make_state(sql_query=sql))
        assert result["sql_safe"] is False
        assert keyword in result["error"]

    def test_blocks_drop_lowercase(self, security_agent, make_state):
        """Case insensitivity: 'drop' detected via .upper() (line 120)."""
        result = security_agent.check_security(make_state(sql_query="drop table employees"))
        assert result["sql_safe"] is False

    def test_blocks_mixed_case(self, security_agent, make_state):
        result = security_agent.check_security(make_state(sql_query="DrOp TaBlE employees"))
        assert result["sql_safe"] is False

    def test_blocks_delete_lowercase(self, security_agent, make_state):
        result = security_agent.check_security(make_state(sql_query="delete from employees"))
        assert result["sql_safe"] is False

    def test_error_message_format(self, security_agent, make_state):
        """Error message pattern: "Forbidden keyword '<WORD>' detected." (line 123)."""
        result = security_agent.check_security(make_state(sql_query="DROP TABLE x"))
        assert result["error"] == "Forbidden keyword 'DROP' detected."

    def test_first_forbidden_keyword_wins(self, security_agent, make_state):
        """Multiple forbidden keywords: first one in the list is reported."""
        result = security_agent.check_security(
            make_state(sql_query="DROP TABLE x; DELETE FROM y")
        )
        # DROP comes before DELETE in the forbidden list
        assert "DROP" in result["error"]


class TestCheckSecurityReturnContract:
    """Verify returned dict keys match documented behavior."""

    def test_safe_returns_sql_safe_and_error(self, security_agent, make_state):
        """
        FIX VERIFICATION (Phase 2: C-02, m-03 — now fixed):
        Safe path now returns {'sql_safe': True, 'error': ''}
        to explicitly clear any stale error in LangGraph state.
        """
        result = security_agent.check_security(make_state(sql_query="SELECT 1"))
        assert result == {"sql_safe": True, "error": ""}
        assert "error" in result
        assert result["error"] == ""

    def test_unsafe_returns_both_keys(self, security_agent, make_state):
        result = security_agent.check_security(make_state(sql_query="DROP TABLE x"))
        assert "sql_safe" in result
        assert "error" in result
        assert result["sql_safe"] is False
        assert isinstance(result["error"], str)
        assert len(result["error"]) > 0


class TestCheckSecurityNoFalsePositives:
    """
    FIX VERIFICATION (Phase 2: M-01 — now fixed):
    Word-boundary regex matching prevents false positives.
    Forbidden keywords inside identifiers/values are no longer blocked.
    """

    def test_no_false_positive_drop_in_value(self, security_agent, make_state):
        """'Dropout' no longer triggers DROP."""
        result = security_agent.check_security(
            make_state(sql_query="SELECT * FROM employees WHERE name = 'Dropout'")
        )
        assert result["sql_safe"] is True

    def test_no_false_positive_update_in_column(self, security_agent, make_state):
        """'updated_at' no longer triggers UPDATE."""
        result = security_agent.check_security(
            make_state(sql_query="SELECT updated_at FROM logs")
        )
        assert result["sql_safe"] is True

    def test_no_false_positive_delete_in_value(self, security_agent, make_state):
        """'Deleter' no longer triggers DELETE."""
        result = security_agent.check_security(
            make_state(sql_query="SELECT * FROM employees WHERE name = 'Deleter'")
        )
        assert result["sql_safe"] is True

    def test_no_false_positive_alter_in_value(self, security_agent, make_state):
        """'Altered' no longer triggers ALTER."""
        result = security_agent.check_security(
            make_state(sql_query="SELECT * FROM employees WHERE status = 'Altered'")
        )
        assert result["sql_safe"] is True

    def test_no_false_positive_insert_in_value(self, security_agent, make_state):
        """'Inserting' no longer triggers INSERT."""
        result = security_agent.check_security(
            make_state(sql_query="SELECT * FROM logs WHERE action = 'Inserting'")
        )
        assert result["sql_safe"] is True
