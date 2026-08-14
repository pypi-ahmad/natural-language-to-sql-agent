# Security Policy

## Runtime Data Safety

Generated SQL is treated as untrusted. Query connections are read-only,
AST validation permits one SELECT statement, table allowlists restrict the
visible database surface, and SQLite progress handlers bound execution.
PostgreSQL requires a non-privileged role, verifies read-only transaction
state, confines names to one configured schema, and uses non-executing JSON
plans rather than `EXPLAIN ANALYZE`.
Operational audits store hashes and literal-redacted SQL only; raw questions,
results, database paths, samples, and credentials are excluded.
The `config` CLI command replaces configured API keys with `***`.
This includes `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`,
`HF_TOKEN`, and `XAI_API_KEY`; launcher output never prints their values.
Audit events accept only an explicit field allowlist, and database failures use
generic user-facing messages. CSV exports prefix formula-like cells before they
reach spreadsheet software.
CI audits the locked dependency graph with `uv audit --locked`; transitive
security floors are constraints rather than advertised runtime dependencies.

SQLite uploads are limited by extension, byte size, and magic header, written
under a content-derived name in a per-session temporary directory, and opened
read-only. Uploaded sample rows are excluded from model prompts unless the user
explicitly enables them.
Uploads are capped at 50 MB in both application validation and Streamlit server
configuration. The UI and CLI are single-user, loopback-only tools. Operators
configure `NL2SQL_OLLAMA_BASE_URL`; browser users cannot edit it. Plain HTTP is
accepted only for loopback endpoints, while remote endpoints require HTTPS.
Hugging Face and xAI use fixed HTTPS API roots. Custom Hugging Face values are
model repository identifiers, not editable endpoint URLs, and are validated
before requests are constructed.

The local state database stores messages, pending approvals, approved SQL,
bounded plans/metrics, usage, and immutable pricing snapshots. It explicitly
excludes raw result rows, CSV payloads, uploads, schemas, API keys, DSNs, and
blocked or unapproved SQL. Protect the local user profile and state file as you
would any conversation history.

UI cost estimates use provider-reported usage and locally configured pricing.
They do not inspect or expose keys, prompts, result rows, or provider billing
records, and are not authoritative invoices. CSV exports contain cost metadata
only and receive formula neutralization at serialization.

## Supported Versions

Security fixes are applied to the default branch and recent actively maintained updates.

## Reporting a Vulnerability

Report potential vulnerabilities through [GitHub private vulnerability
reporting](https://github.com/pypi-ahmad/natural-language-to-sql-agent/security/advisories/new).
Do not disclose vulnerability details in a public issue.

When reporting, include:

- A clear description of the issue
- Impact assessment
- Reproduction steps or proof of concept
- Suggested remediation, if available

Avoid posting exploit details that could put users at risk.

## Response Process

Maintainers will triage reports, assess severity, and communicate remediation status
through issue updates and release/change notes when fixes are available.
