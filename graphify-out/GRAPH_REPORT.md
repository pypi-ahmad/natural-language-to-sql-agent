# Graph Report - D:\AI\Github\natural-language-to-sql-agent  (2026-08-14)

## Corpus Check
- 68 files · ~139,381 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 916 nodes · 1733 edges · 58 communities (42 shown, 16 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 251 edges (avg confidence: 0.78)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Audit Logging
- StateStore
- _make_agent
- cli.py
- pricing.py
- Database
- list_models
- validate_sqlite_upload
- config/__init__.py
- database.py
- validate_sql
- TestPrompts
- Settings
- pages.py
- sql_validator.py
- factory.py
- NL2SQLAgent
- conftest.py
- QueryResult
- TestParser
- components.py
- PostgresDatabase
- build_chat_model
- test_sql_validator.py
- Any
- test_ui_app.py
- AgentState
- TestDatabaseExecute
- .execute
- prepare_sql
- streamlit_app.py
- DatabaseBackend
- NL2SQL Agent
- referenced_tables
- TestDatabaseSchema
- security/__init__.py
- workflow.py
- test_postgres.py
- test_ui_components.py
- Approval-first Execution
- SQLite Default and PostgreSQL Opt-in
- Effective-dated Model Pricing
- Dataset Evaluation Corpus
- Persistence Privacy Boundary
- Database Backend Contract
- v0.4.0 Release
- Approval-first Execution
- Code of Conduct
- Demo SQLite Database
- Dependabot Dependency Updates
- Generated Graph Artifacts
- Historical Pricing Snapshots
- data/__init__.py
- Zero to Hero Study Handbook
- tests/__init__.py

## God Nodes (most connected - your core abstractions)
1. `_make_agent()` - 45 edges
2. `Settings` - 45 edges
3. `build_chat_model()` - 39 edges
4. `Database` - 31 edges
5. `validate_sql()` - 30 edges
6. `NL2SQLAgent` - 29 edges
7. `get_settings()` - 29 edges
8. `StateStore` - 27 edges
9. `reset_settings_cache()` - 23 edges
10. `AgentState` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Agnes AI Provider Integration` --references--> `Settings`  [EXTRACTED]
  ARCHITECTURE.md → src/nl2sql_agent/config/settings.py
- `test_main_app_renders_chat_navigation()` --calls--> `reset_settings_cache()`  [INFERRED]
  tests/unit/test_ui_app.py → src/nl2sql_agent/config/settings.py
- `Agnes AI Provider Integration` --references--> `build_chat_model()`  [EXTRACTED]
  ARCHITECTURE.md → src/nl2sql_agent/llm/factory.py
- `Agnes AI Provider` --references--> `build_chat_model()`  [EXTRACTED]
  README.md → src/nl2sql_agent/llm/factory.py
- `Agnes AI Provider Learning Trace` --references--> `build_chat_model()`  [EXTRACTED]
  ZERO_TO_HERO_STUDY_HANDBOOK.md → src/nl2sql_agent/llm/factory.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Approval-first Persistence Flow** — architecture_local_state_store, readme_saved_sessions, security_persistence_privacy_boundary [EXTRACTED 1.00]
- **Read-only Query Safety** — architecture_database_backend_contract, architecture_sql_safety_defense_in_depth, changelog_postgresql_read_only_backend [INFERRED 0.85]
- **Approval-first Workspace** — readme_approval_first_execution, readme_five_view_streamlit_ui, readme_saved_sessions [INFERRED 0.85]
- **Safe Read-only Execution** — readme_read_only_database_backends, readme_ast_sql_safety, readme_postgresql_read_only_role [INFERRED 0.85]
- **Persistent Cost Observability** — readme_saved_sessions, readme_query_insights, zero_to_hero_study_handbook_query_pricing [INFERRED 0.85]

## Communities (58 total, 16 thin omitted)

### Community 0 - "Audit Logging"
Cohesion: 0.05
Nodes (39): CompiledStateGraph, Exception, Agent module: LangGraph workflow, state, and high-level entry point., AgentState, Typed state for the LangGraph agent. Using ``TypedDict`` (not Pydantic) to keep…, The complete state threaded through the workflow. All fields are optional…, NL2SQLAgent, NodeTrace (+31 more)

### Community 1 - "StateStore"
Cohesion: 0.07
Nodes (56): cache_resource, Database, DatabaseBackend, DataFrame, _default_models(), Any, Provider, Streamlit UI helpers (separated from the entry point for testability). (+48 more)

### Community 2 - "_make_agent"
Cohesion: 0.06
Nodes (38): AuditLogger, hash_text(), Any, Path, Privacy-preserving append-only audit events., Return a stable SHA-256 digest without retaining the source text., Remove literal values from parseable SQL, or retain only a digest., Write sanitized operational events to a local JSONL file. (+30 more)

### Community 3 - "cli.py"
Cohesion: 0.06
Nodes (14): _make_agent(), Tests for the LangGraph agent workflow., Build an NL2SQLAgent with a mock LLM and the seeded test DB., TestCheckSecurity, TestExecuteSql, TestExecutionEdgeCases, TestFetchSchema, TestHighLevelRun (+6 more)

### Community 4 - "pricing.py"
Cohesion: 0.08
Nodes (39): Agnes AI Provider, v0.5.0 Release Notes, RequestMode, LLM module: provider factory, model discovery, chat-model construction., calculate_cost(), CostBreakdown, CostLine, _d() (+31 more)

### Community 5 - "Database"
Cohesion: 0.09
Nodes (19): cost_rows_to_csv(), _csv_cell(), _json(), Any, Connection, Decimal, Path, Row (+11 more)

### Community 6 - "list_models"
Cohesion: 0.08
Nodes (16): fallback_models(), list_models(), _list_ollama(), Hard-coded fallback list when the SDK call fails or is unavailable., Discover available model IDs for ``provider``. Hosted providers return their…, live_llm(), _ollama_alive(), ollama_model() (+8 more)

### Community 7 - "validate_sqlite_upload"
Cohesion: 0.12
Nodes (25): Result-based evaluation for NL2SQL models and policies., AgentRunner, EvalCase, EvaluationCaseResult, EvaluationReport, EvaluationRunner, _file_digest(), load_cases() (+17 more)

### Community 8 - "config/__init__.py"
Cohesion: 0.12
Nodes (17): model_validator, Configuration module for the NL2SQL agent., default_model_for(), env_var_for(), env_var_value(), Provider, Application configuration via Pydantic Settings. Loads from environment…, Return the API key configured for ``provider``, or ``None``. (+9 more)

### Community 9 - "database.py"
Cohesion: 0.10
Nodes (10): Database, Path, Return a non-sensitive database label., Return a stable identity without reading database contents., Create the demo tables and (optionally) seed sample data. Idempotent: ``CREATE…, Drop the database file (use only in tests or interactive reset)., Backward-compatible module-level setup helper., A small wrapper around :mod:`sqlite3` for the agent's database. The class is… (+2 more)

### Community 10 - "validate_sql"
Cohesion: 0.14
Nodes (9): Validate that ``sql`` is safe to execute under ``policy``. Returns the list of…, Allow-list knobs for SQL safety., SQLPolicy, validate_sql(), TestCTE, TestEmptyAndInvalid, TestJoins, TestSubqueries (+1 more)

### Community 11 - "TestPrompts"
Cohesion: 0.17
Nodes (7): BaseSettings, field_validator, parametrize, Runtime configuration for the NL2SQL agent. Values are resolved in this order:…, Settings, TestSettings, ValueError

### Community 12 - "Settings"
Cohesion: 0.19
Nodes (20): ChatAnthropic, ChatGoogleGenerativeAI, ChatOllama, ChatOpenAI, RuntimeError, _build_agnes(), _build_anthropic(), _build_gemini() (+12 more)

### Community 13 - "pages.py"
Cohesion: 0.17
Nodes (20): Expression, Func, Select, _check_select(), _flatten_selects(), _function_name(), _is_aggregate_call(), ValueError (+12 more)

### Community 14 - "sql_validator.py"
Cohesion: 0.16
Nodes (19): Path, ValueError, Validation and session-local storage for untrusted SQLite uploads., Raised when an uploaded file cannot be accepted as SQLite., Reject unsupported or oversized uploads before reading their contents., Validate filename, size, and SQLite magic header; return SHA-256., Store validated bytes under a content-derived session-local name., save_sqlite_upload() (+11 more)

### Community 15 - "factory.py"
Cohesion: 0.17
Nodes (5): BaseChatModel, build_chat_model(), Build a LangChain chat model from runtime configuration. Args: settings: A…, TestBuildChatModel, Agnes AI Provider Learning Trace

### Community 16 - "NL2SQLAgent"
Cohesion: 0.17
Nodes (12): QueryMetrics, QueryPlan, QueryPlanNode, Shared database contracts and query observability types., One normalized node in a database query plan., A normalized, non-executing query plan., Return a JSON-serializable representation., Runtime measurements recorded for an executed query. (+4 more)

### Community 17 - "conftest.py"
Cohesion: 0.16
Nodes (18): MonkeyPatch, empty_db(), example_questions(), make_state(), mock_llm(), fixture, Path, Shared pytest fixtures and helpers. (+10 more)

### Community 18 - "QueryResult"
Cohesion: 0.15
Nodes (9): _csv_cell(), _fmt_cell(), QueryResult, Standalone pretty-printer used by tests and CLI., A successful SQL execution result., Render the result as a Markdown table., Neutralize string cells that spreadsheet programs may execute., render_table() (+1 more)

### Community 19 - "TestParser"
Cohesion: 0.18
Nodes (10): DatabaseError, RuntimeError, A provider-neutral database failure safe for workflow handling., _sample_cell(), PostgresDatabase, Any, Connection, PostgreSQL access constrained by role checks and read-only transactions. (+2 more)

### Community 20 - "components.py"
Cohesion: 0.17
Nodes (10): _list_tables(), Connection, Row, _quote_identifier(), Yield a hardened read-only query connection. The connection is closed when the…, Yield the narrowly scoped connection used only for demo setup., Return ordinary user tables in deterministic order., Return ranked schema context for the LLM prompt. (+2 more)

### Community 21 - "PostgresDatabase"
Cohesion: 0.12
Nodes (4): Tests for the CLI entry point., TestAskCommand, TestEvalCommand, TestParser

### Community 22 - "build_chat_model"
Cohesion: 0.20
Nodes (6): get_settings(), Return the cached :class:`Settings` instance. Use this as a…, Clear the settings cache. Tests use this to pick up env changes., reset_settings_cache(), live_settings(), TestConfigCommand

### Community 23 - "test_sql_validator.py"
Cohesion: 0.15
Nodes (7): parametrize, Tests for the SQL safety validator., TestDangerousFunctions, TestDestructiveStatements, TestFalsePositives, TestMultiStatement, TestSafeQueries

### Community 24 - "Any"
Cohesion: 0.24
Nodes (14): ArgumentParser, Namespace, _build_agent(), build_parser(), cmd_ask(), cmd_config(), cmd_eval(), cmd_serve() (+6 more)

### Community 26 - "AgentState"
Cohesion: 0.15
Nodes (5): BaseChatModel, Collection, DatabaseBackend, Protocol, Minimum interface required by the NL2SQL workflow.

### Community 27 - "TestDatabaseExecute"
Cohesion: 0.26
Nodes (4): prepare_sql(), Collection, Validate, authorize, and canonicalize one executable SELECT., TestPrepareSql

### Community 28 - ".execute"
Cohesion: 0.22
Nodes (9): fixture, StateStore, Tests for local saved sessions, pricing, and dashboard aggregates., _session(), store(), test_pending_query_uses_explicit_allowlist(), test_run_cost_and_metrics_are_aggregated(), test_saved_messages_exclude_raw_results_and_csv() (+1 more)

### Community 29 - "prepare_sql"
Cohesion: 0.31
Nodes (4): Return the set of table names referenced in ``sql``. Used by the executor's…, Return physical table names from already-parsed statements., referenced_tables(), TestReferencedTables

### Community 31 - "DatabaseBackend"
Cohesion: 0.22
Nodes (9): AST SQL Safety, Multi-provider LLM Factory, NL2SQL Agent, PostgreSQL Read-only Role, Query Insights, Read-only Database Backends, Factory Pattern, Policy-based Security (+1 more)

### Community 32 - "NL2SQL Agent"
Cohesion: 0.25
Nodes (6): Security module: SQL validation, input sanitization, redaction., parse_sql(), PreparedSQL, Validated SQL ready for execution., Parse ``sql`` into a list of statements using sqlglot. Empty / whitespace-only…, TestParseSql

### Community 33 - "referenced_tables"
Cohesion: 0.29
Nodes (8): Effective-dated Pricing, Local State Store, Approval-first Execution, Five-view Streamlit UI, LangGraph Workflow, Saved Sessions, Versioned Local State Store, Per-call Query Pricing

### Community 34 - "TestDatabaseSchema"
Cohesion: 0.46
Nodes (6): _cursor(), Tests for PostgreSQL read-only connection and plan behavior., _safe_connection(), test_connection_is_read_only_parameterized_and_rolled_back(), test_preflight_uses_json_explain_without_analyze(), test_privileged_postgres_role_is_rejected()

### Community 35 - "security/__init__.py"
Cohesion: 0.38
Nodes (5): AppTest, Tests for user-visible Streamlit provider controls., _sidebar_app(), test_sidebar_accepts_custom_hugging_face_model(), test_sidebar_shows_only_approved_cloud_models()

### Community 36 - "workflow.py"
Cohesion: 0.40
Nodes (5): Approval-first Public API, SQLite Default and PostgreSQL Opt-in, Backward Compatibility, Compatible Public API, v0.4.0 Upgrade Addendum

### Community 37 - "test_postgres.py"
Cohesion: 0.50
Nodes (4): Agnes AI Provider Integration, v0.5.0 Agnes Release, Agnes AI Migration Surface, Agnes Fixed HTTPS API Root

### Community 38 - "test_ui_components.py"
Cohesion: 0.50
Nodes (4): Cost Export Privacy, Persistence Privacy Boundary, Runtime Data Safety, SQLite Upload Validation

### Community 39 - "Approval-first Execution"
Cohesion: 1.00
Nodes (3): Database Backend Contract, Read-only Query Insights, SQL Safety Defense in Depth

### Community 40 - "SQLite Default and PostgreSQL Opt-in"
Cohesion: 0.67
Nodes (3): Five-view Streamlit Workspace, PostgreSQL Read-only Backend, v0.4.0 Release

## Knowledge Gaps
- **31 isolated node(s):** `Dependabot Dependency Updates`, `Continuous Integration Workflow`, `Pre-commit Quality Gates`, `Generated Graph Artifacts`, `Code of Conduct` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_settings()` connect `build_chat_model` to `Audit Logging`, `StateStore`, `cli.py`, `config/__init__.py`, `TestPrompts`, `Settings`, `factory.py`, `Any`, `AgentState`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Why does `Database` connect `database.py` to `cli.py`, `validate_sqlite_upload`, `NL2SQLAgent`, `conftest.py`, `components.py`, `test_ui_app.py`, `AgentState`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `_make_agent()` connect `cli.py` to `Audit Logging`, `validate_sql`, `_make_agent`, `build_chat_model`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `_make_agent()` (e.g. with `get_settings()` and `SQLPolicy`) actually correct?**
  _`_make_agent()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Settings` (e.g. with `.test_injected_database_is_never_seeded()` and `.test_agnes_uses_documented_chat_thinking()`) actually correct?**
  _`Settings` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `build_chat_model()` (e.g. with `_build_agent()` and `_build_agent()`) actually correct?**
  _`build_chat_model()` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `Database` (e.g. with `QueryMetrics` and `QueryPlan`) actually correct?**
  _`Database` has 10 INFERRED edges - model-reasoned connections that need verification._
