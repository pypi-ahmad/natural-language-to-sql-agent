"""Streamlit entry point for the NL2SQL agent.

Run with::

    streamlit run src/nl2sql_agent/ui/streamlit_app.py

or::

    uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py
"""

from __future__ import annotations

import streamlit as st

from ..config import get_settings
from ..llm import LLMProviderError, build_chat_model, list_models
from ..utils import configure_logging, get_logger
from .components import render_chat_history, render_run_result, render_sidebar

logger = get_logger(__name__)


def _init_session_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("ollama_base_url", "http://localhost:11434")


def main() -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)

    st.set_page_config(
        page_title="NL2SQL Agent",
        page_icon="",
        layout="wide",
    )
    _init_session_state()

    cfg = render_sidebar()

    provider: str | None = cfg["provider"]
    model: str | None = cfg["model"]
    api_key: str | None = cfg["api_key"]
    ollama_base_url: str | None = cfg["ollama_base_url"]

    # Optionally refresh the model list when the user clicks the button.
    if st.session_state.pop(f"refresh_trigger_{provider}", False):
        with st.spinner(f"Fetching {provider} models…"):
            fetched = list_models(
                provider,  # type: ignore[arg-type]
                api_key=api_key,
                base_url=ollama_base_url if provider == "ollama" else None,
            )
        if fetched:
            st.session_state[f"models_{provider}"] = fetched
            st.sidebar.success(f"Found {len(fetched)} models.")
        else:
            st.sidebar.warning("No models returned. Check connection / API key.")

    st.title("Natural Language to SQL")
    st.caption(
        f"Provider: **{provider}** • Model: **{model}** • DB: `{settings.db_path}`"
    )

    render_chat_history()

    # Example questions (clickable)
    st.markdown("##### Try a question")
    cols = st.columns(3)
    examples = [
        "How many employees are in each department?",
        "What is the total salary in Engineering?",
        "Who is the highest-paid employee overall?",
    ]
    for col, ex in zip(cols, examples, strict=False):
        if col.button(ex, key=f"ex_{ex[:10]}"):
            st.session_state["pending_question"] = ex

    user_query = st.chat_input("Ask about the data…")
    pending = st.session_state.pop("pending_question", None)
    if pending and not user_query:
        user_query = pending

    if not user_query:
        return

    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        status = st.status("Thinking…", expanded=True)
        try:
            llm = build_chat_model(
                settings=settings,
                provider=provider,  # type: ignore[arg-type]
                model=model,
            )
        except LLMProviderError as exc:
            status.update(label="Configuration error", state="error")
            st.error(str(exc))
            return

        from ..agent import NL2SQLAgent

        agent = NL2SQLAgent(llm, settings=settings)

        try:
            events = list(agent.stream(user_query))
        except Exception as exc:
            logger.exception("Agent run failed")
            status.update(label="Run failed", state="error")
            st.error(f"{exc.__class__.__name__}: {exc}")
            return

        final_state: dict[str, object] = {}
        for node_name, update in events:
            final_state.update(update)
            if node_name == "fetch_schema":
                status.write("Schema loaded.")
            elif node_name == "writer":
                sql = update.get("sql_query", "")
                status.write(f"SQL drafted: `{sql[:120]}`")
            elif node_name == "guardian":
                if update.get("error"):
                    status.write(f"Security: {update['error']}")
                else:
                    status.write("Security check passed.")
            elif node_name == "executor":
                if update.get("error"):
                    status.write(f"Execution error: `{update['error']}`")
                else:
                    status.write(
                        f"Returned {update.get('row_count', 0)} row(s)."
                    )
            elif node_name == "summarizer":
                status.write("Final answer ready.")

        status.update(label="Done", state="complete", expanded=False)

        answer = str(final_state.get("final_answer") or "(no answer)")
        render_run_result(
            final_answer=answer,
            sql_query=str(final_state.get("sql_query", "")),
            columns=final_state.get("columns") or [],  # type: ignore[arg-type]
            raw_rows=final_state.get("raw_rows") or [],  # type: ignore[arg-type]
            error=str(final_state.get("error", "")),
        )

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "sql": final_state.get("sql_query", ""),
            }
        )


if __name__ == "__main__":  # pragma: no cover
    main()
