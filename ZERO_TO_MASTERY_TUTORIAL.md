# From first query to workflow maintenance

This tutorial starts with an offline query and ends with a regression-test
exercise. It assumes basic Python functions, imports and assertions. Complete
[onboarding](ONBOARDING.md) first. The [study handbook](ZERO_TO_HERO_STUDY_HANDBOOK.md)
provides the longer source walkthrough.

## 1. Prepare and execute without a model server

Create the ignored `outputs` directory if necessary. Save this script as
`outputs/tutorial.py`, then run `uv run python outputs/tutorial.py` from the
repository root.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from nl2sql_agent.agent import NL2SQLAgent
from nl2sql_agent.config import Settings
from nl2sql_agent.db import Database

with TemporaryDirectory() as workspace:
    database = Database(Path(workspace) / "tutorial.sqlite3")
    database.ensure_schema(seed=True)
    model = MagicMock()
    model.invoke.return_value = AIMessage(
        content='{"action":"sql","sql":"SELECT COUNT(*) AS total FROM employees"}'
    )
    settings = Settings(
        _env_file=None,
        provider="ollama",
        model="phi4-mini:3.8b",
        db_backend="sqlite",
        schema_catalog_path=None,
        audit_enabled=False,
        max_retries=1,
        db_max_rows=1000,
        sql_allow_aggregates=True,
    )
    agent = NL2SQLAgent(
        model,
        settings=settings,
        database=database,
        allowed_tables={"employees"},
        include_sample_values=False,
    )
    prepared = agent.prepare("How many employees are there?")
    assert prepared["outcome"] == "prepared"
    assert prepared["executed"] is False
    result = agent.execute_prepared(prepared)
    assert result["outcome"] == "executed"
    assert result["raw_rows"] == [(10,)]
    assert result["final_answer"].startswith("total: 10")
    assert "A safety LIMIT was applied" in result["final_answer"]
    assert model.invoke.call_count == 1
    print(result["final_answer"])
```

Expected output starts with `total: 10`, followed by the safety-LIMIT notice;
logging may also appear. The fixed response lets you test application flow
without measuring model accuracy. The temporary directory
is removed when the context exits. The script disables audit output and does
not create a UI session store. It ignores `.env` and overrides settings relevant
to the exercise; unrelated process settings must still pass validation.

The database is injected, so the script explicitly creates and seeds it.
Preparation obtains metadata and a plan without executing the SELECT. Approved
execution revalidates SQL and renders the answer from returned cells, without
another model response.

Checkpoint: replace `COUNT(*)` with `COUNT(*) + 1`. Predict which assertion
fails, run the script, then restore the original expression.

## 2. Separate policy from text cleanup

Save this independent example as `outputs/policy_lesson.py` and run
`uv run python outputs/policy_lesson.py`. It does not open a database.

```python
from nl2sql_agent.security import SQLValidationError, validate_sql
from nl2sql_agent.utils.text import strip_sql_fences, truncate

assert strip_sql_fences("SQL: SELECT 1;") == "SELECT 1"
assert truncate("employee count", 8) == "emplo..."
validate_sql("SELECT 1")
try:
    validate_sql("DELETE FROM employees")
except SQLValidationError:
    print("Policy rejected the statement before database access.")
else:
    raise AssertionError("Expected the validator to reject DELETE")
```

Cleanup removes text wrappers; it does not authorize SQL. The validator rejects
the write statement before database access. Keep validation even if a model
promises read-only SQL.

Checkpoint: explain why a provider refusing to generate SQL does not prove that
the validator blocked it. Find the corresponding test in `tests/unit/test_decisions.py`.

## 3. Follow clarification and stale approval

```powershell
uv run pytest tests/unit/test_decisions.py -q -k "clarification or changed_permissions"
```

Read the tests alongside `prepare()`, `run()` and `execute_prepared()`. A
clarification follow-up passes the original question plus collected replies.
Changing permissions after preparation returns `error_code="stale_preparation"`
without execution.

In the first script, set `agent.allowed_tables` to an empty frozenset between
preparation and execution. The execution assertion should fail. Inspect the
outcome and error code, then restore the script. Do not edit a signature to
bypass approval checks.

Checkpoint: explain why changing database row values can change a result even
when the preparation context still matches. The signature does not hash rows.

## 4. Interpret evaluation results

```powershell
uv run pytest tests/unit/test_evaluation.py tests/unit/test_benchmark.py -q
```

Read [the benchmark protocol](benchmarks/README.md), then answer:

1. Why must duplicate rows survive unordered comparison?
2. Why can matching truncated prefixes not establish a full-result match?
3. Why do provider failures remain in attempted denominators?
4. Why is a missing category null rather than a perfect score?

Answers: multiplicity is part of the result; omitted rows are unknown; removing
failures would hide unsuccessful attempts; and no cases means no measurement.
The live artifacts are historical evidence, not output from this tutorial.
No model comparison is required here.

## 5. Capstone

Add a regression for edited SQL at the approval boundary. Use the `seeded_db`
fixture and existing fake-model patterns. Prepare a permitted count query,
then supply an invalid column through `execute_prepared(sql_query=...)`.

Acceptance criteria:

- Exercise the approval method so the test covers more than low-level validation.
- Assert the error/outcome contract and `executed=False`.
- Confirm that model invocation count did not increase after approval.
- Run the focused test and decision suite without a live provider.

Follow the [contributor runbook](CONTRIBUTOR_RUNBOOK.md) to review the change.
Use this exercise to check your understanding of the workflow. Assessing model
quality, production readiness and security requires separate work.

### Reference solution

Try the exercise before reading this solution. To run it, save the block in
`tests/unit/test_tutorial_approval.py` and use
`uv run pytest tests/unit/test_tutorial_approval.py -q`. It uses the existing
`seeded_db` fixture; it does not need a provider or credentials.

```python
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from nl2sql_agent.agent import NL2SQLAgent
from nl2sql_agent.config import Settings


def test_edited_invalid_column_does_not_request_a_rewrite(seeded_db):
    model = MagicMock()
    model.invoke.return_value = AIMessage(
        content='{"action":"sql","sql":"SELECT COUNT(*) AS total FROM employees"}'
    )
    agent = NL2SQLAgent(
        model,
        settings=Settings(
            _env_file=None,
            provider="ollama",
            model="phi4-mini:3.8b",
            db_backend="sqlite",
            audit_enabled=False,
            schema_catalog_path=None,
            sql_allow_aggregates=True,
        ),
        database=seeded_db,
        allowed_tables={"employees"},
        include_sample_values=False,
    )
    prepared = agent.prepare("How many employees are there?")
    assert prepared["outcome"] == "prepared"
    result = agent.execute_prepared(
        prepared, sql_query="SELECT missing_column FROM employees"
    )
    assert result["outcome"] == "database_error"
    assert result["executed"] is False
    assert result["error"]
    assert result["raw_rows"] == []
    assert model.invoke.call_count == 1
```

The failure occurs during database preflight because the column does not exist.
The approved-execution path returns that failure without asking the model for
different SQL. Compare this with the full workflow's bounded repair loop.

## Continue independently

Choose an extension from the [developer guide](DEVELOPER_GUIDE.md), identify its
owner and affected contracts, and write a regression before changing behavior.
Use the [handbook exercises](ZERO_TO_HERO_STUDY_HANDBOOK.md#52-practice-exercises)
to check schema selection, pricing and persistence knowledge.
