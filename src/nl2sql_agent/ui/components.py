"""Streamlit UI helpers (separated from the entry point for testability)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import streamlit as st

from ..config import Provider, env_var_for, env_var_value


def render_sidebar(
    *,
    providers: Iterable[Provider] = ("ollama", "gemini", "openai", "anthropic"),
) -> dict[str, str | None]:
    """Render the sidebar and return the user's selections.

    Returns a dict with keys: ``provider``, ``model``, ``api_key``,
    ``ollama_base_url``. The caller is expected to build the LLM and
    agent from this.
    """
    providers = list(providers)
    st.sidebar.title("Agent Configuration")

    provider_labels = {p: p.title() for p in providers}
    default_idx = providers.index("ollama") if "ollama" in providers else 0
    selected_label = st.sidebar.selectbox(
        "LLM provider",
        options=[provider_labels[p] for p in providers],
        index=default_idx,
        help="Local Ollama is the default and works without any API key.",
    )
    provider: Provider = next(
        p for p, label in provider_labels.items() if label == selected_label
    )

    ollama_base_url = st.sidebar.text_input(
        "Ollama base URL",
        value=st.session_state.get("ollama_base_url", "http://localhost:11434"),
        help="Where your local Ollama server is listening.",
        disabled=(provider != "ollama"),
    )

    # API key handling
    env_var = env_var_for(provider)
    api_key: str | None = None
    if env_var:
        sys_key = env_var_value(env_var)
        if sys_key:
            st.sidebar.success(f"Loaded {env_var} from environment")
            if st.sidebar.checkbox("Override API key", value=False, key=f"override_{provider}"):
                api_key = st.sidebar.text_input(
                    f"{env_var}",
                    type="password",
                    key=f"key_{provider}",
                )
            else:
                api_key = sys_key
        else:
            api_key = st.sidebar.text_input(
                f"Enter {env_var}",
                type="password",
                key=f"key_{provider}",
                help=f"Stored in environment variable {env_var} if not entered here.",
            )
            if not api_key:
                st.sidebar.warning(f"{env_var} required for {selected_label}.")

    # Model selection
    models: list[str] = list(
        st.session_state.get(f"models_{provider}", []) or [],
    )
    if st.sidebar.button("Refresh model list", key=f"refresh_{provider}"):
        st.session_state[f"refresh_trigger_{provider}"] = True
    if not models:
        # Sensible defaults until the user fetches.
        models = list(_default_models(provider))

    model = st.sidebar.selectbox(
        "Model",
        options=models,
        index=0,
        key=f"model_{provider}",
    )

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
        "ollama_base_url": ollama_base_url,
    }


def _default_models(provider: Provider) -> Iterable[str]:
    if provider == "ollama":
        return ["qwen3.5:4b", "qwen3.5:2b", "qwen3.5:0.8b", "llama3.1"]
    if provider == "gemini":
        return ["gemini-1.5-flash", "gemini-1.5-pro"]
    if provider == "openai":
        return ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
    if provider == "anthropic":
        return ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"]
    return []


def render_chat_history() -> None:
    """Render the chat history from ``st.session_state.messages``."""
    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            extra = msg.get("sql")
            if extra:
                with st.expander("SQL used"):
                    st.code(extra, language="sql")


def render_run_steps(placeholder: Any) -> Any:
    """Create a status expander that the caller will write to."""
    return placeholder.status("Thinking…", expanded=True)


def render_run_result(
    *,
    final_answer: str,
    sql_query: str,
    columns: list[str] | None,
    raw_rows: list[tuple[object, ...]] | None,
    error: str = "",
) -> None:
    """Render the final answer, plus SQL and a small data preview."""
    if error and not final_answer:
        st.error(error)
        return
    if final_answer:
        st.markdown(final_answer)
    with st.expander("Generated SQL", expanded=False):
        st.code(sql_query or "(no SQL generated)", language="sql")
    if columns and raw_rows is not None:
        try:
            import pandas as pd

            df = pd.DataFrame(raw_rows, columns=columns)
            with st.expander(
                f"Raw results ({len(raw_rows)} row{'s' if len(raw_rows) != 1 else ''})",
                expanded=False,
            ):
                st.dataframe(df, use_container_width=True)
        except ImportError:  # pragma: no cover - pandas is in dev only
            st.caption("(install pandas to preview raw results)")
