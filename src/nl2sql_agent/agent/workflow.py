"""LangGraph workflow for the NL2SQL agent.

The workflow is:

```
fetch_schema → writer → guardian ─┬─(safe)─→ executor ─┬─(ok)─→ summarizer
                                  └─(unsafe)─→ summarizer
                                                   │
                                                   └─(error)─→ writer (retry)
```

Each node is a small method that reads the relevant state keys, performs
its single responsibility, and returns a partial state dict. Nodes are
typed via :class:`AgentState`.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Collection, Iterator, Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..config import Settings, get_settings
from ..db import (
    Database,
    DatabaseBackend,
    DatabaseError,
    PostgresDatabase,
    QueryPlan,
    QueryResult,
)
from ..db.schema_context import SchemaCatalog
from ..llm.budget import BudgetExhausted, Invokable
from ..llm.pricing import UsageRecord
from ..prompts import (
    SQL_WRITER_USER,
    SUMMARIZER_SYSTEM,
    SUMMARIZER_USER,
    error_section,
    format_data,
    sql_writer_system,
)
from ..security import SQLPolicy, SQLValidationError, prepare_sql
from ..utils import AuditLogger, get_logger, hash_text, strip_sql_fences
from .decisions import DECISION_CONTRACT, WriterDecision
from .state import AgentState

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class NodeTrace:
    """One step of an agent run, for observability."""

    node: str
    duration_ms: float
    summary: str


class NL2SQLAgent:
    """The end-to-end SQL data analyst agent.

    Use :meth:`get_workflow` to obtain a compiled LangGraph, then stream
    events from it with ``.stream(inputs)`` or run a single pass with
    ``.invoke(inputs)``.
    """

    def __init__(
        self,
        llm: Invokable,
        *,
        settings: Settings | None = None,
        database: DatabaseBackend | None = None,
        allowed_tables: Collection[str] | None = None,
        include_sample_values: bool | None = None,
        db_fingerprint: str | None = None,
    ) -> None:
        self.llm = llm
        self.settings = settings or get_settings()
        # managed_demo: no explicit database was supplied and the configured
        # backend is the bundled SQLite one, so this agent owns the demo
        # database's full lifecycle (auto-create/seed below, sample values
        # in schema text by default, and a stable "demo" fingerprint instead
        # of one derived from the file path).
        managed_demo = database is None and self.settings.db_backend == "sqlite"
        if database is not None:
            self.db = database
        elif self.settings.db_backend == "postgres":
            if self.settings.postgres_dsn is None:  # validated by Settings
                raise ValueError("PostgreSQL DSN is not configured")
            self.db = PostgresDatabase(
                self.settings.postgres_dsn.get_secret_value(),
                schema=self.settings.postgres_schema,
                timeout_seconds=self.settings.db_query_timeout_seconds,
                lock_timeout_seconds=self.settings.db_lock_timeout_seconds,
                max_rows=self.settings.db_max_rows,
            )
        else:
            self.db = Database(
                self.settings.db_path,
                timeout_seconds=self.settings.db_query_timeout_seconds,
                max_rows=self.settings.db_max_rows,
                max_vm_steps=self.settings.db_max_vm_steps,
            )
        if managed_demo:
            cast(Database, self.db).ensure_schema(seed=self.settings.db_seed)
        available_tables = self.db.list_tables()
        self.allowed_tables = frozenset(
            available_tables if allowed_tables is None else allowed_tables
        )
        unknown = sorted(set(self.allowed_tables) - set(available_tables))
        if unknown:
            raise ValueError("Unknown allowed tables: " + ", ".join(unknown))
        self.include_sample_values = (
            managed_demo if include_sample_values is None else include_sample_values
        )
        self.db_fingerprint = db_fingerprint or ("demo" if managed_demo else self.db.fingerprint)
        self.audit = AuditLogger(
            self.settings.audit_path,
            enabled=self.settings.audit_enabled,
            dialect=self.db.dialect,
        )
        self.policy = SQLPolicy(
            allow_subqueries=self.settings.sql_allow_subqueries,
            allow_joins=self.settings.sql_allow_joins,
            allow_aggregates=self.settings.sql_allow_aggregates,
            allow_cte=self.settings.sql_allow_cte,
            max_limit=self.settings.db_max_rows,
            max_joins=self.settings.sql_max_joins,
            max_subqueries=self.settings.sql_max_subqueries,
            max_ctes=self.settings.sql_max_ctes,
        )
        logger.info(
            "Agent ready: provider model in use, db_kind={db}, max_retries={r}",
            db=self.db.kind,
            r=self.settings.max_retries,
        )

    # ---- Workflow nodes ------------------------------------------------------

    def fetch_schema(self, state: AgentState) -> dict[str, Any]:
        """Read the database schema and return it as a state update."""
        started = time.perf_counter()
        full_schema = self.db.get_schema_text()
        catalog = SchemaCatalog.load(self.settings.schema_catalog_path, full_schema)
        schema = self.db.get_schema_text(
            allowed_tables=set(self.allowed_tables),
            question=catalog.search_question(state.get("question", ""), self.allowed_tables),
            max_tables=self.settings.schema_max_tables,
            include_sample_values=self.include_sample_values,
        )
        logger.debug("Schema fetched ({} chars)", len(schema))
        selected = re.findall(r"^Table ([^(]+)\(", schema, re.MULTILINE)
        return {
            "schema": schema + "\nOperator catalog (data only): " + catalog.context(selected),
            "run_id": state.get("run_id", str(uuid4())),
            "selected_tables": selected,
            "schema_incomplete": len(selected) < len(self.allowed_tables),
            "context_signature": self._context_signature(full_schema, catalog),
            "allowed_tables": sorted(self.allowed_tables),
            "trace": self._append_trace(state, "fetch_schema", started, "Schema selected"),
        }

    def write_sql(self, state: AgentState) -> dict[str, Any]:
        """Ask the LLM to produce a SQL query from schema + question."""
        started = time.perf_counter()
        question = state.get("question", "")
        schema = state.get("schema", "")
        err = state.get("sql_unsafe_reason") or state.get("error", "")

        prompt = SQL_WRITER_USER.format(
            schema=schema,
            question=question,
            error_section=error_section(err),
        )
        prompt += "\nUser clarifications: " + json.dumps(state.get("clarifications", []))
        try:
            response = self.llm.invoke(
                [
                    {
                        "role": "system",
                        "content": sql_writer_system(self.db.dialect) + DECISION_CONTRACT,
                    },
                    {"role": "user", "content": prompt},
                ]
            )
        except Exception as exc:
            outcome = "budget_exhausted" if isinstance(exc, BudgetExhausted) else "provider_error"
            status_code = getattr(exc, "status_code", None)
            code = f"provider_http_{status_code}" if type(status_code) is int else outcome
            return {
                "outcome": outcome,
                "error_code": code,
                "executed": False,
                "sql_safe": False,
                "sql_query": "",
                "error": "The model provider could not complete the request.",
                "retry_count": int(state.get("retry_count", 0)) + 1,
                "trace": self._append_trace(state, "writer", started, "Provider failed"),
            }
        raw_sql = getattr(response, "content", "") or ""
        text_content = getattr(response, "text", None)
        if isinstance(text_content, str):
            raw_sql = text_content
        sql = strip_sql_fences(str(raw_sql))
        retry = int(state.get("retry_count", 0)) + 1
        logger.info("writer attempt={n} sql_hash={sql_hash}", n=retry, sql_hash=hash_text(sql))
        usage, records = self._merge_usage(state, response, stage="writer")
        decision_fields: dict[str, Any] = {"assumptions": [], "clarification_question": ""}
        # Accept legacy SQL-only adapters while new prompts request decisions.
        # JSON-looking responses must validate; they never fall back to SQL.
        content = str(raw_sql).strip()
        if content.startswith("{") or content.startswith("```json"):
            try:
                content = content.removeprefix("```json").removesuffix("```").strip()
                decision = WriterDecision.model_validate_json(content)
            except ValueError:
                return {
                    "outcome": "generation_error",
                    "error_code": "invalid_decision",
                    "error": "Model returned an invalid decision. Return the required JSON object.",
                    "executed": False,
                    "sql_safe": False,
                    "sql_query": "",
                    "retry_count": retry,
                    "token_usage": usage,
                    "usage_records": records,
                }
            decision_fields["assumptions"] = decision.assumptions
            if decision.action != "sql":
                outcome = "needs_clarification" if decision.action == "clarify" else "unanswerable"
                if decision.action == "clarify" and len(state.get("clarifications", [])) >= 2:
                    outcome = "unanswerable"
                return {
                    **decision_fields,
                    "outcome": outcome,
                    "error_code": "",
                    "error": "",
                    "executed": False,
                    "sql_safe": False,
                    "sql_query": "",
                    "clarification_question": decision.message
                    if outcome == "needs_clarification"
                    else "",
                    "final_answer": decision.message,
                    "retry_count": retry,
                    "token_usage": usage,
                    "usage_records": records,
                }
            sql = decision.sql
        return {
            **decision_fields,
            "sql_query": sql,
            "outcome": "generated",
            "error_code": "",
            "executed": False,
            "sql_safe": False,
            "retry_count": retry,
            # Clear stale fields from the previous attempt.
            "error": "",
            "sql_unsafe_reason": "",
            "result": "",
            "token_usage": usage,
            "usage_records": records,
            "trace": self._append_trace(state, "writer", started, f"SQL attempt {retry}"),
        }

    def check_security(self, state: AgentState) -> dict[str, Any]:
        """Validate the generated SQL against :class:`SQLPolicy`."""
        started = time.perf_counter()
        sql = state.get("sql_query", "")
        if state.get("outcome") in {
            "provider_error",
            "budget_exhausted",
            "needs_clarification",
            "unanswerable",
            "generation_error",
        }:
            return {}
        try:
            prepared = prepare_sql(
                sql,
                self.policy,
                allowed_tables=self.allowed_tables,
                dialect=self.db.dialect,
                allowed_schema=(
                    self.settings.postgres_schema if self.db.dialect == "postgres" else None
                ),
            )
            plan = self.db.preflight(prepared.sql)
        except (SQLValidationError, sqlite3.Error, DatabaseError) as exc:
            category = "validation" if isinstance(exc, SQLValidationError) else "preflight"
            outcome = exc.code if isinstance(exc, SQLValidationError) else "database_error"
            logger.warning("Guardian blocked SQL category={category}", category=category)
            self._write_audit(
                state,
                "blocked",
                sql=sql,
                validation=category,
                duration_ms=self._duration_ms(started),
            )
            return {
                "sql_safe": False,  # not in state, but consumed by routing
                "outcome": outcome,
                "error_code": outcome,
                "executed": False,
                "error": f"SQL {category} failed: {exc}",
                "sql_unsafe_reason": str(exc),
                "trace": self._append_trace(state, "guardian", started, f"Blocked by {category}"),
            }
        self._write_audit(
            state,
            "prepared",
            sql=prepared.sql,
            validation="passed",
            duration_ms=self._duration_ms(started),
        )
        return {
            "sql_query": prepared.sql,
            "outcome": "prepared",
            "error_code": "",
            "executed": False,
            "sql_safe": True,
            "error": "",
            "sql_unsafe_reason": "",
            "query_plan": plan.to_dict(),
            "row_limit_applied": prepared.row_limit_applied
            or state.get("row_limit_applied", False),
            "warnings": self._plan_warnings(plan),
            "trace": self._append_trace(state, "guardian", started, "Validated and prepared"),
        }

    def execute_sql(self, state: AgentState) -> dict[str, Any]:
        """Run the validated SQL against the database."""
        started = time.perf_counter()
        sql = state.get("sql_query", "")
        try:
            qr = cast(QueryResult, self.db.execute(sql))
        except (sqlite3.Error, DatabaseError) as exc:
            logger.warning("SQL execution failed type={kind}", kind=exc.__class__.__name__)
            self._write_audit(
                state,
                "failed",
                sql=sql,
                error_type=exc.__class__.__name__,
                duration_ms=self._duration_ms(started),
            )
            return {
                "error": "The database could not execute the query.",
                "outcome": "database_error",
                "error_code": "database_error",
                "executed": False,
                "result": "",
                "raw_rows": [],
                "columns": [],
                "row_count": 0,
                "csv_data": "",
                "truncated": False,
                "trace": self._append_trace(state, "executor", started, "Execution failed"),
            }
        except Exception as exc:
            logger.exception("Unexpected SQL execution error")
            self._write_audit(
                state,
                "failed",
                sql=sql,
                error_type=exc.__class__.__name__,
                duration_ms=self._duration_ms(started),
            )
            return {
                "error": "The database could not execute the query.",
                "outcome": "database_error",
                "error_code": "database_error",
                "executed": False,
                "result": "",
                "raw_rows": [],
                "columns": [],
                "row_count": 0,
                "csv_data": "",
                "truncated": False,
                "trace": self._append_trace(state, "executor", started, "Execution failed"),
            }

        self._write_audit(
            state,
            "executed",
            sql=sql,
            row_count=qr.row_count,
            truncated=qr.truncated,
            duration_ms=self._duration_ms(started),
        )
        warnings = list(state.get("warnings", []))
        if qr.metrics.duration_ms >= self.settings.query_warn_duration_ms > 0:
            warnings.append(f"Slow query: {qr.metrics.duration_ms:.1f} ms")
        if (
            qr.metrics.work_units is not None
            and qr.metrics.work_units >= self.settings.query_warn_sqlite_vm_steps > 0
        ):
            warnings.append(f"High SQLite work: {qr.metrics.work_units:,} VM steps")
        if qr.truncated:
            warnings.append(f"Results truncated at {self.settings.db_max_rows:,} rows")
        metrics = qr.metrics.to_dict()
        metrics["warnings"] = warnings
        return {
            "error": "",
            "result": qr.to_markdown(),
            "outcome": "executed",
            "error_code": "",
            "executed": True,
            "raw_rows": list(qr.rows),
            "columns": list(qr.columns),
            "row_count": qr.row_count,
            "csv_data": qr.to_csv(),
            "truncated": qr.truncated,
            "query_metrics": metrics,
            "warnings": warnings,
            "trace": self._append_trace(
                state, "executor", started, f"Returned {qr.row_count} rows"
            ),
        }

    def summarize_result(self, state: AgentState) -> dict[str, Any]:
        """Ask the LLM to write a natural-language answer from the data."""
        started = time.perf_counter()
        question = state.get("question", "")
        sql = state.get("sql_query", "")
        data = format_data(state.get("result", ""))
        err = state.get("error", "")

        if state.get("outcome") in {"needs_clarification", "unanswerable"}:
            return {"final_answer": state.get("final_answer", "More information is needed.")}
        if err:
            return {"final_answer": self._fallback_answer(state, None)}
        if state.get("executed") is True:
            # Results are rendered directly from database cells, so summaries
            # cannot introduce unsupported numbers or hide sampled rows.
            rows = state.get("raw_rows", [])
            if not rows:
                answer = "The query returned no rows."
            elif len(rows) == 1:
                answer = "; ".join(
                    f"{name}: {value}"
                    for name, value in zip(state.get("columns", []), rows[0], strict=True)
                )
            else:
                answer = f"Returned {len(rows)} rows.\n\n" + state.get("result", "")
            if state.get("truncated"):
                answer += "\n\nThe fetch row cap truncated these results."
            if state.get("row_limit_applied"):
                answer += "\n\nA safety LIMIT was applied to the SQL; the result may be a subset."
            if len(rows) > 100:
                answer += (
                    "\n\nThe preview shows the first 100 rows. Download CSV for all fetched rows."
                )
            return {
                "final_answer": answer,
                "trace": self._append_trace(
                    state, "summarizer", started, "Grounded result rendered"
                ),
            }

        prompt = SUMMARIZER_USER.format(
            question=question,
            sql=sql,
            data=data,
            error=err,
        )

        # If summarization itself fails, fall back to a deterministic
        # answer so the UI is never blank.
        response: object | None = None
        try:
            response = self.llm.invoke(
                [
                    {"role": "system", "content": SUMMARIZER_SYSTEM},
                    {"role": "user", "content": prompt},
                ]
            )
            answer = str(getattr(response, "content", "") or "").strip()
        except Exception as exc:
            logger.exception("Summarizer failed; using fallback")
            answer = self._fallback_answer(state, exc)

        if not answer:
            answer = self._fallback_answer(state, None)

        usage, records = self._merge_usage(state, response, stage="summarizer")
        return {
            "final_answer": answer,
            "result": answer,
            "token_usage": usage,
            "usage_records": records,
            "trace": self._append_trace(state, "summarizer", started, "Answer composed"),
        }

    # ---- Routing -------------------------------------------------------------

    def route_after_security(self, state: AgentState) -> str:
        """Decide whether to execute the SQL or summarize the safety error."""
        if state.get("outcome") in {
            "provider_error",
            "budget_exhausted",
            "policy_blocked",
            "needs_clarification",
            "unanswerable",
        }:
            return "summarizer"
        if not state.get("error"):
            return "executor"
        retry = int(state.get("retry_count", 0))
        maximum = int(state.get("max_retries", self.settings.max_retries))
        return "writer" if retry < maximum else "summarizer"

    def route_after_prepare(self, state: AgentState) -> str:
        """Retry failed preparation or finish with a safe candidate/error.

        "prepared" is a routing sentinel, not a success signal: it also
        covers the case where retries are exhausted while SQL is still
        unsafe (see :meth:`route_after_security`). Callers of
        :meth:`prepare`/:meth:`stream_prepare` must check ``state["error"]``
        rather than assume "prepared" means the SQL is safe to run.
        """
        route = self.route_after_security(state)
        return "writer" if route == "writer" else "prepared"

    def route_after_execute(self, state: AgentState) -> str:
        """Retry the writer on execution error, otherwise summarize."""
        err = state.get("error", "")
        max_retries = int(
            state.get("max_retries", self.settings.max_retries),
        )
        retry = int(state.get("retry_count", 0))
        if err and retry < max_retries:
            logger.info(
                "Retry writer (errored attempt={n}/{max})",
                n=retry,
                max=max_retries,
            )
            return "writer"
        return "summarizer"

    # ---- Workflow assembly ---------------------------------------------------

    def get_workflow(self) -> CompiledStateGraph[AgentState]:  # ty: ignore[invalid-type-arguments]
        """Return a compiled LangGraph workflow ready for invocation."""
        graph: StateGraph[AgentState] = StateGraph(AgentState)  # ty: ignore[invalid-type-arguments, invalid-argument-type]

        graph.add_node("fetch_schema", self.fetch_schema)
        graph.add_node("writer", self.write_sql)
        graph.add_node("guardian", self.check_security)
        graph.add_node("executor", self.execute_sql)
        graph.add_node("summarizer", self.summarize_result)

        graph.add_edge(START, "fetch_schema")
        graph.add_edge("fetch_schema", "writer")
        graph.add_edge("writer", "guardian")
        graph.add_conditional_edges(
            "guardian",
            self.route_after_security,
            {"executor": "executor", "writer": "writer", "summarizer": "summarizer"},
        )
        graph.add_conditional_edges(
            "executor",
            self.route_after_execute,
            {"writer": "writer", "summarizer": "summarizer"},
        )
        graph.add_edge("summarizer", END)

        return graph.compile()

    def get_prepare_workflow(self) -> CompiledStateGraph[AgentState]:  # ty: ignore[invalid-type-arguments]
        """Return a graph that stops after SQL validation and preflight."""
        graph: StateGraph[AgentState] = StateGraph(AgentState)  # ty: ignore[invalid-type-arguments, invalid-argument-type]
        graph.add_node("fetch_schema", self.fetch_schema)
        graph.add_node("writer", self.write_sql)
        graph.add_node("guardian", self.check_security)
        graph.add_edge(START, "fetch_schema")
        graph.add_edge("fetch_schema", "writer")
        graph.add_edge("writer", "guardian")
        graph.add_conditional_edges(
            "guardian",
            self.route_after_prepare,
            {"writer": "writer", "prepared": END},
        )
        return graph.compile()

    # ---- High-level helpers --------------------------------------------------

    def run(
        self,
        question: str,
        *,
        max_retries: int | None = None,
        clarifications: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the workflow end-to-end and return the final state.

        Returns a dict containing ``final_answer``, ``sql_query``,
        ``columns``, ``raw_rows``, ``error``, etc.
        """
        workflow = self.get_workflow()
        inputs = self._initial_state(
            question, max_retries=max_retries, clarifications=clarifications
        )
        result = cast(AgentState, workflow.invoke(inputs))
        return dict(result)

    def stream(
        self,
        question: str,
        *,
        max_retries: int | None = None,
        clarifications: list[str] | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Stream (node_name, state_update) events for live UI updates."""
        workflow = self.get_workflow()
        inputs = self._initial_state(
            question, max_retries=max_retries, clarifications=clarifications
        )
        for event in workflow.stream(inputs):
            for node, update in event.items():
                if update is not None:
                    yield node, update

    def prepare(
        self,
        question: str,
        *,
        max_retries: int | None = None,
        clarifications: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate, validate, and preflight SQL without executing it."""
        result = self.get_prepare_workflow().invoke(
            self._initial_state(question, max_retries=max_retries, clarifications=clarifications)
        )
        return dict(result)

    def stream_prepare(
        self,
        question: str,
        *,
        max_retries: int | None = None,
        clarifications: list[str] | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Stream preparation stages without executing SQL."""
        inputs = self._initial_state(
            question, max_retries=max_retries, clarifications=clarifications
        )
        for event in self.get_prepare_workflow().stream(inputs):
            for node, update in event.items():
                if update is not None:
                    yield node, update

    def execute_prepared(
        self,
        prepared_state: Mapping[str, Any],
        *,
        sql_query: str | None = None,
    ) -> dict[str, Any]:
        """Revalidate and execute an optionally edited prepared query."""
        state = cast(AgentState, dict(prepared_state))
        full_schema = self.db.get_schema_text()
        catalog = SchemaCatalog.load(self.settings.schema_catalog_path, full_schema)
        if state.get("outcome") != "prepared" or state.get(
            "context_signature"
        ) != self._context_signature(full_schema, catalog):
            return {
                **state,
                "executed": False,
                "outcome": "generation_error",
                "error_code": "stale_preparation",
                "sql_safe": False,
                "row_count": 0,
                "error": "Database, permissions, or catalog changed. Prepare this question again.",
                "final_answer": "Prepare this question again before execution.",
                "raw_rows": [],
                "columns": [],
                "csv_data": "",
            }
        if sql_query is not None:
            state["sql_query"] = sql_query
        checked = self.check_security(state)
        state.update(cast(AgentState, checked))
        if state.get("error"):
            state.update(
                {
                    "raw_rows": [],
                    "columns": [],
                    "row_count": 0,
                    "csv_data": "",
                    "truncated": False,
                    "final_answer": f"I couldn't run this query: {state['error']}",
                }
            )
            return dict(state)
        state.update(cast(AgentState, self.execute_sql(state)))
        state.update(cast(AgentState, self.summarize_result(state)))
        return dict(state)

    # ---- Internals -----------------------------------------------------------

    def _context_signature(self, schema: str, catalog: SchemaCatalog) -> str:
        return hash_text(
            json.dumps(
                {
                    "database": self.db_fingerprint,
                    "backend_identity": self.db.fingerprint,
                    "tables": sorted(self.allowed_tables),
                    "schema": schema,
                    "catalog": catalog.model_dump(),
                    "policy": asdict(self.policy),
                },
                sort_keys=True,
            )
        )

    @staticmethod
    def _fallback_answer(state: AgentState, exc: Exception | None) -> str:
        """Deterministic answer when the LLM summarizer is unavailable."""
        err = state.get("error", "")
        if err:
            return f"I couldn't complete the query: {err}"
        data = state.get("result", "")
        if data and data != "No data found.":
            return f"Here are the results:\n\n{data}"
        return "The query returned no rows."

    def _initial_state(
        self,
        question: str,
        *,
        max_retries: int | None,
        clarifications: list[str] | None = None,
    ) -> AgentState:
        if clarifications is not None and len(clarifications) > 2:
            raise ValueError("At most two clarification replies are supported")
        return {
            "run_id": str(uuid4()),
            "question": question,
            "clarifications": list(clarifications or []),
            "retry_count": 0,
            "max_retries": int(
                max_retries if max_retries is not None else self.settings.max_retries
            ),
            "error": "",
            "trace": [],
            "outcome": "pending",
            "error_code": "",
            "executed": False,
            "token_usage": {},
            "usage_records": [],
            "warnings": [],
            "provider": self.settings.provider,
            "model": self.settings.model,
            "allowed_tables": sorted(self.allowed_tables),
        }

    @staticmethod
    def _duration_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 3)

    def _append_trace(
        self,
        state: AgentState,
        node: str,
        started: float,
        summary: str,
    ) -> list[dict[str, object]]:
        trace = list(state.get("trace", []))
        trace.append(asdict(NodeTrace(node, self._duration_ms(started), summary)))
        return trace

    @staticmethod
    def _merge_usage(
        state: AgentState,
        response: object,
        *,
        stage: str,
    ) -> tuple[dict[str, int], list[dict[str, object]]]:
        current = dict(state.get("token_usage", {}))
        records = list(state.get("usage_records", []))
        reported = getattr(response, "usage_metadata", None)
        if not isinstance(reported, dict):
            return current, records
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = reported.get(key)
            if isinstance(value, int):
                current[key] = current.get(key, 0) + value
        # Provider SDKs disagree on the cache-token key name inside
        # input_token_details (e.g. "cache_read" vs "cache_read_tokens");
        # check both so pricing stays accurate across providers.
        details = reported.get("input_token_details", {})
        if not isinstance(details, dict):
            details = {}
        record = UsageRecord(
            stage=stage,
            input_tokens=max(int(reported.get("input_tokens", 0)), 0),
            output_tokens=max(int(reported.get("output_tokens", 0)), 0),
            cache_read_tokens=max(
                int(details.get("cache_read", details.get("cache_read_tokens", 0))), 0
            ),
            cache_creation_tokens=max(
                int(details.get("cache_creation", details.get("cache_creation_tokens", 0))), 0
            ),
        )
        records.append(record.to_dict())
        return current, records

    def _plan_warnings(self, plan: QueryPlan) -> list[str]:
        warnings: list[str] = []
        if self.settings.query_warn_full_scan:
            warnings.extend(plan.warnings)
        if (
            plan.estimated_rows is not None
            and plan.estimated_rows >= self.settings.query_warn_estimated_rows > 0
        ):
            warnings.append(f"Large estimate: {plan.estimated_rows:,} rows")
        if (
            plan.estimated_total_cost is not None
            and plan.estimated_total_cost >= self.settings.query_warn_postgres_cost > 0
        ):
            warnings.append(f"High PostgreSQL planner cost: {plan.estimated_total_cost:,.1f}")
        return list(dict.fromkeys(warnings))

    def _write_audit(self, state: AgentState, event: str, **fields: Any) -> None:
        self.audit.write(
            event=event,
            run_id=state.get("run_id", "unknown"),
            question=state.get("question", ""),
            provider=self.settings.provider,
            model=self.settings.model,
            database=self.db_fingerprint,
            retries=max(int(state.get("retry_count", 0)) - 1, 0),
            **fields,
        )
