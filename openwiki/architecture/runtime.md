---
type: Architecture
title: Runtime architecture
description: Ownership and runtime boundaries between the query agent, database adapters, model clients, and user interfaces.
tags: [architecture, agent, execution]
status: draft
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:43:28.075Z
sources:
  - id: openwiki-source-db5b4c977ba42e953f015885
    resource: repo://src/nl2sql_agent/agent/state.py
  - id: openwiki-source-697296a3dbab6e8c15c6817a
    resource: repo://src/nl2sql_agent/agent/workflow.py
  - id: openwiki-source-b527ee101f959598a6526f76
    resource: repo://src/nl2sql_agent/cli.py
  - id: openwiki-source-535043f44d928cdbc8825e13
    resource: repo://src/nl2sql_agent/db/base.py
  - id: openwiki-source-c277c6c2429356b044845774
    resource: repo://tests/unit/test_agent.py
  - id: openwiki-source-2e4757d9bdf13a56752d6d7a
    resource: repo://tests/unit/test_decisions.py
generated: { by: "codex", at: "2026-09-27T13:38:19.239Z" }
---

# Runtime architecture

The application has one query workflow shared by the CLI and Streamlit. `NL2SQLAgent` receives an invokable model and an optional database backend. When no backend is injected, settings select SQLite or PostgreSQL. Only the managed SQLite demo is created and seeded automatically; an injected database is not seeded.

## Ownership and flow

| Component | Responsibility | Boundary |
| --- | --- | --- |
| Agent | Select schema, request a decision, validate, execute, render | Owns workflow state and explicit outcomes |
| Model client | Return a writer decision or SQL-compatible response | Cannot authorize database access |
| Database backend | Expose visible tables/schema, preflight, execute | Owns connection policy and execution limits |
| CLI | Run a question to completion | Uses the direct execution graph |
| Streamlit | Prepare a candidate for review, then explicitly execute | Approval is checked again by the agent |

The full LangGraph flow is `fetch_schema → writer → guardian → executor → summarizer`, with conditional exits and bounded writer retries. The node named `guardian` is deterministic SQL validation and preflight. It is distinct from the optional Granite Guardian evaluation model.

The prepare graph ends after validation/preflight. It does not contain an executor. A graph route named `prepared` can also terminate a failed preparation; callers must inspect the returned outcome and error, not infer success from that route.

## State and results

`AgentState` is a partial TypedDict so node updates can merge through LangGraph. It carries question/clarifications, selected schema, SQL, explicit outcome, execution evidence, usage, plans, metrics, and operational traces. A SQL string by itself does not prove execution.

Successful execution is rendered directly from database cells. Empty results, a single row, and tabular results have deterministic output paths. Notices distinguish a SQL safety LIMIT, fetched-row truncation, and a 100-row preview. The legacy summarizer fallback can call the model for states outside the successful-execution path.

## Extension seams

A new backend must supply the `DatabaseBackend` contract: identity, dialect, table/schema discovery, non-executing preflight, and execution. Backend connection restrictions remain necessary even when the agent validates SQL. A new model integration belongs behind the factory and must preserve failure and usage reporting.

Focused regressions cover injected-database ownership, clarification without execution, missing or changed approval context, and deterministic successful answers.

Continue with [query decisions and approval](../workflows/query-review.md), [database context](../integrations/databases-schema.md), or [model providers](../integrations/model-providers.md).
