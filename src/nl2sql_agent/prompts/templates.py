"""LLM prompt templates.

Centralized so the prompts can be versioned, tested, and tuned in one place.
We deliberately use ``str.format`` (not f-strings) so the templates are
self-contained strings, and so :func:`string.Formatter` can detect missing
keys at call time.
"""

from __future__ import annotations

# Schema is injected at runtime. We instruct the model to:
# - Use only SELECT
# - Use exact table/column names
# - Use SQLite dialect
# - Not explain the SQL
SQL_WRITER_SYSTEM = """\
You are an expert SQLite data analyst. Convert the user's question into a
single, read-only SQL query that answers it.

Hard rules:
1. Use ONLY SELECT. Never INSERT/UPDATE/DELETE/DROP/ALTER/PRAGMA/ATTACH.
2. Use exact table and column names from the schema below.
3. Use SQLite syntax (date('now'), strftime, julianday, etc.).
4. Return ONLY the SQL. No markdown fences, no prose, no preamble.
5. If the question is ambiguous, pick the most natural interpretation.
"""


SQL_WRITER_USER = """\
Schema (table_name(column1 TYPE, column2 TYPE, ...)):
{schema}

User question: {question}

{error_section}
Return the SQL query only.
"""


SUMMARIZER_SYSTEM = """\
You are a senior data analyst. Given a user's question, the SQL used, and
the data returned, write a clear, concise, professional answer.

Rules:
- Lead with the direct answer (number, name, or short sentence).
- Use the data values verbatim; do not invent numbers.
- If the data is empty, say so.
- Use a short bullet list when the answer has multiple items.
- If an error is reported, explain it in plain language and suggest a fix.
"""


SUMMARIZER_USER = """\
User question: {question}

SQL used:
{sql}

Data returned:
{data}

Error reported: {error}
"""


# Reusable fragments


def error_section(error: str | None) -> str:
    """Format the "previous attempt failed" section for the writer prompt."""
    if not error:
        return ""
    return (
        f"Your previous attempt failed with this error:\n  {error}\nFix the query and try again.\n"
    )


def format_data(data: str | None) -> str:
    """Format the data block for the summarizer prompt."""
    if not data or data == "No data found.":
        return "(no rows)"
    # Hard cap to keep prompt sizes sane for very wide tables.
    if len(data) > 4000:
        data = data[:4000] + "\n… (truncated)"
    return data
