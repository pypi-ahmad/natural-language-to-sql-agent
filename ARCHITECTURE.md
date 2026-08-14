# Architecture Guide

This document explains the design decisions behind the project. It is
written for engineers who want to **extend** the agent (add a new
provider, add a new safety rule, swap the database) or who want to
**understand** why things are the way they are.

---

## 1. Design principles

1. **One module, one responsibility.** Every sub-package has a
   single, well-defined job:
   - `config` — runtime configuration
   - `db` — database I/O
   - `security` — SQL validation
   - `llm` — LLM client construction
   - `prompts` — prompt templates
   - `agent` — orchestration
   - `persistence` — local sessions, pricing, and run summaries
   - `ui` — Streamlit presentation
   - `utils` — shared helpers (logging, text)

2. **No hidden global state.** All settings come from
   `nl2sql_agent.config.get_settings()`. Tests can monkeypatch the
   environment and reset the cache with `reset_settings_cache()`.

3. **No magic.** Every LangGraph node is a plain Python method on
   `NL2SQLAgent`. You can read them, log them, and replace them
   individually.

4. **Allow-list, not deny-list.** The SQL safety model is allow-list:
   the validator parses the SQL and only allows the operations you
   have explicitly opted into. This is more secure than the
   traditional "block destructive keywords" approach.

5. **Database agnostic of LLM, LLM agnostic of database.** The two
   most important external dependencies are connected only through
   the agent layer. You can swap the database engine (Postgres,
   MySQL) without touching the LLM, and vice versa.

---

## 2. Module dependency graph

```
                   ┌──────────────┐
                   │   config     │  (no deps on other modules)
                   └──────┬───────┘
                          │
       ┌──────────────────┼─────────────────────┐
       ▼                  ▼                     ▼
   ┌────────┐         ┌──────────┐         ┌──────────┐
   │  db    │         │ security │         │   llm    │
   └────┬───┘         └─────┬────┘         └─────┬────┘
        │                   │                    │
        │            ┌──────┴──────┐             │
        └───────────►│  prompts    │◄────────────┘
                     └──────┬──────┘
                            │
                            ▼
                     ┌────────────┐
                     │   agent    │
                     └─────┬──────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
         ┌─────────┐               ┌──────────┐
         │   ui    │               │   cli    │
         └─────────┘               └──────────┘
                            ▲
                     ┌──────┴──────┐
                     │   utils     │  (logging, text)
                     └─────────────┘
```

There are **no cycles**. The CLI and UI both depend on `agent`; the
`agent` depends on `db`, `security`, `llm`, `prompts`, and `config`;
the foundational modules depend only on `config` and `utils`.

---

## 3. State machine

The agent's state is a `TypedDict` with `total=False`, so partial
updates from nodes can be merged by LangGraph without `KeyError`.

```
(run_id, question, schema, allowed_tables, sql_query, sql_safe, error,
 retry_count, max_retries, raw_rows, columns, row_count, trace,
 usage_records, cost_breakdown, query_plan, query_metrics, warnings,
 token_usage, final_answer)
```

### Lifecycle

```
START
  ↓
fetch_schema
  ↓ (writes: schema)
writer
  ↓ (writes: sql_query, retry_count; clears: error, sql_unsafe_reason)
guardian
  ├── safe → executor
  ├── unsafe AND retry_count < max_retries → writer
  └── unsafe AND retry_count >= max_retries → summarizer
executor
  ├── ok → summarizer
  └── errored AND retry_count < max_retries → writer (with error in prompt)
  └── errored AND retry_count >= max_retries → summarizer
summarizer
  ↓ (writes: final_answer, result)
END
```

Approval-first clients use the same first three nodes through `prepare()` and
stop after the guardian. `execute_prepared()` validates the possibly edited SQL
again before calling the executor and summarizer. Existing `run()` and
`stream()` retain their end-to-end behavior.

The evaluation runner drives the compatible `run()` interface. It compares
query results with read-only reference queries, scores malicious prompts by
their blocked state, records timing/retry/token metrics, and verifies the
database file digest is unchanged.

The Streamlit client uses the two-phase path. Upload bytes are checked for an
allowed extension, size, and SQLite header, then stored under their SHA-256 in
a session-owned temporary directory. Changing the database, provider, or model
starts a new saved context; changing the allowlist invalidates pending SQL.
Saved history retains messages, approved SQL, pricing snapshots, and bounded
metrics, but never raw rows, CSV payloads, uploads, schemas, keys, or DSNs.

---

## 4. SQL safety in depth

### The five layers

1. **Read-only connection.** SQLite uses URI `mode=ro`, `query_only`, disabled
   extension loading, and `trusted_schema=OFF`. PostgreSQL uses a
   non-autocommit read-only transaction, verifies `transaction_read_only`, and
   rejects privileged roles before queries are accepted.
2. **Driver constraint.** `sqlite3.Cursor.execute()` refuses to
   execute multi-statement input. So `SELECT 1; DROP TABLE x` already
   raises `ProgrammingError` at the driver level.
3. **AST validation.** The `validate_sql()` function parses the SQL
   with `sqlglot` and rejects:
   - Anything that isn't a single SELECT (or UNION thereof).
   - Dangerous file, configuration, sleep, dblink, advisory-lock, and
     large-object functions.
   - Forbidden keywords as a paranoid fallback (CREATE, PRAGMA, etc.).
4. **Configurable policy.** Joins, subqueries, aggregates, CTEs, and
   UNION can each be turned off via the `SQLPolicy` object. The
   `Settings.sql_allow_*` flags propagate from environment variables.
5. **Authorization and resource bounds.** Scope-aware traversal checks physical
   tables against the allowlist while treating CTE aliases as derived sources;
   a same-named CTE cannot hide an unauthorized physical table.
   SQLite uses `EXPLAIN QUERY PLAN`, elapsed-time and VM-step guards;
   PostgreSQL uses non-executing JSON `EXPLAIN`, statement/lock timeouts, and a
   configured single-schema boundary. Serialized LIMIT clauses bound rows.

`prepare_sql()` parses each candidate once and reuses that AST for policy
validation, physical-table discovery, authorization, and executable LIMIT
canonicalization. A unit guard prevents accidental reintroduction of repeated
parsing on this latency-sensitive path.

`get_schema_text()` uses one read-only connection, normalizes each identifier
once while ranking tables, and fetches foreign-key metadata only for the tables
selected for the prompt. Regression tests guard the single-pass ranking and
connection reuse.

### Why AST over regex?

The v0.1 keyword regex couldn't distinguish:

| v0.1 (regex) | v0.2 (AST) |
|---|---|
| `SELECT * FROM updated_at` → "UPDATE detected" (false positive) | `updated_at` is a column, not a statement — passes |
| `SELECT * FROM my_drop_log` → "DROP detected" (false positive) | `my_drop_log` is a table — passes |
| `SELECT load_extension('evil.so')` → not blocked | `load_extension` is a function — blocked |
| `SELECT 1; DROP TABLE x` → blocked by driver only | Blocked at AST layer, never reaches driver |

---

## 5. Multi-provider design

The LLM factory is intentionally **small and boring**:

```python
def build_chat_model(settings, *, provider=None, model=None) -> BaseChatModel:
    ...
```

It returns a LangChain `BaseChatModel`. The agent doesn't care which
one it gets — it only ever calls `.invoke(messages)`. The supported adapters
are Ollama, Hugging Face, OpenAI, Anthropic, Gemini, and xAI. Hugging Face and
xAI reuse the existing OpenAI-compatible LangChain client against fixed direct
endpoints, so they do not require provider-specific SDKs.

Hosted providers run at medium reasoning effort. OpenAI, Anthropic, Gemini,
and xAI use strict model allow-lists; Hugging Face accepts validated
`namespace/model[:routing-policy]` IDs. Only Ollama performs live model
discovery. Provider defaults and approved choices live with `Settings`, so the
factory, CLI, and UI cannot drift.

To add another provider:

1. Reuse an existing compatible LangChain client or add the smallest required
   provider package.
2. Add a private `_build_<provider>(cfg, **common)` function in
   `src/nl2sql_agent/llm/factory.py`.
3. Add its approved/default model choices and credential environment name.
4. Wire the provider name into `Settings.provider` and the sidebar.
5. Add model discovery only when the provider genuinely requires it.

That's it. No other module needs to change.

---

## 6. Observability strategy

The project uses **Loguru** as a single logging backend, with
optional JSON output for log aggregators.

Runtime metadata lists only dependencies imported by the application.
Security-only floors for transitive packages live in uv constraints, keeping
the published dependency surface truthful without weakening lock-file audits.

Audit JSONL accepts only a fixed operational-field allowlist. Questions are
hashed, SQL literals are redacted, and exception detail is not returned to UI
users. Uploads are capped at 50 MB before byte materialization; CSV exports
neutralize spreadsheet formulas at the serialization boundary.

```python
from nl2sql_agent.utils import configure_logging, get_logger

configure_logging(level="INFO", json=False)
log = get_logger(__name__)
log.info("user asked a question", extra={"user_id": "..."})
```

The agent's workflow emits structured events:

```
12:34:56.789 | INFO  | nl2sql_agent.agent.workflow:__init__:84 - Agent ready: provider model in use, db=company.db, max_retries=3
12:34:56.798 | DEBUG | nl2sql_agent.agent.workflow:fetch_schema:95 - Schema fetched (243 chars)
12:34:57.231 | INFO  | nl2sql_agent.agent.workflow:write_sql:118 - writer attempt=1 produced sql=SELECT COUNT(*) ...
12:34:57.456 | INFO  | nl2sql_agent.db.database:execute:185 - Query returned 1 row in 4ms
```

Set `NL2SQL_LOG_LEVEL=DEBUG` for verbose output, or
`NL2SQL_LOG_JSON=true` for structured logging.

Each LLM call contributes provider-reported input, output, cache-read, and
cache-creation usage. Effective-dated rules price each call using its actual
mode and long-context threshold. The local state store keeps immutable pricing
snapshots with approved runs, enabling session/model totals, budget alerts,
CSV export, and historical reproducibility. It stores no prompts, result rows,
credentials, DSNs, or provider billing records and is not an invoice.

Database execution also emits normalized plan and runtime metrics. The UI
shows trends and threshold warnings without running `EXPLAIN ANALYZE`; this
keeps planning read-only and avoids executing a query twice.

---

## 7. Why LangGraph, not a hand-rolled loop?

A plain while-loop in a function would also work. We chose LangGraph
for three reasons:

1. **Streaming.** LangGraph gives us `app.stream(inputs)` out of the
   box, which is what the Streamlit UI uses to show live status.
2. **Composability.** You can add a new node, a new edge, or a
   sub-graph without rewriting the whole loop.
3. **Inspection.** LangSmith and LangGraph Studio can visualize the
   state machine and replay specific runs.

The cost is one extra dependency (`langgraph`) and a slightly less
direct style of code. We judged the trade-off worth it.

---

## 8. Extensibility checklist

To extend the system, follow these recipes:

### Add a new LLM provider

1. Reuse a compatible client or add the provider's minimal dependency.
2. Add a `_<provider>` entry to `Provider` literal in
   `config/settings.py`.
3. Add a `_build_<provider>` function in `llm/factory.py`.
4. Add its model policy and credential environment name.
5. Update the `render_sidebar` in `ui/components.py` to include the
   new provider; add live discovery only when necessary.

### Add a new SQL safety rule

1. Add a new field to `SQLPolicy` in `security/sql_validator.py`.
2. Add the corresponding `Settings` field in `config/settings.py`.
3. Add a check in `_check_select()` in `security/sql_validator.py`.
4. Add a parametrized test in `tests/unit/test_sql_validator.py`.

### Add a new LangGraph node

1. Add a method on `NL2SQLAgent` in `agent/workflow.py`.
2. `graph.add_node("<name>", self.<method>)`.
3. Wire edges with `add_edge` or `add_conditional_edges`.

### Add a database engine

1. Create `src/nl2sql_agent/db/<engine>.py` implementing `DatabaseBackend`.
2. Select it from `Settings.db_backend` in the workflow and UI.
3. Add tests under `tests/unit/test_db_<engine>.py`.

### Extend saved sessions

Add a versioned migration to `StateStore`, persist only explicitly allowed
fields, and keep database content and credentials outside the state database.
