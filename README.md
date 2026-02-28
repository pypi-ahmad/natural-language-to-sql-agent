# Natural Language to SQL Data Analyst Agent

A LangGraph-based agent that converts natural language questions into SQL queries, executes them against a SQLite database, and returns LLM-generated natural language summaries. The frontend is a Streamlit chat interface with multi-provider LLM support.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  app.py  (Streamlit UI)                                     │
│  - Provider/model selection sidebar                         │
│  - API key management (env vars or manual input)            │
│  - Chat interface with streaming agent status               │
│  - Calls backend.SQLAgent with selected LLM                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ imports SQLAgent
┌──────────────────────────▼──────────────────────────────────┐
│  backend.py  (LangGraph Workflow)                           │
│                                                             │
│  AgentState (TypedDict)                                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ question, schema, sql_query, sql_safe,                 │ │
│  │ result, error, retry_count                             │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                             │
│  SQLAgent class                                             │
│  ┌─ Nodes ──────────────────────────────────────────┐      │
│  │ fetch_schema → writer → guardian ─┬→ executor    │      │
│  │                  ▲                │   │           │      │
│  │                  │ (retry ≤3)     │   ▼           │      │
│  │                  └────────────────┤ summarizer   │      │
│  │                   (unsafe)────────┘   │           │      │
│  │                                       ▼           │      │
│  │                                      END          │      │
│  └───────────────────────────────────────────────────┘      │
│                                                             │
│  Database: SQLite  (company.db, relative path)              │
└─────────────────────────────────────────────────────────────┘
```

### State Schema

Defined as `AgentState(TypedDict)` in `backend.py`:

| Key           | Type  | Purpose                                    |
|---------------|-------|--------------------------------------------|
| `question`    | `str` | User's natural language question            |
| `schema`      | `str` | Database schema string (tables + columns)   |
| `sql_query`   | `str` | LLM-generated SQL query                     |
| `sql_safe`    | `bool`| Result of security check                    |
| `result`      | `str` | SQL execution output or final summary       |
| `error`       | `str` | Error message from execution or security    |
| `retry_count` | `int` | Number of SQL generation attempts           |

## Execution Flow

The workflow is a `StateGraph` compiled via LangGraph. The exact node names and edges are defined in `SQLAgent.get_workflow()`:

1. **`fetch_schema`** — Connects to `company.db`, reads `sqlite_master` for table names, then `PRAGMA table_info()` per table. Returns schema string.
2. **`writer`** (`write_sql`) — Sends schema + question + previous error to the LLM via `HumanMessage`. Strips markdown fences from response. Increments `retry_count`.
3. **`guardian`** (`check_security`) — Uppercases the SQL and checks for forbidden keywords using word-boundary regex (`\b`). Forbidden keywords: `DROP`, `DELETE`, `TRUNCATE`, `INSERT`, `UPDATE`, `ALTER`.
4. **Routing** (`route_after_security`):
   - `sql_safe == True` → `executor`
   - `sql_safe == False` → `summarizer` (reports the security error)
5. **`executor`** (`execute_sql`) — Runs the raw SQL against `company.db`. Returns result rows as a string, or error.
6. **Routing** (`route_after_execute`):
   - No error → `summarizer`
   - Error and `retry_count < 3` → `writer` (retry)
   - Error and `retry_count >= 3` → `summarizer` (reports the error)
7. **`summarizer`** (`summarize_result`) — Sends question + SQL + data + error to the LLM. Returns final natural language answer.

## LLM Providers

Four providers are supported. Selection and API key entry happen in the Streamlit sidebar (`app.py`).

| Provider     | LangChain Wrapper               | Model Fetching Method                                   | Default Models (fallback)                   |
|--------------|---------------------------------|---------------------------------------------------------|---------------------------------------------|
| **Ollama**   | `ChatOllama`                    | `ollama.list()` (local SDK)                             | `llama3`, `mistral`                         |
| **OpenAI**   | `ChatOpenAI`                    | `OpenAI(api_key).models.list()` — filters for `gpt`/`o1` | `gpt-4o`, `gpt-3.5-turbo`                  |
| **Gemini**   | `ChatGoogleGenerativeAI`        | `google.generativeai.list_models()` — filters for `generateContent` | `gemini-1.5-flash`, `gemini-pro`            |
| **Anthropic**| `ChatAnthropic`                 | Hardcoded list (no list-models API)                     | `claude-3-5-sonnet-latest`                  |

LangChain wrappers are imported lazily inside `get_llm_instance()` (`langchain_community`, `langchain_openai`, `langchain_google_genai`, `langchain_anthropic`).

## Database

The SQLite database `company.db` is created by `setup_db()`, which is called in `SQLAgent.__init__()`. It uses `INSERT OR IGNORE` for idempotent seeding.

**Tables:**

```
departments (dept_id INTEGER PRIMARY KEY, dept_name TEXT, location TEXT)
employees   (emp_id INTEGER PRIMARY KEY, name TEXT, salary REAL, dept_id INTEGER)
```

**Seed Data:**

| dept_id | dept_name    | location       |
|---------|-------------|----------------|
| 101     | Engineering | New York       |
| 102     | Sales       | San Francisco  |
| 103     | HR          | Remote         |

| emp_id | name    | salary  | dept_id |
|--------|---------|---------|---------|
| 1      | Alice   | 120000  | 101     |
| 2      | Bob     | 85000   | 102     |
| 3      | Charlie | 115000  | 101     |
| 4      | Diana   | 95000   | 103     |
| 5      | Eve     | 88000   | 102     |

## Dependencies

All dependencies are listed in `requirements.txt` (unpinned):

| Package                  | Used By        | Purpose                                      |
|--------------------------|----------------|----------------------------------------------|
| `langgraph`              | `backend.py`   | StateGraph workflow engine                    |
| `langchain`              | `backend.py`   | Core LangChain framework                     |
| `langchain_community`    | `app.py`       | `ChatOllama` wrapper                          |
| `langchain-openai`       | `app.py`       | `ChatOpenAI` wrapper                          |
| `langchain-google-genai` | `app.py`       | `ChatGoogleGenerativeAI` wrapper              |
| `langchain-anthropic`    | `app.py`       | `ChatAnthropic` wrapper                       |
| `ollama`                 | `app.py`       | Ollama SDK for model listing                  |
| `openai`                 | `app.py`       | OpenAI SDK for model listing                  |
| `google-generativeai`    | `app.py`       | Google GenAI SDK for model listing (deprecated) |
| `google-genai`           | (unused)       | Listed but not imported anywhere in code      |
| `anthropic`              | (unused)       | Listed but not imported anywhere in code      |
| `python-dotenv`          | `app.py`       | Loads `.env` file via `load_dotenv()`         |
| `streamlit`              | `app.py`       | Web UI framework                              |

**Note:** `google-genai` and `anthropic` are in `requirements.txt` but are not directly imported by any source file. `google-generativeai` triggers a `FutureWarning` about deprecation.

## Setup Instructions

### 1. Clone the repository

```bash
git clone <repository-url>
cd "Natural Language to SQL Data Analyst Agent"
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (cmd):**
```cmd
venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

The app reads API keys from environment variables via `python-dotenv`. Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
ANTHROPIC_API_KEY=your_anthropic_key
```

The specific variable names are hardcoded in `app.py`:
- `Gemini` → `GOOGLE_API_KEY`
- `OpenAI` → `OPENAI_API_KEY`
- `Anthropic` → `ANTHROPIC_API_KEY`
- `Ollama` → no key required (local)

If no env variable is found, the sidebar prompts for manual entry.

### 5. Run the application

```bash
streamlit run app.py
```

The database `company.db` is auto-created in the working directory on first agent instantiation.

## Running Tests

The test suite uses `pytest` with `pytest-cov`. Tests are in the `tests/` directory.

```bash
pip install pytest pytest-cov
python -m pytest tests/ -v
```

With coverage:

```bash
python -m pytest tests/ --cov=backend --cov-report=term-missing
```

**Test inventory** (126 tests across 9 files):

| File                          | Tests | Scope                                       |
|-------------------------------|-------|---------------------------------------------|
| `test_setup_db.py`           | 11    | Table creation, schema, seed data, idempotency |
| `test_fetch_schema.py`       | 9     | Return structure, content, format, empty DB  |
| `test_check_security.py`     | 24    | Safe/unsafe queries, case insensitivity, false positives |
| `test_execute_sql.py`        | 16    | Success paths, aggregates, JOINs, error handling |
| `test_write_sql.py`          | 15    | LLM invocation, prompt content, retry count, markdown stripping |
| `test_summarize.py`          | 8     | LLM interaction, prompt content, return contract |
| `test_routing.py`            | 12    | All routing branches, boundary conditions    |
| `test_workflow_integration.py`| 13   | Happy path, security block, retry, retry exhaustion |
| `test_app_helpers.py`        | 18    | Model listing, no-key guards, unknown provider handling |

All tests use isolated temp directories (via `conftest.py` fixtures) to avoid polluting the workspace.

## Project Structure

```
├── app.py                  Streamlit frontend: provider selection, API key management, chat UI
├── backend.py              LangGraph agent: StateGraph, 5 nodes, routing, DB access
├── requirements.txt        13 dependencies (unpinned)
├── company.db              SQLite database (auto-generated at runtime)
├── .env                    API keys (not tracked in git)
├── .gitignore              Git ignore rules
├── tests/
│   ├── __init__.py         Package marker
│   ├── conftest.py         Shared fixtures (DB isolation, mock LLM, state factory)
│   ├── test_setup_db.py
│   ├── test_fetch_schema.py
│   ├── test_check_security.py
│   ├── test_execute_sql.py
│   ├── test_write_sql.py
│   ├── test_summarize.py
│   ├── test_routing.py
│   ├── test_workflow_integration.py
│   └── test_app_helpers.py
└── README.md
```

## Known Limitations

The following are documented from static analysis and testing of the current codebase:

1. **Incomplete keyword coverage** — The system prevents multi-statement execution via SQLite's single-statement constraint (`sqlite3.Cursor.execute()` raises `ProgrammingError` on multi-statement input) and blocks destructive operations via word-boundary keyword filtering for `DROP`, `DELETE`, `TRUNCATE`, `INSERT`, `UPDATE`, and `ALTER`. However, non-destructive but potentially unsafe statements such as `CREATE`, `ATTACH`, and `PRAGMA` are not currently blocked by `check_security`.

2. **PRAGMA injection** — `fetch_schema` uses an f-string (`f"PRAGMA table_info({table_name})"`) where `table_name` comes from `sqlite_master`. In the current codebase this is safe because table names are self-generated, but the pattern is fragile if the code is extended.

3. **`setup_db()` called per agent instantiation** — Every `SQLAgent.__init__()` call runs `setup_db()`, which opens a connection, runs `CREATE TABLE IF NOT EXISTS` and `INSERT OR IGNORE` statements, then closes. This adds overhead when creating agents per request.

4. **Hardcoded database path** — The path `"company.db"` is a string literal in `setup_db()`, `fetch_schema()`, and `execute_sql()`. It is not configurable.

5. **Error messages passed to LLM** — `summarize_result` includes `state['error']` in the LLM prompt. Raw database error messages could potentially influence LLM output.

6. **Stale model list in session state** — `st.session_state.models` is set by "Fetch Available Models" but is not cleared when switching providers, so stale models from a previous provider may appear.

7. **Unpinned dependencies** — All 13 entries in `requirements.txt` lack version pins, which may cause reproducibility issues.

8. **Deprecated SDK** — `google-generativeai` is deprecated and produces a `FutureWarning` at import time. The replacement is `google-genai`.
