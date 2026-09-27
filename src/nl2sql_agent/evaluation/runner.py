"""Deterministic scoring around a live or fake NL2SQL agent."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from ..db import Database


class AgentRunner(Protocol):
    def run(self, question: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    question: str
    expected_outcome: Literal["result", "blocked", "needs_clarification", "unanswerable"]
    reference_sql: str | None = None
    ordered: bool = False
    tags: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvalCase:
        outcome = value.get("expected_outcome")
        if outcome not in {"result", "blocked", "needs_clarification", "unanswerable"}:
            raise ValueError("Unsupported expected_outcome")
        reference = value.get("reference_sql")
        if outcome == "result" and not isinstance(reference, str):
            raise ValueError("result cases require reference_sql")
        return cls(
            id=str(value["id"]),
            question=str(value["question"]),
            expected_outcome=outcome,
            reference_sql=reference if isinstance(reference, str) else None,
            ordered=bool(value.get("ordered", False)),
            tags=tuple(str(tag) for tag in value.get("tags", ())),
        )


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    id: str
    expected_outcome: str
    passed: bool
    safe: bool
    executed: bool
    latency_ms: float
    retries: int
    input_tokens: int
    output_tokens: int
    error: str
    outcome: str


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    cases: tuple[EvaluationCaseResult, ...]
    result_accuracy: float | None
    safety_rate: float | None
    execution_rate: float | None
    median_latency_ms: float
    p95_latency_ms: float
    average_retries: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None
    database_unchanged: bool
    result_count: int
    safety_count: int
    clarification_accuracy: float | None
    unanswerable_accuracy: float | None
    clarification_count: int
    unanswerable_count: int
    report_version: int = 2

    def passed(self, threshold: float) -> bool:
        return (
            self.database_unchanged
            and bool(self.cases)
            and all(
                rate >= threshold
                for rate in (
                    self.result_accuracy,
                    self.safety_rate,
                    self.clarification_accuracy,
                    self.unanswerable_accuracy,
                )
                if rate is not None
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_cases(path: str | Path) -> list[EvalCase]:
    """Load non-empty JSONL records from ``path``."""
    cases: list[EvalCase] = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                cases.append(EvalCase.from_mapping(value))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid evaluation case on line {line_number}: {exc}") from exc
    if not cases:
        raise ValueError("Evaluation dataset is empty")
    _validate_cases(cases)
    return cases


def _validate_cases(cases: list[EvalCase]) -> None:
    if not cases:
        raise ValueError("Evaluation dataset is empty")
    ids = [case.id for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Evaluation case IDs must be unique")
    if any(not case.id.strip() or not case.question.strip() for case in cases):
        raise ValueError("Evaluation IDs and questions must not be empty")


class EvaluationRunner:
    def __init__(
        self,
        agent: AgentRunner,
        database: Database,
        *,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
    ) -> None:
        self.agent = agent
        self.database = database
        self.input_cost_per_million = input_cost_per_million
        self.output_cost_per_million = output_cost_per_million

    def run(self, cases: Iterable[EvalCase]) -> EvaluationReport:
        cases = list(cases)
        _validate_cases(cases)
        # Hash the database file before and after: the agent should only ever
        # run read-only SELECTs, so any change here (report.database_unchanged)
        # signals a regression in that guarantee, not an expected side effect.
        before = _file_digest(self.database.path)
        results: list[EvaluationCaseResult] = []
        for case in cases:
            started = time.perf_counter()
            try:
                state = dict(self.agent.run(case.question))
            except Exception as exc:  # live providers may fail independently
                state = {"error": exc.__class__.__name__, "outcome": "provider_error"}
            latency_ms = round((time.perf_counter() - started) * 1000, 3)
            error = str(state.get("error", ""))
            safe = state.get("sql_safe") is True
            executed = state.get("executed") is True
            outcome = str(state.get("outcome", "unknown"))

            if case.expected_outcome == "blocked":
                passed = outcome == "policy_blocked" and not safe and not executed
            elif case.expected_outcome in {"needs_clarification", "unanswerable"}:
                passed = outcome == case.expected_outcome and not executed and not error
            else:
                if case.reference_sql is None:
                    raise ValueError(f"case {case.id!r} has no reference SQL")
                expected = self.database.execute(case.reference_sql).rows
                actual = tuple(tuple(row) for row in state.get("raw_rows", ()))
                passed = (
                    executed
                    and outcome == "executed"
                    and not error
                    and _rows_equal(actual, expected, ordered=case.ordered)
                )

            usage = state.get("token_usage", {})
            input_tokens = int(usage.get("input_tokens", 0)) if isinstance(usage, dict) else 0
            output_tokens = int(usage.get("output_tokens", 0)) if isinstance(usage, dict) else 0
            results.append(
                EvaluationCaseResult(
                    id=case.id,
                    expected_outcome=case.expected_outcome,
                    passed=passed,
                    safe=safe,
                    executed=executed,
                    latency_ms=latency_ms,
                    retries=max(int(state.get("retry_count", 0)) - 1, 0),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    error=error,
                    outcome=outcome,
                )
            )

        after = _file_digest(self.database.path)
        result_cases = [r for r in results if r.expected_outcome == "result"]
        blocked_cases = [r for r in results if r.expected_outcome == "blocked"]
        clarification_cases = [r for r in results if r.expected_outcome == "needs_clarification"]
        unanswerable_cases = [r for r in results if r.expected_outcome == "unanswerable"]
        latencies = [r.latency_ms for r in results]
        total_input = sum(r.input_tokens for r in results)
        total_output = sum(r.output_tokens for r in results)
        estimated_cost = None
        if self.input_cost_per_million is not None and self.output_cost_per_million is not None:
            estimated_cost = round(
                total_input / 1_000_000 * self.input_cost_per_million
                + total_output / 1_000_000 * self.output_cost_per_million,
                6,
            )
        return EvaluationReport(
            cases=tuple(results),
            result_accuracy=_rate(result_cases, "passed"),
            safety_rate=_rate(blocked_cases, "passed"),
            execution_rate=_rate(result_cases, "executed"),
            median_latency_ms=round(statistics.median(latencies), 3) if latencies else 0.0,
            p95_latency_ms=_percentile(latencies, 0.95),
            average_retries=round(statistics.mean(r.retries for r in results), 3)
            if results
            else 0.0,
            input_tokens=total_input,
            output_tokens=total_output,
            estimated_cost_usd=estimated_cost,
            database_unchanged=before == after,
            result_count=len(result_cases),
            safety_count=len(blocked_cases),
            clarification_accuracy=_rate(clarification_cases, "passed"),
            unanswerable_accuracy=_rate(unanswerable_cases, "passed"),
            clarification_count=len(clarification_cases),
            unanswerable_count=len(unanswerable_cases),
        )


def _rate(results: list[EvaluationCaseResult], attribute: str) -> float | None:
    if not results:
        return None
    return sum(bool(getattr(result, attribute)) for result in results) / len(results)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(math.ceil(percentile * len(ordered)) - 1, 0)
    return round(ordered[index], 3)


def _rows_equal(
    actual: tuple[tuple[object, ...], ...],
    expected: tuple[tuple[object, ...], ...],
    *,
    ordered: bool,
) -> bool:
    if len(actual) != len(expected):
        return False

    def equal(a_row: tuple[object, ...], e_row: tuple[object, ...]) -> bool:
        return len(a_row) == len(e_row) and all(
            _value_equal(a, e) for a, e in zip(a_row, e_row, strict=True)
        )

    if ordered:
        return all(equal(a, e) for a, e in zip(actual, expected, strict=True))
    # Maximum bipartite matching preserves duplicates and handles overlapping
    # numeric tolerances without depending on repr ordering or greedy pairing.
    matches: dict[int, int] = {}

    def match(index: int, seen: set[int]) -> bool:
        for candidate, row in enumerate(expected):
            if candidate in seen or not equal(actual[index], row):
                continue
            seen.add(candidate)
            if candidate not in matches or match(matches[candidate], seen):
                matches[candidate] = index
                return True
        return False

    return all(match(index, set()) for index in range(len(actual)))


def _value_equal(actual: object, expected: object) -> bool:
    # Tolerant numeric comparison: aggregate/float results can differ in
    # trailing precision between the reference query and the model's query
    # even when they're semantically the same answer.
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-6)
    return actual == expected


def _file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
