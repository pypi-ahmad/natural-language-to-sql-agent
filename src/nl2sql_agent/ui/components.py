"""Streamlit UI helpers (separated from the entry point for testability)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import streamlit as st

from ..config import Provider, env_var_for, env_var_value, supported_models_for
from ..llm.pricing import MODEL_PRICING, estimate_model_cost


def render_sidebar(
    *,
    providers: Iterable[Provider] = (
        "ollama",
        "huggingface",
        "openai",
        "anthropic",
        "gemini",
        "xai",
    ),
) -> dict[str, Any]:
    """Render the sidebar and return the user's selections.

    The caller is expected to build the LLM and agent from this.
    """
    providers = list(providers)
    st.sidebar.title("Agent settings")

    data_source = st.sidebar.segmented_control(
        "Database",
        options=["Demo", "Upload"],
        default="Demo",
        key="data_source",
    )

    display_names = {
        "ollama": "Ollama",
        "huggingface": "Hugging Face",
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "gemini": "Gemini",
        "xai": "xAI",
    }
    provider_labels = {p: display_names[p] for p in providers}
    default_idx = providers.index("ollama") if "ollama" in providers else 0
    selected_label = st.sidebar.selectbox(
        "LLM provider",
        options=[provider_labels[p] for p in providers],
        index=default_idx,
        help="Local Ollama is the default and works without any API key.",
    )
    provider: Provider = next(p for p, label in provider_labels.items() if label == selected_label)

    # API key handling
    env_var = env_var_for(provider)
    api_key: str | None = None
    if env_var:
        sys_key = env_var_value(env_var)
        if sys_key:
            st.sidebar.success(f"Loaded {env_var} from environment")
            if st.sidebar.toggle("Override API key", value=False, key=f"override_{provider}"):
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
    models: list[str] = []
    if provider == "ollama":
        models = list(st.session_state.get("models_ollama", []) or [])
        if st.sidebar.button("Refresh model list", key="refresh_ollama"):
            st.session_state["refresh_trigger_ollama"] = True
    if not models:
        models = list(_default_models(provider))

    model = st.sidebar.selectbox(
        "Model",
        options=models,
        index=0,
        key=f"model_{provider}",
        accept_new_options=provider == "huggingface",
        placeholder=(
            "Select or enter namespace/model[:routing-policy]"
            if provider == "huggingface"
            else None
        ),
    )

    return {
        "data_source": data_source,
        "provider": provider,
        "model": model,
        "api_key": api_key,
    }


def _default_models(provider: Provider) -> Iterable[str]:
    return supported_models_for(provider)


def render_chat_history() -> None:
    """Render the chat history from ``st.session_state.messages``."""
    for msg in st.session_state.get("messages", []):
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant" and msg.get("sql") is not None:
                render_run_result(
                    final_answer=str(msg.get("content", "")),
                    sql_query=str(msg.get("sql", "")),
                    columns=list(msg.get("columns", [])),
                    raw_rows=list(msg.get("raw_rows", [])),
                    error=str(msg.get("error", "")),
                    csv_data=str(msg.get("csv_data", "")),
                    trace=list(msg.get("trace", [])),
                    run_id=str(msg.get("run_id", "result")),
                    model=str(msg.get("model", "")),
                    token_usage=dict(msg.get("token_usage", {})),
                )
            else:
                st.markdown(msg["content"])


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
    csv_data: str = "",
    trace: list[dict[str, object]] | None = None,
    run_id: str = "result",
    model: str = "",
    token_usage: dict[str, int] | None = None,
) -> None:
    """Render the final answer, plus SQL and a small data preview."""
    if error:
        st.error(error, icon=":material/error:")
    if final_answer:
        st.markdown(final_answer)
    if token_usage:
        input_tokens = max(int(token_usage.get("input_tokens", 0)), 0)
        output_tokens = max(int(token_usage.get("output_tokens", 0)), 0)
        estimated_cost = estimate_model_cost(model, input_tokens, output_tokens)
        with st.container(horizontal=True):
            st.metric("Input tokens", f"{input_tokens:,}", border=True)
            st.metric("Output tokens", f"{output_tokens:,}", border=True)
            st.metric(
                "Estimated cost",
                f"${estimated_cost:.6f}" if estimated_cost is not None else "Unavailable",
                border=True,
            )
        pricing = MODEL_PRICING.get(model)
        if pricing is not None:
            st.caption(
                f"{pricing.display_name}: ${pricing.input_price:.2f} input / "
                f"${pricing.output_price:.2f} output per 1M tokens. {pricing.details} "
                "Estimate uses standard rates; cache, batch, fast-mode, and long-context "
                "adjustments are not applied."
            )
        else:
            st.caption("No API pricing was supplied for this model.")
    with st.expander("SQL used", icon=":material/code:"):
        st.code(sql_query or "(no SQL generated)", language="sql")
    if columns and raw_rows is not None:
        try:
            import pandas as pd

            df = pd.DataFrame(raw_rows, columns=columns)
            with st.expander(
                f"Raw results ({len(raw_rows)} row{'s' if len(raw_rows) != 1 else ''})",
                expanded=False,
            ):
                st.dataframe(df, width="stretch", hide_index=True)
                if csv_data:
                    st.download_button(
                        "Download CSV",
                        data=csv_data,
                        file_name=f"query-{run_id[:8]}.csv",
                        mime="text/csv",
                        icon=":material/download:",
                        key=f"download_{run_id}",
                    )
        except ImportError:  # pragma: no cover - pandas is in dev only
            st.caption("(install pandas to preview raw results)")
    if trace:
        with st.expander("Run stages", icon=":material/query_stats:"):
            for item in trace:
                raw_duration = item.get("duration_ms", 0.0)
                duration = float(raw_duration) if isinstance(raw_duration, (int, float)) else 0.0
                st.caption(
                    f"{item.get('node', 'stage')}: {item.get('summary', '')} ({duration:.1f} ms)"
                )
