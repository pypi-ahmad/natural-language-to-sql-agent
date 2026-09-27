---
type: testing
title: Testing and maintenance
description: Offline verification, explicitly enabled service tests, coverage boundaries and documentation maintenance.
tags: [testing, ci, maintenance]
status: draft
sources:
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-4d1645cb6317345817452838
    resource: repo://.pre-commit-config.yaml
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-f0a6e7dc03522b2682f88655
    resource: repo://tests/conftest.py
  - id: openwiki-source-29c20cf786ce388eea43bd6e
    resource: repo://tests/integration/test_ollama_live.py
  - id: openwiki-source-a4cded8e49aa361ecac7df11
    resource: repo://tests/integration/test_postgres_live.py
  - id: openwiki-source-d7b60eb8c8f8433aac6ff347
    resource: repo://tests/unit/test_ui_app.py
generated: { by: "codex", at: "2026-09-27T13:15:44.986Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:31:57.770Z
---

# Testing and maintenance

## Offline development checks

From the checkout, install the locked development environment and run the unit suite:

```powershell
uv sync --locked --all-groups
uv run pytest tests/unit -q
```

Shared fixtures reset cached settings and remove listed provider credentials and backend overrides from the process environment. Database fixtures use temporary directories. Model behavior is mocked for unit tests.

Streamlit AppTest coverage includes initial navigation, pricing controls and clarification followed by explicit approval. The approval test asserts that preparation has not executed SQL, clicking **Run query** executes it, and the two writer responses do not trigger a third summarization call.

## CI contract

The verification job runs on both Ubuntu and Windows. It synchronizes the lockfile, runs pytest with coverage, runs the local hooks through `prek`, audits locked dependencies, builds distributions and checks the installed wheel's CLI help in an isolated environment.

The configured hooks check Ruff formatting, Ruff lint, ty and secrets. Coverage uses branch measurement and an 80% threshold, but excludes the Streamlit application and page modules as well as the package entrypoint. Passing coverage is not a claim that every UI path is measured; AppTest supplies separate behavioral checks.

Useful local commands matching those checks are:

```powershell
uv run pytest -q --cov=nl2sql_agent --cov-report=term-missing
uv run prek run --all-files
uv audit --locked
uv build
```

Hooks and dependency audits have their own environment and network requirements. A successful unit run does not imply that every CI step or platform has been rerun locally.

## Live-service tests are explicit

Ollama tests require `NL2SQL_LIVE_TESTS=1`, a reachable server and the selected installed model. The default test model is `qwen3.5:0.8b`; override it with `NL2SQL_TEST_MODEL`. The tests skip if these conditions are unmet. Enabling them makes actual model calls.

PostgreSQL tests instead require `NL2SQL_TEST_POSTGRES_ADMIN_DSN`. The fixture refuses any database name other than `nl2sql_test`, then creates its test role and tables. Use a fresh disposable instance: the fixture is not a general-purpose cleanup or migration tool. CI provides PostgreSQL 17 in a disposable service. Tests cover prepared execution, read-only permissions and composite foreign-key pairing.

## Maintaining claims

Read current source and focused tests before revising a wiki statement. Test definitions establish intended contracts; actual execution results should identify the command and scope run. Do not present opt-in tests, provider availability or old benchmark artifacts as newly executed evidence.

For model-quality evidence, use [benchmarks](../evaluation/benchmarks.md). For enforcement boundaries, use [SQL safety](../concepts/sql-safety.md). Return to [quickstart](../quickstart.md) for task routing.
