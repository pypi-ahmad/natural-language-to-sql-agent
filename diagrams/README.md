# Architecture diagrams

Open the standalone HTML files locally. Each includes theme switching, zoom,
search, and relationship tracing without a web service.

| View | Source | Desktop containment |
| --- | --- | --- |
| [Architecture](nl2sql-architecture.html) | [JSON](nl2sql-architecture.json) | Pass |
| [SQL workflow](nl2sql-workflow.html) | [JSON](nl2sql-workflow.json) | **Fail: vertical overflow** |
| [Data flow](nl2sql-dataflow.html) | [JSON](nl2sql-dataflow.json) | Pass |
| [Approval sequence](nl2sql-sequence.html) | [JSON](nl2sql-sequence.json) | Pass |
| [Run lifecycle](nl2sql-lifecycle.html) | [JSON](nl2sql-lifecycle.json) | Pass |

All five pass Archify's nine structural checks with zero composition errors
and warnings. [Receipts](receipts.json) record the exact specification and HTML
SHA-256 values. Structural validation is not a visual-quality guarantee.

The adjacent `*.visual-check.json` receipts measure 1440×900, 1600×1000,
1920×1080, and 2048×1320. Contact sheets and light/dark screenshots are included.
The data-flow screenshots were inspected at 1440×900 light and 2048×1320 dark;
sequence and lifecycle were inspected at 2048×1320 in both themes. Automated
receipts correctly keep their separate `visualReview` field as `pending`.

The workflow remains usable with page scrolling, but does not meet Archify's
first-screen containment requirement. Two attempted geometry corrections
introduced readability failures. The last structurally valid version was
retained under the skill's bounded-repair rule; this is an unresolved layout
limitation, not a passed visual review.

The workflow and data-flow views focus on the SQL path. Clarification,
unanswerable, provider-error, and policy-block outcomes can end without SQL
execution; see the lifecycle view and [architecture guide](../ARCHITECTURE.md).

To regenerate, use the installed Archify skill's `deliver` command, then
`visual-check`. Refresh the receipts after any specification change. Git
preserves these artifacts' bytes to keep their hashes stable across platforms.
