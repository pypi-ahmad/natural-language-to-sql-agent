---
type: operations
title: Sessions, pricing and audit records
description: Local session storage, cost estimates and redacted audit events have different persistence and privacy boundaries.
tags: [persistence, privacy, audit, pricing]
status: draft
sources:
  - id: openwiki-source-0a87f5e71f7477419b5f3d3a
    resource: repo://src/nl2sql_agent/config/settings.py
  - id: openwiki-source-0a9b9f9ae29ed5e29579f8bf
    resource: repo://src/nl2sql_agent/persistence.py
  - id: openwiki-source-4597ae7b5a99345e74920670
    resource: repo://src/nl2sql_agent/ui/streamlit_app.py
  - id: openwiki-source-5e2b5cceb8263bafb4785027
    resource: repo://src/nl2sql_agent/utils/audit.py
  - id: openwiki-source-bb1488635fe334be6dbdb52d
    resource: repo://tests/unit/test_audit.py
  - id: openwiki-source-450a627fa9179a63a122c466
    resource: repo://tests/unit/test_persistence.py
generated: { by: "codex", at: "2026-09-27T13:38:19.239Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:38:19.239Z
---

# Sessions, pricing and audit records

## Two independent stores

The default application state database is `~/.nl2sql-agent/state.sqlite3`; the default audit destination is `logs/audit.jsonl`, with auditing enabled. Changing one destination does not move the other.

`StateStore` owns sessions, ordered messages, pending queries, pricing rules, run records and preferences. SQLite connections enable foreign keys and a busy timeout. Message insertion uses an immediate transaction to allocate positions safely; deleting a session cascades to its dependent records.

## Saved content

Message and pending-query payloads use explicit field allowlists. Structured `raw_rows`, CSV exports and schema text are excluded. Pending state can still contain the question, generated SQL, clarifications and approval context.

Result values can reach disk because message `content` is stored verbatim. The UI builds assistant content from `final_answer`, which can include returned values, and passes that content unchanged to persistence. The `result_not_stored` flag describes the structured result payload, not the absence of values from answer text. User messages and session titles also retain question text.

Run records retain SQL only for approved runs; approved SQL can contain literal values. Saving a run uses its run ID when available and replaces an existing record with that ID, rather than adding another charge row. Records retain usage, pricing snapshots, metrics and execution outcome for reporting.

## Cost reports and limits

The UI chooses effective pricing rules and computes estimates from usage records. Missing pricing produces an unpriced warning. Session and monthly budget thresholds generate warnings at 80% and 100%; they do not block execution. These UI warnings are distinct from the benchmark reservation ledger described in [model providers](../integrations/model-providers.md).

Cost CSV export neutralizes spreadsheet formula prefixes. Estimates remain dependent on configured rates and provider usage metadata.

## Audit privacy boundary

Audit events hash questions and record their length instead of recording their text. SQL is parsed, comments removed and literal nodes replaced by placeholders. If parsing fails, the event retains only a SQL hash. Unsupported metadata fields raise an error rather than being silently serialized. Disabled auditing writes nothing.

These protections apply to the audit log, not automatically to the session database. Treat both destinations as sensitive local data and manage file access, backups and retention accordingly.

## Evidence and related work

Focused persistence tests cover payload exclusions, run costs and metrics, initialization, pricing validation and CSV handling. Audit tests cover question hashing, literal removal, parse failure, disabled logging and metadata rejection. These tests define specific contracts; they are not a complete privacy audit.

See [CLI and Streamlit](../workflows/cli-streamlit.md) for session behavior and [verification](../testing/verification.md) for runnable checks.
