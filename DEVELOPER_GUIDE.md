# Developer guide

Use [onboarding](ONBOARDING.md) for setup and the [contributor runbook](CONTRIBUTOR_RUNBOOK.md)
for the steps from implementation to review. This guide maps changes to their
responsible modules and explains the contracts to preserve. The application is a Python package with
a CLI and Streamlit UI; it does not expose a project REST API requiring OpenAPI.

## Find the responsible code

| Change | Implementation | Focused tests |
| --- | --- | --- |
| Configuration or provider policy | `src/nl2sql_agent/config/settings.py`, `llm/factory.py` | `tests/unit/test_settings.py`, `test_llm_factory.py` |
| Decisions, clarification or approval | `src/nl2sql_agent/agent/decisions.py`, `agent/workflow.py` | `tests/unit/test_decisions.py`, `test_agent.py` |
| SQL authorization | `src/nl2sql_agent/security/sql_validator.py` | `tests/unit/test_sql_validator.py` |
| Database plans, results or schema selection | `src/nl2sql_agent/db/` | `tests/unit/test_database.py`, `test_postgres.py`, `test_decisions.py` |
| Session persistence | `src/nl2sql_agent/persistence.py` | `tests/unit/test_persistence.py` |
| UI approval and navigation | `src/nl2sql_agent/ui/` | `tests/unit/test_ui_app.py` |
| Pricing or benchmark spending | `src/nl2sql_agent/llm/pricing.py`, `llm/budget.py` | `tests/unit/test_pricing.py`, `test_budget.py` |
| Evaluation and dataset selection | `src/nl2sql_agent/evaluation/` | `tests/unit/test_evaluation.py`, `test_benchmark.py`, `test_judge.py` |

The [architecture guide](ARCHITECTURE.md) explains dependency direction. The
[API reference](API_REFERENCE.md) lists exported objects. Source signatures and
tests are authoritative when documentation disagrees with them.

## Trace a request

CLI `ask` constructs the configured model and calls the full workflow. Streamlit
uses preparation first, waits for approval, then calls `execute_prepared()`.
Preparation includes schema discovery, generation, policy validation and
non-executing preflight. It must not call the executor.

Writer decisions can request clarification or report missing data without SQL.
The full graph can retry recoverable failures; the approved-execution method
performs one attempt and never silently rewrites reviewed SQL. Successful
answers are rendered from database cells. The legacy summarization fallback
can still make a model call outside the successful-execution path.

Inspect `outcome`, `executed` and `error_code` together. Do not infer success
from populated SQL, a route name, or an empty error field alone. State updates
are partial, so callers must handle missing optional keys.

## Preserve these contracts

- An injected database is not initialized or seeded by the agent. Create a
  disposable fixture explicitly when testing database behavior.
- `allowed_tables=None` selects visible tables; an empty collection authorizes
  none. Unknown table names fail construction.
- Approval context covers database identity, schema, catalog, permissions and
  SQL policy. It does not freeze database row values.
- SQL authorization stays deterministic. A model refusal and a policy block
  are different evaluation outcomes.
- Saved message text can contain result values. Structured-payload exclusions
  do not redact text; audit redaction is a separate contract.
- UI cost alerts do not enforce the benchmark driver's persistent spending cap.

## Work on Python code

Keep dependencies in `pyproject.toml` and `uv.lock`. Use the existing Ruff and
ty configuration; a documentation change should not add a formatter or doc-site
dependency. Keep public type annotations accurate and use docstrings for the
meaning of inputs, outputs, side effects and errors that types cannot express.

For a public method, explain whether it executes SQL, calls a provider, writes
local state, or can raise before returning an outcome. Describe exceptions as well as returned failure states: setup, schema discovery
and catalog loading can raise. Keep obvious accessors short. Include a runnable example when a boundary
case is easy to misunderstand.

`utils.text.strip_sql_fences()` only normalizes text. Always pass generated SQL
through the guardian before execution. `truncate()` treats a non-positive cap
as disabled, and uses a plain prefix when the suffix would consume the cap.

## Extend a subsystem

For a provider, inspect settings, the factory, UI selection, pricing and saved
session restoration together. Mock construction and discovery before attempting
live calls. Check model availability and supported request options separately against the
live provider. Mock-based tests cannot verify them.

For a database adapter, implement `DatabaseBackend`, preserve read-only
connections and bounded results, and add dialect-specific policy and preflight
tests. The protocol's `execute()` type is broad; workflow code consumes result
attributes and methods, so matching method names alone is insufficient.

For an outcome or state field, trace writer parsing, routing, UI rendering,
persistence allowlists and evaluator scoring. Add tests for failure paths as
well as successful results. See the [tutorial capstone](ZERO_TO_MASTERY_TUTORIAL.md#5-capstone)
for a bounded exercise.

## Review evidence

Use the [benchmark protocol](benchmarks/README.md) for model comparisons. Keep
failed attempts, case IDs, denominators and configuration. A source change does
not update old manifests or make their results current. The [documentation audit](DOCUMENTATION_AUDIT.md)
records the scope and limits of the documentation checks.
