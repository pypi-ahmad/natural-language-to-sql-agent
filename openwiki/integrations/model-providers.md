---
type: Integration
title: Model providers and cost controls
description: Runtime provider configuration, discovery, model contracts, pricing estimates, and the benchmark-only persistent budget.
tags: [models, providers, configuration, costs]
status: draft
sources:
  - id: openwiki-source-b527ee101f959598a6526f76
    resource: repo://src/nl2sql_agent/cli.py
  - id: openwiki-source-0a87f5e71f7477419b5f3d3a
    resource: repo://src/nl2sql_agent/config/settings.py
  - id: openwiki-source-ca8411aa2a237c877029e40b
    resource: repo://src/nl2sql_agent/evaluation/benchmark.py
  - id: openwiki-source-4bbb8b2652c448cccd68e8dc
    resource: repo://src/nl2sql_agent/llm/budget.py
  - id: openwiki-source-2467c57015054cd0559a03aa
    resource: repo://src/nl2sql_agent/llm/factory.py
  - id: openwiki-source-84444bf833dd0daf8d3cec66
    resource: repo://src/nl2sql_agent/llm/pricing.py
  - id: openwiki-source-0db687b727f9e03b63c59e4f
    resource: repo://tests/unit/test_budget.py
generated: { by: "codex", at: "2026-09-27T13:15:44.986Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:31:57.770Z
---

# Model providers and cost controls

`Settings` resolves programmatic values, environment variables, a UTF-8 `.env` file, then defaults. Most fields use the `NL2SQL_` prefix; credentials have explicit provider aliases. Configure credentials outside tracked files. The CLI's config output masks configured provider keys and the PostgreSQL DSN.

The model factory supports Ollama, OpenAI, Hugging Face, Anthropic, Gemini, xAI and Agnes. Hosted provider model lists are repository choices, not live service availability guarantees. Most hosted providers require an approved identifier; Hugging Face accepts a namespace/model with optional routing suffix. Ollama accepts local identifiers but rejects Granite Guardian as a generator.

## Adapter differences

| Adapter | Current repository behavior |
| --- | --- |
| Ollama | ChatOllama with context, output cap, keep-alive and request timeout; no explicit thinking override |
| OpenAI / Hugging Face / xAI | Shared OpenAI-compatible Responses API configuration, medium reasoning and SDK retries disabled |
| Agnes | Chat Completions configuration, thinking enabled in the extra body and SDK retries disabled |
| Gemini | Medium thinking level |
| Anthropic | Adaptive thinking with medium effort |

These are implementation contracts, not evidence that every upstream endpoint supports every setting. Provider/interface failures remain explicit agent outcomes. Do not assume equal compute across providers.

Hosted discovery returns curated choices without a network request. Ollama discovery queries the server and filters out the Guardian model; connection failures ultimately return an empty list. Remote Ollama URLs require HTTPS; credentials, query strings and fragments in the URL are rejected.

## Estimates versus enforcement

Pricing rules are selected by model and effective date. Overlapping rules fail rather than silently choosing one. Cost calculations use Decimal arithmetic and per-call usage, including request mode, cache reads/writes and long-context rates when configured. Missing mode or long-context prices raise a pricing-unavailable error. These values are estimates, not provider invoices.

The benchmark driver separately wraps supported paid models in `BudgetedModel`. Its SQLite ledger atomically reserves cost before sending a request and persists the ceiling across restarts. An existing ledger's ceiling cannot be changed. Reported valid usage reconciles reservations; failed calls or missing usage retain the conservative reservation. Unexpected overruns are recorded and block further spending.

That hard ceiling applies to the benchmark wrapper, not ordinary CLI/UI model calls. UI budget alerts and stored cost estimates must not be described as equivalent enforcement. Do not start a new ledger to evade a depleted benchmark budget.

Tests mock adapter construction and discovery and verify persisted reservations, failed-call accounting, reconciliation and blocked requests. They do not prove hosted availability.

Related: [benchmark protocol](../evaluation/benchmarks.md), [local records](../operations/persistence-audit.md), and [CLI/UI workflows](../workflows/cli-streamlit.md).
