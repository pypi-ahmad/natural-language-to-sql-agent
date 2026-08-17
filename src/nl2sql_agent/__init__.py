"""Natural Language to SQL Agent — production-grade local-first agent.

Top-level package: :class:`nl2sql_agent.NL2SQLAgent` is the public entry
point. Configuration lives in :mod:`nl2sql_agent.config`, the database
layer in :mod:`nl2sql_agent.db`, SQL safety in :mod:`nl2sql_agent.security`,
LLM provider integration in :mod:`nl2sql_agent.llm`, the LangGraph
workflow in :mod:`nl2sql_agent.agent`, and the Streamlit UI in
:mod:`nl2sql_agent.ui`.
"""

from __future__ import annotations

from importlib.metadata import version

__version__ = version("nl2sql-agent")

__all__ = ["__version__"]
