# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-06-22

### Major release — production modernization

This is a complete rewrite of the project from a two-file Streamlit demo
into a properly modularized, tested, production-grade Python package.
**All v0.1 functionality is preserved; public behavior is equivalent.**

#### Added

- **`src/` layout** with a single `nl2sql_agent` package replacing the old
  `app.py` / `backend.py` pair. Sub-packages: `config`, `db`, `security`,
  `llm`, `prompts`, `agent`, `ui`, `utils`.
- **Pydantic Settings configuration** with env-var overrides
  (`NL2SQL_*` prefix) and `.env` file support. See
  `src/nl2sql_agent/config/settings.py`.
- **AST-based SQL safety** using `sqlglot` parsing and an allow-list
  policy. Replaces the v0.1 regex deny-list. New dangerous-function
  blocklist (`load_extension`, `readfile`, `writefile`, `shell`,
  `system`, `edit`).
- **Configurable SQL policy**: per-knob toggles for subqueries, joins,
  aggregates, CTEs, UNION. All policy violations raise
  `SQLValidationError` with a UI-friendly message.
- **Multi-provider LLM factory** with explicit support for Ollama,
  OpenAI, Gemini, and Anthropic. LangChain `langchain_*` providers
  (including the new `langchain_ollama` package) used throughout.
- **Streamlit UI rewrite** with sidebar provider picker, model
  discovery button, live per-step status, chat history, expandable
  SQL view, raw results table, and clickable example questions.
- **CLI** with subcommands `ask`, `config`, `serve`. The `ask`
  subcommand is suitable for scripts and CI.
- **Structured logging** via Loguru with optional JSON output and
  stdlib-logging intercept.
- **174 unit tests** organized by module. New tests for settings,
  security, prompts, text utilities, CLI, and the agent workflow.
- **Live integration test** (`tests/integration/test_ollama_live.py`)
  that drives the agent against a real local Ollama.
- **Mermaid architecture diagram** in README.

#### Changed

- **Python 3.12.10**, `uv`-managed, `pyproject.toml` is the single
  source of truth for dependencies. Replaces `requirements.txt`.
- **Pinned dependencies** with conservative version ranges (e.g.
  `langgraph>=0.6.7,<0.7`).
- **Default LLM** is now `phi4-mini:3.8b` (2.5 GB VRAM, fits 8 GB GPUs
  comfortably). v0.1 defaulted to `llama3` (untested in this repo).
- **Database access** is now context-managed and per-call; no long-lived
  shared connection.
- **Settings are typed** end-to-end. Configuration errors fail at
  import time, not at query time.
- **Error contract** for the executor is explicit: every code path
  returns both `result` and `error` keys (with sensible defaults), so
  downstream nodes never see `KeyError`.
- **CLI entry point** is `nl2sql-agent` (was `python -m app`).

#### Security

- **C-03 (incomplete keyword coverage)**: closed. The new validator
  parses SQL into an AST and rejects any non-SELECT top-level, any
  dangerous function, and any forbidden keyword with word-boundary
  matching.
- **M-04 / M-05 (connection leaks)**: closed. All connections are
  opened and closed via `Database.connect()` context manager.
- **M-07 (raw error in LLM prompt)**: now wrapped and truncated
  (`format_data()`); the writer prompt uses an explicit `error_section`
  block instead of free-form f-string interpolation.
- **M-10 (no recursion limit)**: the new routing still uses LangGraph
  defaults, but the retry cap is enforced by `route_after_execute` and
  is configurable per-run.
- **m-01 (deprecated `google.generativeai`)**: removed. We now use
  `google-genai` (which itself uses the maintained SDK under the
  hood).
- **m-02 (unpinned dependencies)**: closed. All deps are pinned in
  `pyproject.toml`.
- **m-03 (unused packages)**: closed. The minimum necessary SDKs are
  listed in `pyproject.toml`.

#### Fixed

- **PRAGMA f-string interpolation** (C-04): closed. We use
  `sqlglot`'s parameterised `pragma_table_info(?)` instead of
  f-stringing table names.
- **Hardcoded database path** (M-06): closed. The path is a `Settings`
  field and propagates everywhere.

#### Removed

- `app.py` and `backend.py` at the repo root (replaced by
  `src/nl2sql_agent/`).
- `requirements.txt` (replaced by `pyproject.toml`).
- `tests/test_*.py` legacy files that tested the old `backend.py`
  shape. Equivalent coverage lives in `tests/unit/`.

#### Developer experience

- `uv sync --extra dev` replaces `pip install -r requirements.txt`.
- `uv run <command>` runs commands inside the managed venv.
- `uv run ruff check src tests` for lint.
- `uv run mypy src/nl2sql_agent` for type checking.
- `uv run pytest tests/unit` for tests.
- `uv run pytest --cov=src/nl2sql_agent --cov-report=term-missing` for
  coverage.

---

## [0.1.0] — 2026-03-01

Initial release. Streamlit + LangGraph + SQLite, two-file layout
(`app.py` + `backend.py`), keyword-based SQL safety, 126 tests, 100%
coverage of `backend.py`.
