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
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

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
from ..security import SQLPolicy, SQLValidationError, validate_sql
from ..utils import get_logger, strip_sql_fences, truncate
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
    ) -> None:
        self.llm = llm
        self.settings = settings or get_settings()
        self.db = database or Database(
            self.settings.db_path,
            timeout_seconds=self.settings.db_query_timeout_seconds,
            max_rows=self.settings.db_max_rows,
        )
        self.db.ensure_schema(seed=self.settings.db_seed)
        self.policy = SQLPolicy(
            allow_subqueries=self.settings.sql_allow_subqueries,
            allow_joins=self.settings.sql_allow_joins,
            allow_aggregates=self.settings.sql_allow_aggregates,
            allow_cte=self.settings.sql_allow_cte,
        )
        logger.info(
            "Agent ready: provider model in use, db={db}, max_retries={r}",
            db=str(self.settings.db_path),
            r=self.settings.max_retries,
        )

    # ---- Workflow nodes ------------------------------------------------------

    def fetch_schema(self, state: AgentState) -> dict[str, Any]:
        """Read the database schema and return it as a state update."""
        schema = self.db.get_schema_text()
        logger.debug("Schema fetched ({} chars)", len(schema))
        return {"schema": schema}

    def write_sql(self, state: AgentState) -> dict[str, Any]:
        """Ask the LLM to produce a SQL query from schema + question."""
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
        logger.info(
            "writer attempt={n} produced sql={sql}",
            n=retry,
            sql=truncate(sql, 120),
        )
        return {
            "sql_query": sql,
            "retry_count": retry,
            # Clear stale fields from the previous attempt.
            "error": "",
            "sql_unsafe_reason": "",
            "result": "",
        }

    def check_security(self, state: AgentState) -> dict[str, Any]:
        """Validate the generated SQL against :class:`SQLPolicy`."""
        sql = state.get("sql_query", "")
        try:
            validate_sql(sql, self.policy)
        except SQLValidationError as exc:
            logger.warning("Guardian blocked SQL: {err}", err=exc)
            return {
                "sql_safe": False,  # not in state, but consumed by routing
                "error": f"SQL validation failed: {exc}",
                "sql_unsafe_reason": str(exc),
            }
        return {"sql_safe": True, "error": ""}

    def execute_sql(self, state: AgentState) -> dict[str, Any]:
        """Run the validated SQL against the database."""
        sql = state.get("sql_query", "")
        try:
            qr = self.db.execute(sql)
        except sqlite3.Error as exc:
            logger.warning("SQL execution failed: {err}", err=exc)
            return {
                "error": f"{exc.__class__.__name__}: {exc}",
                "result": "",
                "raw_rows": [],
                "columns": [],
                "row_count": 0,
            }
        except Exception as exc:
            logger.exception("Unexpected SQL execution error")
            return {
                "error": f"{exc.__class__.__name__}: {exc}",
                "result": "",
                "raw_rows": [],
                "columns": [],
                "row_count": 0,
            }

        return {
            "error": "",
            "result": qr.to_markdown(),
            "raw_rows": list(qr.rows),
            "columns": list(qr.columns),
            "row_count": qr.row_count,
        }

    def summarize_result(self, state: AgentState) -> dict[str, Any]:
        """Ask the LLM to write a natural-language answer from the data."""
        question = state.get("question", "")
        sql = state.get("sql_query", "")
        data = format_data(state.get("result", ""))
        err = state.get("error", "")

        prompt = SUMMARIZER_USER.format(
            question=question, sql=sql, data=data, error=err,
        )

        # If summarization itself fails, fall back to a deterministic
        # answer so the UI is never blank.
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

        return {"final_answer": answer, "result": answer}

    # ---- Routing -------------------------------------------------------------

    def route_after_security(self, state: AgentState) -> str:
        """Decide whether to execute the SQL or summarize the safety error."""
        return "executor" if not state.get("error") else "summarizer"

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
                n=retry, max=max_retries,
            )
            return "writer"
        return "summarizer"

    # ---- Workflow assembly ---------------------------------------------------

    def get_workflow(self) -> CompiledStateGraph[AgentState]:
        """Return a compiled LangGraph workflow ready for invocation."""
        graph: StateGraph[AgentState] = StateGraph(AgentState)

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
            {"executor": "executor", "summarizer": "summarizer"},
        )
        graph.add_conditional_edges(
            "executor",
            self.route_after_execute,
            {"writer": "writer", "summarizer": "summarizer"},
        )
        graph.add_edge("summarizer", END)

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
        inputs: AgentState = {
            "question": question,
            "retry_count": 0,
            "max_retries": int(
                max_retries if max_retries is not None else self.settings.max_retries
            ),
            "error": "",
        }
        result: AgentState = workflow.invoke(inputs)  # type: ignore[assignment]
        return dict(result)

    def stream(
        self,
        question: str,
        *,
        max_retries: int | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        """Stream (node_name, state_update) events for live UI updates."""
        workflow = self.get_workflow()
        inputs: AgentState = {
            "question": question,
            "retry_count": 0,
            "max_retries": int(
                max_retries if max_retries is not None else self.settings.max_retries
            ),
            "error": "",
        }
        for event in workflow.stream(inputs):
            yield from event.items()

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
