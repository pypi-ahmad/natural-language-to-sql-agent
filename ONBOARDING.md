# Developer onboarding

Start here if you can read basic Python but have not worked on this repository.
You do not need an API key, model download, or PostgreSQL server for the first
exercise. Run commands from the repository root in PowerShell.

## 1. Prepare the checkout

Install Git and uv if they are not already available. Clone the repository using
the commands in [README](README.md#3-quick-start), then run:

```powershell
uv sync --locked --all-groups
uv run python --version
uv run nl2sql-agent --help
uv run pytest tests/unit -q
```

The project supports Python `>=3.12.10,<3.13`. The help command lists the CLI
without running a model. Unit tests use temporary databases and mock models.
A passing unit suite gives you an offline baseline. Provider availability and
PostgreSQL configuration require separate checks.

Keep credentials out of the checkout. A local `.env` and process environment
can affect settings. Do not paste `config` output into an issue without checking
paths and endpoints, even though the command masks credentials.

## 2. Run the first workflow

Complete the [offline tutorial](ZERO_TO_MASTERY_TUTORIAL.md). Its first script
creates a temporary demo database, prepares a fixed model response, then runs
the approved SQL. The expected employee count is 10. It does not make network
requests or write saved sessions.

Before continuing, explain why preparation has `executed=False` and why the
model is called once even though an answer is rendered after execution.

## 3. Learn the boundaries

Read these in order:

1. [Developer guide](DEVELOPER_GUIDE.md): module ownership and extension work.
2. [API reference](API_REFERENCE.md): interfaces and outcome fields.
3. [Security policy](SECURITY.md): read-only controls and persistence privacy.
4. [Study handbook](ZERO_TO_HERO_STUDY_HANDBOOK.md): source walkthroughs and exercises.

Keep `tests/unit/test_decisions.py` open alongside `agent/workflow.py`.
Follow one clarification test and one stale-preparation test from input to
assertion. A returned SQL string alone does not mean execution succeeded.

## 4. Make a first contribution

Choose an existing issue or agree on a small change with the maintainer. Follow
the [contributor runbook](CONTRIBUTOR_RUNBOOK.md), add a focused regression test,
and record the exact checks you ran. Do not change benchmark results to make a
documentation or test change look like a new evaluation.

Before working independently, practice locating the responsible module and
reproducing a problem offline. Explain the expected outcome and identify a test
that would catch a regression.

## If setup fails

| Symptom | Next check |
| --- | --- |
| `uv` is not recognized | Confirm uv is installed and available in this terminal's PATH; reopen the terminal after installation. |
| Python version is outside the supported range | Run the locked sync from the checkout; do not reuse an unrelated environment. |
| Import failure | Confirm the working directory and rerun the locked sync. Use `uv run`, not a global Python interpreter. |
| Settings validation fails | Review local `.env` and process overrides without sharing their values. The tutorial disables `.env` loading and sets its relevant settings explicitly. |
| A unit test fails | Save the command and traceback, rerun that test alone, and compare against your starting baseline. |
| A live-service test skips | Check its documented opt-in conditions. Skipped tests are not provider verification. |

Live inference is a later, optional step. Follow the README provider setup only
after reviewing what prompt context leaves the machine and what may remain on disk.
