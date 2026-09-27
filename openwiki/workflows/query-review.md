---
type: workflow
title: Query decisions and approval
description: Writer decisions, bounded recovery, context-bound SQL approval and deterministic result rendering.
tags: [decisions, approval, retries, grounding]
status: draft
sources:
  - id: openwiki-source-7734639af5fa0c53589a6ee8
    resource: repo://src/nl2sql_agent/agent/decisions.py
  - id: openwiki-source-697296a3dbab6e8c15c6817a
    resource: repo://src/nl2sql_agent/agent/workflow.py
  - id: openwiki-source-2e4757d9bdf13a56752d6d7a
    resource: repo://tests/unit/test_decisions.py
generated: { by: "codex", at: "2026-09-27T13:15:44.986Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:43:28.075Z
---

# Query decisions and approval

## Generate a decision

The writer receives schema context, the question, prior error feedback and clarification replies. Its structured decision has one of three actions: `sql`, `clarify` or `unanswerable`. Strict validation forbids extra fields. SQL actions require nonempty SQL; non-SQL actions require a message and no SQL. Assumptions are limited to ten entries.

Legacy SQL-only responses remain accepted. JSON-looking responses must validate and cannot fall back to raw SQL when malformed. Invalid decisions produce `generation_error` with `invalid_decision`.

Clarification never executes SQL. Each follow-up supplies the original question and collected replies. More than two supplied replies raises an error; another clarification request after two replies becomes unanswerable.

## Recover only within the workflow boundary

The full graph runs schema retrieval, writing, validation/preflight, execution and answer rendering. Writer attempts increment `retry_count`; the configured `max_retries` therefore bounds writer attempts rather than granting that many extra attempts.

Policy blocks, provider failures, budget exhaustion, clarification and unanswerable decisions stop the writer loop. Recoverable generation/preflight errors can return to the writer within the bound. Database execution errors can also trigger another writer attempt in the full graph. Provider exceptions become generic user-facing errors rather than exposing the exception text.

The preparation graph stops after validation/preflight and contains no executor. Its routing label `prepared` is also an end-of-graph sentinel on failure, so callers must inspect the returned outcome and error rather than infer success from routing alone.

## Approve against current context

`execute_prepared` requires a prepared outcome and a matching context signature. That signature includes database identity, backend fingerprint, allowed tables, schema, catalog and SQL policy. Missing legacy context or a changed signature returns `stale_preparation` and requires preparing again.

The signature is a context check, not an immutable snapshot of database rows. Data can change between preparation and execution. An edited SQL string is validated and preflighted again immediately before execution.

This method performs one approved execution attempt; it does not enter the full graph's writer-repair loop. A failed approved query therefore cannot silently replace the user's reviewed SQL with a newly generated query.

## Render what executed

Database errors clear row/export fields and mark execution false. Successful execution carries rows, columns, CSV, truncation and metrics. Slow-query, SQLite-work and fetch-truncation warnings are attached when their configured conditions apply.

For executed states, answers are deterministic: no rows produces an empty-result message, one row produces named values, and multiple rows use the result table. The answer distinguishes fetch truncation, a safety SQL LIMIT and the first-100-row preview. The legacy non-executed summarization path can still call the model; ordinary successful execution does not.

Focused decision tests cover clarification, malformed decisions, provider failures, policy versus preflight outcomes and stale approval. See [SQL safety](../concepts/sql-safety.md), [CLI and Streamlit](cli-streamlit.md) and [persistence](../operations/persistence-audit.md).
