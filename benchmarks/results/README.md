# Live evaluation evidence — 2026-09-27

These are development runs on the repository owner's Windows laptop, not a
leaderboard submission or a frozen model-ranking study. JSON manifests retain
case IDs, outcomes, SQL, usage, settings, and failed attempts. No raw database
rows, credentials, private endpoints, or reasoning traces are included.

## Common cases

Each generator is scheduled on the same 30 synthetic HR case IDs and the same
20 BIRD Mini-Dev IDs. The synthetic subset contains 24 result questions, two
clarification questions, two unanswerable questions, and two policy requests.
The BIRD subset is entirely `california_schools`.

| Generator | Synthetic result matches | All synthetic cases passed | BIRD result matches |
| --- | --- | --- | --- |
| GPT-6 Luna | 22/24 | 26/30 | 3/20 |
| Agnes 3.0 Flash | 9/24 | 9/30 | 8/20 |
| GPT-OSS 120B, fixed Groq route | 9/24 | 9/30 | 0/20 |
| Granite 4.2 3B | 22/24 | 23/30 | 0/20 |
| Qwen 3.5 9B | Run in progress | Run in progress | Run in progress |

Result matching requires explicit execution plus matching rows, not merely
the presence of SQL. All-case totals also score the non-result categories.
Provider/interface errors count as failed attempts rather than disappearing
from the denominator. There is no inferred winner from this table.

Important observations:

- Agnes and GPT-OSS each had 21 provider/interface failures in their 30-case
  synthetic runs. GPT-OSS had 20 such failures in BIRD. A later one-case probe
  succeeded for Agnes and failed for GPT-OSS. The retained error category does
  not establish the provider's root cause.
- Luna executed ten BIRD cases, requested clarification on nine, and had one
  generation failure. Three executed results matched the gold rows.
- Agnes executed fifteen BIRD cases, requested clarification on one, and had
  four generation failures. Eight executed results matched.
- Granite's BIRD run had twenty generation failures. Each case consumed 3,072
  output tokens over three capped attempts. This is a failure of this bounded
  configuration, not a measurement of unconstrained model capability.
- Luna refused both write requests as unanswerable. No SQL ran, but those
  refusals are not credited as deterministic policy blocks. The stricter metric
  therefore reports zero policy-block successes for that run.

## Ablation

GPT-6 Luna ran the same first twelve HR cases in four configurations:

| Configuration | Attempts allowed | Detailed schema cap | Result matches |
| --- | --- | --- | --- |
| Single pass | 1 | 100 | 12/12 |
| Retries | 3 | 100 | 12/12 |
| Schema selection | 1 | 8 | 12/12 |
| Full | 3 | 8 | 12/12 |

These easy cases show no measured accuracy benefit. HR has only two tables,
so both schema caps include the full schema; this ablation does not establish
retrieval quality on large schemas. Do not claim improvement from these scores.

## Local execution and judge

[Hardware metadata](../hardware.json) records model digests, quantization,
context size, and observed GPU allocation. Local models run sequentially.
The output cap is 1,024 tokens per generator request and the local context is
4,096 tokens. Provider reasoning behavior and wall-clock budgets differ; this
is not an equal-compute comparison.

Guardian uses a separate 32-token yes/no scoring path with thinking disabled.
Its four calibration labels were explicitly reviewed by the repository owner.
It scores read-only SQL form, not semantic correctness, and never gates query
execution. Its live report will be attached after the generator queue finishes.

## Provenance and retained attempts

The main synthetic files are `luna-synthetic.json`, `agnes-synthetic.json`,
`gpt-oss-synthetic-v2.json`, and `granite-synthetic-v2.json`. Matching `*-bird.json`
files contain BIRD attempts. Qwen is still running.

`granite-synthetic.json` (6/30) and `gpt-oss-synthetic.json` (19/30) are interrupted
earlier attempts, not the main comparison. They are retained rather than
overwritten. The two `*-availability-probe.json` files are single-case diagnostic
probes, not replacement accuracy runs.

Early manifests were produced while code and fixture metadata were being
developed. They record a dirty worktree and some dataset hashes differ. The
later driver adds actual Python-source and database-file hashes. Earlier
reports cannot be reconstructed exactly from their Git commit alone; none has
been rewritten to claim a clean frozen revision.

All paid calls, including probes and retries, use one persistent ledger with a
US$2 ceiling. The final conservative ledger total will be recorded after the
queue finishes. It includes unresolved reservations and is not a provider invoice.

BIRD source and licensing attribution, selection IDs, and reproduction commands
are in the [benchmark protocol](../README.md). Questions and databases remain
under BIRD's CC BY-SA 4.0 terms, not this project's MIT license.
