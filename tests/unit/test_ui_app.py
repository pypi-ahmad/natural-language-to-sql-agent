"""Streamlit smoke tests for navigation and persistent configuration pages."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from nl2sql_agent.config import reset_settings_cache


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
