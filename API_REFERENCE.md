# API reference

For working examples, see the [offline tutorial](ZERO_TO_MASTERY_TUTORIAL.md).
For extension work and module ownership, use the [developer guide](DEVELOPER_GUIDE.md).

This reference covers the public objects exported by the `nl2sql_agent`
subpackages. Import workflow objects from their subpackages; the top-level
package currently exports only `__version__`.

## Agent

```python
from nl2sql_agent.agent import AgentState, NL2SQLAgent, NodeTrace
```

### `NL2SQLAgent`

Constructor signature (reference notation):

```text
NL2SQLAgent(
    llm,
    *,
    settings=None,
    database=None,
    allowed_tables=None,
    include_sample_values=None,
    db_fingerprint=None,
)
```

`llm` must provide `invoke(messages)` and a response compatible with the writer's
content/text and optional usage fields; a LangChain chat model satisfies this contract. `database` may be any
`DatabaseBackend`; when omitted, settings select SQLite or PostgreSQL.

| Method | Purpose |
| --- | --- |
| `run(question, *, max_retries=None, clarifications=None)` | Generate a decision; execute validated SQL and render the result when answerable. |
| `stream(question, *, max_retries=None, clarifications=None)` | Yield `(node_name, state_update)` pairs during an end-to-end run. |
| `prepare(question, *, max_retries=None, clarifications=None)` | Generate a decision and preflight any SQL without executing it. |
| `stream_prepare(question, *, max_retries=None, clarifications=None)` | Stream the preparation stages. |
| `execute_prepared(prepared_state, *, sql_query=None)` | Revalidate and execute prepared or edited SQL, then summarize the result. |
| `get_workflow()` | Return the compiled end-to-end LangGraph workflow. |
| `get_prepare_workflow()` | Return the compiled preparation-only workflow. |

The returned state may include `sql_query`, `sql_safe`, `raw_rows`, `columns`,
`query_plan`, `query_metrics`, `token_usage`, `warnings`, `error`, and
`final_answer`. Check keys defensively because `AgentState` is a `total=False`
`TypedDict` and nodes return partial updates.

Use `outcome` and `executed` to determine success, never the presence of rows.
Terminal outcomes include `prepared`, `executed`, `needs_clarification`,
`unanswerable`, `policy_blocked`, `generation_error`, `provider_error`,
`database_error`, and `budget_exhausted`. `error_code` gives a stable reason.
At most two clarification replies are accepted. Prepared states carry a
`context_signature`; old or changed context requires preparation again.
`execute_prepared()` performs one revalidated execution attempt, without the
full graph's automatic writer-repair loop. A signature is not a row snapshot.
`selected_tables`, `schema_incomplete`, `assumptions`, and `row_limit_applied`
describe the context and result limits.

## Configuration

```python
from nl2sql_agent.config import Settings, get_settings
```

- `Settings()` loads validated configuration from constructor values,
  environment variables, `.env`, and defaults.
- `get_settings()` returns the cached process settings.
- `reset_settings_cache()` clears that cache for a later reload.
- `supported_models_for(provider)` and `default_model_for(provider)` expose the
  configured model policy.
- `validate_model_for(provider, model)` returns the accepted model ID or raises
  `ValueError`.
- `env_var_for(provider)` returns the provider credential variable name when
  one is required.

Valid providers are `ollama`, `huggingface`, `openai`, `anthropic`, `gemini`,
`xai`, and `agnes`.

## Database backends

```python
from nl2sql_agent.db import Database

sqlite = Database("company.db", timeout_seconds=15, max_rows=1000)
sqlite.ensure_schema(seed=True)
result = sqlite.execute("SELECT COUNT(*) AS count FROM employees")
```

`Database` uses SQLite. `PostgresDatabase` requires a DSN for a non-privileged
role and verifies that each transaction is read-only. Both implement:

| Method | Return | Notes |
| --- | --- | --- |
| `list_tables()` | `tuple[str, ...]` | List visible base tables. |
| `get_schema_text(...)` | `str` | Render ranked, optionally filtered schema context. |
| `preflight(sql)` | `QueryPlan` | Inspect a query without executing it. |
| `execute(sql)` | `QueryResult` | Execute SQL already approved by the security layer. |

`execute()` does not validate SQL. Call `prepare_sql()` or use `NL2SQLAgent`
before passing generated SQL to a backend. Backend failures are normalized as
`DatabaseError` where the implementation can safely hide provider details.

`QueryPlan`, `QueryPlanNode`, `QueryMetrics`, and `QueryResult` are immutable
dataclasses used for normalized planning and runtime data. `setup_db()` creates
the SQLite schema, while `render_table()` formats rows as Markdown.

## SQL security

```python
from nl2sql_agent.security import SQLPolicy, prepare_sql

prepared = prepare_sql(
    "SELECT name FROM employees ORDER BY name",
    SQLPolicy(max_limit=100),
    allowed_tables={"employees"},
)
print(prepared.sql)
```

| Function | Purpose |
| --- | --- |
| `parse_sql(sql, *, dialect="sqlite")` | Parse SQL with SQLGlot or raise `SQLValidationError`. |
| `validate_sql(sql, policy=None, *, dialect="sqlite", allowed_schema=None)` | Enforce statement and policy rules; return parsed `Select` nodes. |
| `referenced_tables(sql, *, dialect="sqlite")` | Return physical table names referenced by the SQL. |
| `prepare_sql(...)` | Parse once, validate, authorize tables, and apply the configured row limit. |

`SQLPolicy` enables joins, subqueries, aggregates, CTEs and UNION by default.
Its `allow_union` flag is available in Python, without a corresponding settings
field. The validator's top-level set-operation branch explicitly supports UNION.
An additional keyword scan can reject valid literals or quoted identifiers.

`SQLValidationError` indicates rejected or invalid SQL. Treat its message as a
user-facing validation result, not as permission to execute the original SQL.

## LLM providers and pricing

```python
from nl2sql_agent.llm import build_chat_model, list_models
```

- `build_chat_model(settings=None, *, provider=None, model=None,
  temperature=None, max_tokens=None)` constructs a LangChain chat model.
- `list_models(provider, *, api_key=None, base_url=None)` discovers models when
  supported and otherwise returns approved choices.
- `fallback_models(provider)` returns local fallback choices.
- `calculate_cost()`, `effective_pricing_rule()`, and
  `estimate_model_cost()` operate on local pricing configuration. Estimates
  are not provider invoices.

Missing credentials, unsupported providers, and provider initialization errors
raise `LLMProviderError`.

## Evaluation

```python
from nl2sql_agent.evaluation import EvaluationRunner, load_cases

cases = load_cases("src/nl2sql_agent/evaluation/data/demo.jsonl")
report = EvaluationRunner(agent, database).run(cases)
```

`EvaluationRunner` compares executed results with reference-query results,
scores expected blocks, records runtime and usage data, and verifies that the
SQLite database digest is unchanged. `load_cases()` raises `ValueError` for an
empty or malformed JSONL corpus. Result matching also requires untruncated
actual and reference rows; unordered comparisons preserve duplicate counts.

It also rejects duplicate IDs and empty runs. Report version 2 includes case
counts and null metrics for missing categories. Policy credit requires
`outcome="policy_blocked"` without execution; result credit requires
`outcome="executed"` and `executed=True`. Clarification and unanswerable
decisions are scored separately.

`nl2sql_agent.llm.budget` provides `Rates`, `BudgetLedger`, and `BudgetedModel`.
Reserve before a call and reconcile only known usage. Uncertain calls retain
their reservation. `BudgetExhausted` stops requests that cannot fit.

## Saved sessions

`StateStore(path)` creates or opens the local SQLite state database. It provides
session creation/listing/loading/renaming/deletion, ordered messages, pending
approval storage, idempotent run records, pricing rules and preferences.
`append_message()` permits user/assistant roles and stores content verbatim;
payload fields are allowlisted, not recursively redacted. `save_pending()`
retains question and unapproved SQL. `save_run(..., approved=False)` omits SQL
from the run record only. `replace_pricing_rules()` rejects invalid or
overlapping windows. SQLite errors can propagate to callers.

Use [the persistence guide](openwiki/operations/persistence-audit.md) for privacy
and reporting boundaries. Signatures and typed parameters live in
[`persistence.py`](src/nl2sql_agent/persistence.py).

## Utilities

The `nl2sql_agent.utils` package exports logging, audit, redaction, and text
helpers: `configure_logging`, `get_logger`, `AuditLogger`, `hash_text`,
`redact_sql`, `strip_sql_fences`, and `truncate`.

## Prompt templates

`nl2sql_agent.prompts` exports `SQL_WRITER_SYSTEM`, `SQL_WRITER_USER`,
`SUMMARIZER_SYSTEM`, and `SUMMARIZER_USER`. The helper
`sql_writer_system(dialect)` selects dialect-specific writer instructions;
`error_section(error)` and `format_data(data)` build bounded prompt sections.
Keep application prompts in this module so the CLI, UI, and evaluator use the
same templates.

## Streamlit UI helpers

`nl2sql_agent.ui` exports `main`, `render_sidebar`, `render_chat_history`,
`render_run_steps`, and `render_run_result`. These functions require an active
Streamlit runtime and use `st.session_state`; they are not a framework-neutral
UI API. Launch them through `nl2sql-agent serve` or the documented Streamlit
command.

## Exported constants and types

| Package | Exports |
| --- | --- |
| `nl2sql_agent` | `__version__` |
| `nl2sql_agent.agent` | `AgentState`, `NL2SQLAgent`, `NodeTrace` |
| `nl2sql_agent.config` | `Provider`, `Settings`, model-policy and environment helpers |
| `nl2sql_agent.db` | Backend protocol, errors, plan/result dataclasses, SQLite/PostgreSQL backends, seed constants, formatting/setup helpers |
| `nl2sql_agent.evaluation` | `EvalCase`, `EvaluationCaseResult`, `EvaluationReport`, `EvaluationRunner`, `load_cases` |
| `nl2sql_agent.llm` | Provider/model constants, provider error, pricing dataclasses and errors, model construction/discovery, cost functions |
| `nl2sql_agent.prompts` | Four prompt templates plus formatting helpers |
| `nl2sql_agent.security` | Dangerous-function constant, SQL policy/result types, validation error, parse/validate/prepare/table helpers |
| `nl2sql_agent.ui` | Streamlit entry point and rendering helpers |
| `nl2sql_agent.utils` | Audit, logging, redaction, hashing, and text helpers |

## CLI

```text
nl2sql-agent ask QUESTION [--clarification REPLY] [--provider PROVIDER] [--model MODEL] [--api-key KEY] [--show-sql]
nl2sql-agent config
nl2sql-agent serve [--port PORT] [--host HOST]
nl2sql-agent eval [--dataset PATH] [--output PATH] [--min-pass-rate RATE]
                  [--provider PROVIDER] [--model MODEL] [--api-key KEY]
                  [--input-cost-per-million VALUE]
                  [--output-cost-per-million VALUE]
```

`serve` rejects non-loopback hosts and uses a source-relative script path, so
launch it from the checkout. `ask` executes directly; it has no approval prompt.
`eval` exits unsuccessfully when any present scored category is below
`--min-pass-rate`, the report is empty, or database integrity fails. Missing
categories remain null and are not assigned a perfect score.
