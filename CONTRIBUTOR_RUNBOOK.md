# Contributor runbook

Use this procedure after [development setup](ONBOARDING.md). Project expectations
and conduct remain in [CONTRIBUTING.md](CONTRIBUTING.md).

## 1. Establish a baseline

```powershell
git status --short
git diff --stat
uv sync --locked --all-groups
uv run pytest tests/unit -q
```

Preserve existing changes. Record any failures before starting so you can distinguish them from regressions. Agree on the issue and
scope before substantial work. When you are ready to start your own contribution,
create a focused branch from the intended base; do not reset a dirty checkout.

## 2. Reproduce and edit

Find the owner in the [developer guide](DEVELOPER_GUIDE.md). Write a focused test
that demonstrates the expected behavior, run it, then make the smallest change
that satisfies it. Use temporary databases and fake models for routine tests.

For example, when editing decision handling:

```powershell
uv run pytest tests/unit/test_decisions.py -q
uv run pytest tests/unit/test_agent.py -q
```

For documentation-only work, compare every behavior claim against source and
tests. Preserve legal text and historical evidence. Update the API reference
when a public contract changes, and keep tutorial examples runnable.

## 3. Verify the change

```powershell
uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check src
uv run pytest tests/unit -q --cov=nl2sql_agent --cov-report=term-missing
uv run prek run --all-files
uv audit --locked
uv build
git diff --check
```

Use the unit command for an explicitly offline suite. CI's broader pytest
command also collects integration tests, whose execution depends on opt-in
settings. CI tests Ubuntu and Windows and supplies PostgreSQL 17 separately.
Coverage requires 80%; it excludes selected UI modules and the package entrypoint.
AppTest supplies separate UI behavior checks.

The hooks check formatting, lint, types and secrets. Audit and isolated tooling
may require network access. If a check is blocked, record the reason and leave its result unresolved.

After building, inspect the wheel paths under `dist/` and run the installed-wheel
smoke command from [README](README.md#12-verification) with the exact new wheel.
Do not silently select an older wheel from a previous build.

## 4. Handle live checks deliberately

Ollama tests require `NL2SQL_LIVE_TESTS=1` and a running model server. PostgreSQL
tests require `NL2SQL_TEST_POSTGRES_ADMIN_DSN` targeting a disposable database
named `nl2sql_test`; the fixture creates roles and tables. Never point that
fixture at a user's database. See [test maintenance](openwiki/testing/verification.md).

Do not run paid benchmarks as a routine documentation check. If a model run is
part of the agreed change, preserve its artifacts and follow the existing
budget and provenance rules in [benchmarks](benchmarks/README.md).

## 5. Update related documents

| Change | Documents to check |
| --- | --- |
| Public Python interface | Docstring, API reference, affected tutorial examples |
| Defaults or environment variables | README configuration, onboarding if setup changes |
| Execution or privacy | Architecture, security policy, affected OpenWiki pages |
| Evaluation semantics | Dataset guide, benchmark protocol, scoring correction if needed |
| Contributor tooling | This runbook, contributing guide, onboarding |

Use OpenWiki's resumable page workflow for its pages. Do not edit generated
Claims, provenance, indexes or managed instruction blocks manually.

## 6. Prepare the review

Review the diff for credentials, unintended generated files and unrelated edits.
Describe the problem, implementation, tests and remaining limits in the PR.
Separate completed checks from instructions someone still needs to run.

Commit and publish only when you intend to submit the contribution. A successful
local test run does not establish that remote CI passed or that a PR was merged.

## Failure triage

| Failure | Action |
| --- | --- |
| Test fails only in the suite | Check settings-cache and environment isolation in fixtures. |
| Coverage falls below 80% | Inspect missing branches; do not lower the threshold to hide a gap. |
| Secret scanner flags content | Inspect privately. Remove actual secrets; justify false positives narrowly. |
| Provider fails during a live run | Retain the failed attempt and its configuration; do not substitute a best retry. |
| Approval becomes stale | Prepare again against the current context; do not bypass signature checks. |
| Documentation example fails | Fix the example or its stated prerequisites, then rerun it. |
