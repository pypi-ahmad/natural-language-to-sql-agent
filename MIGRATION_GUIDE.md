# Migration Guide — v0.1 → v0.2

This guide covers the user-facing and developer-facing changes between
v0.1 and v0.2. The behavior of the agent is unchanged; the changes are
in **how the project is installed, configured, and extended**.

> **Current `main`:** Existing `run()`, `stream()`, and `ask` callers remain
> compatible. New optional capabilities include `prepare()` /
> `execute_prepared()`, session-scoped SQLite uploads, table authorization,
> hardened read-only execution, and `nl2sql-agent eval`.
> Current `main` also enforces a 50 MB upload cap, loopback-only serving,
> operator-only Ollama endpoint configuration, scope-aware physical-table
> authorization, formula-safe CSV export, and generic database errors.
> Redundant direct dependency declarations were removed; transitive security
> floors are maintained through uv constraints and checked with `uv audit`.
>
> **v0.4 addendum:** SQLite remains the default. Set
> `NL2SQL_DB_BACKEND=postgres`, `NL2SQL_POSTGRES_DSN`, and optionally
> `NL2SQL_POSTGRES_SCHEMA` to use a least-privileged read-only PostgreSQL role.
> The UI now has Chat, Costs, Sessions, Insights, and Pricing views. Local
> saved history excludes result rows, uploads, schemas, keys, and DSNs.

---

## 1. Installation

### v0.1

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### v0.2

```bash
uv venv --python 3.12.10
uv sync --all-groups
uv pip install -e .
```

`uv` is the only required new tool. Everything else (Streamlit, LangChain,
LangGraph, sqlglot) is now pinned in `pyproject.toml` and installed
automatically.

---

## 2. Running the UI

### v0.1

```bash
streamlit run app.py
```

### v0.2

```bash
uv run streamlit run src/nl2sql_agent/ui/streamlit_app.py
```

---

## 3. Running from the CLI

### v0.1

Not available.

### v0.2

```bash
uv run nl2sql-agent ask "How many employees are in Engineering?"
uv run nl2sql-agent ask --show-sql --provider openai --model gpt-5.6-luna "Total salary?"
uv run nl2sql-agent config           # show resolved configuration
uv run nl2sql-agent serve --port 8501 # launch the UI
```

On Windows, `Launch NL2SQL Agent.cmd` is the equivalent double-click entrypoint.

---

## 4. Configuration

### v0.1

Hard-coded in `app.py` and `backend.py`. The only configurable thing
was the API key from environment variables.

### v0.2

Everything is configurable via environment variables prefixed with
`NL2SQL_` (provider, model, DB path, retry count, SQL policy, log
level, etc.). See `README.md` §6 for the full table or run
`uv run nl2sql-agent config` to see what the active config looks like.

Example `.env` file:

```ini
NL2SQL_PROVIDER=ollama
NL2SQL_MODEL=phi4-mini:3.8b
NL2SQL_OLLAMA_BASE_URL=http://localhost:11434
NL2SQL_DB_PATH=company.db
NL2SQL_MAX_RETRIES=3
NL2SQL_LOG_LEVEL=INFO
NL2SQL_LOG_JSON=false
```

---

## 5. Public Python API

### v0.1

```python
from backend import SQLAgent
from app import get_llm_instance

llm = get_llm_instance("ollama", "llama3")
agent = SQLAgent(llm)
result = agent.get_workflow().invoke({"question": "...", "retry_count": 0, "error": ""})
```

### v0.2

```python
from langchain_ollama import ChatOllama
from nl2sql_agent.config import Settings
from nl2sql_agent.agent import NL2SQLAgent

llm = ChatOllama(model="phi4-mini:3.8b")
agent = NL2SQLAgent(llm, settings=Settings(db_path="company.db"))
result = agent.run("What is the total salary in Engineering?")
print(result["final_answer"])
```

The v0.2 API is **stricter and more discoverable**: type hints
throughout, explicit dataclass return values, named arguments
everywhere.

---

## 6. SQL safety

### v0.1

Deny-list of 6 keywords with word-boundary regex.

### v0.2

AST-based allow-list using `sqlglot`. Single-statement SELECT only.
Configurable per-knob policy. New dangerous-function blocklist.

This is a **security improvement** — there is no action required on
your part, but if you previously relied on the deny-list to reject
specific keywords, the AST validator is more accurate and configurable.

---

## 7. Database path

### v0.1

Hard-coded `"company.db"` in three functions.

### v0.2

`NL2SQL_DB_PATH` env var or `Settings(db_path=...)` argument.
Defaults to `company.db` in the current working directory.

---

## 8. Tests

### v0.1

`python -m pytest tests/ -v` — 126 tests, 100% coverage of
`backend.py`.

### v0.2

```bash
uv run pytest tests/unit -v          # offline unit suite
uv run pytest tests/integration -v   # live Ollama, requires service
uv run pytest --cov=src/nl2sql_agent --cov-report=term-missing
```

The old `tests/test_*.py` files at the repo root have been removed;
their coverage is in `tests/unit/` organized by module.

---

## 9. Tooling

| Tool | v0.1 | v0.2 |
|---|---|---|
| Dependency manager | `pip` + `requirements.txt` | `uv` + `pyproject.toml` |
| Lint | none configured | `ruff check` (in `pyproject.toml`) |
| Type check | none configured | `ty` (in `pyproject.toml`) |
| Coverage | `pytest-cov` (basic) | `pytest-cov` with branch + missing-line reporting |
| Logging | `print()` | `loguru` (configurable, JSON-capable) |
| Packaging | none | `uv_build` (`uv pip install -e .` works) |

---

## 10. What is **not** changing

- The agent's behavior (schema → write → guard → execute → summarize).
- The database schema (still `departments` and `employees` with the
  same seed data).
- The Streamlit chat UX conceptually (input box, history, status
  indicator, SQL preview).
- The multi-provider design. Current main supports Ollama, Hugging Face,
  OpenAI, Anthropic, Gemini, and xAI; hosted models use medium reasoning.
- Public outputs (Markdown answers, raw rows, error messages).

If your v0.1 scripts imported the agent and asked questions, they will
keep working with the v0.2 package after the import path is updated.

---

## 11. Using the current approval-first API

```python
prepared = agent.prepare("What is the total salary in Engineering?")
result = agent.execute_prepared(prepared, sql_query=prepared["sql_query"])
```

Automation can continue using `run()` or `stream()` unchanged. The Streamlit
UI uses the two-phase API so SQL can be reviewed before execution. Run the new
result and safety corpus with `uv run nl2sql-agent eval`. Current main also
records per-call provider usage and applies editable effective-dated pricing,
including cache, batch, fast-mode, and long-context rates. Local and custom
models remain unpriced until an applicable rule is configured.

PostgreSQL is intentionally opt-in and the packaged evaluation corpus remains
SQLite-only. Create the restricted role shown in `README.md`, configure its DSN
outside the browser, and run `uv run nl2sql-agent ask ...` or open the UI.
