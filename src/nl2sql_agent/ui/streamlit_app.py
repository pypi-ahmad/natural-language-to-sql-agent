"""Approval-first Streamlit interface for the NL2SQL agent."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import streamlit as st

from nl2sql_agent.agent import AgentState, NL2SQLAgent
from nl2sql_agent.config import Provider, Settings, get_settings
from nl2sql_agent.db import Database, DatabaseBackend, DatabaseError, PostgresDatabase
from nl2sql_agent.llm import (
    DEFAULT_PRICING_RULES,
    LLMProviderError,
    PricingUnavailableError,
    RequestMode,
    UsageRecord,
    build_chat_model,
    calculate_cost,
    effective_pricing_rule,
    list_models,
)
from nl2sql_agent.persistence import StateStore
from nl2sql_agent.ui.components import render_chat_history, render_sidebar
from nl2sql_agent.ui.database_upload import (
    SQLiteUploadError,
    save_sqlite_upload,
    validate_sqlite_upload,
    validate_upload_metadata,
)
from nl2sql_agent.utils import configure_logging, get_logger

logger = get_logger(__name__)


def _init_session_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("pending_query", None)
    st.session_state.setdefault("active_context", None)
    st.session_state.setdefault("current_session_id", None)
    if "upload_workspace" not in st.session_state:
        st.session_state.upload_workspace = tempfile.TemporaryDirectory(prefix="nl2sql-upload-")


@st.cache_resource
def _demo_database(
    path: str,
    timeout_seconds: float,
    max_rows: int,
    max_vm_steps: int,
    seed: bool,
) -> Database:
    db = Database(
        path,
        timeout_seconds=timeout_seconds,
        max_rows=max_rows,
        max_vm_steps=max_vm_steps,
    )
    db.ensure_schema(seed=seed)
    return db


@st.cache_resource
def _state_store(path: str) -> StateStore:
    return StateStore(path)


def _runtime_settings(
    settings: Settings,
    *,
    provider: Provider,
    model: str,
    api_key: str | None,
) -> Settings:
    runtime = settings.model_copy(deep=True)
    runtime.provider = provider
    runtime.model = model
    if provider == "openai":
        runtime.openai_api_key = api_key
    elif provider == "gemini":
        runtime.google_api_key = api_key
    elif provider == "anthropic":
        runtime.anthropic_api_key = api_key
    elif provider == "huggingface":
        runtime.hf_token = api_key
    elif provider == "xai":
        runtime.xai_api_key = api_key
    return runtime


def _resolve_database(
    settings: Settings,
    data_source: str,
) -> tuple[DatabaseBackend, str, str, bool] | None:
    if data_source == "Demo":
        db = _demo_database(
            str(settings.db_path),
            settings.db_query_timeout_seconds,
            settings.db_max_rows,
            settings.db_max_vm_steps,
            settings.db_seed,
        )
        return db, settings.db_path.name, "demo", True

    if data_source == "PostgreSQL":
        if settings.postgres_dsn is None:
            st.sidebar.error("PostgreSQL is not configured by the operator.")
            return None
        try:
            db = PostgresDatabase(
                settings.postgres_dsn.get_secret_value(),
                schema=settings.postgres_schema,
                timeout_seconds=settings.db_query_timeout_seconds,
                lock_timeout_seconds=settings.db_lock_timeout_seconds,
                max_rows=settings.db_max_rows,
            )
            db.list_tables()
        except (DatabaseError, ValueError):
            st.sidebar.error(
                "The PostgreSQL connection is unavailable or does not use a safe read-only role.",
                icon=":material/error:",
            )
            return None
        return db, "PostgreSQL", db.fingerprint, False

    uploaded = st.sidebar.file_uploader(
        "SQLite database",
        type=["db", "sqlite", "sqlite3"],
        accept_multiple_files=False,
        help="The file stays in this browser session and is queried read-only.",
    )
    if uploaded is None:
        st.sidebar.info("Upload a SQLite database to continue.")
        return None
    try:
        validate_upload_metadata(
            uploaded.name,
            size=uploaded.size,
            max_mb=settings.db_upload_max_mb,
        )
        data = uploaded.getvalue()
        digest = validate_sqlite_upload(
            uploaded.name,
            data,
            max_mb=settings.db_upload_max_mb,
        )
        workspace = Path(st.session_state.upload_workspace.name)
        path = save_sqlite_upload(workspace, data, digest)
        db = Database(
            path,
            timeout_seconds=settings.db_query_timeout_seconds,
            max_rows=settings.db_max_rows,
            max_vm_steps=settings.db_max_vm_steps,
        )
        db.list_tables()
    except (SQLiteUploadError, sqlite3.Error) as exc:
        st.sidebar.error(str(exc), icon=":material/error:")
        return None
    return db, Path(uploaded.name).name, digest, False


def _build_agent(
    runtime: Settings,
    database: DatabaseBackend,
    *,
    allowed_tables: list[str],
    include_sample_values: bool,
    fingerprint: str,
) -> NL2SQLAgent:
    llm = build_chat_model(settings=runtime)
    return NL2SQLAgent(
        llm,
        settings=runtime,
        database=database,
        allowed_tables=allowed_tables,
        include_sample_values=include_sample_values,
        db_fingerprint=fingerprint,
    )


def _history_message(state: dict[str, Any], *, model: str) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": str(state.get("final_answer", "")),
        "sql": str(state.get("sql_query", "")),
        "columns": list(state.get("columns", [])),
        "raw_rows": list(state.get("raw_rows", [])),
        "error": str(state.get("error", "")),
        "csv_data": str(state.get("csv_data", "")),
        "trace": list(state.get("trace", [])),
        "run_id": str(state.get("run_id", "result")),
        "model": model,
        "token_usage": dict(state.get("token_usage", {})),
        "usage_records": list(state.get("usage_records", [])),
        "cost_breakdown": dict(state.get("cost_breakdown", {})),
        "query_plan": dict(state.get("query_plan", {})),
        "query_metrics": dict(state.get("query_metrics", {})),
        "warnings": list(state.get("warnings", [])),
        "approved": bool(state.get("approved", False)),
        "result_not_stored": False,
    }


def _apply_cost(
    state: dict[str, Any],
    *,
    model: str,
    store: StateStore | None,
) -> None:
    rules = store.list_pricing_rules() if store is not None else list(DEFAULT_PRICING_RULES)
    calculated_at = datetime.now(UTC)
    rule = effective_pricing_rule(rules, model, calculated_at)
    warnings = list(state.get("warnings", []))
    if rule is None:
        warnings.append(f"No effective pricing is configured for {model}; this run is unpriced.")
        state["warnings"] = list(dict.fromkeys(warnings))
        return
    records = []
    for raw in state.get("usage_records", []):
        records.append(
            UsageRecord(
                stage=str(raw.get("stage", "model")),
                input_tokens=int(raw.get("input_tokens", 0)),
                output_tokens=int(raw.get("output_tokens", 0)),
                cache_read_tokens=int(raw.get("cache_read_tokens", 0)),
                cache_creation_tokens=int(raw.get("cache_creation_tokens", 0)),
                request_mode=cast(RequestMode, raw.get("request_mode", "standard")),
            )
        )
    try:
        state["cost_breakdown"] = calculate_cost(
            rule, records, calculated_at=calculated_at
        ).to_dict()
    except PricingUnavailableError as exc:
        warnings.append(str(exc) + "; this run is unpriced.")
    state["warnings"] = list(dict.fromkeys(warnings))


def _budget_alerts(
    store: StateStore | None,
    session_id: str | None,
    state: dict[str, Any],
) -> None:
    if store is None or session_id is None:
        return
    current = Decimal(str((state.get("cost_breakdown") or {}).get("total_cost", "0")))
    if current <= 0:
        return
    month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    existing_session = store.cost_total(session_id=session_id)
    existing_month = store.cost_total(start_at=month_start.isoformat())
    warnings = list(state.get("warnings", []))
    for label, total, limit in (
        (
            "Session budget",
            existing_session + current,
            store.get_preference_decimal("session_budget_usd"),
        ),
        (
            "Monthly budget",
            existing_month + current,
            store.get_preference_decimal("monthly_budget_usd"),
        ),
    ):
        if limit <= 0:
            continue
        ratio = total / limit
        if ratio >= 1:
            warnings.append(f"{label} reached 100% (${total:.4f} of ${limit:.2f}).")
        elif ratio >= Decimal("0.8"):
            warnings.append(f"{label} reached 80% (${total:.4f} of ${limit:.2f}).")
    state["warnings"] = list(dict.fromkeys(warnings))


def _persist_result(
    store: StateStore | None,
    session_id: str | None,
    state: dict[str, Any],
    *,
    provider: str,
    model: str,
    database: DatabaseBackend,
    fingerprint: str,
) -> None:
    if store is None or session_id is None:
        return
    message = _history_message(state, model=model)
    persisted_message = dict(message)
    persisted_message["result_not_stored"] = bool(state.get("approved"))
    if not state.get("approved"):
        persisted_message.pop("sql", None)
    store.append_message(session_id, "assistant", message["content"], persisted_message)
    store.save_run(
        session_id,
        state,
        provider=provider,
        model=model,
        database_kind=database.kind,
        database_fingerprint=fingerprint,
        approved=bool(state.get("approved", False)),
    )


def _ensure_session(
    store: StateStore | None,
    *,
    context: tuple[str, str, str],
    database: DatabaseBackend,
    database_name: str,
    fingerprint: str,
    provider: str,
    model: str,
) -> str | None:
    if st.session_state.active_context == context and st.session_state.current_session_id:
        return cast(str, st.session_state.current_session_id)
    st.session_state.messages = []
    st.session_state.pending_query = None
    st.session_state.active_context = context
    if store is None:
        st.session_state.current_session_id = None
        return None
    session_id = store.create_session(
        database_kind=database.kind,
        database_label=database_name,
        database_fingerprint=fingerprint,
        provider=provider,
        model=model,
    )
    st.session_state.current_session_id = session_id
    return session_id


def _stage_text(node: str, update: dict[str, Any]) -> str:
    if node == "fetch_schema":
        return "Relevant schema selected."
    if node == "writer":
        return f"SQL draft {update.get('retry_count', 1)} generated."
    if node == "guardian" and update.get("error"):
        return "SQL blocked; requesting a corrected draft."
    if node == "guardian":
        return "SQL validated and preflighted."
    return node.replace("_", " ").capitalize()


def _chat_page() -> None:
    settings = get_settings()
    store = cast(StateStore | None, st.session_state.get("state_store"))
    cfg = render_sidebar(postgres_enabled=settings.postgres_dsn is not None)
    provider = cast(Provider, cfg["provider"])
    model = str(cfg["model"])
    api_key = cast(str | None, cfg["api_key"])
    data_source = str(cfg["data_source"] or "Demo")

    if st.session_state.pop(f"refresh_trigger_{provider}", False):
        with st.spinner(f"Fetching {provider} models…"):
            fetched = list_models(
                provider,
                api_key=api_key,
                base_url=settings.ollama_base_url if provider == "ollama" else None,
            )
        if fetched:
            st.session_state[f"models_{provider}"] = fetched
            st.sidebar.success(f"Found {len(fetched)} models.")
        else:
            st.sidebar.warning("No models returned. Check the connection or API key.")

    resolved = _resolve_database(settings, data_source)
    st.title("Natural language to SQL")
    if resolved is None:
        st.caption(f"Provider: **{provider}** · Model: **{model}**")
        render_chat_history()
        return
    database, database_name, fingerprint, demo_samples = resolved
    try:
        tables = list(database.list_tables())
    except (sqlite3.Error, DatabaseError):
        st.error("The database catalog could not be read.", icon=":material/error:")
        return
    if not tables:
        st.error("The database has no ordinary user tables.", icon=":material/error:")
        return

    allowed_tables = st.sidebar.multiselect(
        "Allowed tables",
        options=tables,
        default=tables,
        key=f"allowed_{fingerprint}",
    )
    include_sample_values = demo_samples
    if data_source == "Upload":
        include_sample_values = st.sidebar.toggle(
            "Include sample rows in prompts",
            value=False,
            key=f"sample_{fingerprint}",
            help="Off by default to avoid sending uploaded values to the model.",
        )
    else:
        st.sidebar.caption("The demo includes bounded sample rows in prompts.")

    context = (fingerprint, provider, model)
    session_id = _ensure_session(
        store,
        context=context,
        database=database,
        database_name=database_name,
        fingerprint=fingerprint,
        provider=provider,
        model=model,
    )

    st.caption(f"Provider: **{provider}** · Model: **{model}** · Database: **{database_name}**")
    schema_expander = st.expander(
        "Database schema",
        icon=":material/table_chart:",
        on_change="rerun",
    )
    if schema_expander.open:
        with schema_expander:
            st.code(
                database.get_schema_text(allowed_tables=set(allowed_tables)),
                language="text",
            )

    with st.sidebar:
        if st.button("Clear history", icon=":material/delete:", width="stretch"):
            st.session_state.messages = []
            st.session_state.pending_query = None
            st.session_state.current_session_id = None
            st.session_state.active_context = None
            st.rerun()

    render_chat_history()
    runtime = _runtime_settings(
        settings,
        provider=provider,
        model=model,
        api_key=api_key,
    )

    pending = st.session_state.pending_query
    if pending:
        with st.chat_message("assistant"):
            st.info(
                "Review or edit the validated SQL, then run it.",
                icon=":material/edit:",
            )
            edited_sql = st.text_area(
                "SQL preview",
                value=str(pending.get("sql_query", "")),
                height=140,
                key=f"sql_editor_{pending['run_id']}",
            )
            with st.container(horizontal=True):
                run_clicked = st.button(
                    "Run query",
                    type="primary",
                    icon=":material/play_arrow:",
                )
                cancel_clicked = st.button("Cancel", icon=":material/close:")
            if cancel_clicked:
                cancelled = {"role": "assistant", "content": "Query cancelled before execution."}
                st.session_state.messages.append(cancelled)
                if store is not None and session_id is not None:
                    store.append_message(session_id, "assistant", cancelled["content"])
                    store.clear_pending(session_id)
                st.session_state.pending_query = None
                st.rerun()
            if run_clicked:
                try:
                    agent = _build_agent(
                        runtime,
                        database,
                        allowed_tables=allowed_tables,
                        include_sample_values=include_sample_values,
                        fingerprint=fingerprint,
                    )
                    with st.status("Executing approved SQL…", expanded=True) as status:
                        result = agent.execute_prepared(pending, sql_query=edited_sql)
                        status.write("SQL revalidated immediately before execution.")
                        status.update(label="Execution complete", state="complete")
                except LLMProviderError as exc:
                    st.error(str(exc), icon=":material/error:")
                except Exception:
                    logger.exception("Prepared query execution failed")
                    st.error("The query could not be executed.", icon=":material/error:")
                else:
                    result["approved"] = True
                    _apply_cost(result, model=model, store=store)
                    _budget_alerts(store, session_id, result)
                    history = _history_message(result, model=model)
                    st.session_state.messages.append(history)
                    _persist_result(
                        store,
                        session_id,
                        result,
                        provider=provider,
                        model=model,
                        database=database,
                        fingerprint=fingerprint,
                    )
                    if store is not None and session_id is not None:
                        store.clear_pending(session_id)
                    st.session_state.pending_query = None
                    st.rerun()

    if not allowed_tables:
        st.warning("Select at least one allowed table before asking a question.")
        return

    selected_example = None
    if not st.session_state.messages and data_source == "Demo" and not pending:
        suggestions = {
            "Employees by department": "How many employees are in each department?",
            "Engineering salary": "What is the total salary in Engineering?",
            "Highest paid": "Who is the highest-paid employee overall?",
        }
        selected_example = st.pills(
            "Try asking",
            options=list(suggestions),
            label_visibility="collapsed",
        )
        if selected_example:
            selected_example = suggestions[selected_example]

    user_query = st.chat_input(
        "Ask about the data…" if not pending else "Approve or cancel the pending SQL first",
        disabled=bool(pending),
    )
    user_query = user_query or selected_example
    if not user_query or pending:
        return

    st.session_state.messages.append({"role": "user", "content": user_query})
    if store is not None and session_id is not None:
        store.append_message(session_id, "user", user_query)
    try:
        agent = _build_agent(
            runtime,
            database,
            allowed_tables=allowed_tables,
            include_sample_values=include_sample_values,
            fingerprint=fingerprint,
        )
    except LLMProviderError as exc:
        st.error(str(exc), icon=":material/error:")
        return

    final_state: AgentState = {
        "question": user_query,
        "trace": [],
        "token_usage": {},
    }
    with st.chat_message("assistant"):
        status = st.status("Preparing SQL…", expanded=True)
        try:
            for node_name, update in agent.stream_prepare(user_query):
                final_state.update(cast(AgentState, update))
                status.write(_stage_text(node_name, update))
        except Exception:
            logger.exception("SQL preparation failed")
            status.update(label="Preparation failed", state="error")
            if provider == "huggingface":
                st.error(
                    "SQL preparation failed. Verify that the Hugging Face model supports "
                    "the Responses API and medium reasoning."
                )
            else:
                st.error("SQL preparation failed. Check the provider connection.")
            return
        if final_state.get("error"):
            final_state["final_answer"] = (
                "The query was blocked before execution: " + final_state["error"]
            )
            status.update(label="Query blocked", state="error", expanded=False)
            blocked = dict(final_state)
            blocked["approved"] = False
            _apply_cost(blocked, model=model, store=store)
            _budget_alerts(store, session_id, blocked)
            st.session_state.messages.append(_history_message(blocked, model=model))
            _persist_result(
                store,
                session_id,
                blocked,
                provider=provider,
                model=model,
                database=database,
                fingerprint=fingerprint,
            )
        else:
            status.update(label="SQL ready for review", state="complete", expanded=False)
            pending_state = dict(final_state)
            pending_state.update(
                {
                    "provider": provider,
                    "model": model,
                    "database_kind": database.kind,
                    "database_fingerprint": fingerprint,
                }
            )
            st.session_state.pending_query = pending_state
            if store is not None and session_id is not None:
                store.save_pending(session_id, pending_state)
    st.rerun()


def main() -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level, json=settings.log_json)
    st.set_page_config(
        page_title="NL2SQL Agent",
        page_icon=":material/database:",
        layout="wide",
    )
    _init_session_state()
    try:
        st.session_state.state_store = _state_store(str(settings.state_path))
        st.session_state.persistence_error = ""
    except (OSError, sqlite3.Error, RuntimeError):
        logger.exception("Local state store unavailable")
        st.session_state.state_store = None
        st.session_state.persistence_error = (
            "Saved sessions, editable pricing, and historical dashboards are unavailable."
        )
    from nl2sql_agent.ui.pages import costs_page, insights_page, pricing_page, sessions_page

    pages = [
        st.Page(_chat_page, title="Chat", icon=":material/chat:", default=True),
        st.Page(costs_page, title="Costs", icon=":material/payments:"),
        st.Page(sessions_page, title="Sessions", icon=":material/history:"),
        st.Page(insights_page, title="Insights", icon=":material/monitoring:"),
        st.Page(pricing_page, title="Pricing", icon=":material/price_change:"),
    ]
    navigation = st.navigation(pages, position="top")
    if st.session_state.persistence_error:
        st.warning(st.session_state.persistence_error, icon=":material/warning:")
    navigation.run()


if __name__ == "__main__":  # pragma: no cover
    main()
