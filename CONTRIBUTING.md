# Contributing to NL2SQL Agent

You can contribute bug reports, feature suggestions, code, or documentation to
this free, community-driven project.

## Before you start

For anything beyond a trivial fix, open an issue first (or comment on an existing one) describing what you want to change and why. This avoids duplicate work and lets us agree on the approach before you invest time in it.

Do not include real API keys, database credentials, connection strings, private schemas, or production data in an issue or pull request.

## Development setup

For a first checkout, follow [onboarding](ONBOARDING.md). For an existing
checkout, use the [contributor runbook](CONTRIBUTOR_RUNBOOK.md) from baseline
checks through review. The [developer guide](DEVELOPER_GUIDE.md) maps changes
to implementation owners and tests.

```bash
git clone https://github.com/pypi-ahmad/natural-language-to-sql-agent.git
cd natural-language-to-sql-agent
uv sync --locked --all-groups
```

This installs the pinned Python (3.12.10) and every development dependency group.

## Making a change

1. Fork and clone the repository.
2. Create a focused branch from `main`.
3. Make your change and add focused regression tests when behavior changes.
   Tests use fake models by default; live services require explicit opt-in.
4. Run the checks (see below) and fix anything they flag.
5. Update `README.md`, `ARCHITECTURE.md`, or other docs when your change affects public behavior or configuration.
6. Open a pull request with a clear description of the problem, the fix, and how you verified it.

## Required checks

```bash
uv run ruff check src tests
uv run pytest -q --cov=nl2sql_agent
uv run ty check src
uv audit --locked
uv build
```

Then run the same gate CI runs, which also covers formatting and secret scanning:

```bash
uv run prek run --all-files
```

CI runs the suite on Windows and Linux, requires 80% coverage, checks a real
PostgreSQL 17 fixture, and runs `nl2sql-agent --help` from an isolated wheel.

Coverage excludes the Streamlit app and page modules; AppTest separately checks
their behavior. Ollama tests require `NL2SQL_LIVE_TESTS=1`, a reachable server
and the selected installed model. PostgreSQL tests require
`NL2SQL_TEST_POSTGRES_ADMIN_DSN` pointing to a fresh disposable `nl2sql_test`
database; the fixture creates roles and tables and does not clean up a user's
database. See [verification](openwiki/testing/verification.md).

For documentation changes, follow current source and tests, preserve historical
benchmark artifacts, and distinguish actual checks from instructions to run
them. Update OpenWiki through its page-job lifecycle; do not hand-edit its
Claims, provenance, indexes or managed setup blocks.

## Coding conventions

- Match the existing code style; don't introduce unrelated formatting changes.
- Keep the database layer, agent workflow, LLM factory, and security validator cleanly separated: see [ARCHITECTURE.md](ARCHITECTURE.md) for the intended boundaries.
- Treat any new LLM provider integration, SQL safety rule, or database backend as security-sensitive: add tests that cover both the allowed and rejected paths.
- Never log or persist raw API keys, database connection strings, or full query results in audit output: see [SECURITY.md](SECURITY.md) for what's already redacted.

## Pull requests

- Keep pull requests focused so reviewers can verify each behavioral change.
- Describe what you changed and why in the PR description.
- Be patient: this is maintained in spare time, so review may take a bit.

## Code of conduct

Be respectful and constructive. Disagreements about approach are fine and expected; personal attacks, harassment, or bad-faith behavior are not, and issues/PRs/comments that cross that line will be closed or removed.

## No financial contributions

This project does not want or accept donations, sponsorships, or any other form of financial support. You can contribute code, tests, docs, or a reproducible bug report.
