# Graph Report - .  (2026-08-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 673 nodes · 1269 edges · 45 communities (35 shown, 10 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 205 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3b4ee491`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- utils/__init__.py
- NL2SQLAgent
- _make_agent
- streamlit_app.py
- runner.py
- validate_sql
- Database
- TestPrompts
- validate_sqlite_upload
- list_models
- factory.py
- sql_validator.py
- conftest.py
- build_chat_model
- Settings
- TestParser
- config/__init__.py
- QueryResult
- test_sql_validator.py
- cli.py
- get_settings
- prepare_sql
- fallback_models
- .execute
- database.py
- TestDatabaseExecute
- Provider Catalog
- referenced_tables
- TestDatabaseSchema
- test_ui_components.py
- db/__init__.py
- parse_sql
- Unreleased Changes
- Continuous Integration Workflow
- Code of Conduct
- Datasets
- Provider Credential Handling
- data/__init__.py
- nl2sql_agent/__init__.py
- nl2sql-agent
- BaseChatModel
- parametrize

## God Nodes (most connected - your core abstractions)
1. `_make_agent()` - 42 edges
2. `Settings` - 37 edges
3. `build_chat_model()` - 36 edges
4. `NL2SQLAgent` - 31 edges
5. `get_settings()` - 31 edges
6. `validate_sql()` - 29 edges
7. `Database` - 27 edges
8. `AgentState` - 22 edges
9. `SQLPolicy` - 22 edges
10. `reset_settings_cache()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Hosted Model Policy` --semantically_similar_to--> `Provider Catalog`  [INFERRED] [semantically similar]
  ARCHITECTURE.md → README.md
- `test_load_cases()` --calls--> `load_cases()`  [INFERRED]
  tests/unit/test_evaluation.py → src/nl2sql_agent/evaluation/runner.py
- `_make_agent()` --calls--> `SQLPolicy`  [INFERRED]
  tests/unit/test_agent.py → src/nl2sql_agent/security/sql_validator.py
- `test_hash_text_does_not_expose_input()` --calls--> `hash_text()`  [INFERRED]
  tests/unit/test_audit.py → src/nl2sql_agent/utils/audit.py
- `test_invalid_sql_is_not_logged_raw()` --calls--> `redact_sql()`  [INFERRED]
  tests/unit/test_audit.py → src/nl2sql_agent/utils/audit.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Hosted Provider Governance** — architecture_hosted_model_policy, readme_provider_catalog, security_provider_credentials [INFERRED 0.85]

## Communities (45 total, 10 thin omitted)

### Community 0 - "utils/__init__.py"
Cohesion: 0.05
Nodes (40): BaseChatModel, Collection, AuditLogger, hash_text(), Any, Path, Privacy-preserving append-only audit events., Return a stable SHA-256 digest without retaining the source text. (+32 more)

### Community 1 - "NL2SQLAgent"
Cohesion: 0.07
Nodes (30): CompiledStateGraph, Exception, Agent module: LangGraph workflow, state, and high-level entry point., AgentState, Typed state for the LangGraph agent. Using ``TypedDict`` (not Pydantic) to keep…, The complete state threaded through the workflow. All fields are optional…, NL2SQLAgent, NodeTrace (+22 more)

### Community 2 - "_make_agent"
Cohesion: 0.07
Nodes (14): RuntimeError, _make_agent(), Tests for the LangGraph agent workflow., Build an NL2SQLAgent with a mock LLM and the seeded test DB., TestCheckSecurity, TestExecuteSql, TestExecutionEdgeCases, TestFetchSchema (+6 more)

### Community 3 - "streamlit_app.py"
Cohesion: 0.09
Nodes (33): cache_resource, Database, env_var_for(), env_var_value(), Return the standard environment variable name for the provider's API key., Read a name from the process environment without a Settings instance., _default_models(), Any (+25 more)

### Community 4 - "runner.py"
Cohesion: 0.12
Nodes (25): Protocol, Result-based evaluation for NL2SQL models and policies., AgentRunner, EvalCase, EvaluationCaseResult, EvaluationReport, EvaluationRunner, _file_digest() (+17 more)

### Community 5 - "validate_sql"
Cohesion: 0.14
Nodes (9): Validate that ``sql`` is safe to execute under ``policy``. Returns the list of…, Allow-list knobs for SQL safety., SQLPolicy, validate_sql(), TestCTE, TestEmptyAndInvalid, TestJoins, TestSubqueries (+1 more)

### Community 6 - "Database"
Cohesion: 0.12
Nodes (8): Database, Path, Create the demo tables and (optionally) seed sample data. Idempotent: ``CREATE…, Drop the database file (use only in tests or interactive reset)., Backward-compatible module-level setup helper., A small wrapper around :mod:`sqlite3` for the agent's database. The class is…, setup_db(), TestSetup

### Community 7 - "TestPrompts"
Cohesion: 0.13
Nodes (8): Prompt module: centralized, versioned prompt templates., error_section(), format_data(), LLM prompt templates. Centralized so the prompts can be versioned, tested, and…, Format the "previous attempt failed" section for the writer prompt., Format the data block for the summarizer prompt., Tests for the prompt templates., TestPrompts

### Community 8 - "validate_sqlite_upload"
Cohesion: 0.16
Nodes (19): Path, ValueError, Validation and session-local storage for untrusted SQLite uploads., Raised when an uploaded file cannot be accepted as SQLite., Reject unsupported or oversized uploads before reading their contents., Validate filename, size, and SQLite magic header; return SHA-256., Store validated bytes under a content-derived session-local name., save_sqlite_upload() (+11 more)

### Community 9 - "list_models"
Cohesion: 0.15
Nodes (10): list_models(), _list_ollama(), Discover available model IDs for ``provider``. Hosted providers return their…, live_settings(), _ollama_alive(), ollama_model(), fixture, End-to-end smoke test that requires a running local Ollama instance. Marked… (+2 more)

### Community 10 - "factory.py"
Cohesion: 0.20
Nodes (18): ChatAnthropic, ChatGoogleGenerativeAI, ChatOllama, ChatOpenAI, _build_anthropic(), _build_gemini(), _build_huggingface(), _build_ollama() (+10 more)

### Community 11 - "sql_validator.py"
Cohesion: 0.19
Nodes (18): Expression, Func, Select, _check_select(), _flatten_selects(), _function_name(), _is_aggregate_call(), ValueError (+10 more)

### Community 12 - "conftest.py"
Cohesion: 0.16
Nodes (18): MonkeyPatch, empty_db(), example_questions(), make_state(), mock_llm(), fixture, Path, Shared pytest fixtures and helpers. (+10 more)

### Community 13 - "build_chat_model"
Cohesion: 0.21
Nodes (4): BaseChatModel, build_chat_model(), Build a LangChain chat model from runtime configuration. Args: settings: A…, TestBuildChatModel

### Community 14 - "Settings"
Cohesion: 0.20
Nodes (6): BaseSettings, field_validator, parametrize, Runtime configuration for the NL2SQL agent. Values are resolved in this order:…, Settings, TestSettings

### Community 15 - "TestParser"
Cohesion: 0.12
Nodes (4): Tests for the CLI entry point., TestAskCommand, TestEvalCommand, TestParser

### Community 16 - "config/__init__.py"
Cohesion: 0.19
Nodes (11): model_validator, Configuration module for the NL2SQL agent., default_model_for(), Provider, Application configuration via Pydantic Settings. Loads from environment…, Return the API key configured for ``provider``, or ``None``., Return the deterministic model choices shown for ``provider``., Return the default model used when a provider is selected. (+3 more)

### Community 17 - "QueryResult"
Cohesion: 0.19
Nodes (7): _fmt_cell(), QueryResult, Standalone pretty-printer used by tests and CLI., A successful SQL execution result., Render the result as a Markdown table., render_table(), TestQueryResult

### Community 18 - "test_sql_validator.py"
Cohesion: 0.15
Nodes (7): parametrize, Tests for the SQL safety validator., TestDangerousFunctions, TestDestructiveStatements, TestFalsePositives, TestMultiStatement, TestSafeQueries

### Community 19 - "cli.py"
Cohesion: 0.24
Nodes (14): ArgumentParser, Namespace, _build_agent(), build_parser(), cmd_ask(), cmd_config(), cmd_eval(), cmd_serve() (+6 more)

### Community 20 - "get_settings"
Cohesion: 0.21
Nodes (5): get_settings(), Return the cached :class:`Settings` instance. Use this as a…, Clear the settings cache. Tests use this to pick up env changes., reset_settings_cache(), TestConfigCommand

### Community 21 - "prepare_sql"
Cohesion: 0.21
Nodes (7): Security module: SQL validation, input sanitization, redaction., prepare_sql(), PreparedSQL, Collection, Validate, authorize, and canonicalize one executable SELECT., Validated SQL ready for execution., TestPrepareSql

### Community 22 - "fallback_models"
Cohesion: 0.23
Nodes (5): fallback_models(), Hard-coded fallback list when the SDK call fails or is unavailable., LLM module: provider factory, model discovery, chat-model construction., Tests for the LLM provider factory and model discovery., TestFallbackModels

### Community 23 - ".execute"
Cohesion: 0.24
Nodes (6): Connection, Yield a hardened read-only query connection. The connection is closed when the…, Yield the narrowly scoped connection used only for demo setup., Return ordinary user tables in deterministic order., Execute a single SELECT and return its result. Enforces ``max_rows`` by…, Compile a query plan without executing the SELECT.

### Community 24 - "database.py"
Cohesion: 0.20
Nodes (8): Row, _csv_cell(), _list_tables(), _quote_identifier(), SQLite database layer. Provides: - :class:`Database`: a thin, thread-safe…, Return ranked schema context for the LLM prompt., Neutralize string cells that spreadsheet programs may execute., _sample_cell()

### Community 26 - "Provider Catalog"
Cohesion: 0.20
Nodes (10): Architecture Guide, NL2SQL Architecture Diagram, Hosted Model Policy, SQL Defense in Depth, Migration Guide, NL2SQL Agent Overview, Provider Catalog, Upgrade Summary (+2 more)

### Community 27 - "referenced_tables"
Cohesion: 0.31
Nodes (4): Return the set of table names referenced in ``sql``. Used by the executor's…, Return physical table names from already-parsed statements., referenced_tables(), TestReferencedTables

### Community 29 - "test_ui_components.py"
Cohesion: 0.47
Nodes (5): AppTest, Tests for user-visible Streamlit provider controls., _sidebar_app(), test_sidebar_accepts_custom_hugging_face_model(), test_sidebar_shows_only_approved_cloud_models()

### Community 30 - "db/__init__.py"
Cohesion: 0.33
Nodes (3): Database layer: SQLite wrapper, schema, seed data, and helpers., Seed data for the demo company database., Tests for the database layer.

### Community 31 - "parse_sql"
Cohesion: 0.50
Nodes (3): parse_sql(), Parse ``sql`` into a list of statements using sqlglot. Empty / whitespace-only…, TestParseSql

### Community 32 - "Unreleased Changes"
Cohesion: 0.67
Nodes (3): Unreleased Changes, Windows Double-click Launcher, Current Main Release Notes

### Community 33 - "Continuous Integration Workflow"
Cohesion: 0.67
Nodes (3): Dependabot Dependency Updates, Continuous Integration Workflow, Quality Hooks

## Knowledge Gaps
- **15 isolated node(s):** `Dependabot Dependency Updates`, `Quality Hooks`, `Code of Conduct`, `Harassment-Free Participation`, `Datasets` (+10 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_settings()` connect `get_settings` to `utils/__init__.py`, `NL2SQLAgent`, `_make_agent`, `streamlit_app.py`, `list_models`, `factory.py`, `build_chat_model`, `Settings`, `config/__init__.py`, `cli.py`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._
- **Why does `Database` connect `Database` to `utils/__init__.py`, `NL2SQLAgent`, `_make_agent`, `runner.py`, `conftest.py`, `.execute`, `database.py`, `TestDatabaseExecute`, `db/__init__.py`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Why does `_make_agent()` connect `_make_agent` to `utils/__init__.py`, `NL2SQLAgent`, `get_settings`, `validate_sql`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `_make_agent()` (e.g. with `get_settings()` and `SQLPolicy`) actually correct?**
  _`_make_agent()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `Settings` (e.g. with `.test_injected_database_is_never_seeded()` and `.test_anthropic_uses_medium_adaptive_thinking_without_sampling()`) actually correct?**
  _`Settings` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `build_chat_model()` (e.g. with `.test_count_employees()` and `.test_total_engineering_salary()`) actually correct?**
  _`build_chat_model()` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `NL2SQLAgent` (e.g. with `AgentState` and `.test_count_employees()`) actually correct?**
  _`NL2SQLAgent` has 4 INFERRED edges - model-reasoned connections that need verification._