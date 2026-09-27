# Documentation

## Start here

1. [Onboarding](../ONBOARDING.md): install the checkout, run offline checks and
   learn where to make a first contribution.
2. [Hands-on tutorial](../ZERO_TO_MASTERY_TUTORIAL.md): prepare and execute a
   query with a fake model, inspect failures and complete a regression exercise.
3. [Study handbook](../ZERO_TO_HERO_STUDY_HANDBOOK.md): work through the source,
   data contracts, configuration and exercises. A [PDF](../ZERO_TO_HERO_STUDY_HANDBOOK.pdf)
   is also available.

## Complete a task

| Task | Guide |
| --- | --- |
| Find the module and tests responsible for a change | [Developer guide](../DEVELOPER_GUIDE.md) |
| Reproduce, implement, verify and prepare a contribution | [Contributor runbook](../CONTRIBUTOR_RUNBOOK.md) |
| Check contribution expectations | [Contributing](../CONTRIBUTING.md) |
| Configure or run the application | [README](../README.md) |
| Diagnose setup problems | [Onboarding troubleshooting](../ONBOARDING.md#if-setup-fails) |
| Reproduce a model evaluation | [Benchmark protocol](../benchmarks/README.md) |

## Look up a contract

- [Python and CLI API reference](../API_REFERENCE.md)
- [Architecture and extension boundaries](../ARCHITECTURE.md)
- [Security and data handling](../SECURITY.md)
- [Dataset definitions](../DATASET.md)
- [Source-grounded OpenWiki](../openwiki/quickstart.md)

Python signatures and docstrings live with the implementation under
`src/nl2sql_agent/`. The [documentation audit](../DOCUMENTATION_AUDIT.md) defines
the public-symbol coverage count and records which examples were run.

## Interpret historical evidence

[Benchmark results](../benchmarks/results/README.md), [release notes](../RELEASE_NOTES.md)
and [migration history](../MIGRATION_GUIDE.md) describe their stated versions
and runs. They do not replace current source or prove that a live service works
today. [Diagram receipts](../diagrams/README.md) retain their visual-review limits.

## Maintain these pages

Keep runnable examples with tutorials, task procedures in runbooks, signatures
in the API reference and design explanations in the architecture guide. Link
between them when a topic overlaps. Preserve commands, legal text and historical
metrics during prose edits. Update OpenWiki through its page workflow rather
than editing generated Claims or provenance.
