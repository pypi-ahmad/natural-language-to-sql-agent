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

import sqlite3
import time
from collections.abc import Collection, Iterator, Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..config import Settings, get_settings
from ..db import Database
from ..prompts import (
    SQL_WRITER_SYSTEM,
    SQL_WRITER_USER,
    SUMMARIZER_SYSTEM,
    SUMMARIZER_USER,
    error_section,
    format_data,
)
from ..security import SQLPolicy, SQLValidationError, prepare_sql
from ..utils import AuditLogger, get_logger, hash_text, strip_sql_fences
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
        llm: BaseChatModel,
        *,
        settings: Settings | None = None,
        database: Database | None = None,
        allowed_tables: Collection[str] | None = None,
        include_sample_values: bool | None = None,
        db_fingerprint: str | None = None,
    ) -> None:
        self.llm = llm
        self.settings = settings or get_settings()
        managed_demo = database is None
        self.db = database or Database(
            self.settings.db_path,
            timeout_seconds=self.settings.db_query_timeout_seconds,
            max_rows=self.settings.db_max_rows,
            max_vm_steps=self.settings.db_max_vm_steps,
        )
        if managed_demo:
            self.db.ensure_schema(seed=self.settings.db_seed)
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
        self.db_fingerprint = db_fingerprint or (
            "demo" if managed_demo else hash_text(str(self.db.path.resolve()))
        )
        self.audit = AuditLogger(
            self.settings.audit_path,
            enabled=self.settings.audit_enabled,
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
            "Agent ready: provider model in use, db={db}, max_retries={r}",
            db=str(self.settings.db_path),
            r=self.settings.max_retries,
        )

    # ---- Workflow nodes ------------------------------------------------------

    def fetch_schema(self, state: AgentState) -> dict[str, Any]:
        """Read the database schema and return it as a state update."""
        started = time.perf_counter()
        schema = self.db.get_schema_text(
            allowed_tables=set(self.allowed_tables),
            question=state.get("question", ""),
            max_tables=self.settings.schema_max_tables,
            include_sample_values=self.include_sample_values,
        )
        logger.debug("Schema fetched ({} chars)", len(schema))
        return {
            "schema": schema,
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
        response = self.llm.invoke(
            [
                {"role": "system", "content": SQL_WRITER_SYSTEM},
                {"role": "user", "content": prompt},
            ]
        )
        raw_sql = getattr(response, "content", "") or ""
        sql = strip_sql_fences(str(raw_sql))
        retry = int(state.get("retry_count", 0)) + 1
        logger.info("writer attempt={n} sql_hash={sql_hash}", n=retry, sql_hash=hash_text(sql))
        return {
            "sql_query": sql,
            "retry_count": retry,
            # Clear stale fields from the previous attempt.
            "error": "",
            "sql_unsafe_reason": "",
            "result": "",
            "token_usage": self._merge_usage(state, response),
            "trace": self._append_trace(state, "writer", started, f"SQL attempt {retry}"),
        }

    def check_security(self, state: AgentState) -> dict[str, Any]:
        """Validate the generated SQL against :class:`SQLPolicy`."""
        started = time.perf_counter()
        sql = state.get("sql_query", "")
        try:
            prepared = prepare_sql(
                sql,
                self.policy,
                allowed_tables=self.allowed_tables,
            )
            self.db.preflight(prepared.sql)
        except (SQLValidationError, sqlite3.Error) as exc:
            category = "validation" if isinstance(exc, SQLValidationError) else "preflight"
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
            "sql_safe": True,
            "error": "",
            "sql_unsafe_reason": "",
            "trace": self._append_trace(state, "guardian", started, "Validated and prepared"),
        }

    def execute_sql(self, state: AgentState) -> dict[str, Any]:
        """Run the validated SQL against the database."""
        started = time.perf_counter()
        sql = state.get("sql_query", "")
        try:
            qr = self.db.execute(sql)
        except sqlite3.Error as exc:
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
        return {
            "error": "",
            "result": qr.to_markdown(),
            "raw_rows": list(qr.rows),
            "columns": list(qr.columns),
            "row_count": qr.row_count,
            "csv_data": qr.to_csv(),
            "truncated": qr.truncated,
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

        usage = self._merge_usage(state, response)
        return {
            "final_answer": answer,
            "result": answer,
            "token_usage": usage,
            "trace": self._append_trace(state, "summarizer", started, "Answer composed"),
        }

    # ---- Routing -------------------------------------------------------------

    def route_after_security(self, state: AgentState) -> str:
        """Decide whether to execute the SQL or summarize the safety error."""
        if not state.get("error"):
            return "executor"
        retry = int(state.get("retry_count", 0))
        maximum = int(state.get("max_retries", self.settings.max_retries))
        return "writer" if retry < maximum else "summarizer"

    def route_after_prepare(self, state: AgentState) -> str:
        """Retry failed preparation or finish with a safe candidate/error."""
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
    ) -> dict[str, Any]:
        """Run the workflow end-to-end and return the final state.

        Returns a dict containing ``final_answer``, ``sql_query``,
        ``columns``, ``raw_rows``, ``error``, etc.
        """
        workflow = self.get_workflow()
        inputs = self._initial_state(question, max_retries=max_retries)
        result = cast(AgentState, workflow.invoke(inputs))
        return dict(result)

    def stream(
        self,
        question: str,
        *,
        max_retries: int | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Stream (node_name, state_update) events for live UI updates."""
        workflow = self.get_workflow()
        inputs = self._initial_state(question, max_retries=max_retries)
        for event in workflow.stream(inputs):
            yield from event.items()

    def prepare(
        self,
        question: str,
        *,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """Generate, validate, and preflight SQL without executing it."""
        result = self.get_prepare_workflow().invoke(
            self._initial_state(question, max_retries=max_retries)
        )
        return dict(result)

    def stream_prepare(
        self,
        question: str,
        *,
        max_retries: int | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Stream preparation stages without executing SQL."""
        inputs = self._initial_state(question, max_retries=max_retries)
        for event in self.get_prepare_workflow().stream(inputs):
            yield from event.items()

    def execute_prepared(
        self,
        prepared_state: Mapping[str, Any],
        *,
        sql_query: str | None = None,
    ) -> dict[str, Any]:
        """Revalidate and execute an optionally edited prepared query."""
        state = cast(AgentState, dict(prepared_state))
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
    ) -> AgentState:
        return {
            "run_id": str(uuid4()),
            "question": question,
            "retry_count": 0,
            "max_retries": int(
                max_retries if max_retries is not None else self.settings.max_retries
            ),
            "error": "",
            "trace": [],
            "token_usage": {},
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
    def _merge_usage(state: AgentState, response: object) -> dict[str, int]:
        current = dict(state.get("token_usage", {}))
        reported = getattr(response, "usage_metadata", None)
        if not isinstance(reported, dict):
            return current
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = reported.get(key)
            if isinstance(value, int):
                current[key] = current.get(key, 0) + value
        return current

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
