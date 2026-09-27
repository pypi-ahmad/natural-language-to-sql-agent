---
name: Bug report
about: Something isn't working the way it should
title: "[Bug] "
labels: bug
assignees: ''
---

Fill in the details you have. You can submit the report with missing fields.

## What happened

A clear description of the bug.

## Steps to reproduce

1. Database backend (SQLite / PostgreSQL):
2. LLM provider and model:
3. The question you asked (or the CLI/UI action you took):
4. What you expected to happen:
5. What actually happened:

## Diagnostics

```
Paste reviewed, sanitized settings or error text here. The config command
masks credentials but can still expose local paths and endpoint addresses.
```

## Environment

- OS:
- Python version:
- How you're running it (`uv run streamlit run ...`, `nl2sql-agent serve`, `nl2sql-agent ask`, etc.):

## Anything else

Any other context, such as schema shape, screenshots, or logs.

> Please don't paste real API keys, database connection strings, or private schema/data into this issue.
