# Datasets

The application includes a demo database and packaged smoke cases. The
repository also includes a larger synthetic suite and a pinned BIRD workflow.

## Extended benchmark data

See [benchmarks/README.md](benchmarks/README.md) for 120 synthetic cases across
four schemas, source licensing, pinned BIRD selection, and live-run limits.
The synthetic schemas share query patterns; they are not independent evidence
of generalization. Every golden query is checked by the offline suite.

Evaluation v2 rejects empty corpora and duplicate IDs, requires explicit
execution for result matches, and treats absent categories as null metrics.
Model refusals, policy blocks, and provider failures are distinct outcomes.

## Demo SQLite database

The packaged evaluation corpus and reference queries are SQLite-only. The
optional PostgreSQL runtime backend is exercised separately and does not alter
these deterministic fixtures.

`Database("company.db").ensure_schema(seed=True)` creates `company.db` with four departments
and ten employees from `src/nl2sql_agent/db/seed.py`. It is the default data
source for the UI, CLI, examples, tests, and evaluation references.

## NL2SQL smoke-evaluation corpus

`src/nl2sql_agent/evaluation/data/demo.jsonl` is packaged with every wheel and
contains 15 cases: 12 expected-result questions and three
malicious requests that must be blocked. Result cases are scored by executing
their reference SQL and comparing returned values, not by requiring one exact
SQL string. Provider refusal is not credited as a deterministic policy block.
Truncated actual or reference rows cannot establish a complete result match.

Each JSONL record contains:

- `id`: stable case identifier.
- `question`: natural-language model input.
- `expected_outcome`: `result` or `blocked`.
- `reference_sql`: required for result cases and executed read-only.
- `ordered`: whether result row order is significant.
- `tags`: filtering and reporting metadata.

Run the corpus with:

```bash
uv run nl2sql-agent eval
uv run nl2sql-agent eval --model qwen3.5:4b --min-pass-rate 0.9
```

Reports are written under `outputs/evals/` unless `--output` is supplied. They
include accuracy, safety, execution rate, latency, retries, token counts, an
optional caller-supplied cost estimate, and a database-integrity check.

This small corpus verifies the packaged demo path. It does not measure
cross-domain text-to-SQL performance, large-schema retrieval, or production
accuracy. Do not compare its pass rate with BIRD, Spider, or another external
benchmark.
