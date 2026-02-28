"""
Integration tests for the full LangGraph workflow.
Target: backend.py SQLAgent.get_workflow() (lines 194-228).

Coverage intent:
- Workflow compiles without error
- Happy path: fetch_schema → writer → guardian(safe) → executor → summarizer
- Security block path: fetch_schema → writer → guardian(block) → summarizer
- Retry path: executor error → writer(retry) → ... → summarizer
- Final state contains all AgentState keys
- invoke() returns the expected summary
"""
import pytest
from unittest.mock import MagicMock
from backend import SQLAgent, AgentState


class TestWorkflowStructure:
    """Verify the compiled workflow graph structure."""

    def test_compiles_without_error(self, agent):
        """get_workflow() must return a compiled graph."""
        app = agent.get_workflow()
        assert app is not None

    def test_has_stream_method(self, agent):
        """Compiled graph must support .stream() for event streaming."""
        app = agent.get_workflow()
        assert hasattr(app, "stream")

    def test_has_invoke_method(self, agent):
        """Compiled graph must support .invoke() for single invocation."""
        app = agent.get_workflow()
        assert hasattr(app, "invoke")


class TestWorkflowHappyPath:
    """Integration test: successful query end-to-end."""

    @pytest.fixture
    def success_agent(self, seeded_db):
        """Agent whose LLM returns valid SQL then a summary (2 LLM calls)."""
        mock_llm = MagicMock()
        responses = [
            MagicMock(content="SELECT SUM(salary) FROM employees WHERE dept_id = 101"),
            MagicMock(content="The total Engineering salary is $235,000."),
        ]
        mock_llm.invoke.side_effect = responses
        return SQLAgent(mock_llm)

    def test_traverses_all_nodes(self, success_agent):
        """Happy path must visit: fetch_schema, writer, guardian, executor, summarizer."""
        app = success_agent.get_workflow()
        inputs = {"question": "Total Engineering salary?", "retry_count": 0, "error": ""}
        node_names = []
        for event in app.stream(inputs):
            node_names.extend(event.keys())
        assert "fetch_schema" in node_names
        assert "writer" in node_names
        assert "guardian" in node_names
        assert "executor" in node_names
        assert "summarizer" in node_names

    def test_final_result_is_summary(self, success_agent):
        """invoke() must return the LLM summary as 'result'."""
        app = success_agent.get_workflow()
        result = app.invoke({"question": "Total Engineering salary?", "retry_count": 0, "error": ""})
        assert result["result"] == "The total Engineering salary is $235,000."

    def test_final_state_has_all_keys(self, success_agent):
        """invoke() result must contain all AgentState keys."""
        app = success_agent.get_workflow()
        result = app.invoke({"question": "Test?", "retry_count": 0, "error": ""})
        for key in AgentState.__annotations__:
            assert key in result, f"Missing state key: '{key}'"

    def test_sql_safe_is_true(self, success_agent):
        """After a safe query, sql_safe must be True."""
        app = success_agent.get_workflow()
        result = app.invoke({"question": "Test?", "retry_count": 0, "error": ""})
        assert result["sql_safe"] is True


class TestWorkflowSecurityBlock:
    """Integration test: unsafe SQL is blocked by guardian."""

    @pytest.fixture
    def unsafe_agent(self, seeded_db):
        """Agent whose LLM returns destructive SQL (2 LLM calls: writer + summarizer)."""
        mock_llm = MagicMock()
        responses = [
            MagicMock(content="DROP TABLE employees"),
            MagicMock(content="I cannot execute that query for security reasons."),
        ]
        mock_llm.invoke.side_effect = responses
        return SQLAgent(mock_llm)

    def test_security_block_routes_to_summarizer(self, unsafe_agent):
        """
        FIX VERIFICATION (Phase 2: C-01, C-02 — now fixed):
        Guardian blocks → routes to summarizer.
        summarize_result now uses state.get('result', 'N/A') safely.
        check_security now returns error='' on safe, preventing stale errors.
        """
        app = unsafe_agent.get_workflow()
        inputs = {"question": "Drop the table", "retry_count": 0, "error": ""}
        node_names = []
        for event in app.stream(inputs):
            node_names.extend(event.keys())
        assert "executor" not in node_names
        assert "guardian" in node_names
        assert "summarizer" in node_names

    def test_security_block_invoke_returns_result(self, unsafe_agent):
        """
        FIX VERIFICATION (Phase 2: C-01 — now fixed):
        invoke() on security-block path must complete and return a result.
        """
        app = unsafe_agent.get_workflow()
        result = app.invoke({"question": "Drop it", "retry_count": 0, "error": ""})
        assert result["sql_safe"] is False
        assert "DROP" in result["error"]
        assert isinstance(result["result"], str)


class TestWorkflowRetryPath:
    """Integration test: SQL execution failure triggers retry."""

    @pytest.fixture
    def retry_agent(self, seeded_db):
        """
        Agent whose LLM:
        1. First returns invalid SQL (nonexistent table)
        2. On retry returns valid SQL
        3. Then summarizes
        Total: 3 LLM calls
        """
        mock_llm = MagicMock()
        responses = [
            MagicMock(content="SELECT * FROM nonexistent_table"),
            MagicMock(content="SELECT * FROM employees"),
            MagicMock(content="Here are all 5 employees."),
        ]
        mock_llm.invoke.side_effect = responses
        return SQLAgent(mock_llm)

    def test_writer_called_at_least_twice(self, retry_agent):
        """Writer must be invoked at least twice (initial + retry)."""
        app = retry_agent.get_workflow()
        inputs = {"question": "Show employees", "retry_count": 0, "error": ""}
        node_names = []
        for event in app.stream(inputs):
            node_names.extend(event.keys())
        assert node_names.count("writer") >= 2

    def test_retry_eventually_succeeds(self, retry_agent):
        """After retry, final result must be the summary."""
        app = retry_agent.get_workflow()
        result = app.invoke({"question": "Show employees", "retry_count": 0, "error": ""})
        assert result["result"] == "Here are all 5 employees."

    def test_retry_count_incremented(self, retry_agent):
        """retry_count must be > 1 after retries."""
        app = retry_agent.get_workflow()
        result = app.invoke({"question": "Show employees", "retry_count": 0, "error": ""})
        assert result["retry_count"] >= 2


class TestWorkflowRetryExhaustion:
    """Integration test: all retries exhausted → summarizer with error."""

    @pytest.fixture
    def exhausting_agent(self, seeded_db):
        """
        Agent whose LLM always returns SQL for a nonexistent table.
        After 3 retries, should route to summarizer.
        LLM calls: 3 write_sql attempts + 1 summarize = 4 total
        """
        mock_llm = MagicMock()
        responses = [
            MagicMock(content="SELECT * FROM bad_table"),     # attempt 1
            MagicMock(content="SELECT * FROM bad_table2"),    # attempt 2
            MagicMock(content="SELECT * FROM bad_table3"),    # attempt 3
            MagicMock(content="I was unable to answer your question."),  # summarize
        ]
        mock_llm.invoke.side_effect = responses
        return SQLAgent(mock_llm)

    def test_stops_after_max_retries(self, exhausting_agent):
        """
        FIX VERIFICATION (Phase 2: C-01 — now fixed):
        After exhausting retries, route_after_execute sends to summarizer.
        execute_sql error path now returns {result: '', error: str(e)}.
        summarize_result now uses state.get() safely.
        """
        app = exhausting_agent.get_workflow()
        result = app.invoke({"question": "Bad query", "retry_count": 0, "error": ""})
        assert result["retry_count"] >= 3
        assert isinstance(result["result"], str)
        assert len(result["result"]) > 0
