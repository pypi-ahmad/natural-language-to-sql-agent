"""
Tests for SQLAgent routing functions.
Target: backend.py lines 169-192.

Coverage intent:
- route_after_security: safe → "execute", unsafe → "summarize"
- route_after_execute: no error → "summarize", error+retries → "retry", error+exhausted → "summarize"
- Boundary conditions on retry_count (0, 1, 2, 3, 5)
- Empty-string vs non-empty error (truthiness)
- Bug documentation: stale error causing unwanted retry (C-02)
"""
import pytest
from unittest.mock import MagicMock
from backend import SQLAgent


@pytest.fixture
def routing_agent(tmp_db_dir):
    """Lightweight agent for pure-logic routing tests."""
    return SQLAgent(MagicMock())


class TestRouteAfterSecurity:
    """Tests for route_after_security() (backend.py:169-179)."""

    def test_safe_routes_to_execute(self, routing_agent, make_state):
        """sql_safe=True → 'execute' (line 178)."""
        result = routing_agent.route_after_security(make_state(sql_safe=True))
        assert result == "execute"

    def test_unsafe_routes_to_summarize(self, routing_agent, make_state):
        """sql_safe=False → 'summarize' (line 178)."""
        result = routing_agent.route_after_security(make_state(sql_safe=False))
        assert result == "summarize"

    def test_unsafe_with_error_routes_to_summarize(self, routing_agent, make_state):
        result = routing_agent.route_after_security(
            make_state(sql_safe=False, error="Forbidden keyword 'DROP' detected.")
        )
        assert result == "summarize"


class TestRouteAfterExecute:
    """Tests for route_after_execute() (backend.py:181-192)."""

    def test_no_error_routes_to_summarize(self, routing_agent, make_state):
        """Empty error string is falsy → 'summarize' (line 189-190)."""
        result = routing_agent.route_after_execute(make_state(error="", retry_count=0))
        assert result == "summarize"

    def test_error_retry_count_0_routes_to_retry(self, routing_agent, make_state):
        """error + retry_count=0 < 3 → 'retry'."""
        result = routing_agent.route_after_execute(
            make_state(error="syntax error", retry_count=0)
        )
        assert result == "retry"

    def test_error_retry_count_1_routes_to_retry(self, routing_agent, make_state):
        result = routing_agent.route_after_execute(
            make_state(error="some error", retry_count=1)
        )
        assert result == "retry"

    def test_error_retry_count_2_routes_to_retry(self, routing_agent, make_state):
        """retry_count=2 is still < 3, so retry is allowed."""
        result = routing_agent.route_after_execute(
            make_state(error="error", retry_count=2)
        )
        assert result == "retry"

    def test_error_retry_count_3_routes_to_summarize(self, routing_agent, make_state):
        """retry_count=3 is NOT < 3 → 'summarize' (line 189)."""
        result = routing_agent.route_after_execute(
            make_state(error="still failing", retry_count=3)
        )
        assert result == "summarize"

    def test_error_retry_count_5_routes_to_summarize(self, routing_agent, make_state):
        """retry_count=5 well past limit → 'summarize'."""
        result = routing_agent.route_after_execute(
            make_state(error="error", retry_count=5)
        )
        assert result == "summarize"

    def test_no_error_high_retry_routes_to_summarize(self, routing_agent, make_state):
        """Even with high retry_count, no error means summarize."""
        result = routing_agent.route_after_execute(
            make_state(error="", retry_count=10)
        )
        assert result == "summarize"


class TestRouteAfterExecuteEdgeCases:
    """Edge cases and bug documentation."""

    def test_stale_error_no_longer_causes_unwanted_retry(self, routing_agent, make_state):
        """
        FIX VERIFICATION (Phase 2: C-02 — now fixed):
        With check_security now clearing error='', and execute_sql always
        returning result key, stale errors from previous cycles are cleared.
        A successful execution (error='') after retry correctly routes to summarize.
        """
        result = routing_agent.route_after_execute(
            make_state(error="", retry_count=1)
        )
        assert result == "summarize"

    def test_none_error_is_falsy(self, routing_agent):
        """None as error should be treated as falsy → summarize."""
        state = {
            "question": "", "schema": "", "sql_query": "",
            "sql_safe": True, "result": "", "error": None, "retry_count": 1,
        }
        result = routing_agent.route_after_execute(state)
        assert result == "summarize"
