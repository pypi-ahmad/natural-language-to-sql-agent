"""Typed state for the LangGraph agent.

Using ``TypedDict`` (not Pydantic) to keep LangGraph's reducer semantics
intact while documenting every field with a precise type and a short
purpose note.
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """The complete state threaded through the workflow.

    All fields are optional (``total=False``) so partial updates from
    individual nodes can be merged without LangGraph complaining about
    missing keys.
    """

    # ---- User input ----
    question: str
    """The original natural-language question from the user."""

    # ---- Schema context ----
    schema: str
    """Human-readable schema description for the LLM prompt."""

    # ---- SQL generation ----
    sql_query: str
    """The most recent SQL candidate produced by the writer."""
    sql_unsafe_reason: str
    """Set by the guardian when validation fails; included in the writer retry prompt."""

    # ---- Execution result ----
    result: str
    """Rendered data (Markdown table) or summarized natural-language answer."""
    raw_rows: list[tuple[object, ...]]
    """Structured rows from the last successful execution (for the UI)."""
    columns: list[str]
    """Column names corresponding to ``raw_rows``."""
    row_count: int
    """Number of rows returned by the last successful execution."""

    # ---- Errors and retries ----
    error: str
    """Most recent error message (security, execution, or none)."""
    retry_count: int
    """Number of writer attempts so far."""
    max_retries: int

    # ---- Preparation, observability, and usage ----
    run_id: str
    """Opaque correlation identifier shared by preparation and execution."""
    sql_safe: bool
    """Whether the latest SQL candidate passed policy and database preflight."""
    allowed_tables: list[str]
    """Database tables authorized for this run."""
    trace: list[dict[str, object]]
    """Operational stage timings; never model chain-of-thought."""
    token_usage: dict[str, int]
    """Input, output, and total token counts when providers report them."""
    usage_records: list[dict[str, object]]
    """Per-call provider usage used for cache, mode, and long-context pricing."""
    provider: str
    model: str
    cost_breakdown: dict[str, object]
    """Immutable estimated-cost snapshot calculated for this run."""
    query_plan: dict[str, object]
    """Normalized non-executing database plan."""
    query_metrics: dict[str, object]
    """Execution duration, work units, row count, and truncation state."""
    warnings: list[str]
    """Plan, runtime, and cost warnings suitable for display."""
    csv_data: str
    """RFC 4180 CSV for the latest successful result."""
    truncated: bool
    """Whether the database row cap truncated the result."""
    """Per-run retry cap (mirrored from settings for downstream access)."""

    # ---- Final output ----
    final_answer: str
    """The summarizer's final natural-language answer."""
