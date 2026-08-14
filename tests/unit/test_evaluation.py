"""Tests for result-based NL2SQL evaluation."""

from __future__ import annotations

import json

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
    agent = FakeAgent([{"raw_rows": [("Bob",), ("Alice",)], "error": "", "retry_count": 1}])
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
        [{"sql_query": "DROP TABLE employees", "error": "SQL validation failed", "sql_safe": False}]
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
