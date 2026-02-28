"""
Tests for SQLAgent.summarize_result() — LLM-based result summarization.
Target: backend.py lines 148-166.

Coverage intent:
- LLM invoked exactly once
- Prompt includes question, sql_query, and result
- Return contract: {result: <str>}
- Returns only 'result' key
"""
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage


class TestSummarizeResultLlmInteraction:
    """Verify LLM invocation behavior."""

    def test_calls_llm_invoke_once(self, agent, mock_llm, make_state):
        agent.summarize_result(make_state(
            question="Total salary?",
            sql_query="SELECT SUM(salary) FROM employees",
            result="[(503000.0,)]"
        ))
        assert mock_llm.invoke.call_count == 1

    def test_invoked_with_human_message(self, agent, mock_llm, make_state):
        agent.summarize_result(make_state(result="[(1,)]"))
        args = mock_llm.invoke.call_args[0][0]
        assert len(args) == 1
        assert isinstance(args[0], HumanMessage)


class TestSummarizeResultPromptContent:
    """Verify the prompt template includes all required context."""

    def test_prompt_includes_question(self, agent, mock_llm, make_state):
        """backend.py:158 — User Question in prompt."""
        agent.summarize_result(make_state(question="Who earns the most?", result="test"))
        prompt = mock_llm.invoke.call_args[0][0][0].content
        assert "Who earns the most?" in prompt

    def test_prompt_includes_sql(self, agent, mock_llm, make_state):
        """backend.py:159 — SQL Used in prompt."""
        agent.summarize_result(make_state(
            sql_query="SELECT MAX(salary) FROM employees",
            result="test"
        ))
        prompt = mock_llm.invoke.call_args[0][0][0].content
        assert "SELECT MAX(salary) FROM employees" in prompt

    def test_prompt_includes_data(self, agent, mock_llm, make_state):
        """backend.py:160 — Data Found in prompt."""
        agent.summarize_result(make_state(result="[(120000.0, 'Alice')]"))
        prompt = mock_llm.invoke.call_args[0][0][0].content
        assert "[(120000.0, 'Alice')]" in prompt


class TestSummarizeResultReturn:
    """Verify the returned dict structure."""

    def test_returns_result_key(self, agent, mock_llm, make_state):
        mock_llm.invoke.return_value.content = "The total salary is $503,000."
        result = agent.summarize_result(make_state(result="data"))
        assert result["result"] == "The total salary is $503,000."

    def test_returns_only_result_key(self, agent, mock_llm, make_state):
        result = agent.summarize_result(make_state(result="data"))
        assert list(result.keys()) == ["result"]

    def test_passes_through_llm_content(self, agent, mock_llm, make_state):
        """Return value is whatever LLM.content returns, unmodified."""
        mock_llm.invoke.return_value.content = "Custom answer with *markdown*"
        result = agent.summarize_result(make_state(result="data"))
        assert result["result"] == "Custom answer with *markdown*"
