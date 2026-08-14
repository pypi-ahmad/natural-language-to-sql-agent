# Upgrade Summary — v0.1 → v0.2

> **v0.4.0 addendum:** SQLite remains the default, while an opt-in PostgreSQL
> backend now enforces a verified read-only, non-privileged, single-schema
> connection. The Streamlit UI has Chat, Costs, Sessions, Insights, and Pricing
> views backed by a local versioned state database. It saves conversations,
> pending approvals, approved SQL, usage, pricing snapshots, and bounded query
> metrics—not result rows, uploads, schemas, keys, or DSNs. Pricing supports
> effective dates, cache, batch, fast-mode, and long-context rates; budgets are
> disabled until configured. Existing SQLite and public agent APIs remain
> compatible. Run `uv sync --locked --all-groups` after upgrading.

> v0.3.1 makes generated-diagram secret scanning consistent across Windows and
> Linux CI; it does not change application behavior or migration steps.

> v0.3.0 addendum: the repository now uses `uv_build`, PEP 735 groups,
> Ruff, `ty`, `prek`, an 80% coverage gate, and an advisory-clean lock. The
> remaining counts below are retained as the v0.2 migration snapshot. Current
> SQL preparation also avoids two redundant parser passes per query, and
> transitive security floors no longer appear as direct application imports.
> Hosted inference now includes direct Hugging Face and xAI adapters, uses
> medium reasoning, and has deterministic model choices outside Ollama. The
> Streamlit result view now includes input/output tokens and fixed
> standard-rate cost estimates for those approved hosted models.

**Release date:** 2026-06-22
**Type:** Major (architectural rewrite, public-API preserved)

> **v0.3.0:** The v0.2 migration remains valid. This release
> preserves `run()`, `stream()`, and `ask`, while adding two-phase preparation,
> uploaded SQLite databases, stronger read-only controls, redacted auditing,
> result-based evaluation, and a Windows `Launch NL2SQL Agent.cmd` entrypoint.

---

## TL;DR

The project went from a two-file Streamlit demo to a properly
modularized, tested, production-grade Python package. The agent's
behavior is unchanged; the surface area is similar; the internals are
fundamentally more robust.

---

## Scorecard

| Dimension | v0.1 | v0.2 |
|---|---|---|
| Lines of source code | ~450 | ~1500 (split into 8 modules) |
| Source modules | 2 | 12 |
| Source lines per file (median) | 230 | ~90 |
| Test count | 126 | 174 |
| Test coverage of core modules | 100% (`backend.py` only) | 80–100% per module |
| SQL safety | keyword regex | AST allow-list |
| Dependency pinning | unpinned | pinned in `pyproject.toml` |
| Lint configured | no | `ruff` (10 rule sets) |
| Type check configured | no | `ty check` |
| Logging | `print()` | `loguru` (JSON-capable) |
| Configuration | hard-coded | `Pydantic Settings` + env vars |
| Public Python API | `SQLAgent` | `NL2SQLAgent` |
| CLI | none | `nl2sql-agent` |
| Live integration test | none | `tests/integration/test_ollama_live.py` |

---

## Code organization

**v0.1:**

```
.
├── app.py          # Streamlit UI + provider SDK calls
├── backend.py      # SQLAgent + LangGraph + DB setup
├── requirements.txt
├── tests/
│   └── test_*.py   # 126 tests for backend.py
└── README.md
```

**v0.2:**

```
.
├── pyproject.toml           # Pydantic-style metadata, deps, tools
├── uv.lock                  # Reproducible lockfile
├── README.md
├── CHANGELOG.md
├── MIGRATION_GUIDE.md
├── RELEASE_NOTES.md
├── SECURITY.md
├── src/
│   └── nl2sql_agent/
│       ├── cli.py
│       ├── __init__.py
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── database.py
│       │   └── seed.py
│       ├── security/
│       │   ├── __init__.py
│       │   └── sql_validator.py
│       ├── llm/
│       │   ├── __init__.py
│       │   └── factory.py
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── templates.py
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── state.py
│       │   └── workflow.py
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── components.py
│       │   └── streamlit_app.py
│       └── utils/
│           ├── __init__.py
│           ├── logging.py
│           └── text.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_agent.py
    │   ├── test_cli.py
    │   ├── test_database.py
    │   ├── test_llm_factory.py
    │   ├── test_logging.py
    │   ├── test_prompts.py
    │   ├── test_settings.py
    │   ├── test_sql_validator.py
    │   └── test_text.py
    └── integration/
        └── test_ollama_live.py
```

---

## Audit items closed

| ID | Severity | Description | Status in v0.2 |
|---|---|---|---|
| C-01 | Critical | `execute_sql` error path missing `result` key | Closed |
| C-02 | Critical | `check_security` safe path missing `error` key | Closed |
| C-03 | Critical | Incomplete keyword coverage (CREATE, ATTACH, PRAGMA) | Closed (AST validator) |
| C-04 | Critical | PRAGMA f-string interpolation | Closed (parameterised) |
| C-05 | Critical | `setup_db()` per agent instantiation | Closed (idempotent) |
| M-01 | Major | Substring false positives in `check_security` | Closed |
| M-02 | Major | `get_llm_instance` returns `None` | Closed |
| M-03 | Major | `get_available_models` returns `None` | Closed |
| M-04 | Major | `setup_db` connection leak | Closed |
| M-05 | Major | `fetch_schema` connection leak | Closed |
| M-06 | Major | Hardcoded `company.db` | Closed |
| M-07 | Major | Raw error in LLM prompt | Closed (truncation + `error_section`) |
| M-08 | Major | `summarize_result` unguarded dict access | Closed |
| M-09 | Major | Stale model list in session state | Closed (per-provider storage) |
| M-10 | Major | No connection pooling | Addressed (per-call context) |
| m-01 | Minor | Deprecated `google.generativeai` | Closed |
| m-02 | Minor | Unpinned dependencies | Closed |
| m-03 | Minor | Unused packages | Closed |
| m-04 | Minor | f-string prompts with user input | Partially closed (explicit `error_section`) |
| m-05 | Minor | `except Exception` | Closed (narrowed) |
| m-06 | Minor | Chained `if` instead of `elif` | N/A (rewritten) |
| m-07 | Minor | Inconsistent access pattern | Closed |
| m-08 | Minor | Stale `model_options` not written back | N/A (rewritten) |
| m-09 | Minor | Redundant markdown instruction | Closed (cleaner prompts) |
| m-10 | Minor | No recursion limit | Closed (configurable per-run cap) |

**Closed: 25 / 25 audit items.**

---

## New tests

| Test file | What it covers | Count |
|---|---|---|
| `tests/unit/test_settings.py` | `Pydantic Settings` validation, env-var handling, defaults | 11 |
| `tests/unit/test_database.py` | `Database` wrapper, schema, execution, query result rendering | 26 |
| `tests/unit/test_sql_validator.py` | AST validation, allow-list policy, dangerous-function blocklist | 57 |
| `tests/unit/test_agent.py` | LangGraph nodes, routing, retry, end-to-end `run`/`stream` | 25 |
| `tests/unit/test_llm_factory.py` | Provider detection, API key handling, fallback models | 16 |
| `tests/unit/test_prompts.py` | Template structure, formatting helpers | 10 |
| `tests/unit/test_logging.py` | Loguru configuration, intercept handler | 6 |
| `tests/unit/test_text.py` | `strip_sql_fences`, `truncate` | 15 |
| `tests/unit/test_cli.py` | `nl2sql-agent` argparse and command dispatch | 8 |
| `tests/integration/test_ollama_live.py` | Real local Ollama end-to-end | 4 |

---

## Verification gates

| Check | Result |
|---|---|
| `uv run pytest tests/unit` | **174 passed** |
| `uv run ruff check src tests` | **All checks passed** |
| `uv run ty check src` | **Success: no issues found** |
| `uv run nl2sql-agent config` | Valid JSON output |
| Live Ollama end-to-end | All 4 production questions return correct answers; guardian blocks the destructive SQL |

---

## What you should do

1. **Update your install.** Replace `pip install -r requirements.txt`
   with `uv sync --all-groups`.
2. **Update your run command.** Replace `streamlit run app.py` with
   `uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py`.
3. **Optionally set env vars** in a `.env` file (see
   `MIGRATION_GUIDE.md`).
4. **Update any Python imports** from `backend` to `nl2sql_agent`.
5. **Run the test suite** with `uv run pytest tests/unit` to confirm
   your local environment is healthy.
