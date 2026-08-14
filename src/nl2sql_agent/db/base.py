"""Shared database contracts and query observability types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol, runtime_checkable


class DatabaseError(RuntimeError):
    """A provider-neutral database failure safe for workflow handling."""


@dataclass(frozen=True, slots=True)
class QueryPlanNode:
    """One normalized node in a database query plan."""

    operation: str
    relation: str = ""
    detail: str = ""
    estimated_rows: int | None = None
    total_cost: float | None = None


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """A normalized, non-executing query plan."""

    backend: str
    nodes: tuple[QueryPlanNode, ...] = ()
    estimated_rows: int | None = None
    estimated_total_cost: float | None = None
    full_scan_relations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class QueryMetrics:
    """Runtime measurements recorded for an executed query."""

    duration_ms: float = 0.0
    work_units: int | None = None
    row_count: int = 0
    truncated: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@runtime_checkable
class DatabaseBackend(Protocol):
    """Minimum interface required by the NL2SQL workflow."""

    @property
    def kind(self) -> str: ...

    @property
    def dialect(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def fingerprint(self) -> str: ...

    def list_tables(self) -> tuple[str, ...]: ...

    def get_schema_text(
        self,
        *,
        allowed_tables: set[str] | frozenset[str] | None = None,
        question: str = "",
        max_tables: int | None = None,
        include_sample_values: bool = False,
    ) -> str: ...

    def preflight(self, sql: str) -> QueryPlan: ...

    def execute(self, sql: str) -> object: ...
