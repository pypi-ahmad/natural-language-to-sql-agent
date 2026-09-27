# Implementation and verification

## What changed

- Explicit execution outcomes separate SQL preparation, execution, clarification,
  refusal, policy blocks, generation failures, and provider failures.
- Approval is bound to the database, schema, allowlist, policy, and catalog.
  Edited SQL is validated again immediately before execution.
- Shared schema ranking includes foreign-key connectors. An empty allowlist
  stays empty. PostgreSQL discovery works with a SELECT-only role and pairs
  composite foreign-key columns correctly.
- CLI and Streamlit support up to two clarification replies. Successful answers
  are rendered from returned cells, with separate query-limit, fetch-limit, and
  preview notices. No second model call invents a narrative over the rows.
- The restored test suite covers evaluator false positives, authorization,
  approval context, clarification, provider configuration, and budget accounting.
  Truncated result prefixes cannot pass as complete results; the evidence report
  preserves and corrects three earlier false-positive BIRD scores explicitly.
- A 120-case synthetic corpus, pinned BIRD selection, persistent US$2 ledger,
  model comparisons, ablations, and a separate local Guardian judge provide
  inspectable evaluation artifacts.
- Documentation follows the current implementation. Five interactive diagrams
  include source specifications and validation receipts; the handbook PDF was
  regenerated from Markdown.

## Verification

The latest full CI suite passed 352 tests on both Windows and Linux, with six
opt-in integration tests skipped, at 85.34% coverage. A separate PostgreSQL 17
job passed all three real integration tests. The local full suite passed 349
tests before the final truncation and continuation regressions were added;
their focused suites also passed. The 80% threshold was not lowered. The existing
coverage configuration excludes the Streamlit entrypoint and page module;
separate AppTest cases exercise the UI, including
clarification through explicit query approval and execution.

Ruff, ty, reviewed secret checks, dependency audit, source/wheel builds, an
isolated installed-wheel CLI smoke, and local Markdown file-link checks passed.
CI also exercises PostgreSQL 17 with an unprivileged reader role. The tests
verify read-only execution, FK discovery, and composite key pairing.

GitHub review: [PR #7](https://github.com/pypi-ahmad/natural-language-to-sql-agent/pull/7).
Nothing has been merged, tagged, or deployed by this workflow.

All five generators completed coverage of the common 30 synthetic and 20 BIRD
case IDs. Qwen required a separate continuation for eight previously unattempted
synthetic IDs; its original failures remain in the totals. The
[case-level results](benchmarks/results/README.md) include corrected truncated-row
scores, provider failures, and provenance limits. The conservative paid-call
ledger total is US$0.103428525 against the US$2 ceiling. Guardian matched the four
reviewed calibration labels and scored twelve recorded SQL samples; this is a
narrow SQL-form smoke check.

## Deliberate limits

- SQL-only model output remains a compatibility path; structured JSON decisions
  are preferred and validated when returned.
- Answer rendering is deterministic. There is no claim-validated free-form
  model narrative layer.
- Live synthetic comparisons use the 30 HR development cases, not the 90
  held-out-schema cases. All 120 cases are validated; their 96 golden result
  queries execute in fixture tests.
- The live BIRD subset is 20 questions from one database. The pinned 50-case
  selection spans three databases; it is not a full leaderboard evaluation.
- Early development manifests record the Git commit and dirty-tree status but
  lack exact source/database hashes. Later runs include these hashes. Earlier
  evidence is retained rather than rewritten to imply cleaner provenance.
- The four Guardian calibration labels were explicitly human-reviewed by the
  repository owner. They test only a narrow SQL-form criterion, not semantic
  correctness, robustness, or a representative human study.
- Archify's workflow view passes structural checks but still overflows desktop
  viewports. Its bounded repair limit stopped further layout changes. See the
  [diagram receipt](diagrams/README.md); the remaining diagrams pass containment.

## Resume positioning

This project now provides concrete engineering work to discuss: read-only SQL
execution, context-bound approval, clarification, cross-platform CI, PostgreSQL
integration, and reproducible failure reporting. Describe it as an evaluated
NL-to-SQL application, not a production-proven system or a state-of-the-art SQL
model. Report exact benchmark subsets and denominators with any accuracy claim.

## Skills applied

Implementation used the requested investigation, minimal-change, and Python
tooling guidance: `using-agent-skills`, `investigate-first`, `surgical-patch`,
`karpathy-guidelines`, `ponytail`, `ponytail:ponytail`, `modern-python:modern-python`,
`modern-uv`, `developing-with-streamlit`, and `user-env-variable`.

Model and dataset work used `hf-cli`, `huggingface-best`, and
`huggingface-datasets`. Documentation used `doc-sync` in code-to-doc mode,
`doc-coauthoring`, `documentation-expert`, `documentation-writer`,
`code-documenter`, `technical-writer`, `humanizer:humanizer`, and `archify`.
`caveman` guided concise updates; authenticated GitHub work used `gh-cli:gh-cli`.
`i-have-adhd:i-have-adhd` was unavailable; communication stayed short and explicit.
