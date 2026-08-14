"""AST-based SQL safety validator.

Why this exists: a deny-list of keywords (e.g. ``DROP``, ``DELETE``) cannot
distinguish a column name like ``updated_at`` from a destructive statement,
nor block unknown-but-dangerous operations. Instead, we parse the SQL with
``sqlglot`` and apply allow-list rules on the AST:

1. Exactly one statement.
2. Top-level operation is a ``SELECT`` (with optional ``UNION``/``INTERSECT``/``EXCEPT``).
3. No dangerous functions (``sqlite_load_extension``, ``readfile``, etc.).
4. No subqueries, joins, CTEs, or aggregates unless explicitly enabled.

This is the same approach used by production text-to-SQL systems like
LangChain's ``SQLDatabaseChain`` and Vanna.ai.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

import sqlglot
from sqlglot import expressions as exp
from sqlglot.optimizer.scope import traverse_scope

from ..utils import get_logger

logger = get_logger(__name__)


class SQLValidationError(ValueError):
    """Raised when a SQL string fails safety validation."""


# Functions that can read files, execute shell commands, or otherwise
# access the host. ``sqlite_load_extension`` is a particularly nasty one.
DANGEROUS_FUNCTIONS: Final[frozenset[str]] = frozenset(
    {
        "load_extension",
        "readfile",
        "writefile",
        "edit",
        "shell",
        "system",
    }
)


@dataclass(frozen=True, slots=True)
class SQLPolicy:
    """Allow-list knobs for SQL safety."""

    allow_subqueries: bool = True
    allow_joins: bool = True
    allow_aggregates: bool = True
    allow_cte: bool = True
    allow_union: bool = True
    max_limit: int | None = None  # If set, force-enforce a LIMIT clause.
    max_joins: int | None = None
    max_subqueries: int | None = None
    max_ctes: int | None = None

    @classmethod
    def from_config(
        cls, *, allow_subqueries: bool, allow_joins: bool, allow_aggregates: bool, allow_cte: bool
    ) -> SQLPolicy:
        return cls(
            allow_subqueries=allow_subqueries,
            allow_joins=allow_joins,
            allow_aggregates=allow_aggregates,
            allow_cte=allow_cte,
        )


@dataclass(frozen=True, slots=True)
class PreparedSQL:
    """Validated SQL ready for execution."""

    sql: str
    tables: frozenset[str]


def parse_sql(sql: str) -> list[exp.Expression]:
    """Parse ``sql`` into a list of statements using sqlglot.

    Empty / whitespace-only input returns an empty list. Parse errors are
    converted to :class:`SQLValidationError` with a uniform message.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("SQL is empty")
    try:
        statements: list[exp.Expression | None] = sqlglot.parse(sql, dialect="sqlite")
    except sqlglot.errors.ParseError as exc:
        raise SQLValidationError(f"SQL is not valid: {exc}") from exc

    # ``sqlglot.parse`` returns ``[None]`` for blank input or commands like SET.
    filtered: list[exp.Expression] = [s for s in statements if s is not None]
    if not filtered:
        raise SQLValidationError("SQL parsed to no executable statement")
    return filtered


def _flatten_selects(node: exp.Expression) -> list[exp.Select]:
    """Recursively collect all SELECTs in an expression tree."""
    found: list[exp.Select] = []

    def walk(n: exp.Expression | None) -> None:
        if n is None:
            return
        if isinstance(n, exp.Select):
            found.append(n)
        for child in n.iter_expressions():
            walk(child)

    walk(node)
    return found


def _is_aggregate_call(func: exp.Expression) -> bool:
    """Return True if ``func`` is a SQL aggregate function call."""
    if not isinstance(func, (exp.Anonymous, exp.AggFunc)):
        return False
    return _function_name(func).lower() in {
        "count",
        "sum",
        "avg",
        "min",
        "max",
        "group_concat",
        "total",
    }


def _uses_aggregate(select: exp.Select) -> bool:
    """True if the SELECT uses any aggregate function or GROUP BY."""
    if select.args.get("group"):
        return True
    for expr in select.expressions:
        for child in expr.find_all(exp.Func):
            if _is_aggregate_call(child) or isinstance(child, exp.AggFunc):
                return True
    return False


def _function_name(func: exp.Func) -> str:
    """Return the function name in lowercase.

    Handles three sqlglot cases:
    - Built-in / aggregate (e.g. ``Count``): ``sql_name()`` returns the name.
    - ``Anonymous`` (e.g. ``load_extension('x')``): ``this`` is a string with
      the function name.
    - Schema-qualified: strip ``schema.func`` to just ``func``.
    """
    name: str = func.sql_name()  # type: ignore[no-untyped-call]
    if name and name != "ANONYMOUS":
        return name
    raw = func.this
    if isinstance(raw, str):
        return raw.split(".")[-1]
    return ""


def validate_sql(sql: str, policy: SQLPolicy | None = None) -> list[exp.Select]:
    """Validate that ``sql`` is safe to execute under ``policy``.

    Returns the list of top-level SELECTs in the SQL (caller can use them
    for further inspection, e.g. to extract referenced tables).

    Raises :class:`SQLValidationError` on any violation. The exception
    message is suitable for direct display in the UI.
    """
    return _validate_statements(parse_sql(sql), policy or SQLPolicy())


def _validate_statements(
    statements: list[exp.Expression],
    policy: SQLPolicy,
) -> list[exp.Select]:
    """Validate an already-parsed statement list."""

    if len(statements) > 1:
        raise SQLValidationError(
            f"Multiple SQL statements are not allowed (got {len(statements)}).",
        )

    top = statements[0]
    # UNION/INTERSECT/EXCEPT collapse to a Union node. We allow those.
    if isinstance(top, exp.Union):
        if not policy.allow_union:
            raise SQLValidationError(
                "Set operations (UNION/INTERSECT/EXCEPT) are not allowed.",
            )
        selects = _flatten_selects(top)
    elif isinstance(top, exp.Select):
        selects = [top]
    else:
        raise SQLValidationError(
            f"Only SELECT queries are allowed (got {top.__class__.__name__}).",
        )

    for sel in selects:
        _check_select(sel, policy)

    return selects


def _check_select(sel: exp.Select, policy: SQLPolicy) -> None:
    # CTE / WITH
    if (
        sel.args.get("with") or any(isinstance(p, exp.CTE) for p in sel.find_all(exp.CTE))
    ) and not policy.allow_cte:
        raise SQLValidationError("CTEs (WITH ... AS) are not allowed.")

    # Joins
    if sel.args.get("joins") and not policy.allow_joins:
        raise SQLValidationError("JOIN clauses are not allowed.")
    join_count = sum(1 for _ in sel.find_all(exp.Join))
    if policy.max_joins is not None and join_count > policy.max_joins:
        raise SQLValidationError(f"Queries may contain at most {policy.max_joins} JOIN clauses.")

    # Subqueries: any nested SELECT that isn't the top-level one.
    nested = [s for s in _flatten_selects(sel) if s is not sel]
    if nested and not policy.allow_subqueries:
        raise SQLValidationError("Subqueries are not allowed.")
    subquery_count = sum(1 for _ in sel.find_all(exp.Subquery))
    if policy.max_subqueries is not None and subquery_count > policy.max_subqueries:
        raise SQLValidationError(f"Queries may contain at most {policy.max_subqueries} subqueries.")

    cte_count = sum(1 for _ in sel.find_all(exp.CTE))
    if policy.max_ctes is not None and cte_count > policy.max_ctes:
        raise SQLValidationError(f"Queries may contain at most {policy.max_ctes} CTEs.")

    # Aggregates
    if not policy.allow_aggregates and _uses_aggregate(sel):
        raise SQLValidationError("Aggregate functions are not allowed.")

    # Dangerous functions
    for fn in sel.find_all(exp.Func):
        name = _function_name(fn).lower()
        if name in DANGEROUS_FUNCTIONS:
            raise SQLValidationError(
                f"Function '{name}' is not allowed.",
            )

    # Block PRAGMA / ATTACH / VACUUM / REPLACE / INSTALL even if smuggled
    # in a way sqlglot might parse as part of a SELECT (paranoid).
    banned_top_level = {
        "PRAGMA",
        "ATTACH",
        "DETACH",
        "VACUUM",
        "REINDEX",
        "INSTALL",
        "DROP",
        "DELETE",
        "TRUNCATE",
        "INSERT",
        "UPDATE",
        "ALTER",
        "CREATE",
        "REPLACE",
        "GRANT",
        "REVOKE",
        "COPY",
    }
    sql_upper = sel.sql().upper()
    for word in banned_top_level:
        if re.search(rf"\b{re.escape(word)}\b", sql_upper):
            raise SQLValidationError(
                f"Forbidden keyword '{word}' is not allowed.",
            )


def referenced_tables(sql: str) -> set[str]:
    """Return the set of table names referenced in ``sql``.

    Used by the executor's pre-flight check to confirm that every referenced
    table actually exists in the database.
    """
    return _referenced_tables(parse_sql(sql))


def _referenced_tables(statements: list[exp.Expression]) -> set[str]:
    """Return physical table names from already-parsed statements."""
    return {
        source.name
        for statement in statements
        for scope in traverse_scope(statement)
        for _, source in scope.selected_sources.values()
        if isinstance(source, exp.Table) and source.name
    }


def prepare_sql(
    sql: str,
    policy: SQLPolicy | None = None,
    *,
    allowed_tables: Collection[str] | None = None,
) -> PreparedSQL:
    """Validate, authorize, and canonicalize one executable SELECT."""
    policy = policy or SQLPolicy()
    statements = parse_sql(sql)
    _validate_statements(statements, policy)
    top = statements[0]
    tables = _referenced_tables(statements)

    if allowed_tables is not None:
        allowed = {name.casefold() for name in allowed_tables}
        denied = sorted(name for name in tables if name.casefold() not in allowed)
        if denied:
            raise SQLValidationError("Tables are not allowed for this query: " + ", ".join(denied))

    if policy.max_limit is not None:
        limit = top.args.get("limit")
        limit_n: int | None = None
        if limit is not None and isinstance(limit.expression, exp.Literal):
            try:
                limit_n = int(limit.expression.this)
            except (TypeError, ValueError):
                limit_n = None
        if limit_n is None or limit_n > policy.max_limit:
            top.set(
                "limit",
                exp.Limit(expression=exp.Literal.number(policy.max_limit)),
            )

    return PreparedSQL(
        sql=top.sql(dialect="sqlite"),
        tables=frozenset(tables),
    )
