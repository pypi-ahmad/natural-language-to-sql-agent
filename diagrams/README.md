# Interactive diagrams

These five views reflect the current agent workflow, UI persistence, and SQL
approval boundaries. Open the standalone HTML locally; each includes theme
switching, zoom, search, and relationship tracing without a web service.

| View | Source | Desktop containment |
| --- | --- | --- |
| [Architecture](nl2sql-architecture.html) | [JSON](nl2sql-architecture.json) | Pass |
| [SQL workflow](nl2sql-workflow.html) | [JSON](nl2sql-workflow.json) | Fail: vertical overflow |
| [Data flow](nl2sql-dataflow.html) | [JSON](nl2sql-dataflow.json) | Pass |
| [Approval sequence](nl2sql-sequence.html) | [JSON](nl2sql-sequence.json) | Pass |
| [SQL lifecycle](nl2sql-lifecycle.html) | [JSON](nl2sql-lifecycle.json) | Pass |

The root [architecture diagram](../architecture-diagram.html) and its
[specification](../architecture-diagram.json) are byte-identical compatibility
copies of the architecture view above.

## Validation and visual review

All six HTML artifacts pass Archify's nine showcase structural checks, with zero
composition errors and warnings. [Delivery receipts](receipts.json) record the
exact specification and HTML SHA-256 values and byte counts.

The adjacent `*.visual-check.json` receipts measure 1440×900, 1600×1000,
1920×1080, and 2048×1320. All 20 screenshots were inspected: light and dark at
1440×900 and 2048×1320 for each of the five views. Architecture, data flow,
sequence, and lifecycle pass containment and visual review. The byte-identical
root architecture copy shares the architecture view's evidence. Automated
receipts retain their separate `visualReview: "pending"` field; the inspection
results here are recorded separately.

The workflow remains readable with page scrolling, but fails first-screen
containment at every checked size. At 1440×900 its document height is 1212px;
at 2048×1320 it is 1362px. A two-lane attempt introduced overlaps; restoring
four lanes with a shorter viewBox passed structural checks but still overflowed.
The bounded layout-repair pass stopped there. No content was clipped or hidden
to disguise the failure.

## What the views show

- The agent calls the SQL validator and owns database preflight and execution.
- The UI owns session persistence. Saved answer text can contain returned values,
  even though structured payloads exclude raw rows and schemas.
- The approval sequence checks current context before validating edited SQL,
  then preflights and executes once. Storage writes are synchronous.
- Workflow and lifecycle focus on the review-first SQL branch. Clarification,
  unanswerable, provider-error, and policy-block outcomes can end without
  execution. The CLI skips the UI approval step.
- Preparation may retry recoverable errors. Approved execution does not ask the
  writer for replacement SQL.

Source anchors: [agent workflow](../src/nl2sql_agent/agent/workflow.py),
[Streamlit UI](../src/nl2sql_agent/ui/streamlit_app.py),
[persistence](../src/nl2sql_agent/persistence.py), and the
[architecture guide](../ARCHITECTURE.md).

## Regeneration

Use the installed Archify skill's `validate` and `deliver` commands with
`--quality showcase`, followed by `visual-check`. Inspect the screenshots and
refresh the delivery receipts after any specification change. Keep the root
architecture copy synchronized. Git preserves these artifacts' exact bytes.
