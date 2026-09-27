---
type: Policy
title: SQL policy and execution boundaries
description: How parser policy, table authorization, preflight, read-only connections, and resource limits constrain generated SQL.
tags: [sql, security, policy, database]
status: draft
sources:
  - id: openwiki-source-697296a3dbab6e8c15c6817a
    resource: repo://src/nl2sql_agent/agent/workflow.py
  - id: openwiki-source-84cf171c093164528928cca3
    resource: repo://src/nl2sql_agent/db/database.py
  - id: openwiki-source-34a7a342b749596b14a155e6
    resource: repo://src/nl2sql_agent/db/postgres.py
  - id: openwiki-source-b5243580bb6f85d5a8b3aa6f
    resource: repo://src/nl2sql_agent/security/sql_validator.py
  - id: openwiki-source-a4cded8e49aa361ecac7df11
    resource: repo://tests/integration/test_postgres_live.py
  - id: openwiki-source-2e4757d9bdf13a56752d6d7a
    resource: repo://tests/unit/test_decisions.py
  - id: openwiki-source-1857b39297eaabd761196cdd
    resource: repo://tests/unit/test_sql_validator.py
generated: { by: "codex", at: "2026-09-27T13:31:57.770Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:43:28.075Z
---

# SQL policy and execution boundaries

Query approval combines application policy with database restrictions. These controls constrain execution; they do not prove that a query answers the question correctly or that the application is an isolation boundary for hostile database extensions.

## Validation before execution

`prepare_sql` parses one statement with SQLGlot, checks the permitted query shape, validates backend-specific schema/locking rules, resolves physical table references, and canonicalizes SQL. The current implementation accepts top-level SELECT and the explicitly handled Union AST form; other set operations are not accepted by that top-level branch.

Joins, aggregates, subqueries, and CTEs are enabled by the default policy but can be disabled or capped. Known dangerous functions and a conservative rendered-keyword check are rejected. The keyword check can also reject benign text; this is not a pure AST-only policy.

Physical table names are compared against the explicit allowlist. CTE aliases do not grant permission to access physical tables. An empty allowlist remains empty. A configured maximum adds or clamps the SQL LIMIT; this is separate from the backend fetch cap.

The agent then calls non-executing preflight. Validation failures and database/preflight failures have distinct outcomes. A successful preparation records SQL, a plan, warnings, and `executed=False`.

## Backend enforcement

SQLite query connections use a read-only URI, `query_only=ON`, `trusted_schema=OFF`, and disabled extension loading. Writable connections belong to explicit demo setup/reset paths, not ordinary query execution.

PostgreSQL starts a transaction, enables read-only mode and verifies it server-side, rejects privileged roles, applies transaction-local statement/lock timeouts and search path, and rolls back and closes the connection. Operators should still provision a least-privileged reader account.

SQLite uses a progress handler for elapsed-time and VM-step limits; its connection timeout alone only bounds lock waiting. Both the SQL LIMIT and fetch truncation can affect completeness. SQLite fetches one extra row to detect truncation, while query-plan warnings describe potential cost rather than semantic correctness.

## Approval and verification

UI approval is not a bypass: execution rechecks the preparation context and validates edited SQL again. Direct backend `execute` calls are lower-level and do not perform the agent's parser/allowlist checks.

Tests cover table authorization, CTE/physical-table distinctions, LIMIT enforcement, preparation errors, and real PostgreSQL read-only behavior. See [verification](../testing/verification.md). No live security audit is implied by this documentation run.

Related: [query review](../workflows/query-review.md) and [database/schema context](../integrations/databases-schema.md).
