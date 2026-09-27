---
type: Evaluation
title: Evaluation and benchmark evidence
description: Outcome-aware result scoring, reproducible benchmark controls, and limits of the retained development evidence.
tags: [evaluation, benchmarks, provenance]
status: draft
sources:
  - id: openwiki-source-af5b2fc4a0830cd3de40e530
    resource: repo://benchmarks/README.md
  - id: openwiki-source-37eba630a683bc24ae20041a
    resource: repo://benchmarks/results/README.md
  - id: openwiki-source-34af9c218193c13d9e0fb66a
    resource: repo://benchmarks/results/scoring-corrections.json
  - id: openwiki-source-ca8411aa2a237c877029e40b
    resource: repo://src/nl2sql_agent/evaluation/benchmark.py
  - id: openwiki-source-6f56e44b33360c71f6728eb5
    resource: repo://src/nl2sql_agent/evaluation/judge.py
  - id: openwiki-source-ddb04a5dd908697dd0391cb0
    resource: repo://src/nl2sql_agent/evaluation/runner.py
  - id: openwiki-source-77c9b76448990d4fa474c4a3
    resource: repo://tests/unit/test_benchmark.py
  - id: openwiki-source-6edd9ceda5337c7584127dd3
    resource: repo://tests/unit/test_evaluation.py
  - id: openwiki-source-95f45e1da718797cde961d93
    resource: repo://tests/unit/test_judge.py
generated: { by: "codex", at: "2026-09-27T13:38:19.239Z" }
verified:
  - by: openwiki/0.6.0
    at: 2026-09-27T13:38:19.239Z
---

# Evaluation and benchmark evidence

The evaluator scores observable outcomes rather than SQL text similarity. For a result case, the agent must explicitly report successful execution, return matching rows, and have no error or truncation. A missing execution flag cannot pass by coincidentally matching an empty reference.

Policy cases require an actual `policy_blocked` outcome with neither safety approval nor execution. Provider failures and model refusals do not receive policy-block credit. Clarification and unanswerable cases require their respective outcome without execution or error. Missing categories produce null rates.

## Row equality and completeness

Ordered cases compare corresponding rows. Unordered cases use multiset matching that preserves duplicates; numeric values use relative and absolute tolerances of 1e-6. The evaluator hashes its SQLite database before and after the suite.

Truncation on either the reference or actual result prevents a full-result pass. The retained [scoring correction](../../benchmarks/results/scoring-corrections.json) retracts three historical BIRD passes without rewriting the original reports. Four reference cases exceed the configured 1,000-row cap; they remain in the attempted denominator.

## Corpora and driver

The synthetic corpus contains 120 cases across four domains: 30 HR development cases and 90 held-out-schema cases. Reused query patterns limit claims about independent generalization. Fixture tests execute golden result queries and verify referenced tables.

The driver defaults to the first 30 synthetic cases. BIRD selection is stable by question ID and difficulty quotas. The driver uses the common 20-question subset; the selector also supports a 50-question selection. The published 20-question subset uses one database, not the full BIRD benchmark. Consult the [protocol](../../benchmarks/README.md) for pinned downloads and BIRD licensing.

A run refuses to overwrite an existing output, checkpoints attempted cases, and records settings, commit/dirty state, source/data/database hashes, usage and outcomes. Missing or duplicate BIRD databases become explicit blocked benchmark cases. Three consecutive provider errors or budget exhaustion stop the loop. `completed_at` is updated at checkpoints, so inspect planned versus attempted counts and stop reason before calling a run complete.

`--offset N --limit M` selects an unattempted suffix into a new report. Retain original failures and combine only disjoint IDs. Paid models are wrapped by the persistent budget ledger; unknown configured prices block paid runs.

## Judge and historical evidence

Granite Guardian runs separately with thinking disabled, a 32-token output cap, and a strict yes/no score parser. Exceptions and malformed scores become `judge_failure`. The four SQL-form labels were reviewed by the owner; that review covers SQL form only. It does not verify this wiki or establish semantic SQL correctness.

The [development results](../../benchmarks/results/README.md) preserve provider failures, Qwen's separate continuation, dirty-tree provenance limitations, and non-isolated timings. They are not leaderboard or production-readiness evidence. Documentation updates do not rerun model comparisons.

See [provider costs](../integrations/model-providers.md), [query outcomes](../workflows/query-review.md), and [verification commands](../testing/verification.md).
