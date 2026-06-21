"""Utility helpers used across the agent."""

from __future__ import annotations

import re
from typing import Final

from .logging import configure_logging, get_logger

__all__ = ["configure_logging", "get_logger", "strip_sql_fences", "truncate"]

_SQL_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*```(?:sql|SQL)?\s*\n?(.*?)\n?\s*```\s*$",
    re.DOTALL,
)
_LEADING_SQL_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?:here\s+is\s+the\s+sql|sql:|query:|answer:)\s*",
    re.IGNORECASE,
)


def strip_sql_fences(text: str) -> str:
    """Strip Markdown code fences and leading chatter from an LLM-emitted SQL string.

    Handles ``\\`\\`\\`sql ... \\`\\`\\```, ``\\`\\`\\` ... \\`\\`\\``, and bare SQL.
    """
    if not text:
        return ""

    cleaned = text.strip()

    m = _SQL_FENCE_RE.match(cleaned)
    if m:
        cleaned = m.group(1).strip()

    # If the model wrapped SQL in quotes, drop the outer quotes.
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1].strip()

    # Drop a single leading "SQL:" / "Query:" label if present.
    cleaned = _LEADING_SQL_TOKEN_RE.sub("", cleaned, count=1).strip()

    # Drop trailing semicolons (we use sqlite3's default behavior).
    cleaned = cleaned.rstrip(";").strip()
    return cleaned


def truncate(text: str, max_chars: int, *, suffix: str = "...") -> str:
    """Truncate ``text`` to ``max_chars`` keeping a tail ``suffix`` if cut."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if len(suffix) >= max_chars:
        return text[:max_chars]
    return text[: max_chars - len(suffix)] + suffix
