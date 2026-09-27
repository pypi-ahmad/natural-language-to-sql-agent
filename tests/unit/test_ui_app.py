"""Streamlit smoke tests for navigation and persistent configuration pages."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
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


def test_clarification_then_explicit_approval_executes_without_summary_call(
    tmp_path, monkeypatch, request
):
    monkeypatch.setenv("NL2SQL_STATE_PATH", str(tmp_path / "state.sqlite3"))
    monkeypatch.setenv("NL2SQL_DB_PATH", str(tmp_path / "company.sqlite3"))
    reset_settings_cache()
    model = MagicMock()
    model.invoke.side_effect = [
        AIMessage(content='{"action":"clarify","message":"All employees or one department?"}'),
        AIMessage(content='{"action":"sql","sql":"SELECT COUNT(*) AS total FROM employees"}'),
    ]
    monkeypatch.setattr(streamlit_app, "build_chat_model", lambda *args, **kwargs: model)
    app = AppTest.from_string("from nl2sql_agent.ui.streamlit_app import main\nmain()").run(
        timeout=60
    )
    request.addfinalizer(lambda: app.session_state["upload_workspace"].cleanup())
    app.chat_input[0].set_value("Count the staff").run(timeout=60)
    assert not app.exception
    assert app.session_state["pending_clarification"]["outcome"] == "needs_clarification"
    assert app.session_state["pending_query"] is None
    app.chat_input[0].set_value("All employees").run(timeout=60)
    assert not app.exception
    assert app.session_state["pending_query"]["outcome"] == "prepared"
    assert not app.session_state["pending_query"]["executed"]
    next(button for button in app.button if button.label == "Run query").click().run(timeout=60)
    assert not app.exception
    assert app.session_state["pending_query"] is None
    assert model.invoke.call_count == 2
    answer = app.session_state["messages"][-1]
    assert answer["sql"]
    assert answer["outcome"] == "executed"
    assert answer["executed"] is True
    assert answer["raw_rows"]
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
