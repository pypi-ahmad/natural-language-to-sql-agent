"""Tests for local saved sessions, pricing, and dashboard aggregates."""

from __future__ import annotations

from decimal import Decimal

import pytest

from nl2sql_agent.persistence import StateStore, cost_rows_to_csv


@pytest.fixture
def store(tmp_path):
    return StateStore(tmp_path / "state.sqlite3")


def _session(store: StateStore) -> str:
    return store.create_session(
        database_kind="sqlite",
        database_label="company.db",
        database_fingerprint="demo",
        provider="openai",
        model="gpt-5.6-luna",
    )


def test_store_initializes_idempotently_and_seeds_pricing(tmp_path):
    path = tmp_path / "state.sqlite3"
    first = StateStore(path)
    second = StateStore(path)
    assert len(first.list_pricing_rules()) == 6
    assert len(second.list_pricing_rules()) == 6


def test_saved_messages_exclude_raw_results_and_csv(store):
    session_id = _session(store)
    store.append_message(session_id, "user", "Show salaries")
    store.append_message(
        session_id,
        "assistant",
        "Done",
        {
            "sql": "SELECT salary FROM employees",
            "raw_rows": [(120_000,)],
            "csv_data": "salary\n120000\n",
            "schema": "secret schema",
            "result_not_stored": True,
        },
    )
    messages = store.load_messages(session_id)
    assert messages[0]["content"] == "Show salaries"
    assert messages[1]["sql"].startswith("SELECT")
    assert messages[1]["result_not_stored"] is True
    assert "raw_rows" not in messages[1]
    assert "csv_data" not in messages[1]
    assert "schema" not in messages[1]
    assert store.list_sessions()[0].title == "Show salaries"


def test_pending_query_uses_explicit_allowlist(store):
    session_id = _session(store)
    store.save_pending(
        session_id,
        {
            "run_id": "run-1",
            "question": "Count employees",
            "sql_query": "SELECT COUNT(*) FROM employees",
            "raw_rows": [(10,)],
            "schema": "private",
        },
    )
    pending = store.load_pending(session_id)
    assert pending is not None
    assert pending["run_id"] == "run-1"
    assert "raw_rows" not in pending
    assert "schema" not in pending
    store.clear_pending(session_id)
    assert store.load_pending(session_id) is None


def test_run_cost_and_metrics_are_aggregated(store):
    session_id = _session(store)
    state = {
        "run_id": "run-1",
        "sql_query": "SELECT COUNT(*) FROM employees",
        "token_usage": {"input_tokens": 1000, "output_tokens": 500},
        "usage_records": [
            {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cache_read_tokens": 100,
                "request_mode": "standard",
            }
        ],
        "cost_breakdown": {
            "total_cost": "0.00078",
            "pricing_rule_id": "gpt-5.6-luna-20260814",
        },
        "query_metrics": {"duration_ms": 12.5, "row_count": 1},
        "query_plan": {"backend": "sqlite", "nodes": []},
        "warnings": ["Full table scan: employees"],
        "trace": [{"duration_ms": 20.0}],
    }
    store.save_run(
        session_id,
        state,
        provider="openai",
        model="gpt-5.6-luna",
        database_kind="sqlite",
        database_fingerprint="demo",
        approved=True,
    )
    rows = store.cost_rows()
    assert rows[0]["estimated_cost_usd"] == "0.00078"
    assert rows[0]["approved_sql"].startswith("SELECT")
    assert store.cost_total(session_id=session_id) == Decimal("0.00078")
    assert store.runtime_rows()[0]["plan"]["backend"] == "sqlite"


def test_budget_preferences_default_disabled(store):
    assert store.get_preference_decimal("session_budget_usd") == 0
    store.set_preference_decimal("session_budget_usd", Decimal("1.25"))
    assert store.get_preference_decimal("session_budget_usd") == Decimal("1.25")


def test_pricing_overlap_is_rejected(store):
    rules = store.list_pricing_rules()
    duplicate = rules[0]
    with pytest.raises(ValueError, match="unique"):
        store.replace_pricing_rules([*rules, duplicate])


def test_cost_csv_excludes_prompts_and_neutralizes_formulas():
    exported = cost_rows_to_csv(
        [
            {
                "created_at": "2026-08-14",
                "session_id": "=cmd",
                "session_title": "private title",
                "run_id": "run-1",
                "provider": "openai",
                "model": "gpt-5.6-luna",
                "input_tokens": 1,
                "output_tokens": 1,
                "estimated_cost_usd": "0.1",
                "question": "private question",
                "approved_sql": "SELECT secret",
            }
        ]
    )
    assert "'=cmd" in exported
    assert "private question" not in exported
    assert "SELECT secret" not in exported
    assert "private title" in exported
