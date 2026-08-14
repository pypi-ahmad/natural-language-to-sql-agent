"""Callable Streamlit pages for persistent dashboards and configuration."""

from __future__ import annotations

from datetime import UTC, datetime, time
from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import uuid4

import pandas as pd
import streamlit as st

from ..llm import PricingRule
from ..persistence import StateStore, cost_rows_to_csv


def _store() -> StateStore:
    store = cast(StateStore | None, st.session_state.get("state_store"))
    if store is None:
        st.error("Local persistence is unavailable.", icon=":material/error:")
        st.stop()
    return store


def costs_page() -> None:
    """Render session and model cost totals with a privacy-safe export."""
    st.title("Cost dashboard")
    st.caption("Estimated API costs from provider-reported tokens and frozen pricing snapshots.")
    store = _store()
    rows = store.cost_rows()
    if not rows:
        st.info("No completed runs have been recorded yet.")
        return
    frame = pd.DataFrame(rows)
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True)
    min_date = frame["created_at"].min().date()
    max_date = frame["created_at"].max().date()
    with st.container(horizontal=True):
        date_range = st.date_input("Date range", value=(min_date, max_date), key="costs_dates")
        models = sorted(frame["model"].dropna().unique().tolist())
        selected_models = st.multiselect("Models", models, default=models, key="costs_models")
    filtered = frame
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start = pd.Timestamp(datetime.combine(date_range[0], time.min, tzinfo=UTC))
        end = pd.Timestamp(datetime.combine(date_range[1], time.max, tzinfo=UTC))
        filtered = filtered[(filtered["created_at"] >= start) & (filtered["created_at"] <= end)]
    filtered = filtered[filtered["model"].isin(selected_models)]
    priced = pd.to_numeric(filtered["estimated_cost_usd"], errors="coerce")
    session_id = st.session_state.get("current_session_id")
    session_cost = pd.to_numeric(
        filtered.loc[filtered["session_id"] == session_id, "estimated_cost_usd"],
        errors="coerce",
    ).sum()
    with st.container(horizontal=True):
        st.metric("Estimated cost", f"${priced.sum():,.6f}", border=True)
        st.metric("Current session", f"${session_cost:,.6f}", border=True)
        st.metric("Input tokens", f"{int(filtered['input_tokens'].sum()):,}", border=True)
        st.metric("Unpriced runs", f"{int(priced.isna().sum()):,}", border=True)
    chart = filtered.assign(cost=priced).dropna(subset=["cost"])
    if not chart.empty:
        daily = (
            chart.assign(day=chart["created_at"].dt.date)
            .groupby("day", as_index=False)["cost"]
            .sum()
            .rename(columns={"day": "Date", "cost": "Estimated cost (USD)"})
        )
        by_model = (
            chart.groupby("model", as_index=False)["cost"]
            .sum()
            .rename(columns={"model": "Model", "cost": "Estimated cost (USD)"})
        )
        left, right = st.columns(2)
        with left.container(border=True):
            st.subheader("Daily cost")
            st.line_chart(daily, x="Date", y="Estimated cost (USD)")
        with right.container(border=True):
            st.subheader("Cost by model")
            st.bar_chart(by_model, x="Model", y="Estimated cost (USD)")
    safe_columns = [
        "created_at",
        "session_title",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "request_mode",
        "estimated_cost_usd",
        "warnings",
    ]
    st.subheader("Recent runs")
    st.dataframe(filtered[safe_columns].head(200), hide_index=True)
    export_rows = filtered.to_dict(orient="records")
    st.download_button(
        "Export cost CSV",
        cost_rows_to_csv(export_rows),
        file_name="nl2sql-costs.csv",
        mime="text/csv",
        icon=":material/download:",
    )


def sessions_page() -> None:
    """Browse, reopen, rename, and delete saved conversations."""
    st.title("Saved sessions")
    st.caption("Conversations and approved SQL are saved locally; raw result rows are not.")
    store = _store()
    sessions = store.list_sessions()
    if not sessions:
        st.info("No saved sessions yet.")
        return
    by_id = {session.session_id: session for session in sessions}
    selected_id = st.selectbox(
        "Session",
        options=list(by_id),
        format_func=lambda value: f"{by_id[value].title} · {by_id[value].updated_at[:16]}",
        key="sessions_selected",
    )
    selected = by_id[selected_id]
    with st.container(horizontal=True):
        if st.button("Open in Chat", type="primary", icon=":material/open_in_new:"):
            st.session_state.current_session_id = selected.session_id
            st.session_state.messages = store.load_messages(selected.session_id)
            st.session_state.pending_query = store.load_pending(selected.session_id)
            st.session_state.active_context = (
                selected.database_fingerprint,
                selected.provider,
                selected.model,
            )
            st.session_state.data_source = (
                "PostgreSQL"
                if selected.database_kind == "postgres"
                else "Demo"
                if selected.database_fingerprint == "demo"
                else "Upload"
            )
            st.session_state.provider_selector = {
                "ollama": "Ollama",
                "huggingface": "Hugging Face",
                "openai": "OpenAI",
                "anthropic": "Anthropic",
                "gemini": "Gemini",
                "xai": "xAI",
            }.get(selected.provider, "Ollama")
            st.session_state[f"model_{selected.provider}"] = selected.model
            st.success("Session loaded. Open the Chat tab to continue.")
    with st.form("rename_session", border=False):
        new_title = st.text_input("Title", value=selected.title)
        if st.form_submit_button("Rename", icon=":material/edit:"):
            store.rename_session(selected_id, new_title)
            st.rerun()
    confirm_delete = st.checkbox("Confirm permanent deletion", key="sessions_confirm_delete")
    if st.button(
        "Delete session",
        icon=":material/delete:",
        disabled=not confirm_delete,
    ):
        store.delete_session(selected_id)
        if st.session_state.get("current_session_id") == selected_id:
            st.session_state.current_session_id = None
            st.session_state.messages = []
            st.session_state.pending_query = None
            st.session_state.active_context = None
        st.rerun()
    st.divider()
    for message in store.load_messages(selected_id):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sql"):
                with st.expander("Approved SQL"):
                    st.code(message["sql"], language="sql")
            if message.get("result_not_stored"):
                st.caption("Raw results were not stored; rerun against the connected database.")


def insights_page() -> None:
    """Render execution-plan and runtime trends from persisted runs."""
    st.title("Query insights")
    st.caption("Planner estimates are advisory. PostgreSQL planner cost is not a dollar amount.")
    store = _store()
    rows = store.runtime_rows()
    if not rows:
        st.info("No query metrics have been recorded yet.")
        return
    frame = pd.DataFrame(rows)
    frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True)
    frame["query_duration_ms"] = pd.to_numeric(frame["query_duration_ms"], errors="coerce")
    durations = frame["query_duration_ms"].dropna()
    with st.container(horizontal=True):
        st.metric("Median runtime", f"{durations.quantile(0.5):,.1f} ms", border=True)
        st.metric("p95 runtime", f"{durations.quantile(0.95):,.1f} ms", border=True)
        st.metric("Slow queries", f"{int((durations >= 1000).sum()):,}", border=True)
        st.metric("Runs with warnings", f"{int((frame['warnings'] != '').sum()):,}", border=True)
    trend = frame.dropna(subset=["query_duration_ms"])[["created_at", "query_duration_ms"]]
    if not trend.empty:
        st.line_chart(
            trend.sort_values("created_at"),
            x="created_at",
            y="query_duration_ms",
            x_label="Time",
            y_label="Runtime (ms)",
        )
    warning_values = [
        warning.strip()
        for value in frame["warnings"]
        for warning in str(value).split(";")
        if warning.strip()
    ]
    if warning_values:
        counts = (
            pd.Series(warning_values, name="Warning")
            .value_counts()
            .rename_axis("Warning")
            .reset_index(name="Count")
        )
        st.bar_chart(counts, x="Warning", y="Count", horizontal=True)
    st.subheader("Recent query metrics")
    st.dataframe(
        frame[
            [
                "created_at",
                "session_title",
                "database_kind",
                "query_duration_ms",
                "warnings",
                "run_id",
            ]
        ].head(200),
        hide_index=True,
    )
    selected_run = st.selectbox("Plan details", frame["run_id"].tolist())
    plan = frame.loc[frame["run_id"] == selected_run, "plan"].iloc[0]
    if isinstance(plan, dict):
        if plan.get("estimated_rows") is not None:
            st.metric("Estimated rows", f"{int(plan['estimated_rows']):,}")
        if plan.get("estimated_total_cost") is not None:
            st.metric("Planner cost", f"{float(plan['estimated_total_cost']):,.1f}")
        if plan.get("nodes"):
            st.dataframe(plan["nodes"], hide_index=True)


def _rule_row(rule: PricingRule) -> dict[str, object]:
    return {
        "rule_id": rule.rule_id,
        "model": rule.model,
        "display_name": rule.display_name,
        "effective_from": rule.effective_from.date().isoformat(),
        "effective_to": rule.effective_to.date().isoformat() if rule.effective_to else "",
        "standard_input": str(rule.standard_input),
        "standard_output": str(rule.standard_output),
        "cache_read_input": str(rule.cache_read_input) if rule.cache_read_input is not None else "",
        "cache_creation_input": (
            str(rule.cache_creation_input) if rule.cache_creation_input is not None else ""
        ),
        "batch_input": str(rule.batch_input) if rule.batch_input is not None else "",
        "batch_output": str(rule.batch_output) if rule.batch_output is not None else "",
        "fast_input": str(rule.fast_input) if rule.fast_input is not None else "",
        "fast_output": str(rule.fast_output) if rule.fast_output is not None else "",
        "long_context_threshold": rule.long_context_threshold,
        "long_context_input": (
            str(rule.long_context_input) if rule.long_context_input is not None else ""
        ),
        "long_context_output": (
            str(rule.long_context_output) if rule.long_context_output is not None else ""
        ),
        "notes": rule.notes,
    }


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return Decimal(str(value).strip())


def _parse_date(value: object, *, required: bool) -> datetime | None:
    text = "" if value is None or pd.isna(value) else str(value).strip()
    if not text:
        if required:
            raise ValueError("Effective start date is required")
        return None
    parsed = datetime.fromisoformat(text)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _rules_from_editor(frame: pd.DataFrame) -> list[PricingRule]:
    rules: list[PricingRule] = []
    for raw in frame.to_dict(orient="records"):
        model = str(raw.get("model", "")).strip()
        effective_from = _parse_date(raw.get("effective_from"), required=True)
        if effective_from is None:  # pragma: no cover - required parser raises
            raise ValueError("Effective start date is required")
        rule_id = str(raw.get("rule_id", "")).strip() or f"{model}-{uuid4().hex[:12]}"
        standard_input = _optional_decimal(raw.get("standard_input"))
        standard_output = _optional_decimal(raw.get("standard_output"))
        if standard_input is None or standard_output is None:
            raise ValueError("Standard input and output rates are required")
        threshold = raw.get("long_context_threshold")
        threshold_value = None if threshold is None or pd.isna(threshold) else int(threshold)
        rules.append(
            PricingRule(
                rule_id=rule_id,
                model=model,
                display_name=str(raw.get("display_name", "")).strip(),
                effective_from=effective_from,
                effective_to=_parse_date(raw.get("effective_to"), required=False),
                standard_input=standard_input,
                standard_output=standard_output,
                cache_read_input=_optional_decimal(raw.get("cache_read_input")),
                cache_creation_input=_optional_decimal(raw.get("cache_creation_input")),
                batch_input=_optional_decimal(raw.get("batch_input")),
                batch_output=_optional_decimal(raw.get("batch_output")),
                fast_input=_optional_decimal(raw.get("fast_input")),
                fast_output=_optional_decimal(raw.get("fast_output")),
                long_context_threshold=threshold_value,
                long_context_input=_optional_decimal(raw.get("long_context_input")),
                long_context_output=_optional_decimal(raw.get("long_context_output")),
                notes=str(raw.get("notes", "")).strip(),
            )
        )
    return rules


def pricing_page() -> None:
    """Edit effective-dated pricing and non-blocking budget alerts."""
    st.title("Pricing configuration")
    st.caption(
        "Changes take effect on the next run without restarting. Historical runs keep their "
        "original snapshot. Batch and fast rates apply only to requests actually made in that mode."
    )
    store = _store()
    rules = store.list_pricing_rules()
    with st.form("pricing_rules"):
        edited = st.data_editor(
            pd.DataFrame([_rule_row(rule) for rule in rules]),
            num_rows="dynamic",
            hide_index=True,
            key="pricing_editor",
        )
        save = st.form_submit_button("Save pricing", type="primary", icon=":material/save:")
    if save:
        try:
            store.replace_pricing_rules(_rules_from_editor(edited))
        except (ValueError, InvalidOperation) as exc:
            st.error(str(exc), icon=":material/error:")
        else:
            st.success("Pricing configuration saved.")
            st.rerun()
    st.subheader("Budget alerts")
    with st.form("budgets"):
        session_budget = st.number_input(
            "Session budget (USD, 0 disables)",
            min_value=0.0,
            value=float(store.get_preference_decimal("session_budget_usd")),
            step=0.25,
        )
        monthly_budget = st.number_input(
            "Monthly budget (USD, 0 disables)",
            min_value=0.0,
            value=float(store.get_preference_decimal("monthly_budget_usd")),
            step=1.0,
        )
        if st.form_submit_button("Save budgets", icon=":material/notifications:"):
            store.set_preference_decimal("session_budget_usd", Decimal(str(session_budget)))
            store.set_preference_decimal("monthly_budget_usd", Decimal(str(monthly_budget)))
            st.success("Budget alerts saved. Warnings appear at 80% and 100%.")
