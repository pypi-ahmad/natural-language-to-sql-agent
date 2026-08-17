---
name: Bug report
about: Something isn't working the way it should
title: "[Bug] "
labels: bug
assignees: ''
---

Thanks for taking the time to report this — please fill in as much as you can, but don't let a missing field stop you from posting.

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
Paste the output of `uv run nl2sql-agent config`, or the exact error text
shown in the UI or terminal, here.
```

## Environment

- OS:
- Python version:
- How you're running it (`uv run streamlit run ...`, `nl2sql-agent serve`, `nl2sql-agent ask`, etc.):

## Anything else

Any other context — schema shape, screenshots, logs.

> Please don't paste real API keys, database connection strings, or private schema/data into this issue.
