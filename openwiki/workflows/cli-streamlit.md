---
type: workflow
title: CLI and Streamlit workflows
description: Direct CLI execution, interactive SQL approval, database uploads and local session behavior.
tags: [cli, streamlit, approval, uploads]
status: draft
sources:
  - id: openwiki-source-b527ee101f959598a6526f76
    resource: repo://src/nl2sql_agent/cli.py
  - id: openwiki-source-4312286aa9e23ebf1b1053b9
    resource: repo://src/nl2sql_agent/ui/database_upload.py
  - id: openwiki-source-87eabaa9fb9c43cea9001ccb
    resource: repo://src/nl2sql_agent/ui/pages.py
  - id: openwiki-source-4597ae7b5a99345e74920670
    resource: repo://src/nl2sql_agent/ui/streamlit_app.py
  - id: openwiki-source-d7b60eb8c8f8433aac6ff347
    resource: repo://tests/unit/test_ui_app.py
generated: { by: "codex", at: "2026-09-27T13:38:19.239Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:38:19.239Z
---

# CLI and Streamlit workflows

## Choose the execution surface

`nl2sql-agent ask` invokes the full agent workflow and prints the final answer. It does not pause for an interactive approval click. Use `--show-sql` to print generated SQL and repeated `--clarification` arguments to supply clarification replies. The command returns success for an executed outcome (and its legacy missing-outcome case), otherwise exit code 1.

Streamlit separates preparation from execution. A question runs `stream_prepare`; a clarification requests another reply, while a prepared query opens an editable SQL preview. **Run query** calls `execute_prepared`, which checks the context and revalidates SQL. Cancel clears pending SQL without executing it. New chat input is disabled while a query awaits approval.

Successful results and failures are rendered from their outcome. Approval means the user authorized an attempt, not that the database necessarily executed successfully.

## Local serving and provider settings

From the repository root:

```powershell
uv run nl2sql-agent serve --port 8512
```

The launcher invokes the source Streamlit script with the current Python interpreter. Its host must be `localhost`, `127.0.0.1` or `::1`; this is a local development UI without its own authentication.

Runtime provider/model/key overrides are applied to a deep copy of cached settings, preventing one Streamlit session from mutating the shared settings object. Model refresh is an explicit provider-discovery action and is not proof that inference will succeed.

## Data-source boundaries

The UI supports a managed demo, a SQLite upload and operator-configured PostgreSQL. PostgreSQL is unavailable without a configured DSN and must pass backend role/catalog checks.

Upload validation checks extension and size before reading, then checks the SQLite header and computes a SHA-256 digest. Accepted bytes are written to a session-local server-side workspace under a digest-derived filename and opened read-only. The file is not kept exclusively in browser memory. Catalog access supplies an additional validity check.

Allowed tables are explicitly selected. Upload sample rows are off by default, with an opt-in toggle that allows values into model prompts. Demo prompts include bounded samples; PostgreSQL follows the non-demo path without samples. An empty table selection prevents asking a new question.

## Sessions and supporting pages

Chat context includes database fingerprint, provider, model, sorted table selection and sample-value setting. Changing context resets the active chat and pending state. **Clear history** resets the active in-memory conversation; it is not the saved-session deletion control.

Navigation also exposes Costs, Sessions, Insights and Pricing. Sessions offers load, rename and confirmed permanent deletion. Loading saved content is not a guarantee of restored database connectivity or reusable approval: current context is checked again. If the state database cannot initialize, the application reports that saved sessions, editable pricing and historical dashboards are unavailable.

Read [persistence and audit](../operations/persistence-audit.md) for details about result values in saved answers. See [query review](query-review.md) for execution invariants and [quickstart](../quickstart.md) for setup.
