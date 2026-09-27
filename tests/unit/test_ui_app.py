"""Streamlit smoke tests for navigation and persistent configuration pages."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from nl2sql_agent.config import Settings, reset_settings_cache
from nl2sql_agent.ui import streamlit_app
from nl2sql_agent.ui.streamlit_app import _runtime_settings


def test_in_memory_clarification_survives_rerun_without_persistence(monkeypatch):
    pending = {"question": "How is performance?"}
    state = SimpleNamespace(
        active_context=("demo",),
        current_session_id=None,
        messages=[{"role": "user", "content": "How is performance?"}],
        pending_clarification=pending,
        pending_query=None,
    )
    monkeypatch.setattr(streamlit_app.st, "session_state", state)
    assert (
        streamlit_app._ensure_session(
            None,
            context=("demo",),
            database=SimpleNamespace(kind="sqlite"),
            database_name="demo",
            fingerprint="demo",
            provider="ollama",
            model="demo",
        )
        is None
    )
    assert state.pending_clarification == pending
    assert len(state.messages) == 1


def test_stage_text_does_not_promise_retry_after_policy_block():
    assert "nothing was executed" in streamlit_app._stage_text(
        "guardian", {"outcome": "policy_blocked", "error": "blocked"}
    )


def test_runtime_settings_assigns_agnes_key():
    settings = Settings(_env_file=None)
    runtime = _runtime_settings(
        settings,
        provider="agnes",
        model="agnes-2.5-flash",
        api_key="agnes-test",  # pragma: allowlist secret
    )
    assert runtime.provider == "agnes"
    assert runtime.model == "agnes-2.5-flash"
    assert runtime.agnes_api_key == "agnes-test"  # pragma: allowlist secret


def test_main_app_renders_chat_navigation(tmp_path, monkeypatch):
    monkeypatch.setenv("NL2SQL_STATE_PATH", str(tmp_path / "state.sqlite3"))
    monkeypatch.setenv("NL2SQL_DB_PATH", str(tmp_path / "company.sqlite3"))
    reset_settings_cache()
    script = Path(__file__).parents[2] / "src/nl2sql_agent/ui/streamlit_app.py"
    app = AppTest.from_file(script).run(timeout=60)
    assert not app.exception
    assert app.title[0].value == "Natural language to SQL"
    assert app.chat_input[0].placeholder.startswith("Ask about the data")
    app.session_state["upload_workspace"].cleanup()


def test_pricing_page_renders_editor_and_disabled_budgets(tmp_path):
    path = repr(str(tmp_path / "state.sqlite3"))
    app = AppTest.from_string(
        f"""
import streamlit as st
from nl2sql_agent.persistence import StateStore
from nl2sql_agent.ui.pages import pricing_page
st.session_state.state_store = StateStore({path})
pricing_page()
"""
    ).run(timeout=60)
    assert not app.exception
    assert app.title[0].value == "Pricing configuration"
    assert [item.value for item in app.number_input] == [0.0, 0.0]
