# Release Notes

## v0.5.0 — 2026-08-14

This release adds Agnes AI as the seventh model provider, with the single
approved `agnes-2.5-flash` model. It uses Agnes's fixed OpenAI-compatible API
Hub endpoint and documented Chat Completions Thinking flag, reads
`AGNES_API_KEY` (or `NL2SQL_AGNES_API_KEY`), and appears throughout the CLI,
Streamlit provider selector, and saved-session restoration flow.

The local pricing catalog now includes Agnes's documented current $0 input and
output promotion while retaining its $0.03/$0.15 standard rates in the rule
notes. Existing state databases receive the new rule automatically. No new
runtime dependency or state-schema migration is required.

Upgrade with `uv sync --locked --all-groups`. Existing providers, public agent
APIs, databases, saved sessions, and pricing snapshots remain compatible.

## v0.4.0 — 2026-08-14

This release adds a five-view Streamlit workspace: Chat, Costs, Sessions,
Insights, and Pricing. Conversations, pending approvals, approved SQL, usage,
pricing snapshots, and bounded plan/runtime metadata can be reopened from a
local state database; result rows, CSV payloads, uploads, schemas, credentials,
and DSNs are deliberately not saved.

Pricing is editable and effective-dated, with cache, batch, fast-mode, and
per-call long-context rates. Dashboards show session/month totals, model and
daily breakdowns, disabled-by-default 80%/100% budget alerts, and a
privacy-safe CSV export.

PostgreSQL is now an opt-in backend. It requires a least-privileged role,
verifies read-only transactions, restricts access to one configured schema,
uses parameterized metadata queries and timeouts, and never uses `EXPLAIN
ANALYZE`. SQLite remains the default and the evaluation corpus remains
SQLite-only. Both backends expose normalized plans, runtime trends, and
configurable expensive-query warnings.

Upgrade with `uv sync --locked --all-groups`. Existing SQLite configuration
and the `run()`, `stream()`, `prepare()`, and `execute_prepared()` APIs remain
compatible. See `README.md` for PostgreSQL role creation and new settings.

## v0.3.1 — 2026-08-14

This patch makes the secrets hook deterministic across Windows development and
Linux CI by excluding generated architecture HTML that embeds public Git
revisions. Application behavior and the v0.3.0 feature set are unchanged.

---

## v0.3.0 — 2026-08-14

**Status:** Stable
**Upgrade from:** v0.2.0

This release adds approval-first SQL execution, session-scoped SQLite uploads,
deterministic schema selection, redacted audits, a result-based evaluation CLI,
and a Windows double-click launcher. Hosted inference now includes direct
Hugging Face and xAI access with deterministic medium-effort model choices.

The Streamlit UI now preserves complete result history, exports formula-safe
CSV, reports stage and token metrics, and estimates standard hosted-model cost.
Database access, SQL validation, upload limits, endpoint configuration, error
handling, audit fields, dependencies, CI, packaging, and developer tooling were
also hardened. Existing `run()`, `stream()`, and `ask` automation remains
compatible.

---

## v0.2.0 — Historical release

**Date:** 2026-06-22
**Status:** Stable
**Upgrade from:** v0.1.0

---

## Headline

v0.2.0 is a **complete modernization** of the project. The public
behavior is unchanged (you can still ask questions and get SQL-backed
answers), but the internals have been rewritten for production use.

---

## What you get

1. **A real Python package.** `nl2sql_agent` replaces the old
   `app.py` / `backend.py` pair. It can be installed (`uv pip install
   -e .`), versioned, and published.
2. **A real dependency story.** `uv` + `pyproject.toml` + pinned
   versions, no more `pip install -r requirements.txt` with
   unpinned strings.
3. **A real safety story.** AST-based SQL validation with allow-list
   policy, replacing the v0.1 keyword regex.
4. **A real test story.** 174 unit tests + 1 live integration test,
   organized by module, with 80%+ coverage on every core module.
5. **A real observability story.** Structured Loguru logging with
   optional JSON output.
6. **A real CLI.** `nl2sql-agent ask "..."` for one-shot use, in
   addition to the Streamlit UI.

---

## What's in the box

| File / module | Purpose |
|---|---|
| `src/nl2sql_agent/config/` | Pydantic Settings (single source of truth) |
| `src/nl2sql_agent/db/` | SQLite wrapper + seed data |
| `src/nl2sql_agent/security/` | `sqlglot`-based SQL AST validation |
| `src/nl2sql_agent/llm/` | Multi-provider LLM factory |
| `src/nl2sql_agent/prompts/` | Versioned prompt templates |
| `src/nl2sql_agent/agent/` | LangGraph workflow + state |
| `src/nl2sql_agent/ui/` | Streamlit components + app |
| `src/nl2sql_agent/utils/` | Logging + text helpers |
| `src/nl2sql_agent/cli.py` | `nl2sql-agent` command-line entry point |
| `tests/unit/` | 174 unit tests |
| `tests/integration/` | Live Ollama integration test |
| `pyproject.toml` | Deps + tool config (Ruff, ty, pytest, coverage) |
| `uv.lock` | Reproducible lockfile |

---

## Verified behavior

End-to-end run against a real local Ollama with the default
`phi4-mini:3.8b` model on an RTX 4060 (8 GB):

| Question | SQL produced | Answer |
|---|---|---|
| "How many employees are there?" | `SELECT COUNT(*) FROM employees` | "There are **10** employees." |
| "How many employees are in each department?" | `SELECT d.dept_name, COUNT(e.emp_id) FROM departments d JOIN employees e ON d.dept_id = e.dept_id GROUP BY d.dept_name` | Engineering: 3, HR: 2, Marketing: 2, Sales: 3 |
| "What is the total salary in Engineering?" | `SELECT SUM(salary) FROM employees JOIN departments ON employees.dept_id = departments.dept_id WHERE dept_name = 'Engineering'` | "$377,500" |
| "Who is the highest paid employee and what is their department?" | `SELECT e.name, d.dept_name, MAX(e.salary) FROM employees e JOIN departments d ON e.dept_id = d.dept_id` | "Frank in Engineering, $142,500" |
| (attacker) "destroy everything" | `DROP TABLE employees` | **Blocked by guardian.** Table still has 10 rows. |

---

## Validation gates that passed

- `uv run pytest tests/unit` — 174 passed
- `uv run ruff check src tests` — All checks passed
- `uv run ty check src` — Success: no issues found
- `uv run nl2sql-agent config` — prints valid JSON
- Live Ollama end-to-end — all four production questions return
  correct answers; guardian correctly blocks the destructive SQL
