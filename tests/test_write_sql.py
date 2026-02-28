"""
Tests for SQLAgent.write_sql() — LLM-based SQL generation.
Target: backend.py lines 84-109.

Coverage intent:
- LLM invoked exactly once per call
- Prompt includes schema, question, and error
- Return contract: {sql_query, retry_count}
- retry_count increments by 1
- Markdown stripping (```sql, ```)
- Whitespace stripping (.strip())
- LLM called with HumanMessage
"""
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage


class TestWriteSqlLlmInteraction:
    """Verify LLM invocation behavior."""

    def test_calls_llm_invoke_once(self, agent, mock_llm, make_state):
        """write_sql must call self.llm.invoke() exactly once."""
        agent.write_sql(make_state())
        assert mock_llm.invoke.call_count == 1

    def test_invoked_with_human_message(self, agent, mock_llm, make_state):
        """LLM must receive a list with one HumanMessage (backend.py:107)."""
        agent.write_sql(make_state())
        args = mock_llm.invoke.call_args[0][0]
        assert len(args) == 1
        assert isinstance(args[0], HumanMessage)


class TestWriteSqlPromptContent:
    """Verify the prompt template includes all required context."""

    def test_prompt_includes_schema(self, agent, mock_llm, make_state):
        """backend.py:97 — schema is embedded in prompt."""
        agent.write_sql(make_state(schema="Table 'test': id (INTEGER), name (TEXT)"))
        prompt = mock_llm.invoke.call_args[0][0][0].content
        assert "Table 'test': id (INTEGER), name (TEXT)" in prompt

    def test_prompt_includes_question(self, agent, mock_llm, make_state):
        """backend.py:99 — question is embedded in prompt."""
        agent.write_sql(make_state(question="How many employees?"))
        prompt = mock_llm.invoke.call_args[0][0][0].content
        assert "How many employees?" in prompt

    def test_prompt_includes_error_when_present(self, agent, mock_llm, make_state):
        """backend.py:103 — previous error is included for retry."""
        agent.write_sql(make_state(error="no such column: foo"))
        prompt = mock_llm.invoke.call_args[0][0][0].content
        assert "no such column: foo" in prompt

    def test_prompt_includes_empty_error_on_first_try(self, agent, mock_llm, make_state):
        """On first try, error is empty string."""
        agent.write_sql(make_state(error=""))
        prompt = mock_llm.invoke.call_args[0][0][0].content
        # The prompt still includes the error field, just empty
        assert 'If previous error: ""' in prompt


class TestWriteSqlReturnContract:
    """Verify the returned dict structure and values."""

    def test_returns_sql_query_key(self, agent, mock_llm, make_state):
        mock_llm.invoke.return_value.content = "SELECT * FROM employees"
        result = agent.write_sql(make_state())
        assert "sql_query" in result
        assert result["sql_query"] == "SELECT * FROM employees"

    def test_returns_retry_count_key(self, agent, mock_llm, make_state):
        result = agent.write_sql(make_state(retry_count=0))
        assert "retry_count" in result

    def test_increments_retry_from_zero(self, agent, mock_llm, make_state):
        """backend.py:108 — retry_count = state.get('retry_count', 0) + 1."""
        result = agent.write_sql(make_state(retry_count=0))
        assert result["retry_count"] == 1

    def test_increments_retry_from_two(self, agent, mock_llm, make_state):
        result = agent.write_sql(make_state(retry_count=2))
        assert result["retry_count"] == 3

    def test_returns_only_sql_query_and_retry_count(self, agent, mock_llm, make_state):
        """write_sql must return exactly {sql_query, retry_count}."""
        result = agent.write_sql(make_state())
        assert set(result.keys()) == {"sql_query", "retry_count"}


class TestWriteSqlMarkdownStripping:
    """Verify markdown code block markers are removed (backend.py:108)."""

    def test_strips_sql_code_block(self, agent, mock_llm, make_state):
        mock_llm.invoke.return_value.content = "```sql\nSELECT 1\n```"
        result = agent.write_sql(make_state())
        assert "```" not in result["sql_query"]
        assert "SELECT 1" in result["sql_query"]

    def test_strips_plain_code_block(self, agent, mock_llm, make_state):
        mock_llm.invoke.return_value.content = "```\nSELECT 1\n```"
        result = agent.write_sql(make_state())
        assert "```" not in result["sql_query"]

    def test_strips_leading_trailing_whitespace(self, agent, mock_llm, make_state):
        """backend.py:108 — .strip() is applied."""
        mock_llm.invoke.return_value.content = "  SELECT 1  \n"
        result = agent.write_sql(make_state())
        assert result["sql_query"] == "SELECT 1"

    def test_preserves_internal_whitespace(self, agent, mock_llm, make_state):
        mock_llm.invoke.return_value.content = "SELECT name,\n       salary\nFROM employees"
        result = agent.write_sql(make_state())
        assert "SELECT name," in result["sql_query"]
        assert "FROM employees" in result["sql_query"]
