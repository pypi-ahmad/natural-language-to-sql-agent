## What does this PR do?

A short description of the change and why it's needed. Link the issue it addresses, if any (`Closes #___`).

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor / internal cleanup
- [ ] Other (describe above)

## How was this tested?

```bash
uv run ruff check src
uv run pytest -q --cov=nl2sql_agent
uv run ty check
uv audit --locked
uv build
uv run prek run --all-files
```

- Database backend(s) exercised (SQLite / PostgreSQL):
- LLM provider(s) exercised:

## Checklist

- [ ] I read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] I updated README.md/ARCHITECTURE.md if this change affects public behavior or configuration
- [ ] I did not commit any API keys, database connection strings, or private data
- [ ] Behavioral changes include focused tests or explain why testing was not possible
- [ ] This PR is focused on one change (not several unrelated things bundled together)
