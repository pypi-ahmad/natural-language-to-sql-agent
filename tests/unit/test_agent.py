"""Tests for the LangGraph agent workflow."""

from __future__ import annotations

from unittest.mock import MagicMock

from nl2sql_agent.agent import AgentState, NL2SQLAgent
from nl2sql_agent.security import SQLPolicy


def _make_agent(seeded_db, mock_llm, **policy_overrides) -> NL2SQLAgent:
    """Build an NL2SQLAgent with a mock LLM and the seeded test DB."""
    from nl2sql_agent.config import get_settings

    settings = get_settings()
    agent = NL2SQLAgent.__new__(NL2SQLAgent)
    agent.llm = mock_llm
    agent.settings = settings
    agent.db = seeded_db
    base = {
        "allow_subqueries": settings.sql_allow_subqueries,
        "allow_joins": settings.sql_allow_joins,
        "allow_aggregates": settings.sql_allow_aggregates,
        "allow_cte": settings.sql_allow_cte,
    }
    base.update(policy_overrides)
    agent.policy = SQLPolicy(**base)
    return agent


class TestFetchSchema:
    def test_returns_schema_string(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.fetch_schema({})
        assert "schema" in result
        assert "Table" in result["schema"]
        assert "employees" in result["schema"]


class TestWriteSql:
    def test_calls_llm(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        state: AgentState = {"question": "list all", "schema": "schema-text"}
        result = agent.write_sql(state)
        mock_llm.invoke.assert_called_once()
        assert result["sql_query"] == "SELECT 1"
        assert result["retry_count"] == 1

    def test_includes_error_in_retry(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        state: AgentState = {
            "question": "x", "schema": "", "error": "no such column",
            "retry_count": 1,
        }
        agent.write_sql(state)
        # The user message should include the previous error
        messages = mock_llm.invoke.call_args[0][0]
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "no such column" in user_msg["content"]

    def test_strips_markdown_fence(self, seeded_db, mock_llm):
        response = MagicMock()
        response.content = "```sql\nSELECT * FROM employees\n```"
        mock_llm.invoke.return_value = response
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.write_sql({"question": "list", "schema": ""})
        assert "```" not in result["sql_query"]
        assert "SELECT * FROM employees" in result["sql_query"]

    def test_increments_retry_count(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        state: AgentState = {"question": "x", "schema": "", "retry_count": 2}
        result = agent.write_sql(state)
        assert result["retry_count"] == 3


class TestCheckSecurity:
    def test_safe_query(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.check_security({"sql_query": "SELECT 1 FROM employees"})
        assert result.get("error", "") == ""

    def test_dangerous_query_blocked(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.check_security({"sql_query": "DROP TABLE x"})
        assert "Forbidden" in result.get("error", "") or "SELECT" in result["error"]


class TestExecuteSql:
    def test_runs_safe_query(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.execute_sql({"sql_query": "SELECT name FROM employees ORDER BY name LIMIT 1"})
        assert result["error"] == ""
        assert "Alice" in result["result"]
        assert result["columns"] == ["name"]
        assert len(result["raw_rows"]) == 1

    def test_returns_error_on_bad_sql(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.execute_sql({"sql_query": "SELECT * FROM no_such_table"})
        assert "no such table" in result["error"].lower()
        assert result["result"] == ""

    def test_handles_empty_result(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.execute_sql({"sql_query": "SELECT * FROM employees WHERE name = 'NoOne'"})
        assert result["error"] == ""
        assert result["row_count"] == 0


class TestSummarize:
    def test_calls_llm(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        state: AgentState = {
            "question": "x", "sql_query": "SELECT 1", "result": "1", "error": "",
        }
        result = agent.summarize_result(state)
        assert "final_answer" in result
        mock_llm.invoke.assert_called_once()

    def test_fallback_when_llm_returns_empty(self, seeded_db, mock_llm):
        response = MagicMock()
        response.content = ""
        mock_llm.invoke.return_value = response
        agent = _make_agent(seeded_db, mock_llm)
        state: AgentState = {"question": "x", "sql_query": "SELECT 1", "result": "data", "error": ""}
        result = agent.summarize_result(state)
        assert "data" in result["final_answer"]

    def test_fallback_on_exception(self, seeded_db, mock_llm):
        mock_llm.invoke.side_effect = RuntimeError("api down")
        agent = _make_agent(seeded_db, mock_llm)
        state: AgentState = {"question": "x", "sql_query": "SELECT 1", "result": "", "error": "x"}
        result = agent.summarize_result(state)
        assert "couldn't" in result["final_answer"].lower() or "could not" in result["final_answer"].lower()


class TestRouting:
    def test_security_routes_to_executor_when_safe(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        assert agent.route_after_security({"error": ""}) == "executor"

    def test_security_routes_to_summarize_on_error(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        assert agent.route_after_security({"error": "Forbidden"}) == "summarizer"

    def test_execute_routes_to_retry_when_error(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        assert agent.route_after_execute({"error": "x", "retry_count": 0, "max_retries": 3}) == "writer"

    def test_execute_routes_to_summarize_when_no_error(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        assert agent.route_after_execute({"error": "", "retry_count": 0, "max_retries": 3}) == "summarizer"

    def test_execute_stops_at_max_retries(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        assert agent.route_after_execute({"error": "x", "retry_count": 3, "max_retries": 3}) == "summarizer"

    def test_execute_with_exhausted_retries_uses_state_max(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        # State has explicit max_retries=1, retry_count=1 -> stop
        assert agent.route_after_execute({"error": "x", "retry_count": 1, "max_retries": 1}) == "summarizer"


class TestHighLevelRun:
    def test_run_returns_final_state(self, seeded_db):
        # LLM returns a valid SELECT, executor returns rows, summarizer returns text.
        llm = MagicMock()
        response = MagicMock()
        response.content = "SELECT name FROM employees ORDER BY name LIMIT 2"
        llm.invoke.return_value = response
        agent = _make_agent(seeded_db, llm)
        result = agent.run("list 2 names")
        assert "final_answer" in result
        assert result["sql_query"].startswith("SELECT")
        assert "name" in result["columns"]

    def test_run_with_retry_on_syntax_error(self, seeded_db):
        # First LLM call returns valid SQL but referring to a non-existent column
        # (so the EXECUTOR fails, triggering a retry). Second call returns valid SQL.
        from langchain_core.messages import AIMessage

        llm = MagicMock()
        llm.invoke.side_effect = [
            AIMessage(content="SELECT bogus_column FROM employees"),
            AIMessage(content="SELECT name FROM employees ORDER BY name LIMIT 1"),
        ]
        agent = _make_agent(seeded_db, llm)
        result = agent.run("list one name")
        assert result["retry_count"] == 2
        assert "Alice" in result["result"] or "Alice" in result.get("final_answer", "")

    def test_run_with_dangerous_sql_blocked(self, seeded_db):
        from langchain_core.messages import AIMessage

        llm = MagicMock()
        llm.invoke.side_effect = [
            AIMessage(content="DROP TABLE employees"),
            AIMessage(content="(recovered)"),
        ]
        agent = _make_agent(seeded_db, llm)
        result = agent.run("destroy data")
        # Guardian blocks the DROP, summarizer gets a safety error.
        assert "validation failed" in result.get("error", "").lower() or \
               "forbidden" in result.get("error", "").lower()


class TestWorkflowStructure:
    def test_workflow_compiles(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        wf = agent.get_workflow()
        # LangGraph compiled graph exposes nodes via .nodes
        assert "fetch_schema" in wf.nodes
        assert "writer" in wf.nodes
        assert "guardian" in wf.nodes
        assert "executor" in wf.nodes
        assert "summarizer" in wf.nodes

    def test_stream_yields_events(self, seeded_db):
        from langchain_core.messages import AIMessage

        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content="SELECT 1")
        agent = _make_agent(seeded_db, llm)
        events = list(agent.stream("count"))
        node_names = [name for name, _ in events]
        # All five nodes should have fired.
        assert "fetch_schema" in node_names
        assert "writer" in node_names
        assert "guardian" in node_names
        assert "executor" in node_names
        assert "summarizer" in node_names


class TestExecutionEdgeCases:
    def test_summarizer_no_question(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.summarize_result({"sql_query": "SELECT 1", "result": "data"})
        assert "final_answer" in result

    def test_summarizer_no_sql(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.summarize_result({"question": "x", "result": ""})
        assert "final_answer" in result

    def test_summarizer_fallback_no_data_no_error(self, seeded_db, mock_llm):
        # If the LLM returns empty content, we should still get *something* back.
        response = MagicMock()
        response.content = ""
        mock_llm.invoke.return_value = response
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.summarize_result({"result": "", "error": ""})
        assert result["final_answer"]  # non-empty fallback

    def test_executor_returns_tuple_rows(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.execute_sql({"sql_query": "SELECT name FROM employees LIMIT 1"})
        assert isinstance(result["raw_rows"][0], tuple)

    def test_writer_clears_previous_error(self, seeded_db, mock_llm):
        agent = _make_agent(seeded_db, mock_llm)
        result = agent.write_sql(
            {"question": "x", "schema": "", "error": "old err", "sql_unsafe_reason": "old"}
        )
        assert result["error"] == ""
        assert result["sql_unsafe_reason"] == ""
