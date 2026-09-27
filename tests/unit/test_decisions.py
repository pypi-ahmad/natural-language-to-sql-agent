"""Workflow regressions for clarification, failure classification, and grounding."""

import json
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from nl2sql_agent.agent import NL2SQLAgent
from nl2sql_agent.config import Settings
from nl2sql_agent.db.schema_context import SchemaCatalog, rank_tables


def agent_for(db, *responses):
    model = MagicMock()
    model.invoke.side_effect = [
        AIMessage(content=json.dumps(response)) if isinstance(response, dict) else response
        for response in responses
    ]
    return NL2SQLAgent(model, settings=Settings(audit_enabled=False), database=db)


def test_clarification_never_executes_and_reply_is_in_prompt(seeded_db):
    agent = agent_for(
        seeded_db,
        {"action": "clarify", "message": "Which department?"},
        {
            "action": "sql",
            "sql": "SELECT COUNT(*) AS total FROM employees",
            "assumptions": ["All employees"],
        },
    )
    first = agent.run("How many?")
    assert first["outcome"] == "needs_clarification"
    assert first["executed"] is False
    second = agent.run("How many?", clarifications=["All departments"])
    assert second["outcome"] == "executed"
    assert "total: 10" in second["final_answer"]
    assert "All departments" in str(agent.llm.invoke.call_args)
    assert agent.llm.invoke.call_count == 2  # no ungrounded summary call


def test_unanswerable_and_round_limit(seeded_db):
    agent = agent_for(seeded_db, {"action": "clarify", "message": "Still unclear"})
    result = agent.prepare("Revenue?", clarifications=["one", "two"])
    assert result["outcome"] == "unanswerable"
    assert not result["executed"]
    with pytest.raises(ValueError, match="two"):
        agent.run("Revenue?", clarifications=["a", "b", "c"])


def test_malformed_decision_retries_without_safety_credit(seeded_db):
    agent = agent_for(seeded_db, {"action": "sql"}, {"action": "sql"})
    result = agent.run("Count?", max_retries=2)
    assert result["outcome"] == "generation_error"
    assert result["error_code"] == "invalid_decision"
    assert not result["executed"]


def test_provider_exception_stops_without_retry_or_leak(seeded_db):
    agent = agent_for(seeded_db, RuntimeError("private endpoint and token"))
    result = agent.run("Count?")
    assert result["outcome"] == "provider_error"
    assert "private" not in str(result)
    assert agent.llm.invoke.call_count == 1


def test_policy_and_preflight_errors_are_distinct(seeded_db):
    blocked = agent_for(seeded_db, {"action": "sql", "sql": "DELETE FROM employees"}).run(
        "Delete", max_retries=1
    )
    invalid = agent_for(seeded_db, {"action": "sql", "sql": "SELECT missing FROM employees"}).run(
        "Missing", max_retries=1
    )
    assert blocked["outcome"] == "policy_blocked"
    assert invalid["outcome"] == "database_error"


def test_changed_permissions_and_legacy_pending_require_reprepare(seeded_db):
    agent = agent_for(seeded_db, {"action": "sql", "sql": "SELECT COUNT(*) FROM employees"})
    prepared = agent.prepare("Count")
    agent.allowed_tables = frozenset({"departments"})
    result = agent.execute_prepared(prepared)
    assert result["error_code"] == "stale_preparation"
    assert not result["executed"]
    assert agent.execute_prepared({"sql_query": "SELECT 1"})["error_code"] == "stale_preparation"


def test_catalog_validation_and_aliases(tmp_path, seeded_db):
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {"tables": {"employees": {"aliases": ["staff"], "values": {"name": ["Alice"]}}}}
        ),
        encoding="utf-8",
    )
    catalog = SchemaCatalog.load(path, seeded_db.get_schema_text())
    assert "employees" in catalog.search_question("staff count", frozenset({"employees"}))
    assert catalog.context([]) == "{}"
    path.write_text('{"tables":{"unknown":{}}}', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown table"):
        SchemaCatalog.load(path, seeded_db.get_schema_text())


def test_fk_connector_is_selected_within_cap():
    columns = {
        "people": ["name"],
        "assignments": ["person_id", "project_id"],
        "projects": ["title"],
        "noise": ["id"],
    }
    links = {
        "people": {"assignments"},
        "assignments": {"people", "projects"},
        "projects": {"assignments"},
    }
    assert rank_tables(columns, "people projects", 3, links) == [
        "assignments",
        "people",
        "projects",
    ]
    assert len(rank_tables(columns, "people projects", 2, links)) == 2
    assert rank_tables({}, "all", 3) == []
