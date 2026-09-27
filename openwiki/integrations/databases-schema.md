---
type: Integration
title: Database and schema context
description: SQLite and PostgreSQL discovery, authorized schema selection, foreign-key connectors, and operator catalog context.
tags: [database, schema, sqlite, postgres]
status: draft
sources:
  - id: openwiki-source-697296a3dbab6e8c15c6817a
    resource: repo://src/nl2sql_agent/agent/workflow.py
  - id: openwiki-source-84cf171c093164528928cca3
    resource: repo://src/nl2sql_agent/db/database.py
  - id: openwiki-source-34a7a342b749596b14a155e6
    resource: repo://src/nl2sql_agent/db/postgres.py
  - id: openwiki-source-703a079a7daff2fb2b238ca1
    resource: repo://src/nl2sql_agent/db/schema_context.py
  - id: openwiki-source-a4cded8e49aa361ecac7df11
    resource: repo://tests/integration/test_postgres_live.py
  - id: openwiki-source-2e4757d9bdf13a56752d6d7a
    resource: repo://tests/unit/test_decisions.py
generated: { by: "codex", at: "2026-09-27T13:15:44.986Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:35:51.881Z
---

# Database and schema context

The agent depends on `DatabaseBackend`, not on a particular SQL driver. Both implementations provide visible table names, textual schema context, preflight plans and bounded results. SQLite identifies its database by a hash of the resolved path; PostgreSQL hashes the DSN plus schema. These are connection identities, not hashes proving that data values have stayed unchanged.

## Authorized context selection

The agent distinguishes `allowed_tables=None` (all currently available tables) from an explicit empty collection. Unknown allowed names are rejected when constructing an agent. Schema discovery filters authorized tables before ranking.

Both active schema-discovery paths call the shared `rank_tables` function. It tokenizes the question and scores table-name overlaps more heavily than column-name overlaps. For larger schemas it starts from the strongest two tables, searches the authorized foreign-key graph for a connecting path, and includes that path if it fits the table cap. Remaining slots follow rank order. This is deterministic lexical selection, not embedding retrieval or a guarantee of complete context.

The workflow stores selected table names and `schema_incomplete`. It also hashes full schema metadata, catalog, authorization and backend identity into the preparation context, so later approval can detect a changed context.

## Metadata and privacy

SQLite obtains columns and foreign keys through SQLite metadata. PostgreSQL reads visible columns and uses `pg_catalog.pg_constraint` for foreign keys, pairing composite columns by position and checking SELECT privileges on both ends. This avoids requiring write privileges just to discover relationships. Foreign-key lines can reference another authorized table whose detailed columns were not selected.

Both backends can append up to three sample rows per selected table when explicitly requested. The agent defaults sampling on for its managed demo and off for injected databases. Any sampled values and operator-supplied examples are model context: review their sensitivity before using a hosted provider.

## Operator catalog

`SchemaCatalog` loads optional JSON with table descriptions, aliases, metric definitions and example values. Strict validation rejects unknown fields, unknown table names, and example-value columns absent from the schema. Aliases and metric names can add allowed table-name hints to the search question; only selected tables' catalog entries enter the prompt.

Metric definitions are data for generation, not executable authorization. Catalog changes invalidate a prepared context. See the checked-in [catalog example](../../benchmarks/catalog.example.json).

Focused tests cover catalog validation, an intermediate foreign-key connector within the cap, an empty selection, PostgreSQL role handling, and real composite foreign-key pairing.

Continue with [SQL policy](../concepts/sql-safety.md), [query approval](../workflows/query-review.md), or [database selection in the UI](../workflows/cli-streamlit.md).
