---
type: guide
title: Start here
description: Set up the checkout with uv, choose direct CLI execution or review-first Streamlit, and find source-grounded operational guidance.
tags: [quickstart, setup, navigation]
status: draft
sources:
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-697296a3dbab6e8c15c6817a
    resource: repo://src/nl2sql_agent/agent/workflow.py
  - id: openwiki-source-b527ee101f959598a6526f76
    resource: repo://src/nl2sql_agent/cli.py
  - id: openwiki-source-0a87f5e71f7477419b5f3d3a
    resource: repo://src/nl2sql_agent/config/settings.py
  - id: openwiki-source-0a9b9f9ae29ed5e29579f8bf
    resource: repo://src/nl2sql_agent/persistence.py
  - id: openwiki-source-4597ae7b5a99345e74920670
    resource: repo://src/nl2sql_agent/ui/streamlit_app.py
  - id: openwiki-source-7955f8483b6fd4337be93c37
    resource: repo://tests/unit/test_cli.py
  - id: openwiki-source-d7b60eb8c8f8433aac6ff347
    resource: repo://tests/unit/test_ui_app.py
generated: { by: "codex", at: "2026-09-27T13:15:44.986Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:31:57.770Z
---

# Start here

This project turns natural-language questions into read-only SQL using local or hosted models. The CLI can execute directly; Streamlit exposes a separate SQL review and approval step. Read-only controls reduce risk but do not establish that a generated query answers the intended business question.

## Install and check the checkout

The package requires Python `>=3.12.10,<3.13`. From the repository root, with uv available:

```powershell
uv sync --locked --all-groups
uv run nl2sql-agent --help
uv run pytest tests/unit -q
```

The installed command is `nl2sql-agent`. Development dependencies include test, lint and security groups. Unit tests use mocks and temporary databases; live model and PostgreSQL checks have separate opt-in conditions.

## Try the review-first UI

```powershell
uv run nl2sql-agent serve --port 8512
```

Open the local address printed by Streamlit. Select a provider/model and the demo data source, then ask a question such as “How many employees are in each department?” Answer any clarification, inspect the SQL preview, and choose **Run query** or **Cancel**.

The launcher accepts loopback hosts only. Run it from this checkout because it starts the source Streamlit script using a relative path.

## Use a local model from the CLI

The following command requires a reachable Ollama server with `granite4.2:3b` already installed:

```powershell
uv run nl2sql-agent ask "How many employees are in each department?" --provider ollama --model granite4.2:3b --show-sql
```

This example selects a model explicitly; the configured default is Ollama with `phi4-mini:3.8b`. The project does not install or start the model server through this command. CLI `ask` executes the full workflow without the UI approval pause.

Settings resolve from constructor arguments, environment, the current directory's `.env`, then defaults. Check existing backend settings before using the example: selecting a model does not reset the database configuration. When the agent owns the configured SQLite demo, it creates its schema and optionally seeds it. Injected databases and PostgreSQL do not receive that initialization.

Keep hosted-provider credentials in supported environment settings, not in documentation or shared command history. Selecting a remote provider can send the question and configured schema context to that provider.

## Find the right page

| Task | Read |
| --- | --- |
| Understand components and graph ownership | [Runtime architecture](architecture/runtime.md) |
| Understand clarification, retries and approval | [Query decisions](workflows/query-review.md) |
| Use uploads, sessions and UI pages | [CLI and Streamlit](workflows/cli-streamlit.md) |
| Understand enforcement and its limits | [SQL safety](concepts/sql-safety.md) |
| Configure databases and schema context | [Databases and schema](integrations/databases-schema.md) |
| Choose a provider and interpret pricing | [Model providers](integrations/model-providers.md) |
| Understand what remains on disk | [Persistence and audit](operations/persistence-audit.md) |
| Interpret evaluation artifacts and limitations | [Benchmarks](evaluation/benchmarks.md) |
| Run checks and maintain evidence | [Testing and maintenance](testing/verification.md) |

These pages are machine-authored drafts grounded in source and tests. Source behavior remains authoritative. In particular, saved answer text can contain result values even though structured result payloads are excluded from persistence.
