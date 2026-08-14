# NL2SQL Agent — Production-Grade Natural Language to SQL

[![Python 3.12](https://img.shields.io/badge/python-3.12.10-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checker: ty](https://img.shields.io/badge/type%20checker-ty-blue.svg)](https://docs.astral.sh/ty/)
[![Tests: 317 passing](https://img.shields.io/badge/tests-317_passing-brightgreen.svg)](#testing)

> Turn natural-language questions into safe, auditable SQL against SQLite or
> PostgreSQL. Use a local Ollama model or one of six hosted providers, review
> every generated query, and track sessions, plans, runtime, and estimated cost.

---

## Table of contents

1. [What it is](#1-what-it-is)
2. [Why use it](#2-why-use-it)
3. [Quick start](#3-quick-start)
4. [Architecture](#4-architecture)
5. [How the workflow works](#5-how-the-workflow-works)
6. [Configuration](#6-configuration)
7. [LLM providers](#7-llm-providers)
8. [Local Ollama — what runs on your GPU](#8-local-ollama--what-runs-on-your-gpu)
9. [Safety model](#9-safety-model)
10. [Running the UI](#10-running-the-ui)
11. [CLI](#11-cli)
12. [Testing](#12-testing)
13. [Project layout](#13-project-layout)
14. [API reference](#14-api-reference)
15. [Operations runbook](#15-operations-runbook)
16. [Migration from v0.1](#16-migration-from-v01)
17. [Roadmap](#17-roadmap)
18. [Contributing](#18-contributing)
19. [License](#19-license)

---

## 1. What it is

**NL2SQL Agent** is a small, focused Python service that lets end users ask
business questions in plain English and get a clean, well-formatted answer
backed by real SQL against a real database.

The system is composed of five cooperating pieces:

| Piece | Module | Responsibility |
|---|---|---|
| **Configuration** | `nl2sql_agent.config` | Single source of truth for runtime settings, loaded from env vars, `.env`, or code. |
| **Database** | `nl2sql_agent.db` | Read-only SQLite and PostgreSQL backends with normalized plans and metrics. |
| **Safety** | `nl2sql_agent.security` | AST-based SQL validation using `sqlglot` — allow-lists, not deny-lists. |
| **LLM factory** | `nl2sql_agent.llm` | Multi-provider construction for Ollama, Hugging Face, OpenAI, Anthropic, Gemini, xAI, and Agnes AI. |
| **Agent** | `nl2sql_agent.agent` | LangGraph workflow: schema → write → guard → execute → summarize. |
| **Prompts** | `nl2sql_agent.prompts` | Versioned, single-source prompt templates. |
| **UI** | `nl2sql_agent.ui` | Streamlit Chat, Costs, Sessions, Insights, and Pricing views. |
| **CLI** | `nl2sql_agent.cli` | One-shot CLI for scripts and CI. |

---

## 2. Why use it

- **Local-first by default.** Runs end-to-end on a laptop with no external
  API calls. Default model is **Microsoft Phi-4-mini** served by **Ollama**.
- **Production-grade safety.** SQL is parsed by `sqlglot` into an AST and
  validated against a configurable allow-list policy. The legacy approach
  of regex-matching destructive keywords is gone — it can no longer be
  fooled by column names like `updated_at`.
- **LangGraph, not magic.** Every step is an explicit node you can stream,
  log, debug, and replace. There is a real state machine with retries.
- **Pinned, reproducible, modern.** Python 3.12.10 and `uv`-managed direct
  dependencies, with security floors expressed as transitive constraints.
- **Tested.** A comprehensive offline suite plus opt-in live Ollama integration tests
  (config, db, security, prompts, agent, llm factory, text utilities).
- **Observable.** Structured Loguru logging, request-friendly error
  contracts, JSON logging mode for log aggregators.

---

## 3. Quick start

### Prerequisites

- Windows 11, Linux, or macOS
- Python 3.12.10 — `uv` will install this for you
- Ollama 0.6.2+ running locally (only required for the default provider)

### Install

```bash
git clone <this-repo>
cd natural-language-to-sql-agent
uv sync --all-groups
```

### Pull a small local model

```bash
ollama pull phi4-mini:3.8b     # 2.5 GB — recommended for 8 GB VRAM
# or
ollama pull qwen3.5:4b         # 3.4 GB — better quality, also fits
```

### Run the Streamlit UI

On Windows, double-click `Launch NL2SQL Agent.cmd`. It starts the locked `uv`
environment, opens the app on `127.0.0.1:8512`, and keeps a visible log window;
press Ctrl+C there to stop it.

The equivalent command on any platform is:

```bash
uv run nl2sql-agent serve
```

Open http://localhost:8512, choose **Ollama** as the provider, pick
`phi4-mini:3.8b`, and start asking.

### Or use the CLI for a single question

```bash
uv run nl2sql-agent ask "How many employees are in each department?"
# → Engineering: 3, HR: 2, Marketing: 2, Sales: 3

uv run nl2sql-agent ask --show-sql "What is the total salary in Engineering?"
```

---

## 4. Architecture

```
                       ┌─────────────────────────────────────┐
                       │            Streamlit UI             │
                       │  (provider + model + chat input)    │
                       └────────────────┬────────────────────┘
                                        │ build_chat_model(...)
                                        ▼
   ┌────────────────────────────────────────────────────────────┐
   │                    NL2SQLAgent (LangGraph)                  │
   │                                                            │
   │   ┌─────────────┐  ┌─────────┐  ┌──────────┐  ┌─────────┐  │
   │   │ fetch_schema │→ │ writer  │→ │ guardian │→ │ executor│  │
   │   └─────────────┘  └────┬────┘  └────┬─────┘  └────┬────┘  │
   │         ▲               │           │             │       │
   │         │               │  retry    │  unsafe     │       │
   │         └───────────────┘           │             │       │
   │                                     │             ▼       │
   │                                     │     ┌─────────────┐ │
   │                                     └────→│ summarizer  │ │
   │                                           └──────┬──────┘ │
   └──────────────────────────────────────────────────┼────────┘
                                                      ▼
                                          ┌───────────────────┐
                                          │ Streamlit display │
                                          │  + raw rows table │
                                          └───────────────────┘
```

The agent's responsibilities are **strictly separated**: the database layer
doesn't know about the LLM, the security layer doesn't know about the
workflow, and the LLM factory doesn't know about the database. This makes
each piece independently testable and replaceable.

---

## 5. How the workflow works

Every question goes through the same five nodes, in this order:

| # | Node | Reads from state | Writes to state |
|---|---|---|---|
| 1 | `fetch_schema` | (database) | `schema: str` |
| 2 | `writer` | `question`, `schema`, optional previous `error` | `sql_query`, `retry_count++` |
| 3 | `guardian` | `sql_query` | `error: str` (empty if safe) |
| 4 | `executor` | `sql_query` | `result`, `raw_rows`, `columns`, `row_count`, `error` |
| 5 | `summarizer` | `question`, `sql_query`, `result`, `error` | `final_answer` |

**Routing decisions:**

- After **guardian**: if the SQL is unsafe, skip the executor and go
  directly to the summarizer so the user sees a clear explanation.
- After **executor**: if the SQL failed at execution time *and* the
  retry budget is not exhausted, route back to the **writer** with the
  error injected into the prompt. Otherwise summarize.

The default retry budget is 3 attempts. This is configurable via
`NL2SQL_MAX_RETRIES`.

---

## 6. Configuration

All settings are loaded via Pydantic Settings from environment variables
prefixed with `NL2SQL_`, then from a `.env` file in the working directory,
then from program defaults. You can inspect the resolved configuration at
runtime:

```bash
uv run nl2sql-agent config
```

### Key environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NL2SQL_PROVIDER` | `ollama` | One of `ollama`, `huggingface`, `openai`, `anthropic`, `gemini`, `xai`, `agnes`. |
| `NL2SQL_MODEL` | `phi4-mini:3.8b` | Model identifier for the chosen provider. |
| `NL2SQL_OLLAMA_BASE_URL` | `http://localhost:11434` | Operator-only endpoint. HTTP is loopback-only; remote endpoints require HTTPS. |
| `NL2SQL_OLLAMA_KEEP_ALIVE` | `5m` | How long Ollama keeps the model loaded. |
| `OPENAI_API_KEY` | — | Required when `NL2SQL_PROVIDER=openai`. |
| `GOOGLE_API_KEY` | — | Required when `NL2SQL_PROVIDER=gemini`. |
| `ANTHROPIC_API_KEY` | — | Required when `NL2SQL_PROVIDER=anthropic`. |
| `HF_TOKEN` | — | Required when `NL2SQL_PROVIDER=huggingface`; `NL2SQL_HF_TOKEN` is also accepted. |
| `XAI_API_KEY` | — | Required when `NL2SQL_PROVIDER=xai`; `NL2SQL_XAI_API_KEY` is also accepted. |
| `AGNES_API_KEY` | — | Required when `NL2SQL_PROVIDER=agnes`; `NL2SQL_AGNES_API_KEY` is also accepted. |
| `NL2SQL_DB_PATH` | `company.db` | Path to the SQLite database file. |
| `NL2SQL_DB_BACKEND` | `sqlite` | CLI database backend: `sqlite` or `postgres`. |
| `NL2SQL_POSTGRES_DSN` | — | Operator-only PostgreSQL DSN. Never shown or saved by the UI. |
| `NL2SQL_POSTGRES_SCHEMA` | `public` | Single PostgreSQL schema available to the guardian. |
| `NL2SQL_DB_LOCK_TIMEOUT_SECONDS` | `5` | PostgreSQL lock timeout. |
| `NL2SQL_DB_SEED` | `true` | Seed the database with sample data on first run. |
| `NL2SQL_DB_MAX_ROWS` | `1000` | Cap on rows returned per query. |
| `NL2SQL_DB_QUERY_TIMEOUT_SECONDS` | `15` | Per-query execution timeout. |
| `NL2SQL_DB_MAX_VM_STEPS` | `5000000` | SQLite virtual-machine step limit. |
| `NL2SQL_DB_UPLOAD_MAX_MB` | `50` | Maximum database upload size in the UI. |
| `NL2SQL_MAX_RETRIES` | `3` | SQL rewrite attempts after a failed execution. |
| `NL2SQL_LLM_TEMPERATURE` | `0.0` | Ollama/Agnes sampling temperature; other hosted reasoning models use medium effort. |
| `NL2SQL_LLM_MAX_TOKENS` | `1024` | Max output tokens per LLM call. |
| `NL2SQL_SQL_ALLOW_SUBQUERIES` | `true` | Allow nested SELECT. |
| `NL2SQL_SQL_ALLOW_JOINS` | `true` | Allow JOIN clauses. |
| `NL2SQL_SQL_ALLOW_AGGREGATES` | `true` | Allow COUNT, SUM, AVG, etc. |
| `NL2SQL_SQL_ALLOW_CTE` | `true` | Allow WITH ... AS. |
| `NL2SQL_SQL_MAX_JOINS` | `8` | Maximum JOIN clauses per query. |
| `NL2SQL_SQL_MAX_SUBQUERIES` | `8` | Maximum nested subqueries per query. |
| `NL2SQL_SQL_MAX_CTES` | `8` | Maximum CTEs per query. |
| `NL2SQL_SCHEMA_MAX_TABLES` | `8` | Detailed schemas sent to the writer. |
| `NL2SQL_STATE_PATH` | `~/.nl2sql-agent/state.sqlite3` | Local sessions, pricing, cost, plan, and metric store. |
| `NL2SQL_QUERY_WARN_DURATION_MS` | `1000` | Runtime warning threshold. |
| `NL2SQL_QUERY_WARN_ESTIMATED_ROWS` | `100000` | Planner row-estimate warning threshold. |
| `NL2SQL_QUERY_WARN_POSTGRES_COST` | `10000` | PostgreSQL planner-cost warning threshold. |
| `NL2SQL_QUERY_WARN_SQLITE_VM_STEPS` | `1000000` | SQLite VM-step warning threshold. |
| `NL2SQL_LOG_LEVEL` | `INFO` | Loguru log level. |
| `NL2SQL_LOG_JSON` | `false` | Emit JSON-formatted logs. |
| `NL2SQL_AUDIT_ENABLED` | `true` | Write redacted operational audit events. |
| `NL2SQL_AUDIT_PATH` | `logs/audit.jsonl` | Audit JSONL destination. |

### PostgreSQL read-only role

Use a dedicated role with only connection, schema usage, and table reads. Do
not supply an owner or administrator account:

```sql
CREATE ROLE nl2sql_reader LOGIN PASSWORD '<set outside source control>';
GRANT CONNECT ON DATABASE analytics TO nl2sql_reader;
GRANT USAGE ON SCHEMA public TO nl2sql_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO nl2sql_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO nl2sql_reader;
```

Then configure `NL2SQL_POSTGRES_DSN`, `NL2SQL_POSTGRES_SCHEMA`, and—for CLI
`ask`—`NL2SQL_DB_BACKEND=postgres`. The Streamlit PostgreSQL source appears
when the DSN is present. The app refuses elevated roles and never displays or
persists the DSN. The packaged `eval` corpus remains SQLite-only.

---

## 7. LLM providers

| Provider | Auth | Default model | Notes |
|---|---|---|---|
| **Ollama** | None | `phi4-mini:3.8b` | Local, private, no internet required. |
| **Hugging Face** | `HF_TOKEN` | `openai/gpt-oss-120b:fastest` | Direct HF router; accepts custom `namespace/model[:routing-policy]` IDs. |
| **OpenAI** | `OPENAI_API_KEY` | `gpt-5.6-luna` | Only Luna and `gpt-5.6-terra`; Responses API at medium effort. |
| **Anthropic** | `ANTHROPIC_API_KEY` | `claude-sonnet-5` | Adaptive thinking at medium effort. |
| **Gemini** | `GOOGLE_API_KEY` | `gemini-3.7-flash` | Also supports `gemini-3.5-flash-lite`; medium thinking. |
| **xAI** | `XAI_API_KEY` | `grok-4.6` | Direct xAI API at medium reasoning effort. |
| **Agnes AI** | `AGNES_API_KEY` | `agnes-2.5-flash` | Fixed Agnes API Hub endpoint; documented Chat Completions Thinking mode. |

The hosted allow-lists are enforced in settings, CLI overrides, and the model
factory. Hugging Face remains intentionally flexible, but its custom model ID
must use the documented repository form and support medium reasoning through
the Responses API. Agnes uses the provider's documented boolean Thinking flag,
not an invented low/medium/high effort value. Ollama model names remain
unrestricted. See the [Agnes 2.5 Flash API reference](https://agnes-ai.com/en/docs/agnes-25-flash).

### UI cost estimates

After each hosted-model run, the UI prices each actual model call from
provider-reported input, output, cache-read, and cache-creation usage. Pricing
rules have UTC effective windows and are editable from the Pricing view.

```text
(input tokens × input rate + output tokens × output rate) / 1,000,000
```

| Model | Input / 1M tokens | Output / 1M tokens | Pricing note |
|---|---:|---:|---|
| Sonnet 5 | $2.00 | $10.00 | Batch API receives a 50% discount. |
| Gemini Flash 3.7 | $0.75 | $3.75 | Promotional rate through December 31, 2026. |
| Gemini 3.5 Flash Lite | $0.30 | $2.50 | Batch rate is $0.15 / $1.25. |
| GPT-5.6 Luna | $0.20 | $1.20 | Prompt-cache reads are $0.02. |
| GPT-5.6 Terra | $2.00 | $12.00 | Rates double above 272k input tokens. |
| Grok 4.6 | $2.00 | $6.00 | Fast mode or prompts above 200k use $4 / $12. |
| Agnes 2.5 Flash | $0.00 | $0.00 | Current promotion; documented standard rate is $0.03 / $0.15. |

The seeded catalog is local configuration, not a provider billing feed. Edits
take effect on the next run without a restart; historical runs retain an
immutable rule snapshot. Cache, batch, fast-mode, and long-context prices are
applied only when actual per-call usage identifies them. Normal interactive
chat is standard mode. Missing or expired rules produce an unpriced warning.
The Costs view provides session and monthly totals, model/daily charts,
disabled-by-default budget alerts at 80% and 100%, and privacy-safe CSV export.

The factory is in `nl2sql_agent.llm.factory.build_chat_model`. You can
also call it directly from your own code:

```python
from nl2sql_agent.config import get_settings
from nl2sql_agent.llm import build_chat_model

llm = build_chat_model(get_settings())
response = llm.invoke("What is 2 + 2?")
print(response.content)
```

---

## 8. Local Ollama — what runs on your GPU

The default `phi4-mini:3.8b` model uses about **2.5 GB of VRAM** in Q4_K_M
quantization and runs comfortably on 8 GB GPUs. Tested on an RTX 4060
(8 GB).

| Local model | Size (Q4) | Best for |
|---|---|---|
| `qwen3.5:0.8b` | 1.0 GB | Lowest resource, weakest quality. |
| `qwen3.5:2b` | 2.7 GB | Sweet spot for very tight memory. |
| **`phi4-mini:3.8b`** | **2.5 GB** | **Default. Best quality / size ratio for SQL.** |
| `qwen3.5:4b` | 3.4 GB | Strong alternative, similar size. |
| `qwen3.5:9b` | 6.6 GB | Best quality, requires ~10 GB VRAM. |

> **VRAM math for an 8 GB card:** a 4B Q4 model uses ~3.4 GB, leaving
> ~4 GB for KV cache and the rest of the system. With 9B you typically
> need at least 10 GB or aggressive KV cache offloading.

You can pull any of these with `ollama pull <name>` and switch via
`NL2SQL_MODEL=<name>`.

---

## 9. Safety model

The agent treats every question as untrusted user input and every LLM
output as untrusted generated code.

**Five lines of defense:**

1. **Read-only database connection.** SQLite queries use URI `mode=ro`,
   `query_only`, disabled extensions, and an untrusted-schema policy.
   PostgreSQL uses non-autocommit read-only transactions, verified
   `transaction_read_only`, statement/lock timeouts, a fixed search path, and
   rejects superuser, BYPASSRLS, CREATEDB, or CREATEROLE roles.
2. **AST-based validation.** Before any SQL reaches the database, it is
   parsed by `sqlglot` into an AST and checked:
   - Exactly one statement.
   - Top-level is `SELECT` (or `UNION`/`INTERSECT`/`EXCEPT`).
   - No dangerous SQLite or PostgreSQL file, configuration, advisory-lock, or
     sleep functions; no `SELECT INTO`, row locks, or cross-schema references.
   - No subqueries, joins, CTEs, or aggregates if disabled by policy.
   - Word-boundary scan for `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`,
     `CREATE`, `REPLACE`, `TRUNCATE`, `GRANT`, `REVOKE`, `PRAGMA`,
     `ATTACH`, `DETACH`, `VACUUM`, `REINDEX`, `INSTALL`, `COPY`.
3. **Configurable policy.** Queries are restricted to permitted tables,
   with configurable feature toggles and JOIN/subquery/CTE count limits.
4. **Row cap.** A hard cap (`NL2SQL_DB_MAX_ROWS`, default 1000) prevents
   `SELECT *` from returning millions of rows.
5. **Execution budget and preflight.** SQLite uses a VM-step/deadline guard and
   `EXPLAIN QUERY PLAN`; PostgreSQL uses `EXPLAIN (FORMAT JSON, COSTS TRUE)`
   without `ANALYZE`, so preflight never executes the query.

Audit events contain hashes and literal-redacted SQL, never raw questions,
result rows, database paths, sample values, or credentials.

The validator lives in `src/nl2sql_agent/security/sql_validator.py` and
is fully tested in `tests/unit/test_sql_validator.py`.

---

## 10. Running the UI

On Windows, double-click `Launch NL2SQL Agent.cmd`. For terminal launches:

```bash
# Default port 8512 (from .streamlit/config.toml)
uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py

# Custom port
uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py --server.port 8513
```

### What the UI shows

- **Database source.** Use the seeded demo, a session-scoped SQLite upload, or
  the operator-configured PostgreSQL DSN. Uploaded databases are never seeded
  or modified.
- **Schema controls.** Browse ordinary tables, authorize the tables available
  to SQL, and optionally expose bounded sample rows from uploads to the model.
- **Approval flow.** Generation stops at an editable, validated SQL preview.
  Run explicitly to revalidate and execute it.
- **Saved sessions.** Reopen conversations, pending approvals, and approved
  SQL. Questions, answers, safe metrics, and plans are saved locally; raw
  result rows, CSV payloads, uploads, schemas, keys, and DSNs are not.
- **Costs and insights.** Review session/model costs, budget warnings, runtime
  trends, normalized SQLite/PostgreSQL plans, full scans, and expensive-query
  warnings. Cost export excludes questions, answers, SQL, and results.
- **Provider controls.** Pick one of the approved hosted models, enter a custom
  Hugging Face model ID, or refresh the live Ollama model list. Operators
  configure the Ollama endpoint; it is not editable in the browser.

### Programmatic access

```python
from langchain_ollama import ChatOllama
from nl2sql_agent.config import Settings
from nl2sql_agent.agent import NL2SQLAgent

llm = ChatOllama(model="phi4-mini:3.8b")
agent = NL2SQLAgent(llm, settings=Settings(db_path="company.db"))
result = agent.run("What is the average salary?")
print(result["final_answer"])
```

For approval-first applications, prepare without executing, optionally edit
the SQL, then execute through the same guardian again:

```python
prepared = agent.prepare("What is the average salary?")
result = agent.execute_prepared(prepared, sql_query=prepared["sql_query"])
```

---

## 11. CLI

```text
$ uv run nl2sql-agent --help
usage: nl2sql-agent [-h] {ask,config,serve,eval} ...

$ uv run nl2sql-agent ask --help
usage: nl2sql-agent ask [-h] [--provider PROVIDER] [--model MODEL]
                        [--api-key API_KEY] [--show-sql]
                        question

$ uv run nl2sql-agent config
{
  "provider": "ollama",
  "model": "phi4-mini:3.8b",
  ...
}

$ uv run nl2sql-agent serve --help
usage: nl2sql-agent serve [-h] [--port PORT] [--host HOST]

$ uv run nl2sql-agent eval --min-pass-rate 0.8
cases=15 accuracy=... safety=... execution=... p95_ms=... report=...
```

---

## 12. Testing

SQL preparation has a parse-count regression test. On the documented complex
CTE benchmark (2,000 calls), reuse of a single AST reduced preparation latency
from 4.36 ms to 2.68 ms per call on the development machine; results vary by
hardware.

Schema-context retrieval also has single-pass ranking and connection-reuse
regression tests. Reusing normalized identifiers and loading foreign-key
metadata only for selected tables reduced median retrieval from 3.060 ms to
2.224 ms for 10 tables (27%) and from 25.410 ms to 14.911 ms for 120 tables
(41%) on the development machine; results vary by hardware.

The project ships with **317 tests**, including an offline suite and opt-in
live integration tests for external providers.

```bash
# Unit tests (no external services needed)
uv run pytest tests/unit -v

# With coverage
uv run pytest tests/unit --cov=src/nl2sql_agent --cov-report=term-missing

# Integration test (requires local Ollama running)
uv run pytest tests/integration -v

# Result and safety evaluation (uses the configured provider)
uv run nl2sql-agent eval --min-pass-rate 0.8
```

Upload handling, evaluation scoring, CLI parsing, and agent behavior are
covered offline. A Streamlit `AppTest` smoke check verifies that the documented
entrypoint renders without exceptions.

---

## 13. Project layout

```
natural-language-to-sql-agent/
├── Launch NL2SQL Agent.cmd  # Windows double-click launcher
├── pyproject.toml            # Single source of truth for deps + tool config
├── uv.lock                   # Reproducible lockfile
├── README.md                 # This file
├── CHANGELOG.md              # Release history
├── LICENSE
├── SECURITY.md
├── src/
│   └── nl2sql_agent/
│       ├── __init__.py
│       ├── cli.py            # `nl2sql-agent` command-line entry point
│       ├── config/           # Pydantic Settings
│       ├── db/               # SQLite/PostgreSQL backends + plans/metrics
│       ├── security/         # AST-based SQL safety
│       ├── llm/              # Multi-provider LLM factory
│       ├── prompts/          # Versioned prompt templates
│       ├── agent/            # LangGraph workflow + state
│       ├── evaluation/       # Evaluation runner + packaged demo corpus
│       ├── persistence.py    # Saved sessions, pricing, costs, and insights
│       ├── ui/               # Multipage Streamlit components + app
│       └── utils/            # Logging, redacted audit, text helpers
└── tests/
    ├── conftest.py
    ├── unit/                 # Fast, no external services
    └── integration/          # Requires a running local Ollama
```

---

## 14. API reference

The full, type-annotated surface is discoverable in the source. The most
common entry points:

- `nl2sql_agent.NL2SQLAgent(llm, *, settings=None, database=None,
  allowed_tables=None, include_sample_values=None)` — the workflow class.
  `run()` and `stream()` remain end-to-end; `prepare()`, `stream_prepare()`,
  and `execute_prepared()` support approval-first clients.
- `nl2sql_agent.config.get_settings()` — singleton accessor for the
  `Settings` instance.
- `nl2sql_agent.llm.build_chat_model(settings, *, provider, model, ...)` —
  build any of the seven supported provider integrations.
- `nl2sql_agent.security.validate_sql(sql, policy=None)` — validate a
  SQL string and return the parsed `Select` nodes; pass `dialect="postgres"`
  and `allowed_schema` for PostgreSQL.
- `nl2sql_agent.db.Database(path, *, timeout_seconds, max_rows)` —
  the SQLite wrapper. `PostgresDatabase(dsn, schema=...)` implements the same
  backend contract. `QueryPlan`, `QueryMetrics`, and `QueryResult` expose
  normalized observability data.
- `nl2sql_agent.persistence.StateStore(path)` — persistent sessions, pricing
  rules, run snapshots, dashboard aggregates, and preferences.

---

## 15. Operations runbook

### Verifying the install

```bash
uv run python -c "import nl2sql_agent; print(nl2sql_agent.__version__)"
# → 0.5.1

uv run nl2sql-agent config | python -m json.tool | head -20
```

### Smoke test against local Ollama

```bash
uv run nl2sql-agent ask "How many employees are there?"
# → There are **10** employees.
```

### Verifying the guardian blocks bad SQL

The integration test `tests/integration/test_ollama_live.py` includes a
case that forces the LLM to return `DROP TABLE employees` and asserts
that the table is still there afterward:

```python
class FakeLLM:
    def invoke(self, messages):
        return AIMessage(content="DROP TABLE employees")

agent = NL2SQLAgent(FakeLLM(), settings=live_settings)
result = agent.run("destroy everything")
assert "validation" in result["error"].lower()  # guardian blocked it
```

### Increasing log verbosity

```bash
NL2SQL_LOG_LEVEL=DEBUG uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py
```

### JSON logs for ELK / Loki

```bash
NL2SQL_LOG_JSON=true uv run nl2sql-agent ask "..."
```

### Bumping the retry budget

```bash
NL2SQL_MAX_RETRIES=5 uv run nl2sql-agent ask "complex question"
```

---

## 16. Migration from v0.1

The previous release (`v0.1`, the original `app.py` + `backend.py`
two-file version) has been replaced by a properly modularized package.
For most users, the differences are:

| v0.1 | v0.2 |
|---|---|
| `app.py` and `backend.py` at the repo root | `src/nl2sql_agent/` package |
| `pip install -r requirements.txt` | `uv sync --all-groups` |
| `python -m streamlit run app.py` | `uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py` |
| `from backend import SQLAgent` | `from nl2sql_agent.agent import NL2SQLAgent` |
| Keyword-regex SQL safety | AST-based SQL safety via `sqlglot` |
| Hard-coded `company.db` path | `NL2SQL_DB_PATH` env var |
| `setup_db()` on every agent instantiation | Idempotent; runs once per process |

The 25 known issues from the v0.1 audit are all addressed in v0.2. See
`CHANGELOG.md` for the complete list.

---

## 17. Roadmap

Possible future work after the current unreleased changes:

- **Optional schema embeddings** for databases where deterministic identifier
  ranking is insufficient.
- **OpenTelemetry tracing** with one-line enablement.
- **Additional database engines** such as MySQL via the same backend contract.
- **Optional encrypted multi-user session storage** for server deployments.
- **WebSocket / FastAPI** backend instead of Streamlit for production
  multi-user deployments.

---

## 18. Contributing

1. Fork and clone.
2. Install the pinned Python and all development groups with `uv sync --all-groups`.
3. Make your change. Add tests. Run `uv run ruff check src tests`,
   `uv run ty check src`, and `uv run pytest tests/unit`.
4. Open a PR with a clear description.

---

## 19. License

[MIT](LICENSE).

<p align="center">Made with ❤️ by Ahmad Mujtaba</p>
