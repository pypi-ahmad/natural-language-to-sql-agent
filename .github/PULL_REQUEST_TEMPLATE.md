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
uv run ruff check src tests
uv run ty check src
uv run pytest tests/unit
uv run prek run --all-files
```

- Database backend(s) exercised (SQLite / PostgreSQL):
- LLM provider(s) exercised:

## Checklist

- [ ] I read [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ ] I updated README.md/ARCHITECTURE.md if this change affects public behavior or configuration
- [ ] I did not commit any API keys, database connection strings, or private data
- [ ] New LLM providers, database backends, or SQL safety rules include tests for both allowed and rejected paths
- [ ] This PR is focused on one change (not several unrelated things bundled together)
