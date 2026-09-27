# Reproducible evaluation

`cases.jsonl` contains 120 synthetic cases: 30 HR development cases and 90
held-out-schema cases across retail, inventory, and support. Each schema has
24 result questions, two clarification questions, two unanswerable questions,
and two policy-block requests. Query patterns are reused across schemas;
this suite tests integration and schema transfer, not independent benchmark
generalization. Fixtures intentionally include duplicates, nulls, empty
groups, and missing relationships. Tests execute every golden SQL statement.

The original 15-case demo remains the quick smoke test. Do not tune prompts
against the held-out schemas and then describe their results as untouched.

## Run a bounded comparison

```powershell
uv run python -m nl2sql_agent.evaluation.benchmark --provider ollama --model granite4.2:3b --output outputs/benchmarks/granite-synthetic.json
uv run python -m nl2sql_agent.evaluation.benchmark --provider openai --model gpt-6-luna --output outputs/benchmarks/luna-synthetic.json
```

The default selects the same first 30 HR cases. Use `--limit 120` to include
all schemas. Reports refuse to overwrite existing files and checkpoint every
attempt. They include dataset, database, and Python source hashes, commit,
dirty-tree status, model, settings,
outcome, latency, usage, and SQL, but never credentials, private endpoints,
raw database rows, or reasoning traces. Generated databases stay under outputs.

After diagnosing an interrupted run, use `--offset N` with a new output file to
attempt only the unattempted suffix; `--limit` remains the number of cases to
attempt. The offset is recorded in the manifest. Keep the original failures and
do not replace them with the best result from repeated attempts. A fresh run
still stops after three consecutive provider/interface errors.

All paid calls pass through `outputs/benchmark-budget.db`, with a total US$2
ceiling. Reservations use conservative input estimates and the full output cap;
failures or missing usage retain the reservation. SDK retries are disabled.
Unknown prices block paid runs. This ledger applies to the benchmark driver;
ordinary CLI/UI usage is not subject to this cap. Do not start a new ledger to
bypass a depleted budget. The ledger is a conservative estimate, not an invoice.

GPT-6 Luna uses operator-confirmed endpoint rates. Agnes uses conservative
[list rates](https://wiki.agnes-ai.com/en/docs/agnes-30-flash), excluding any
temporary free promotion. GPT-OSS uses the fixed `openai/gpt-oss-120b:groq`
route and a provider metadata price snapshot. Refresh pricing before a new
comparison. Different providers and reasoning budgets are not equal compute.

## BIRD Mini-Dev

Source: [BIRD-SQL Mini-Dev](https://huggingface.co/datasets/birdsql/bird_mini_dev),
revision `f65faf4ae3b638c1fa6df1d3370c8d92c8366301`. The dataset card specifies
CC BY-SA 4.0. BIRD's questions, evidence, and golden SQL belong to its authors;
they are not relicensed under this repository's MIT license. No BIRD database
files are committed here.

Download the pinned question files:

```powershell
uvx --from huggingface_hub hf download birdsql/bird_mini_dev --repo-type dataset --revision f65faf4ae3b638c1fa6df1d3370c8d92c8366301 --local-dir outputs/bird/source
```

Download the databases from the official package linked on the dataset card
and extract them under `outputs/bird/databases`. The driver locates each
`<db_id>.sqlite` recursively. Missing or duplicate databases are reported as
`benchmark_blocked`; they never silently become an empty accuracy score.

```powershell
uv run python -m nl2sql_agent.evaluation.benchmark --provider openai --model gpt-6-luna --suite bird --limit 20 --output outputs/benchmarks/luna-bird.json
```

`select_bird(..., size=50)` selects 15 simple, 25 moderate, and 10 challenging
questions in stable question-ID order. The common live subset uses 20
questions (6 simple, 10 moderate, 4 challenging). Evidence is included in the
question; database values are not sampled into prompts. This is a bounded
subset evaluation, not the official full BIRD leaderboard protocol.

[The checked-in selection](bird-selection.json) lists all 50 question IDs and
the common 20 live IDs. Selection is difficulty-stratified, not domain-stratified:
the 20-case live subset is entirely `california_schools`. Do not generalize its
scores to all BIRD databases.

## Operator-authored schema context

Set `NL2SQL_SCHEMA_CATALOG_PATH` to a JSON catalog matching your database.
[catalog.example.json](catalog.example.json) demonstrates aliases, descriptions,
and a named metric for the synthetic HR fixture. Adapt it before use with a
different schema. Catalog table names and example-value column names are
validated against visible metadata; unknown references fail closed. Metric
definitions are prompt context, never executable authorization.

## Optional local judge

```powershell
uv run python -m nl2sql_agent.evaluation.judge outputs/benchmarks/luna-full.json --output outputs/benchmarks/guardian.json
```

Granite Guardian 4.1 8B runs separately, with thinking disabled and a strict
`<score>yes</score>` / `<score>no</score>` parser. Missing or malformed scores are
`judge_failure`, never a passing score. The criterion checks read-only SQL form,
not answer correctness. The repository owner explicitly reviewed and confirmed
the four authored labels on 2026-09-27. This is a small smoke calibration, not
a human study or evidence that the judge can assess semantic correctness.
Guardian cannot authorize SQL and is rejected as a generator model.

## Reading results

Result accuracy requires successful execution and matching rows. Unordered
comparison preserves duplicates and allows small numeric tolerances. Policy
tests require an actual deterministic block; a model refusal is reported as
unanswerable, not credited as a validator success. Provider errors and invalid
decisions remain visible. Absent categories are null rather than 100%.

Truncated actual or reference rows cannot pass a full-result comparison. At the
default 1,000-row cap, some BIRD questions are intentionally counted as not
passed rather than credited for a matching prefix. See the published scoring
correction for affected development runs.

Keep failed and interrupted manifests beside completed runs. Compare identical
case IDs and report the attempted denominator. Never infer a model winner from
a partial run or claim production readiness from fixture accuracy.
