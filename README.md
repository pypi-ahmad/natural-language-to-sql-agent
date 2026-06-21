# NL2SQL Agent — Production-Grade Natural Language to SQL

[![Python 3.12](https://img.shields.io/badge/python-3.12.10-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checker: mypy](https://img.shields.io/badge/type%20checker-mypy-blue.svg)](http://mypy-lang.org/)
[![Tests: 174 passing](https://img.shields.io/badge/tests-174_passing-brightgreen.svg)](#testing)

> Turn natural-language questions into safe, auditable SQL against a local
> SQLite database — runs entirely on your machine using a local Ollama LLM,
> with optional cloud providers for heavier workloads.

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
| **Database** | `nl2sql_agent.db` | Thin, type-safe wrapper around SQLite with context-managed connections. |
| **Safety** | `nl2sql_agent.security` | AST-based SQL validation using `sqlglot` — allow-lists, not deny-lists. |
| **LLM factory** | `nl2sql_agent.llm` | Multi-provider chat-model construction (Ollama, OpenAI, Gemini, Anthropic). |
| **Agent** | `nl2sql_agent.agent` | LangGraph workflow: schema → write → guard → execute → summarize. |
| **Prompts** | `nl2sql_agent.prompts` | Versioned, single-source prompt templates. |
| **UI** | `nl2sql_agent.ui` | Streamlit chat interface with live status and SQL preview. |
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
- **Pinned, reproducible, modern.** Python 3.12.10, `uv`-managed, all
  dependencies version-pinned in `pyproject.toml`.
- **Tested.** 174 unit tests, >85% coverage on the core modules
  (config, db, security, prompts, agent, llm factory, text utilities).
- **Observable.** Structured Loguru logging, request-friendly error
  contracts, JSON logging mode for log aggregators.

---

## 3. Quick start

### Prerequisites

- Linux or macOS (or WSL on Windows)
- Python 3.12.10 — `uv` will install this for you
- Ollama 0.5+ running locally (only required for the default provider)

### Install

```bash
git clone <this-repo>
cd natural-language-to-sql-agent
uv venv --python 3.12.10
uv sync --extra dev
uv pip install -e .
```

### Pull a small local model

```bash
ollama pull phi4-mini:3.8b     # 2.5 GB — recommended for 8 GB VRAM
# or
ollama pull qwen3.5:4b         # 3.4 GB — better quality, also fits
```

### Run the Streamlit UI

```bash
uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py
```

Open http://localhost:8501, choose **Ollama** as the provider, pick
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
| `NL2SQL_PROVIDER` | `ollama` | One of `ollama`, `openai`, `gemini`, `anthropic`. |
| `NL2SQL_MODEL` | `phi4-mini:3.8b` | Model identifier for the chosen provider. |
| `NL2SQL_OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama HTTP endpoint. |
| `NL2SQL_OLLAMA_KEEP_ALIVE` | `5m` | How long Ollama keeps the model loaded. |
| `OPENAI_API_KEY` | — | Required when `NL2SQL_PROVIDER=openai`. |
| `GOOGLE_API_KEY` | — | Required when `NL2SQL_PROVIDER=gemini`. |
| `ANTHROPIC_API_KEY` | — | Required when `NL2SQL_PROVIDER=anthropic`. |
| `NL2SQL_DB_PATH` | `company.db` | Path to the SQLite database file. |
| `NL2SQL_DB_SEED` | `true` | Seed the database with sample data on first run. |
| `NL2SQL_DB_MAX_ROWS` | `1000` | Cap on rows returned per query. |
| `NL2SQL_DB_QUERY_TIMEOUT_SECONDS` | `15` | Per-query execution timeout. |
| `NL2SQL_MAX_RETRIES` | `3` | SQL rewrite attempts after a failed execution. |
| `NL2SQL_LLM_TEMPERATURE` | `0.0` | LLM sampling temperature. |
| `NL2SQL_LLM_MAX_TOKENS` | `1024` | Max output tokens per LLM call. |
| `NL2SQL_SQL_ALLOW_SUBQUERIES` | `true` | Allow nested SELECT. |
| `NL2SQL_SQL_ALLOW_JOINS` | `true` | Allow JOIN clauses. |
| `NL2SQL_SQL_ALLOW_AGGREGATES` | `true` | Allow COUNT, SUM, AVG, etc. |
| `NL2SQL_SQL_ALLOW_CTE` | `true` | Allow WITH ... AS. |
| `NL2SQL_LOG_LEVEL` | `INFO` | Loguru log level. |
| `NL2SQL_LOG_JSON` | `false` | Emit JSON-formatted logs. |

---

## 7. LLM providers

| Provider | Auth | Default model | Notes |
|---|---|---|---|
| **Ollama** | None | `phi4-mini:3.8b` | Local, private, no internet required. |
| **OpenAI** | `OPENAI_API_KEY` | `gpt-4o-mini` | Cloud, fast. |
| **Gemini** | `GOOGLE_API_KEY` | `gemini-1.5-flash` | Cloud, large context. |
| **Anthropic** | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-latest` | Cloud, strong reasoning. |

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

1. **Read-only SQLite user.** The database is opened with
   `isolation_level=None` (autocommit) and the executor uses
   `cursor.execute()`, which **prevents multi-statement injection by
   driver constraint**.
2. **AST-based validation.** Before any SQL reaches the database, it is
   parsed by `sqlglot` into an AST and checked:
   - Exactly one statement.
   - Top-level is `SELECT` (or `UNION`/`INTERSECT`/`EXCEPT`).
   - No dangerous functions (`load_extension`, `readfile`, `writefile`,
     `shell`, `system`, `edit`).
   - No subqueries, joins, CTEs, or aggregates if disabled by policy.
   - Word-boundary scan for `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`,
     `CREATE`, `REPLACE`, `TRUNCATE`, `GRANT`, `REVOKE`, `PRAGMA`,
     `ATTACH`, `DETACH`, `VACUUM`, `REINDEX`, `INSTALL`, `COPY`.
3. **Configurable policy.** Each knob (subqueries, joins, aggregates,
   CTEs, UNION) is a boolean. See the env vars above.
4. **Row cap.** A hard cap (`NL2SQL_DB_MAX_ROWS`, default 1000) prevents
   `SELECT *` from returning millions of rows.
5. **Per-query timeout.** `NL2SQL_DB_QUERY_TIMEOUT_SECONDS` (default 15s)
   bounds the time the executor can spend on a single statement.

The validator lives in `src/nl2sql_agent/security/sql_validator.py` and
is fully tested in `tests/unit/test_sql_validator.py`.

---

## 10. Running the UI

```bash
# Default port 8501
uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py

# Custom port
uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py --server.port 8502
```

### What the UI shows

- **Sidebar.** Provider picker, model list (with a refresh button),
  Ollama base URL, API key input. Keys are never logged.
- **Main panel.** Chat history (user + assistant turns), live
  per-step status indicator, expandable SQL view, raw results table.
- **Clickable example questions** for first-time users.

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

---

## 11. CLI

```text
$ uv run nl2sql-agent --help
usage: nl2sql-agent [-h] {ask,config,serve} ...

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
```

---

## 12. Testing

The project ships with **174 unit tests** plus a live integration test
that exercises the agent end-to-end against a real local Ollama.

```bash
# Unit tests (no external services needed)
uv run pytest tests/unit -v

# With coverage
uv run pytest tests/unit --cov=src/nl2sql_agent --cov-report=term-missing

# Integration test (requires local Ollama running)
uv run pytest tests/integration -v
```

**Coverage by module (unit tests only):**

| Module | Coverage |
|---|---|
| `nl2sql_agent/__init__.py` | 100% |
| `nl2sql_agent/agent/state.py` | 100% |
| `nl2sql_agent/agent/workflow.py` | 93% |
| `nl2sql_agent/config/settings.py` | 97% |
| `nl2sql_agent/db/database.py` | 88% |
| `nl2sql_agent/db/seed.py` | 100% |
| `nl2sql_agent/llm/factory.py` | 79% |
| `nl2sql_agent/prompts/templates.py` | 100% |
| `nl2sql_agent/security/sql_validator.py` | 82% |
| `nl2sql_agent/utils/logging.py` | 66% |
| `nl2sql_agent/utils/text.py` | 100% |

UI and CLI modules are exercised manually — Streamlit's runtime doesn't
lend itself to unit testing.

---

## 13. Project layout

```
natural-language-to-sql-agent/
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
│       ├── db/               # Database wrapper + seed data
│       ├── security/         # AST-based SQL safety
│       ├── llm/              # Multi-provider LLM factory
│       ├── prompts/          # Versioned prompt templates
│       ├── agent/            # LangGraph workflow + state
│       ├── ui/               # Streamlit components + app
│       └── utils/            # Logging, text helpers
└── tests/
    ├── conftest.py
    ├── unit/                 # Fast, no external services
    └── integration/          # Requires a running local Ollama
```

---

## 14. API reference

The full, type-annotated surface is discoverable in the source. The most
common entry points:

- `nl2sql_agent.NL2SQLAgent(llm, *, settings=None, database=None)`
  — the workflow class. `agent.run(question)` and `agent.stream(question)`
  are the two main methods.
- `nl2sql_agent.config.get_settings()` — singleton accessor for the
  `Settings` instance.
- `nl2sql_agent.llm.build_chat_model(settings, *, provider, model, ...)` —
  build any of the four supported chat models.
- `nl2sql_agent.security.validate_sql(sql, policy=None)` — validate a
  SQL string and return the parsed `Select` nodes.
- `nl2sql_agent.db.Database(path, *, timeout_seconds, max_rows)` —
  the database wrapper.

---

## 15. Operations runbook

### Verifying the install

```bash
uv run python -c "import nl2sql_agent; print(nl2sql_agent.__version__)"
# → 0.2.0

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
| `pip install -r requirements.txt` | `uv sync --extra dev` |
| `python -m streamlit run app.py` | `uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py` |
| `from backend import SQLAgent` | `from nl2sql_agent.agent import NL2SQLAgent` |
| Keyword-regex SQL safety | AST-based SQL safety via `sqlglot` |
| Hard-coded `company.db` path | `NL2SQL_DB_PATH` env var |
| `setup_db()` on every agent instantiation | Idempotent; runs once per process |

The 25 known issues from the v0.1 audit are all addressed in v0.2. See
`CHANGELOG.md` for the complete list.

---

## 17. Roadmap

Items deliberately **not** in v0.2 but considered for v0.3:

- **Schema embeddings** (RAG-style schema retrieval) using
  `qwen3-embedding:0.6b` for very large databases.
- **OpenTelemetry tracing** with one-line enablement.
- **Multi-database support** (Postgres, MySQL) via the same AST
  validator and a thin driver layer.
- **Conversation memory** with PostgreSQL-backed checkpointing.
- **WebSocket / FastAPI** backend instead of Streamlit for production
  multi-user deployments.

---

## 18. Contributing

1. Fork and clone.
2. Create a virtualenv with `uv venv --python 3.12.10 && uv sync --extra dev`.
3. Make your change. Add tests. Run `uv run ruff check src tests`,
   `uv run mypy src/nl2sql_agent`, and `uv run pytest tests/unit`.
4. Open a PR with a clear description.

---

## 19. License

[MIT](LICENSE).
