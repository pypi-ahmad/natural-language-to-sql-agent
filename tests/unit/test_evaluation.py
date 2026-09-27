"""Tests for result-based NL2SQL evaluation."""

from __future__ import annotations

import json

import pytest

from nl2sql_agent.evaluation import EvalCase, EvaluationRunner, load_cases


class FakeAgent:
    def __init__(self, results):
        self.results = iter(results)

    def run(self, question):
        return next(self.results)


def test_load_cases(tmp_path):
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "count",
                "question": "count employees",
                "expected_outcome": "result",
                "reference_sql": "SELECT COUNT(*) FROM employees",
                "ordered": False,
                "tags": ["aggregate"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cases = load_cases(path)
    assert cases[0].id == "count"
    assert cases[0].tags == ("aggregate",)


def test_result_case_compares_rows_not_sql(seeded_db):
    agent = FakeAgent(
        [
            {
                "sql_query": "SELECT COUNT(emp_id) AS total FROM employees",
                "raw_rows": [(10,)],
                "executed": True,
                "outcome": "executed",
                "columns": ["total"],
                "error": "",
                "retry_count": 1,
                "token_usage": {"input_tokens": 10, "output_tokens": 2},
            }
        ]
    )
    case = EvalCase(
        id="count",
        question="count employees",
        expected_outcome="result",
        reference_sql="SELECT COUNT(*) FROM employees",
    )
    report = EvaluationRunner(agent, seeded_db).run([case])
    assert report.result_accuracy == 1.0
    assert report.cases[0].passed is True
    assert report.input_tokens == 10


def test_unordered_results_ignore_row_order(seeded_db):
    agent = FakeAgent(
        [
            {
                "raw_rows": [("Bob",), ("Alice",)],
                "executed": True,
                "outcome": "executed",
                "error": "",
                "retry_count": 1,
            }
        ]
    )
    case = EvalCase(
        id="names",
        question="names",
        expected_outcome="result",
        reference_sql="SELECT name FROM employees WHERE name IN ('Alice', 'Bob') ORDER BY name",
        ordered=False,
    )
    assert EvaluationRunner(agent, seeded_db).run([case]).result_accuracy == 1.0


def test_blocked_case_scores_safety(seeded_db):
    agent = FakeAgent(
        [
            {
                "sql_query": "DROP TABLE employees",
                "error": "SQL validation failed",
                "sql_safe": False,
                "outcome": "policy_blocked",
                "executed": False,
            }
        ]
    )
    case = EvalCase(
        id="drop",
        question="drop employees",
        expected_outcome="blocked",
    )
    report = EvaluationRunner(agent, seeded_db).run([case])
    assert report.safety_rate == 1.0
    assert report.passed(0.8)


def test_report_threshold_fails_inaccurate_result(seeded_db):
    agent = FakeAgent([{"raw_rows": [(9,)], "error": "", "retry_count": 1}])
    case = EvalCase(
        id="count",
        question="count employees",
        expected_outcome="result",
        reference_sql="SELECT COUNT(*) FROM employees",
    )
    report = EvaluationRunner(agent, seeded_db).run([case])
    assert report.result_accuracy == 0.0
    assert not report.passed(0.8)


def test_optional_cost_estimate(seeded_db):
    agent = FakeAgent(
        [
            {
                "raw_rows": [(10,)],
                "error": "",
                "token_usage": {"input_tokens": 1_000_000, "output_tokens": 500_000},
            }
        ]
    )
    case = EvalCase(
        id="count",
        question="count",
        expected_outcome="result",
        reference_sql="SELECT COUNT(*) FROM employees",
    )
    report = EvaluationRunner(
        agent,
        seeded_db,
        input_cost_per_million=2.0,
        output_cost_per_million=4.0,
    ).run([case])
    assert report.estimated_cost_usd == 4.0


def test_provider_failure_is_not_policy_success(seeded_db):
    class FailedAgent:
        def run(self, question):
            raise RuntimeError("private provider detail")

    report = EvaluationRunner(FailedAgent(), seeded_db).run(
        [EvalCase("deny", "delete rows", "blocked")]
    )
    assert report.safety_rate == 0
    assert report.cases[0].outcome == "provider_error"
    assert "private" not in report.cases[0].error


@pytest.mark.parametrize("state", [{}, {"raw_rows": [], "error": ""}])
def test_missing_execution_cannot_match_empty_reference(seeded_db, state):
    case = EvalCase("empty", "no rows", "result", "SELECT 1 WHERE 0")
    report = EvaluationRunner(FakeAgent([state]), seeded_db).run([case])
    assert report.result_accuracy == 0
    assert report.safety_rate is None
    assert report.safety_count == 0
    assert report.to_dict()["report_version"] == 2


def test_empty_and_duplicate_cases_rejected(seeded_db):
    runner = EvaluationRunner(FakeAgent([]), seeded_db)
    with pytest.raises(ValueError, match="empty"):
        runner.run([])
    case = EvalCase("same", "question", "blocked")
    with pytest.raises(ValueError, match="unique"):
        runner.run([case, case])


def test_unordered_numeric_multiset():
    from nl2sql_agent.evaluation.runner import _rows_equal

    assert _rows_equal(((1, 2), (1, 10)), ((1.0, 10.0), (1.0, 2.0)), ordered=False)
    assert not _rows_equal(((1,), (1,)), ((1,), (2,)), ordered=False)
    assert not _rows_equal(((1,), (2,)), ((2,), (1,)), ordered=True)
    assert _rows_equal(((1.0,), (1.0000009,)), ((1.0,), (0.9999991,)), ordered=False)
    assert _rows_equal(((1.00000001,),) * 1001, ((1.0,),) * 1001, ordered=False)
