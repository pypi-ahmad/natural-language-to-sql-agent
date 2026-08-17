# Contributing to NL2SQL Agent

Thanks for considering a contribution — this is a free, community-driven project, and bug reports, feature suggestions, and pull requests all genuinely help.

## Before you start

For anything beyond a trivial fix, open an issue first (or comment on an existing one) describing what you want to change and why. This avoids duplicate work and lets us agree on the approach before you invest time in it.

Do not include real API keys, database credentials, connection strings, private schemas, or production data in an issue or pull request.

## Development setup

```bash
git clone https://github.com/pypi-ahmad/natural-language-to-sql-agent.git
cd natural-language-to-sql-agent
uv sync --all-groups
```

This installs the pinned Python (3.12.10) and every development dependency group.

## Making a change

1. Fork and clone the repository.
2. Create a focused branch from `main`.
3. Make your change and add or update tests for it.
4. Run the checks (see below) and fix anything they flag.
5. Update `README.md`, `ARCHITECTURE.md`, or other docs when your change affects public behavior or configuration.
6. Open a pull request with a clear description of the problem, the fix, and how you verified it.

## Required checks

```bash
uv run ruff check src tests
uv run ty check src
uv run pytest tests/unit
```

Then run the same gate CI runs, which also covers formatting and secret scanning:

```bash
uv run prek run --all-files
```

CI runs this full suite before a pull request can merge.

## Coding conventions

- Match the existing code style; don't introduce unrelated formatting changes.
- Keep the database layer, agent workflow, LLM factory, and security validator cleanly separated — see [ARCHITECTURE.md](ARCHITECTURE.md) for the intended boundaries.
- Treat any new LLM provider integration, SQL safety rule, or database backend as security-sensitive: add tests that cover both the allowed and rejected paths.
- Never log or persist raw API keys, database connection strings, or full query results in audit output — see [SECURITY.md](SECURITY.md) for what's already redacted.

## Pull requests

- Keep PRs focused — one change per PR is much easier to review than five.
- Describe what you changed and why in the PR description.
- Be patient — this is maintained in spare time, so review may take a bit.

## Code of conduct

Be respectful and constructive. Disagreements about approach are fine and expected; personal attacks, harassment, or bad-faith behavior are not, and issues/PRs/comments that cross that line will be closed or removed.

## No financial contributions

This project does not want or accept donations, sponsorships, or any other form of financial support. If you'd like to give back, the most valuable thing you can do is contribute code, tests, docs, or a well-written bug report. Thank you!
