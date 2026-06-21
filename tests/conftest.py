"""Shared pytest fixtures and helpers."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nl2sql_agent.config import reset_settings_cache
from nl2sql_agent.db import Database


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests don't leak env-var settings between runs."""
    # Clear any cached settings
    reset_settings_cache()
    # Make sure no API keys are picked up from the environment.
    for var in (
        "NL2SQL_PROVIDER", "NL2SQL_MODEL",
        "OPENAI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    reset_settings_cache()


@pytest.fixture
def tmp_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """CWD + db path inside tmp so tests don't pollute the real DB."""
    monkeypatch.chdir(tmp_path)
    return tmp_path / "company.db"


@pytest.fixture
def seeded_db(tmp_db_path: Path) -> Database:
    """Database instance with the demo schema and seed data."""
    db = Database(tmp_db_path)
    db.ensure_schema(seed=True)
    return db


@pytest.fixture
def empty_db(tmp_db_path: Path) -> Database:
    """Database with schema only, no seed data."""
    db = Database(tmp_db_path)
    db.ensure_schema(seed=False)
    return db


@pytest.fixture
def mock_llm() -> MagicMock:
    """Mock LLM whose ``invoke`` returns ``content="SELECT 1"`` by default."""
    llm = MagicMock()
    response = MagicMock()
    response.content = "SELECT 1"
    llm.invoke.return_value = response
    return llm


@pytest.fixture
def make_state():
    """Factory for :class:`AgentState`-compatible dicts with safe defaults."""
    from nl2sql_agent.agent import AgentState

    def _make(**overrides) -> AgentState:
        defaults: AgentState = {
            "question": "",
            "schema": "",
            "sql_query": "",
            "error": "",
            "retry_count": 0,
            "max_retries": 3,
        }
        defaults.update(overrides)  # type: ignore[typeddict-item]
        return defaults

    return _make


@pytest.fixture
def example_questions() -> Iterator[str]:
    """A small set of canonical NL2SQL questions used in integration tests."""
    yield from iter(
        [
            "How many employees are in each department?",
            "What is the total salary in Engineering?",
            "Who is the highest-paid employee overall?",
        ]
    )
