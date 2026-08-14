# Graph Report - .  (2026-08-14)

## Corpus Check
- 94 files · ~138,568 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 898 nodes · 1773 edges · 60 communities (47 shown, 13 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 238 edges (avg confidence: 0.78)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Audit Logging
- Session Persistence
- Agent Workflow Tests
- Command Line Interface
- Cost Calculation
- Agent Database Integration
- Model Discovery
- Upload Handling
- Provider Configuration
- Query Plans and Metrics
- SQL Policy Validation
- Prompt Templates
- Runtime Settings
- Dashboard Pages
- SQL AST Inspection
- Provider Adapters
- LangGraph Orchestration
- Test Fixtures
- Query Result Formatting
- CLI Tests
- Provider UI Controls
- PostgreSQL Backend
- Chat Model Factory
- SQL Validator Tests
- Approval Execution Flow
- Settings Cache
- Agent State
- Database Execution Tests
- SQLite Connections
- SQL Preparation
- Streamlit Application
- Database Backend Contract
- System Architecture
- Physical Table Discovery
- Schema Introspection Tests
- Security Package
- Agent Package
- PostgreSQL Tests
- Streamlit Tests
- Architecture Concepts
- Upgrade Compatibility
- Release Features
- Settings Tests
- Persistence Security
- Database Safety Documentation
- Release Overview
- Approval Workflow Documentation
- Community Conduct
- Evaluation Dataset
- Repository Automation
- Generated Quality Assets
- Pricing Release History
- Evaluation Package
- Study Architecture
- Handbook PDF
- Workflow Data Contracts
- Project Metadata

## God Nodes (most connected - your core abstractions)
1. `_make_agent()` - 45 edges
2. `Settings` - 40 edges
3. `StateStore` - 38 edges
4. `NL2SQLAgent` - 36 edges
5. `build_chat_model()` - 36 edges
6. `Database` - 34 edges
7. `get_settings()` - 32 edges
8. `validate_sql()` - 30 edges
9. `PostgresDatabase` - 24 edges
10. `AgentState` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Approval-first Analysis` --semantically_similar_to--> `Approval-first Execution`  [INFERRED] [semantically similar]
  ZERO_TO_HERO_STUDY_HANDBOOK.pdf → README.md
- `Defense in Depth` --semantically_similar_to--> `Policy-based Security`  [INFERRED] [semantically similar]
  ZERO_TO_HERO_STUDY_HANDBOOK.pdf → ZERO_TO_HERO_STUDY_HANDBOOK.md
- `test_main_app_renders_chat_navigation()` --calls--> `reset_settings_cache()`  [INFERRED]
  tests/unit/test_ui_app.py → src/nl2sql_agent/config/settings.py
- `test_fingerprint_never_contains_dsn()` --calls--> `PostgresDatabase`  [INFERRED]
  tests/unit/test_postgres.py → src/nl2sql_agent/db/postgres.py
- `Interactive Architecture Diagram` --semantically_similar_to--> `LangGraph Workflow`  [INFERRED] [semantically similar]
  architecture-diagram.html → ARCHITECTURE.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Approval-first Persistence Flow** — architecture_approval_first_execution, architecture_local_state_store, readme_saved_sessions, security_persistence_privacy_boundary [EXTRACTED 1.00]
- **Read-only Query Safety** — architecture_database_backend_contract, architecture_sql_safety_defense_in_depth, changelog_postgresql_read_only_backend [INFERRED 0.85]
- **Approval-first Workspace** — readme_approval_first_execution, readme_five_view_streamlit_ui, readme_saved_sessions, zero_to_hero_study_handbook_pdf_approval_first_analysis [INFERRED 0.85]
- **Safe Read-only Execution** — readme_read_only_database_backends, readme_ast_sql_safety, readme_postgresql_read_only_role, zero_to_hero_study_handbook_pdf_defense_in_depth [INFERRED 0.85]
- **Persistent Cost Observability** — readme_effective_dated_model_pricing, readme_saved_sessions, readme_query_insights, zero_to_hero_study_handbook_query_pricing [INFERRED 0.85]

## Communities (60 total, 13 thin omitted)

### Community 0 - "Audit Logging"
Cohesion: 0.06
Nodes (38): AuditLogger, hash_text(), Any, Path, Privacy-preserving append-only audit events., Return a stable SHA-256 digest without retaining the source text., Remove literal values from parseable SQL, or retain only a digest., Write sanitized operational events to a local JSONL file. (+30 more)

### Community 1 - "Session Persistence"
Cohesion: 0.07
Nodes (30): PricingRule, One non-overlapping effective pricing window for a model., cost_rows_to_csv(), _csv_cell(), _json(), Any, Connection, Decimal (+22 more)

### Community 2 - "Agent Workflow Tests"
Cohesion: 0.06
Nodes (14): _make_agent(), Tests for the LangGraph agent workflow., Build an NL2SQLAgent with a mock LLM and the seeded test DB., TestCheckSecurity, TestExecuteSql, TestExecutionEdgeCases, TestFetchSchema, TestHighLevelRun (+6 more)

### Community 3 - "Command Line Interface"
Cohesion: 0.08
Nodes (38): ArgumentParser, Namespace, _build_agent(), build_parser(), cmd_ask(), cmd_config(), cmd_eval(), cmd_serve() (+30 more)

### Community 4 - "Cost Calculation"
Cohesion: 0.09
Nodes (34): RequestMode, LLM module: provider factory, model discovery, chat-model construction., calculate_cost(), CostBreakdown, CostLine, _d(), effective_pricing_rule(), estimate_model_cost() (+26 more)

### Community 5 - "Agent Database Integration"
Cohesion: 0.08
Nodes (13): BaseChatModel, Collection, Database, Path, Row, Return a non-sensitive database label., Return a stable identity without reading database contents., Create the demo tables and (optionally) seed sample data. Idempotent: ``CREATE… (+5 more)

### Community 6 - "Model Discovery"
Cohesion: 0.10
Nodes (13): Exception, fallback_models(), list_models(), _list_ollama(), Hard-coded fallback list when the SDK call fails or is unavailable., Discover available model IDs for ``provider``. Hosted providers return their…, _ollama_alive(), ollama_model() (+5 more)

### Community 7 - "Upload Handling"
Cohesion: 0.14
Nodes (22): cache_resource, Path, ValueError, Validation and session-local storage for untrusted SQLite uploads., Raised when an uploaded file cannot be accepted as SQLite., Reject unsupported or oversized uploads before reading their contents., Validate filename, size, and SQLite magic header; return SHA-256., Store validated bytes under a content-derived session-local name. (+14 more)

### Community 8 - "Provider Configuration"
Cohesion: 0.12
Nodes (16): model_validator, Configuration module for the NL2SQL agent., default_model_for(), env_var_value(), Provider, Application configuration via Pydantic Settings. Loads from environment…, Return the API key configured for ``provider``, or ``None``., Read a name from the process environment without a Settings instance. (+8 more)

### Community 9 - "Query Plans and Metrics"
Cohesion: 0.14
Nodes (16): QueryMetrics, QueryPlan, QueryPlanNode, Shared database contracts and query observability types., One normalized node in a database query plan., A normalized, non-executing query plan., Return a JSON-serializable representation., Runtime measurements recorded for an executed query. (+8 more)

### Community 10 - "SQL Policy Validation"
Cohesion: 0.14
Nodes (9): Validate that ``sql`` is safe to execute under ``policy``. Returns the list of…, Allow-list knobs for SQL safety., SQLPolicy, validate_sql(), TestCTE, TestEmptyAndInvalid, TestJoins, TestSubqueries (+1 more)

### Community 11 - "Prompt Templates"
Cohesion: 0.12
Nodes (10): Prompt module: centralized, versioned prompt templates., error_section(), format_data(), LLM prompt templates. Centralized so the prompts can be versioned, tested, and…, Return the writer contract for the active SQL dialect., Format the "previous attempt failed" section for the writer prompt., Format the data block for the summarizer prompt., sql_writer_system() (+2 more)

### Community 12 - "Runtime Settings"
Cohesion: 0.16
Nodes (6): BaseSettings, field_validator, Runtime configuration for the NL2SQL agent. Values are resolved in this order:…, Settings, parametrize, TestSettings

### Community 13 - "Dashboard Pages"
Cohesion: 0.17
Nodes (20): DataFrame, costs_page(), insights_page(), _optional_decimal(), _parse_date(), pricing_page(), datetime, Decimal (+12 more)

### Community 14 - "SQL AST Inspection"
Cohesion: 0.17
Nodes (20): Expression, Func, Select, _check_select(), _flatten_selects(), _function_name(), _is_aggregate_call(), ValueError (+12 more)

### Community 15 - "Provider Adapters"
Cohesion: 0.19
Nodes (19): ChatAnthropic, ChatGoogleGenerativeAI, ChatOllama, ChatOpenAI, _build_anthropic(), _build_gemini(), _build_huggingface(), _build_ollama() (+11 more)

### Community 16 - "LangGraph Orchestration"
Cohesion: 0.16
Nodes (10): CompiledStateGraph, NL2SQLAgent, Return a compiled LangGraph workflow ready for invocation., Return a graph that stops after SQL validation and preflight., Run the workflow end-to-end and return the final state. Returns a dict…, Stream (node_name, state_update) events for live UI updates., Generate, validate, and preflight SQL without executing it., Stream preparation stages without executing SQL. (+2 more)

### Community 17 - "Test Fixtures"
Cohesion: 0.16
Nodes (18): MonkeyPatch, empty_db(), example_questions(), make_state(), mock_llm(), fixture, Path, Shared pytest fixtures and helpers. (+10 more)

### Community 18 - "Query Result Formatting"
Cohesion: 0.15
Nodes (9): _csv_cell(), _fmt_cell(), QueryResult, Standalone pretty-printer used by tests and CLI., A successful SQL execution result., Render the result as a Markdown table., Neutralize string cells that spreadsheet programs may execute., render_table() (+1 more)

### Community 19 - "CLI Tests"
Cohesion: 0.11
Nodes (5): Natural Language to SQL Agent — production-grade local-first agent. Top-level…, Tests for the CLI entry point., TestAskCommand, TestEvalCommand, TestParser

### Community 20 - "Provider UI Controls"
Cohesion: 0.18
Nodes (15): env_var_for(), Return the standard environment variable name for the provider's API key., _default_models(), Any, Provider, Streamlit UI helpers (separated from the entry point for testability)., Render the chat history from ``st.session_state.messages``., Create a status expander that the caller will write to. (+7 more)

### Community 21 - "PostgreSQL Backend"
Cohesion: 0.19
Nodes (9): DatabaseError, RuntimeError, A provider-neutral database failure safe for workflow handling., PostgresDatabase, Any, Connection, PostgreSQL access constrained by role checks and read-only transactions., Return a stable opaque connection identity without exposing the DSN. (+1 more)

### Community 22 - "Chat Model Factory"
Cohesion: 0.21
Nodes (4): build_chat_model(), BaseChatModel, Build a LangChain chat model from runtime configuration. Args: settings: A…, TestBuildChatModel

### Community 23 - "SQL Validator Tests"
Cohesion: 0.15
Nodes (7): parametrize, Tests for the SQL safety validator., TestDangerousFunctions, TestDestructiveStatements, TestFalsePositives, TestMultiStatement, TestSafeQueries

### Community 24 - "Approval Execution Flow"
Cohesion: 0.23
Nodes (6): Any, Read the database schema and return it as a state update., Validate the generated SQL against :class:`SQLPolicy`., Run the validated SQL against the database., Ask the LLM to write a natural-language answer from the data., Revalidate and execute an optionally edited prepared query.

### Community 25 - "Settings Cache"
Cohesion: 0.21
Nodes (6): get_settings(), Return the cached :class:`Settings` instance. Use this as a…, Clear the settings cache. Tests use this to pick up env changes., reset_settings_cache(), live_settings(), TestConfigCommand

### Community 26 - "Agent State"
Cohesion: 0.16
Nodes (8): AgentState, The complete state threaded through the workflow. All fields are optional…, Ask the LLM to produce a SQL query from schema + question., Decide whether to execute the SQL or summarize the safety error., Retry failed preparation or finish with a safe candidate/error., Retry the writer on execution error, otherwise summarize., Deterministic answer when the LLM summarizer is unavailable., TypedDict

### Community 28 - "SQLite Connections"
Cohesion: 0.24
Nodes (7): _list_tables(), Connection, Yield a hardened read-only query connection. The connection is closed when the…, Yield the narrowly scoped connection used only for demo setup., Return ordinary user tables in deterministic order., Execute a single SELECT and return its result. Enforces ``max_rows`` by…, Compile and normalize a query plan without executing the SELECT.

### Community 29 - "SQL Preparation"
Cohesion: 0.26
Nodes (4): prepare_sql(), Collection, Validate, authorize, and canonicalize one executable SELECT., TestPrepareSql

### Community 30 - "Streamlit Application"
Cohesion: 0.32
Nodes (12): _apply_cost(), _budget_alerts(), _build_agent(), _chat_page(), _ensure_session(), _history_message(), _persist_result(), Any (+4 more)

### Community 31 - "Database Backend Contract"
Cohesion: 0.18
Nodes (3): DatabaseBackend, Protocol, Minimum interface required by the NL2SQL workflow.

### Community 32 - "System Architecture"
Cohesion: 0.20
Nodes (10): AST SQL Safety, Multi-provider LLM Factory, NL2SQL Agent, PostgreSQL Read-only Role, Query Insights, Read-only Database Backends, Factory Pattern, Defense in Depth (+2 more)

### Community 33 - "Physical Table Discovery"
Cohesion: 0.31
Nodes (4): Return the set of table names referenced in ``sql``. Used by the executor's…, Return physical table names from already-parsed statements., referenced_tables(), TestReferencedTables

### Community 35 - "Security Package"
Cohesion: 0.25
Nodes (6): Security module: SQL validation, input sanitization, redaction., parse_sql(), PreparedSQL, Validated SQL ready for execution., Parse ``sql`` into a list of statements using sqlglot. Empty / whitespace-only…, TestParseSql

### Community 36 - "Agent Package"
Cohesion: 0.32
Nodes (5): Agent module: LangGraph workflow, state, and high-level entry point., Typed state for the LangGraph agent. Using ``TypedDict`` (not Pydantic) to keep…, NodeTrace, LangGraph workflow for the NL2SQL agent. The workflow is: ``` fetch_schema →…, One step of an agent run, for observability.

### Community 37 - "PostgreSQL Tests"
Cohesion: 0.46
Nodes (7): _cursor(), Tests for PostgreSQL read-only connection and plan behavior., _safe_connection(), test_connection_is_read_only_parameterized_and_rolled_back(), test_fingerprint_never_contains_dsn(), test_preflight_uses_json_explain_without_analyze(), test_privileged_postgres_role_is_rejected()

### Community 38 - "Streamlit Tests"
Cohesion: 0.38
Nodes (5): AppTest, Tests for user-visible Streamlit provider controls., _sidebar_app(), test_sidebar_accepts_custom_hugging_face_model(), test_sidebar_shows_only_approved_cloud_models()

### Community 39 - "Architecture Concepts"
Cohesion: 0.33
Nodes (6): Approval-first Execution, Interactive Architecture Diagram, Interactive System Overview, Effective-dated Pricing, LangGraph Workflow, Local State Store

### Community 40 - "Upgrade Compatibility"
Cohesion: 0.40
Nodes (5): Approval-first Public API, SQLite Default and PostgreSQL Opt-in, Backward Compatibility, Compatible Public API, v0.4.0 Upgrade Addendum

### Community 41 - "Release Features"
Cohesion: 0.50
Nodes (5): Effective-dated Model Pricing, Five-view Streamlit UI, Saved Sessions, Versioned Local State Store, Per-call Query Pricing

### Community 43 - "Persistence Security"
Cohesion: 0.50
Nodes (4): Cost Export Privacy, Persistence Privacy Boundary, Runtime Data Safety, SQLite Upload Validation

### Community 44 - "Database Safety Documentation"
Cohesion: 1.00
Nodes (3): Database Backend Contract, Read-only Query Insights, SQL Safety Defense in Depth

### Community 45 - "Release Overview"
Cohesion: 0.67
Nodes (3): Five-view Streamlit Workspace, PostgreSQL Read-only Backend, v0.4.0 Release

### Community 46 - "Approval Workflow Documentation"
Cohesion: 0.67
Nodes (3): Approval-first Execution, LangGraph Workflow, Approval-first Analysis

## Knowledge Gaps
- **32 isolated node(s):** `nl2sql-agent`, `Dependabot Dependency Updates`, `Continuous Integration Workflow`, `Pre-commit Quality Gates`, `Generated Graph Artifacts` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `NL2SQLAgent` connect `LangGraph Orchestration` to `Agent Workflow Tests`, `Command Line Interface`, `Agent Package`, `Agent Database Integration`, `Approval Execution Flow`, `Agent State`, `Streamlit Application`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `_make_agent()` connect `Agent Workflow Tests` to `LangGraph Orchestration`, `Settings Cache`, `SQL Policy Validation`, `Audit Logging`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `get_settings()` connect `Settings Cache` to `Agent Workflow Tests`, `Command Line Interface`, `Agent Package`, `Agent Database Integration`, `Provider Configuration`, `Runtime Settings`, `Dashboard Pages`, `Provider Adapters`, `Chat Model Factory`, `Streamlit Application`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `_make_agent()` (e.g. with `get_settings()` and `SQLPolicy`) actually correct?**
  _`_make_agent()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Settings` (e.g. with `.test_injected_database_is_never_seeded()` and `.test_anthropic_uses_medium_adaptive_thinking_without_sampling()`) actually correct?**
  _`Settings` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `NL2SQLAgent` (e.g. with `AgentState` and `.test_count_employees()`) actually correct?**
  _`NL2SQLAgent` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `build_chat_model()` (e.g. with `.test_count_employees()` and `.test_total_engineering_salary()`) actually correct?**
  _`build_chat_model()` has 15 INFERRED edges - model-reasoned connections that need verification._