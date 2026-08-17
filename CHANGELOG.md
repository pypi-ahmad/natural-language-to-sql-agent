# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.2] — 2026-08-17

### Added

- `CONTRIBUTING.md`, `SUPPORT.md`, and `DISCLAIMER.md`, and GitHub issue templates
  (`.github/ISSUE_TEMPLATE/bug_report.md`, `feature_request.md`) and a pull request template.

### Changed

- Stated in the README that the project wants no donations, sponsorships, or other financial
  support, and linked `SUPPORT.md`/`DISCLAIMER.md`.
- Added a repository link, a `Documentation` table referencing every other doc in the repo, and a
  `Community & support` section to the README.
- `Launch NL2SQL Agent.cmd` now detects a missing `.venv` and runs an explicit `uv sync --locked`
  with a first-time-setup message before launching, instead of relying on `uv run --locked` to
  sync silently.

### Fixed

- Corrected `SECURITY.md`'s redacted-fields claim: the `config` command redacts 7 fields (5
  provider keys plus `NL2SQL_AGNES_API_KEY` and the PostgreSQL DSN), not the 5 previously stated.
- Added the two missing environment-variable rows (`NL2SQL_LLM_REQUEST_TIMEOUT_SECONDS`,
  `NL2SQL_QUERY_WARN_FULL_SCAN`) to the README configuration table.
- `nl2sql_agent.__version__` was hardcoded and had drifted to `0.4.0` across the 0.5.0 and 0.5.1
  releases. It now reads from installed package metadata via `importlib.metadata.version`, so it
  can't silently drift from `pyproject.toml` again.

## [0.5.1] — 2026-08-14

### Changed

- The Streamlit UI now defaults to loopback port `8512` for both direct
  Streamlit launches and the `nl2sql-agent serve` wrapper.
- Version advanced to 0.5.1 for this backward-compatible runtime-default fix.

## [0.5.0] — 2026-08-14

### Added

- Direct Agnes AI support for the strictly allow-listed `agnes-2.5-flash`
  model through its fixed OpenAI-compatible API Hub endpoint.
- `AGNES_API_KEY` and `NL2SQL_AGNES_API_KEY` configuration, CLI/UI selection,
  saved-session restoration, and redacted configuration output.
- Effective-dated Agnes pricing seeded at the documented current promotional
  $0/$0 rate, with the $0.03/$0.15 standard rate retained in the rule notes.

### Changed

- Agnes requests use the provider's documented Chat Completions Thinking flag
  instead of an unsupported OpenAI-style effort value.
- Version advanced to 0.5.0 without adding a provider-specific dependency.

### Security

- The Agnes endpoint is fixed to HTTPS and credentials remain process/session
  only; they are excluded from logs, saved sessions, and configuration output.

## [0.4.0] — 2026-08-14

### Added

- Five-view Streamlit interface: Chat, Costs, Sessions, Insights, and Pricing.
- Local saved sessions with reopen, rename, delete, pending approvals, and
  approved-query history; raw rows, CSV payloads, uploads, schemas, keys, and
  DSNs are excluded from persistence.
- Effective-dated editable pricing with cache-read/cache-creation, batch,
  fast-mode, and per-call long-context rates plus immutable run snapshots.
- Session/model cost dashboards, privacy-safe CSV export, and optional
  non-blocking budget alerts at 80% and 100%.
- Strictly read-only PostgreSQL backend with a single configured schema,
  non-privileged role checks, transaction verification, and timeouts.
- Normalized SQLite/PostgreSQL plans, runtime/work-unit metrics, trends, and
  configurable full-scan, row, planner-cost, and latency warnings.

### Changed

- SQL prompts, parsing, canonicalization, audit redaction, and table
  authorization are dialect-aware.
- Provider usage is retained per actual model call so pricing no longer assumes
  all calls are standard, uncached, or short-context.
- Version advanced to 0.4.0 and Psycopg 3 is now a runtime dependency.

### Security

- PostgreSQL rejects superuser, BYPASSRLS, CREATEDB, and CREATEROLE roles and
  blocks cross-schema references, `SELECT INTO`, row locks, unsafe functions,
  and `EXPLAIN ANALYZE` execution paths.
- Ollama discovery now closes its HTTP client deterministically.

## [0.3.1] — 2026-08-14

### Fixed

- CI now excludes generated architecture HTML from entropy-based secret
  detection; the file embeds public Git revisions that are false positives on
  Linux runners.

## [0.3.0] — 2026-08-14

### Added

- Read-only SQLite query connections, table allowlists, deterministic schema
  selection, query preflight checks, structural SQL limits, and redacted JSONL
  audit events.
- Two-phase `prepare()` / `execute_prepared()` APIs with streamed preparation
  events, stage timings, token usage, and validation retries.
- A 15-case result-based evaluation corpus and `nl2sql-agent eval` command with
  JSON reports, threshold exit codes, safety, latency, retry, token, and cost
  metrics.
- Session-scoped SQLite uploads, schema browsing, table authorization,
  approval-first editable SQL, operational stage timings, complete session
  history, CSV downloads, and history reset controls in Streamlit.
- Direct Hugging Face Inference Providers and xAI integrations, with custom
  Hugging Face repository IDs and fixed medium reasoning effort.
- A Windows `Launch NL2SQL Agent.cmd` file for double-click startup through
  the locked `uv` environment.
- Per-run input/output token metrics and standard-rate cost estimates in the
  Streamlit UI for the six approved hosted models.

### Fixed

- SQL preparation now reuses one parsed AST for validation, physical-table
  authorization, and LIMIT canonicalization. A 2,000-call benchmark improved
  from 4.36 ms to 2.68 ms per call (about 39% lower latency).
- Schema-context ranking now evaluates each identifier once, reuses its active
  connection, and loads foreign-key metadata only for selected tables. Median
  latency improved by 27% on 10 tables and 41% on 120 tables.
- Scope-aware authorization now distinguishes CTE aliases from physical tables,
  including same-name shadowing cases.
- CSV formula injection, oversized upload materialization, editable provider
  endpoints, non-loopback UI binding, exception-detail disclosure, and
  unrestricted audit fields are now blocked.
- Runtime and development dependencies were upgraded until `uv audit --locked`
  reported zero known vulnerabilities and no adverse project statuses.
- SQL row limits are now serialized into the statement that is actually
  executed, and query timeouts now use SQLite progress interruption.
- The documented direct Streamlit file entrypoint now uses import-safe absolute
  package imports.
- `nl2sql-agent config` now redacts configured provider API keys.

### Changed

- Removed redundant direct dependency declarations and the duplicate
  `pip-audit` toolchain. Vulnerable transitive version floors are now uv
  constraints, while CI continues to use `uv audit --locked`.
- Simplified agent token accounting, summarizer response state, audit dispatch,
  and evaluation database hashing without changing their public contracts.
- Packaging now uses `uv_build`; development tooling uses PEP 735 dependency
  groups, Ruff formatting/linting, `ty`, `prek`, and an 80% coverage gate.
- The default evaluation corpus is package data, so installed wheels can run
  `nl2sql-agent eval` without a source checkout.
- Hosted model choices are deterministic and enforced across settings, CLI,
  UI, and factory boundaries. Live model discovery remains Ollama-only.

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
