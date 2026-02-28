"""
Shared fixtures for the SQL Agent test suite.

Provides:
- Database isolation via tmp_path + monkeypatch.chdir
- Mock LLM for deterministic testing
- Pre-built SQLAgent instances
- State factory for creating AgentState dicts
"""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def tmp_db_dir(tmp_path, monkeypatch):
    """
    Redirect CWD to tmp_path so all relative file operations
    (e.g., sqlite3.connect('company.db')) resolve inside the temp directory.
    Prevents polluting the real workspace.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def seeded_db(tmp_db_dir):
    """
    Create and seed the company database in a temp directory.
    Calls backend.setup_db() to create tables and insert sample data.
    Returns the tmp directory path.
    """
    from backend import setup_db
    setup_db()
    return tmp_db_dir


@pytest.fixture
def mock_llm():
    """
    Mock LLM that returns a response with .content = 'SELECT 1' by default.
    Tests can override via mock_llm.invoke.return_value.content = "..."
    or mock_llm.invoke.side_effect = [resp1, resp2, ...]
    """
    llm = MagicMock()
    response = MagicMock()
    response.content = "SELECT 1"
    llm.invoke.return_value = response
    return llm


@pytest.fixture
def agent(seeded_db, mock_llm):
    """
    SQLAgent instance with a mock LLM and a seeded temp database.
    The database is in an isolated tmp directory.
    """
    from backend import SQLAgent
    return SQLAgent(mock_llm)


@pytest.fixture
def make_state():
    """
    Factory fixture for creating AgentState-compatible dicts.
    All 7 keys are populated with safe defaults.
    Override any key via keyword arguments.

    Usage:
        state = make_state(question="Who earns the most?", sql_query="SELECT ...")
    """
    def _make(**overrides):
        defaults = {
            "question": "",
            "schema": "",
            "sql_query": "",
            "sql_safe": False,
            "result": "",
            "error": "",
            "retry_count": 0,
        }
        defaults.update(overrides)
        return defaults
    return _make
