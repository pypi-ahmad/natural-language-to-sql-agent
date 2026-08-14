"""End-to-end smoke test that requires a running local Ollama instance.

Marked with the ``integration`` pytest marker; skipped automatically when
Ollama is unreachable. This is the only test in the suite that hits an
external service.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

import pytest

from nl2sql_agent.agent import NL2SQLAgent
from nl2sql_agent.config import Settings, get_settings, reset_settings_cache
from nl2sql_agent.db import Database
from nl2sql_agent.llm import build_chat_model, list_models

OLLAMA_URL = os.environ.get("NL2SQL_OLLAMA_BASE_URL", "http://localhost:11434")
# Use the smallest viable local model by default to keep the test fast.
TEST_MODEL = os.environ.get("NL2SQL_TEST_MODEL", "qwen3.5:0.8b")


def _ollama_alive() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def ollama_model() -> Iterator[str]:
    """Yield a model name, skipping the test if Ollama is unreachable."""
    if not _ollama_alive():
        pytest.skip(f"Ollama not reachable at {OLLAMA_URL}")
    models = list_models("ollama", base_url=OLLAMA_URL)
    chosen = TEST_MODEL if TEST_MODEL in models else (models[0] if models else None)
    if not chosen:
        pytest.skip("No Ollama models available locally")
    return chosen


@pytest.fixture
def live_settings(tmp_path, monkeypatch, ollama_model) -> Settings:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NL2SQL_PROVIDER", "ollama")
    monkeypatch.setenv("NL2SQL_MODEL", ollama_model)
    monkeypatch.setenv("NL2SQL_OLLAMA_BASE_URL", OLLAMA_URL)
    monkeypatch.setenv("NL2SQL_DB_PATH", str(tmp_path / "company.db"))
    monkeypatch.setenv("NL2SQL_LLM_TEMPERATURE", "0")
    reset_settings_cache()
    return get_settings()


@pytest.fixture
def live_llm(live_settings):
    """Close both clients created eagerly by LangChain's Ollama adapter."""
    llm = build_chat_model(live_settings)
    try:
        yield llm
    finally:
        llm._client.close()
        asyncio.run(llm._async_client.close())


class TestOllamaIntegration:
    def test_count_employees(self, live_settings, live_llm, tmp_path):
        agent = NL2SQLAgent(live_llm, settings=live_settings)
        result = agent.run("How many employees are there?")
        assert "final_answer" in result
        assert result["error"] == ""
        # Should return 10 employees (the seed count)
        assert "10" in result.get("final_answer", "") or "10" in result.get("result", "")

    def test_total_engineering_salary(self, live_settings, live_llm, tmp_path):
        agent = NL2SQLAgent(live_llm, settings=live_settings)
        result = agent.run("What is the total salary of all Engineering employees?")
        assert result["error"] == ""
        # Engineering = 101, has Alice(120k)+Charlie(115k)+Frank(142.5k) = 377.5k
        answer = result.get("final_answer", "") + result.get("result", "")
        assert "377" in answer or "377.5" in answer

    def test_guardian_blocks_dangerous_sql(self, live_settings, tmp_path):
        # Force the LLM to produce a DROP and verify the guardian catches it.
        from langchain_core.messages import AIMessage

        class FakeLLM:
            def invoke(self, messages):
                return AIMessage(content="DROP TABLE employees")

        agent = NL2SQLAgent(FakeLLM(), settings=live_settings)
        result = agent.run("destroy everything")
        assert "error" in result
        assert result["error"] != ""
        assert "validation" in result["error"].lower() or "forbidden" in result["error"].lower()
        # Table must still exist.
        db = Database(tmp_path / "company.db")
        count = db.execute("SELECT COUNT(*) FROM employees").rows[0][0]
        assert count == 10
