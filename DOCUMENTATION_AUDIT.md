# Documentation audit and verification

This audit covers developer documentation and Python API explanation in the
current working tree. It is not a security audit, live-provider evaluation,
or release receipt. Existing uncommitted documentation work was preserved.

## Findings addressed

| Finding | Change |
| --- | --- |
| New contributors had to assemble setup and reading order from several guides | Added `ONBOARDING.md` with an offline first workflow and setup troubleshooting. |
| Architecture described components but did not provide one change-to-test map | Added `DEVELOPER_GUIDE.md` with ownership, contracts and extension guidance. |
| Contribution guidance lacked a complete operational checklist | Added `CONTRIBUTOR_RUNBOOK.md` with baseline checks, verification, live-test limits and review preparation. |
| The handbook favored source reading over runnable lessons | Added `ZERO_TO_MASTERY_TUTORIAL.md` as a hands-on companion, with two offline examples, checkpoints and a capstone. |
| High-level workflow docstrings omitted argument and failure semantics | Expanded the five run/preparation/execution method docstrings, including partial updates, lazy iteration and possible propagated errors. |
| Truncation documentation omitted non-positive caps and oversized suffixes | Expanded `truncate()` documentation and added executable examples. |
| Retry setting metadata described extra rewrites instead of writer attempts | Corrected the field description, including the zero-retry boundary, without changing validation or execution. |

## Python documentation coverage

An AST inventory of `src/nl2sql_agent/**/*.py` found:

| Public declaration kind | With a docstring | Total |
| --- | ---: | ---: |
| Classes | 40 | 40 |
| Functions and methods | 139 | 139 |
| Combined | 179 | 179 |

The count includes public declarations at module and class scope. It excludes
underscore-prefixed names, constructors, nested local helpers, imported aliases
and generated dataclass methods. This is docstring-presence coverage, not a
score for parameter completeness or example quality. Public declarations already had docstrings. This pass expanded selected
contract descriptions without changing the count. Type annotations supply parameter and return types;
the prose explains their meaning and error behavior.

The project uses a CLI and Streamlit, so no REST API specification or new
documentation-site dependency was added.

## Checks run

- `uv run pytest tests/unit -q`: 352 passed.
- `uv run pytest --doctest-modules src/nl2sql_agent/utils/text.py -q`: one doctest
  item passed, containing three truncation examples.
- Both complete Python blocks in the new tutorial executed successfully against
  temporary data and a fake model. The first run exposed an omitted LIMIT notice;
  the example was corrected and rerun.
- Tutorial clarification/stale-permission command: two tests passed.
- Tutorial evaluation/benchmark command: 17 tests passed.
- Ruff lint and ty passed after the Python documentation edits.

## Reader review

The follow-up pass added a task-based [documentation index](docs/README.md)
and a capstone reference solution. All three tutorial Python blocks were
executed: the two standalone lessons and the capstone function with a temporary
seeded database. The capstone was invoked directly for this check, not added
to the repository's pytest suite. Application code was unchanged in this pass.

A structured self-review checked whether a new contributor could identify the
first offline command, expected output, source owner, approval boundary, live-test
prerequisites and publication step using only the new guides. The tutorial's
expected-output mismatch was corrected. This was not an independent reader test.

## Limits

Live inference and PostgreSQL were not run for this documentation change. The
full CI matrix, dependency audit, build and installed-wheel smoke remain runbook
instructions, not new verification receipts. Existing benchmark metrics, legal
text and diagram artifacts retain their original meaning and provenance.

The study handbook provides the detailed code walkthrough, and the tutorial
provides runnable exercises. Both cover selected workflows; neither establishes
production readiness or proficiency in every subsystem.
