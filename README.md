# NL2SQL Agent: Local-First Natural Language to SQL

[![Python 3.12](https://img.shields.io/badge/python-3.12.10-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checker: ty](https://img.shields.io/badge/type%20checker-ty-blue.svg)](https://docs.astral.sh/ty/)
[![CI](https://github.com/pypi-ahmad/natural-language-to-sql-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/pypi-ahmad/natural-language-to-sql-agent/actions/workflows/ci.yml)

Repository: [github.com/pypi-ahmad/natural-language-to-sql-agent](https://github.com/pypi-ahmad/natural-language-to-sql-agent)

Turn natural-language questions into SQL against SQLite or PostgreSQL, with
read-only execution controls. Use Ollama or one of six hosted providers.
Streamlit lets you review SQL before execution; CLI `ask` executes directly.

This free, open-source project runs on your machine against your database.
You can contribute bug reports, feature ideas, or pull requests.

> [!IMPORTANT]
> The writer sends your question, selected schema context, clarifications and
> configured samples/catalog values to the selected model. Successful results
> are rendered locally without a second model call. Remote providers receive
> prompt context; saved answer text can retain result values on disk. Read
> [DISCLAIMER.md](DISCLAIMER.md) before connecting sensitive data.


## Table of contents

1. [What it is](#1-what-it-is)
2. [Why use it](#2-why-use-it)
3. [Quick start](#3-quick-start)
4. [Architecture](#4-architecture)
5. [How the workflow works](#5-how-the-workflow-works)
6. [Configuration](#6-configuration)
7. [LLM providers](#7-llm-providers)
8. [Local Ollama: what runs on your GPU](#8-local-ollama--what-runs-on-your-gpu)
9. [Safety model](#9-safety-model)
10. [Running the UI](#10-running-the-ui)
11. [CLI](#11-cli)
12. [Verification](#12-verification)
13. [Project layout](#13-project-layout)
14. [API reference](#14-api-reference)
15. [Operations runbook](#15-operations-runbook)
16. [Migration from v0.1](#16-migration-from-v01)
17. [Roadmap](#17-roadmap)
18. [Contributing](#18-contributing)
19. [License](#19-license)


## 1. What it is

NL2SQL Agent is a Python service for asking business questions in plain English.
It runs SQL against a database and formats the results as an answer.

The application has these components:

| Piece | Module | Responsibility |
|---|---|---|
| Configuration | `nl2sql_agent.config` | Single source of truth for runtime settings, loaded from env vars, `.env`, or code. |
| Database | `nl2sql_agent.db` | Read-only SQLite and PostgreSQL backends with normalized plans and metrics. |
| Safety | `nl2sql_agent.security` | AST-based SQL validation using `sqlglot`: allow-lists, not deny-lists. |
| LLM factory | `nl2sql_agent.llm` | Multi-provider construction for Ollama, Hugging Face, OpenAI, Anthropic, Gemini, xAI, and Agnes AI. |
| Agent | `nl2sql_agent.agent` | LangGraph workflow: schema → write → guard → execute → summarize. |
| Prompts | `nl2sql_agent.prompts` | Versioned, single-source prompt templates. |
| UI | `nl2sql_agent.ui` | Streamlit Chat, Costs, Sessions, Insights, and Pricing views. |
| CLI | `nl2sql_agent.cli` | One-shot CLI for scripts and CI. |


## 2. Why use it

- The default configuration runs on a laptop without external API calls,
  using Microsoft Phi-4-mini served by Ollama.
- Layered SQL safety. SQL is parsed by `sqlglot` into an AST and
  validated against a configurable policy. A conservative keyword scan also
  remains; it can reject otherwise valid literals or quoted identifiers.
- Each LangGraph step is a node you can stream, log, debug, or replace.
  The state machine handles routing and retries.
- Python 3.12.10 and `uv`-managed direct dependencies keep installations
  reproducible. Transitive constraints set minimum secure dependency versions.
- Evaluated by execution result. The packaged 15-case smoke corpus compares
  returned values and checks that malicious requests are blocked. It is not a
  substitute for a cross-domain text-to-SQL benchmark.
- Loguru provides structured logs and optional JSON output for log
  aggregators. Errors follow defined response contracts.


## 3. Quick start

### Prerequisites

- Windows 11, Linux, or macOS
- Python 3.12.10: `uv` will install this for you
- An Ollama server running locally with the selected model installed (only
  required for the local provider; the Python client version is not the server version)

### Install

```bash
git clone https://github.com/pypi-ahmad/natural-language-to-sql-agent.git
cd natural-language-to-sql-agent
uv sync --locked --all-groups
```

### Pull a small local model

```bash
ollama pull phi4-mini:3.8b
# or
ollama pull qwen3.5:4b
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
`phi4-mini:3.8b`, and ask about the demo. Reply to any clarification, review
the SQL preview, then choose **Run query** or **Cancel**.

### Or use the CLI for a single question

```bash
uv run nl2sql-agent ask "How many employees are in each department?"
# Demo reference counts: Engineering 3, HR 2, Marketing 2, Sales 3.
# Model-generated SQL and answer wording can vary.

uv run nl2sql-agent ask --show-sql "What is the total salary in Engineering?"
```


## 4. Architecture

See the [implementation report](IMPLEMENTATION_REPORT.md) for verification and
known limits, and [live evaluation evidence](benchmarks/results/README.md) for
case-level model results. These development runs are not leaderboard scores.

Open the interactive diagrams for the [component architecture](diagrams/nl2sql-architecture.html),
[query workflow](diagrams/nl2sql-workflow.html), [approval sequence](diagrams/nl2sql-sequence.html),
[data flow](diagrams/nl2sql-dataflow.html), and [run lifecycle](diagrams/nl2sql-lifecycle.html).

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
   │         │               │  retry    │  invalid    │       │
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

The agent's responsibilities are separated: the database layer
doesn't know about the LLM, the security layer doesn't know about the
workflow, and the LLM factory doesn't know about the database. This makes
each piece independently testable and replaceable.


## 5. How the workflow works

The SQL execution path uses these five nodes. Clarification, unanswerable,
provider-error, and policy-block outcomes exit before execution:

| # | Node | Reads from state | Writes to state |
|---|---|---|---|
| 1 | `fetch_schema` | (database) | `schema: str` |
| 2 | `writer` | `question`, `schema`, optional previous `error` | `sql_query`, `retry_count++` |
| 3 | `guardian` | `sql_query` | `error: str` (empty if safe) |
| 4 | `executor` | `sql_query` | `result`, `raw_rows`, `columns`, `row_count`, `error` |
| 5 | `summarizer` | `question`, `sql_query`, `result`, `error` | `final_answer` |

Routing decisions:

- After `guardian`, safe SQL proceeds to execution. Generation and preflight
  errors may return to `writer` while attempts remain. Policy blocks are terminal.
- After `executor`, an execution error returns to `writer` while attempts
  remain. Successful and exhausted runs proceed to `summarizer`.

The default retry budget is 3 attempts. This is configurable via
`NL2SQL_MAX_RETRIES`.


## 6. Configuration

All settings are loaded via Pydantic Settings from environment variables
prefixed with `NL2SQL_`, then from a `.env` file in the working directory,
then from program defaults. You can inspect the resolved configuration at
runtime:

```bash
uv run nl2sql-agent config
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NL2SQL_PROVIDER` | `ollama` | One of `ollama`, `huggingface`, `openai`, `anthropic`, `gemini`, `xai`, `agnes`. |
| `NL2SQL_MODEL` | `phi4-mini:3.8b` | Model identifier for the chosen provider. |
| `NL2SQL_OLLAMA_BASE_URL` | `http://localhost:11434` | Operator-only endpoint. HTTP is loopback-only; remote endpoints require HTTPS. |
| `NL2SQL_OLLAMA_KEEP_ALIVE` | `5m` | How long Ollama keeps the model loaded. |
| `OPENAI_API_KEY` |: | Required when `NL2SQL_PROVIDER=openai`. |
| `GOOGLE_API_KEY` |: | Required when `NL2SQL_PROVIDER=gemini`. |
| `ANTHROPIC_API_KEY` |: | Required when `NL2SQL_PROVIDER=anthropic`. |
| `HF_TOKEN` |: | Required when `NL2SQL_PROVIDER=huggingface`; `NL2SQL_HF_TOKEN` is also accepted. |
| `XAI_API_KEY` |: | Required when `NL2SQL_PROVIDER=xai`; `NL2SQL_XAI_API_KEY` is also accepted. |
| `AGNESAI_API_KEY` |: | Canonical Agnes credential; legacy `AGNES_API_KEY` and `NL2SQL_AGNES_API_KEY` are also accepted. |
| `NL2SQL_OLLAMA_NUM_CTX` | `4096` | Local model context window. |
| `NL2SQL_SCHEMA_CATALOG_PATH` |: | Operator-authored JSON descriptions, aliases, metrics, and curated values. |
| `NL2SQL_DB_PATH` | `company.db` | Path to the SQLite database file. |
| `NL2SQL_DB_BACKEND` | `sqlite` | CLI database backend: `sqlite` or `postgres`. |
| `NL2SQL_POSTGRES_DSN` |: | Operator-only PostgreSQL DSN. Never shown or saved by the UI. |
| `NL2SQL_POSTGRES_SCHEMA` | `public` | Single PostgreSQL schema available to the guardian. |
| `NL2SQL_DB_LOCK_TIMEOUT_SECONDS` | `5` | PostgreSQL lock timeout. |
| `NL2SQL_DB_SEED` | `true` | Seed the database with sample data on first run. |
| `NL2SQL_DB_MAX_ROWS` | `1000` | Cap on rows returned per query. |
| `NL2SQL_DB_QUERY_TIMEOUT_SECONDS` | `15` | Per-query execution timeout. |
| `NL2SQL_DB_MAX_VM_STEPS` | `5000000` | SQLite virtual-machine step limit. |
| `NL2SQL_DB_UPLOAD_MAX_MB` | `50` | Maximum database upload size in the UI. |
| `NL2SQL_MAX_RETRIES` | `3` | Total writer attempts, including the first attempt. |
| `NL2SQL_LLM_TEMPERATURE` | `0.0` | Ollama/Agnes sampling temperature; other hosted reasoning models use medium effort. |
| `NL2SQL_LLM_MAX_TOKENS` | `1024` | Max output tokens per LLM call. |
| `NL2SQL_LLM_REQUEST_TIMEOUT_SECONDS` | `60.0` | Per-LLM-call request timeout. |
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
| `NL2SQL_QUERY_WARN_FULL_SCAN` | `true` | Warn when a query plan indicates a full table scan. |
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

Then configure `NL2SQL_POSTGRES_DSN` and `NL2SQL_POSTGRES_SCHEMA` (and, for CLI
`ask`, `NL2SQL_DB_BACKEND=postgres`). The Streamlit PostgreSQL source appears
when the DSN is present. The app refuses elevated roles and never displays or
persists the DSN. The packaged `eval` corpus remains SQLite-only.


## 7. LLM providers

| Provider | Auth | Default model | Notes |
|---|---|---|---|
| Ollama | None | `phi4-mini:3.8b` | Local, private, no internet required. |
| Hugging Face | `HF_TOKEN` | `openai/gpt-oss-120b:fastest` | Direct HF router; accepts custom `namespace/model[:routing-policy]` IDs. |
| OpenAI | `OPENAI_API_KEY` | `gpt-5.6-luna` | Also `gpt-5.6-terra` and `gpt-6-luna`; Responses API at medium effort. |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-5` | Adaptive thinking at medium effort. |
| Gemini | `GOOGLE_API_KEY` | `gemini-3.7-flash` | Also supports `gemini-3.5-flash-lite`; medium thinking. |
| xAI | `XAI_API_KEY` | `grok-4.6` | Direct xAI API at medium reasoning effort. |
| Agnes AI | `AGNESAI_API_KEY` | `agnes-3.0-flash` | Fixed API Hub endpoint; legacy `agnes-2.5-flash` remains selectable. |

Local choices include `granite4.2:3b` and `qwen3.5:9b`. Recorded benchmark digests
identify the artifacts used; an Ollama tag alone is not immutable. Granite Guardian
4.1 is evaluation-only and is excluded from SQL generation. The benchmark HF
route is `openai/gpt-oss-120b:groq`; the app's existing HF default is unchanged.

The hosted allow-lists are enforced in settings, CLI overrides, and the model
factory. Hugging Face remains intentionally flexible, but its custom model ID
must use the documented repository form and support medium reasoning through
the Responses API. Agnes uses the provider's documented boolean Thinking flag,
not a low/medium/high effort value. Ollama model names remain
flexible except that Granite Guardian is rejected for generation. See the
[Agnes 2.5 Flash API reference](https://agnes-ai.com/en/docs/agnes-25-flash).

### UI cost estimates

After each hosted-model run, the UI prices each actual model call from
provider-reported input, output, cache-read, and cache-creation usage. Pricing
rules have UTC effective windows and are editable from the Pricing view.

```text
(input tokens × input rate + output tokens × output rate) / 1,000,000
```

These are seeded application rates, not a live pricing quote. Check your
provider's rates and the rule's effective dates before spending money.

| Model | Input / 1M tokens | Output / 1M tokens | Seeded pricing note |
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


<a id="8-local-ollama--what-runs-on-your-gpu"></a>

## 8. Local Ollama: what runs on your GPU

The application defaults to `phi4-mini:3.8b`. The recorded comparison includes
`granite4.2:3b` and `qwen3.5:9b`; [hardware metadata](benchmarks/hardware.json)
records their digests, quantization and observed allocation. Model file size
is not total runtime memory: context, cache and offloading also matter.

Use the [case-level results](benchmarks/results/README.md) to understand the
tested configuration and failures. They do not establish a general model
ranking or guarantee that a model fits a particular GPU. Pull a selected model
with `ollama pull <name>` and set `NL2SQL_MODEL=<name>`.


## 9. Safety model

The agent treats every question as untrusted user input and every LLM
output as untrusted generated code.

Five lines of defense:

1. Read-only database connection. SQLite queries use URI `mode=ro`,
   `query_only`, disabled extensions, and an untrusted-schema policy.
   PostgreSQL uses non-autocommit read-only transactions, verified
   `transaction_read_only`, statement/lock timeouts, a fixed search path, and
   rejects superuser, BYPASSRLS, CREATEDB, or CREATEROLE roles.
2. AST-based validation. Before any SQL reaches the database, it is
   parsed by `sqlglot` into an AST and checked:
   - Exactly one statement.
   - Top-level is `SELECT` or the explicitly supported `UNION` node.
   - No dangerous SQLite or PostgreSQL file, configuration, advisory-lock, or
     sleep functions; no `SELECT INTO`, row locks, or cross-schema references.
   - No subqueries, joins, CTEs, or aggregates if disabled by policy.
   - Word-boundary scan for `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`,
     `CREATE`, `REPLACE`, `TRUNCATE`, `GRANT`, `REVOKE`, `PRAGMA`,
     `ATTACH`, `DETACH`, `VACUUM`, `REINDEX`, `INSTALL`, `COPY`.
3. Configurable policy. Queries are restricted to permitted tables,
   with configurable feature toggles and JOIN/subquery/CTE count limits.
4. Row cap. A hard cap (`NL2SQL_DB_MAX_ROWS`, default 1000) prevents
   `SELECT *` from returning millions of rows.
5. Execution budget and preflight. SQLite uses a VM-step/deadline guard and
   `EXPLAIN QUERY PLAN`; PostgreSQL uses `EXPLAIN (FORMAT JSON, COSTS TRUE)`
   without `ANALYZE`, so preflight never executes the query.

Audit events contain hashes and literal-redacted SQL, never raw questions,
result rows, database paths, sample values, or credentials.

The validator lives in `src/nl2sql_agent/security/sql_validator.py`, with
regression tests under `tests/unit/test_sql_validator.py`. Model judgments
never replace this policy or the database's read-only boundary.


## 10. Running the UI

On Windows, double-click `Launch NL2SQL Agent.cmd`. For terminal launches:

```bash
# Default port 8512 (from .streamlit/config.toml)
uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py

# Custom port
uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py --server.port 8513
```

### What the UI shows

- Database source. Use the seeded demo, a session-scoped SQLite upload, or
  the operator-configured PostgreSQL DSN. Uploaded databases are never seeded
  or modified.
- Schema controls. Browse ordinary tables, authorize the tables available
  to SQL, and optionally expose bounded sample rows from uploads to the model.
- Approval flow. Generation stops at an editable, validated SQL preview.
  Run explicitly to revalidate and execute it.
- Saved sessions. Reopen conversations, pending approvals, and approved
  SQL. Questions and answers are saved verbatim, so answers can retain result
  values. Structured rows, CSV payloads, uploads, schemas, keys and DSNs are
  excluded from saved payloads. Pending approval also stores unapproved SQL.
- Costs and insights. Review session/model costs, budget warnings, runtime
  trends, normalized SQLite/PostgreSQL plans, full scans, and expensive-query
  warnings. Cost export excludes questions, answers, SQL, and results.
- Provider controls. Pick one of the approved hosted models, enter a custom
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
if prepared.get("outcome") == "prepared" and not prepared.get("error"):
    print(prepared["sql_query"])  # Show this to the approving user.
    # After explicit approval:
    result = agent.execute_prepared(prepared, sql_query=prepared["sql_query"])
```


## 11. CLI

```text
$ uv run nl2sql-agent --help
usage: nl2sql-agent [-h] {ask,config,serve,eval} ...

$ uv run nl2sql-agent ask --help
usage: nl2sql-agent ask [-h] [--clarification CLARIFICATION] [--provider PROVIDER] [--model MODEL]
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


## 12. Verification

CI runs offline tests on Windows and Linux with an 80% coverage threshold,
plus a PostgreSQL 17 service job using an unprivileged read-only role. Local
model tests require `NL2SQL_LIVE_TESTS=1`; normal tests never call hosted models.

```bash
uv sync --locked --all-groups
uv run pytest -q --cov=nl2sql_agent
uv run prek run --all-files
uv audit --locked
uv build
# Installed-wheel smoke: replace WHEEL_PATH with the wheel produced by uv build.
uv run --isolated --no-project --with WHEEL_PATH nl2sql-agent --help

# Result and safety evaluation (uses the configured provider)
uv run nl2sql-agent eval --min-pass-rate 0.8
```

For a live model and database smoke check, run the packaged evaluator. Its 15
cases cover the seeded SQLite database only; see [DATASET.md](DATASET.md).

### Reliable outcomes and benchmark runs

The writer can return SQL, request clarification, or explain why the schema
cannot answer a question. CLI replies use repeated `--clarification` arguments;
the chat UI accepts up to two replies before stopping unresolved questions.
Assumptions appear before SQL approval. A saved query must be prepared again
if its database, schema, allowed tables, catalog, or policy changes.

Successful answers are rendered from database cells. The UI keeps raw fetched
results separate from the answer and identifies SQL limits, fetch truncation,
and the 100-row preview. It does not send result rows to a second model call.

Evaluation report version 2 requires explicit execution evidence for result
accuracy and an explicit `policy_blocked` outcome for policy-block tests.
Provider failures are failures, not successful blocks. Missing categories
have null metrics and zero counts.

See [benchmarks/README.md](benchmarks/README.md) for the 120-case synthetic
suite, pinned BIRD source, budgeted runs, and interpretation limits.


## 13. Project layout

```
natural-language-to-sql-agent/
├── Launch NL2SQL Agent.cmd  # Windows double-click launcher
├── pyproject.toml            # Single source of truth for deps + tool config
├── uv.lock                   # Reproducible lockfile
├── README.md                 # This file
├── API_REFERENCE.md          # Public package and CLI reference
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
└── diagrams/                 # Interactive architecture and workflow diagrams
```


## 14. API reference

See [API_REFERENCE.md](API_REFERENCE.md) for the exported Python surface, CLI
commands, exceptions, and short examples. Common entry points include:

- `nl2sql_agent.agent.NL2SQLAgent(llm, *, settings=None, database=None,
  allowed_tables=None, include_sample_values=None)`: the workflow class.
  `run()` and `stream()` remain end-to-end; `prepare()`, `stream_prepare()`,
  and `execute_prepared()` support approval-first clients.
- `nl2sql_agent.config.get_settings()`: singleton accessor for the
  `Settings` instance.
- `nl2sql_agent.llm.build_chat_model(settings, *, provider, model, ...)`:
  build any of the seven supported provider integrations.
- `nl2sql_agent.security.validate_sql(sql, policy=None)`: validate a
  SQL string and return the parsed `Select` nodes; pass `dialect="postgres"`
  and `allowed_schema` for PostgreSQL.
- `nl2sql_agent.db.Database(path, *, timeout_seconds, max_rows)`:
  the SQLite wrapper. `PostgresDatabase(dsn, schema=...)` implements the same
  backend contract. `QueryPlan`, `QueryMetrics`, and `QueryResult` expose
  normalized observability data.
- `nl2sql_agent.persistence.StateStore(path)`: persistent sessions, pricing
  rules, run snapshots, dashboard aggregates, and preferences.


## 15. Operations runbook

### Verifying the install

```bash
uv run python -c "import nl2sql_agent; print(nl2sql_agent.__version__)"
# → 0.5.2

uv run nl2sql-agent --help
```

### Smoke test against local Ollama

```bash
uv run nl2sql-agent ask "How many employees are there?"
# The seeded demo contains 10 employees; answer wording depends on the generated SQL.
```

### Verifying the guardian blocks bad SQL

You can exercise the validator directly without connecting to a model or
database:

```python
from nl2sql_agent.security import SQLValidationError, validate_sql

try:
    validate_sql("DROP TABLE employees")
except SQLValidationError as exc:
    print(exc)
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


## 16. Migration from v0.1

The previous release (`v0.1`, the original `app.py` + `backend.py`
two-file version) has been replaced by a modular package.
For most users, the differences are:

| v0.1 | v0.2 |
|---|---|
| `app.py` and `backend.py` at the repo root | `src/nl2sql_agent/` package |
| `pip install -r requirements.txt` | `uv sync --all-groups` |
| `python -m streamlit run app.py` | `uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py` |
| `from backend import SQLAgent` | `from nl2sql_agent.agent import NL2SQLAgent` |
| Keyword-regex SQL safety | AST-based SQL safety via `sqlglot` |
| Hard-coded `company.db` path | `NL2SQL_DB_PATH` env var |
| `setup_db()` on every agent instantiation | Idempotent initialization per managed Database instance |

The 25 known issues from the v0.1 audit are all addressed in v0.2. See
`CHANGELOG.md` for the complete list.


## 17. Roadmap

Possible future work:

- Optional schema embeddings for databases where deterministic identifier
  ranking is insufficient.
- OpenTelemetry tracing with one-line enablement.
- Additional database engines such as MySQL via the same backend contract.
- Optional encrypted multi-user session storage for server deployments.
- WebSocket / FastAPI backend instead of Streamlit for production
  multi-user deployments.


## 18. Contributing

1. Fork and clone.
2. Install the pinned Python and all development groups with `uv sync --locked --all-groups`.
3. Make your change. Add focused tests when behavior changes. Run
   `uv run ruff check src tests` and `uv run ty check src`.
4. Run `uv run prek run --all-files`: this is the same gate CI runs, and also checks
   formatting (`ruff format --check`) and secret scanning, which the commands above don't cover.
5. Open a PR with a clear description.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide, and the
[Code of Conduct](CODE_OF_CONDUCT.md) before opening a pull request.


## 19. License

[MIT](LICENSE).


## Documentation

Browse the [documentation index](docs/README.md) for guides grouped by task.

New contributors can start with [onboarding](ONBOARDING.md), follow the
[offline tutorial](ZERO_TO_MASTERY_TUTORIAL.md), then use the
[developer guide](DEVELOPER_GUIDE.md) and [contributor runbook](CONTRIBUTOR_RUNBOOK.md).
The [documentation audit](DOCUMENTATION_AUDIT.md) records coverage and verification limits.

| Document | Purpose |
| --- | --- |
| [OpenWiki quickstart](openwiki/quickstart.md) | Source-grounded task routing, runtime contracts and operational boundaries |
| [Implementation report](IMPLEMENTATION_REPORT.md) | Verification scope, publication status and known limits |
| [Benchmark protocol](benchmarks/README.md) and [results](benchmarks/results/README.md) | Reproduction commands and retained case-level evidence |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system design: modules, workflow, safety model, extension points |
| [API_REFERENCE.md](API_REFERENCE.md) | Exported Python API, CLI commands, errors, and examples |
| [Interactive diagrams](diagrams/nl2sql-architecture.html) | Architecture, workflow, sequence, data-flow, and lifecycle views |
| [DATASET.md](DATASET.md) | Demo data, packaged smoke corpus and benchmark boundaries |
| [SECURITY.md](SECURITY.md) | Security model, redacted fields, and private vulnerability reporting |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, required checks, and pull-request guidance |
| [SUPPORT.md](SUPPORT.md) | Where to ask usage questions and what response time to expect |
| [DISCLAIMER.md](DISCLAIMER.md) | Data responsibility, what reaches an LLM provider, no financial support wanted |
| [CHANGELOG.md](CHANGELOG.md) | Full release history |
| [RELEASE_NOTES.md](RELEASE_NOTES.md) | Human-readable notes for the current release |
| [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) | Upgrading from earlier versions |
| [UPGRADE_SUMMARY.md](UPGRADE_SUMMARY.md) | Historical migration and verification snapshot |
| [Zero-to-Hero Study Handbook](ZERO_TO_HERO_STUDY_HANDBOOK.md) ([PDF](ZERO_TO_HERO_STUDY_HANDBOOK.pdf)) | Full curriculum: NLP, agents, SQL safety, and this codebase from first principles |

## Community & support

| You want to… | Do this |
| --- | --- |
| Report a bug | [Bug report](https://github.com/pypi-ahmad/natural-language-to-sql-agent/issues/new/choose) |
| Suggest a feature | [Feature request](https://github.com/pypi-ahmad/natural-language-to-sql-agent/issues/new/choose) |
| Contribute code or docs | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Ask a usage question | [SUPPORT.md](SUPPORT.md) |
| Report a vulnerability | [SECURITY.md](SECURITY.md) |

> [!NOTE]
> This project does not want or accept donations, sponsorships, or any other financial support, and
> never will. It's free to use and free to modify. If you'd like to give back, you can contribute
> code, tests, docs, or a reproducible bug report.

## Disclaimer

- You run this on your own machine, with your own database and API keys. There is no hosted
  version and no account system.
- You are responsible for the data you process with it. Remote providers
  receive writer prompt context, including configured samples. Successful
  answers are rendered locally. Use a local Ollama endpoint to keep inference
  on your machine, and protect persisted conversation text.
- No warranty and no liability, per the [MIT License](LICENSE): use it at your own risk.

See [DISCLAIMER.md](DISCLAIMER.md) for the full version.

<p align="center">Made with ❤️ by Ahmad Mujtaba</p>
