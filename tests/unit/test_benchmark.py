"""Validate benchmark fixtures and manifests without model or network calls."""

import json
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage

from nl2sql_agent.evaluation import benchmark, load_cases
from nl2sql_agent.security import prepare_sql

ROOT = Path(__file__).resolve().parents[2] / "benchmarks"


def test_all_synthetic_gold_queries_execute_and_reference_real_tables(tmp_path):
    cases = load_cases(ROOT / "cases.jsonl")
    rows = [json.loads(line) for line in (ROOT / "cases.jsonl").read_text().splitlines()]
    assert len(cases) == 120
    assert Counter(row["split"] for row in rows) == {"development": 30, "heldout": 90}
    for row in rows:
        db = benchmark.curated_database(ROOT, row["domain"], tmp_path)
        if row["expected_outcome"] == "result":
            prepared = prepare_sql(row["reference_sql"], allowed_tables=db.list_tables())
            assert sorted(prepared.tables) == row["expected_tables"]
            db.execute(prepared.sql)


def test_bird_selection_is_stable_and_stratified(tmp_path):
    path = tmp_path / "bird.json"
    rows = [
        {"question_id": n, "difficulty": difficulty}
        for n, difficulty in enumerate(["simple"] * 20 + ["moderate"] * 30 + ["challenging"] * 15)
    ]
    path.write_text(json.dumps(rows))
    selected = benchmark.select_bird(path)
    assert len(selected) == 50
    assert Counter(row["difficulty"] for row in selected) == {
        "simple": 15,
        "moderate": 25,
        "challenging": 10,
    }
    assert len(benchmark.select_bird(path, size=20)) == 20
    with pytest.raises(ValueError):
        benchmark.select_bird(path, size=1)


@pytest.mark.parametrize("offset", [0, 1])
def test_benchmark_manifest_records_attempt_not_just_success(tmp_path, monkeypatch, offset):
    model = MagicMock()
    model.invoke.return_value = AIMessage(
        content='{"action":"sql","sql":"SELECT COUNT(*) FROM employees"}'
    )
    monkeypatch.setattr(benchmark, "build_chat_model", lambda cfg: model)
    output = tmp_path / "report.json"
    args = [
        "--provider",
        "ollama",
        "--model",
        "granite4.2:3b",
        "--cases",
        str(ROOT / "cases.jsonl"),
        "--limit",
        "2",
        "--offset",
        str(offset),
        "--output",
        str(output),
        "--ledger",
        str(tmp_path / "ledger.db"),
    ]
    assert benchmark.main(args) == 0
    report = json.loads(output.read_text())
    assert len(report["cases"]) == report["planned"] == 2
    assert report["cases"][0]["passed"] is (offset == 0)
    assert report["cases"][0]["id"] == f"hr-{offset + 1:02}"
    assert report["selection_offset"] == offset
    assert report["cases"][1]["passed"] is False
    assert report["dataset_sha256"]
    assert len(report["source_tree_sha256"]) == 64
    assert len(report["database_sha256"]["hr"]) == 64
    assert report["budget_committed_usd"] == "0"
    assert "raw_rows" not in output.read_text()
    with pytest.raises(SystemExit):
        benchmark.main(args)
