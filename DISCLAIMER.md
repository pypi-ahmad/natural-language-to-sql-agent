# Disclaimer

Please read this before pointing NL2SQL Agent at a database you care about.

## You run this entirely on your own machine, with your own credentials

NL2SQL Agent is a local-first tool. There is no hosted version, backend server
operated by the author, or account system. It connects to SQLite or PostgreSQL
using the model provider you configure. Settings accept constructor values,
environment variables and `.env`; the CLI and UI also support provider-key
overrides. API keys and the PostgreSQL DSN are masked in `config` output. Other
configuration, including paths and endpoint addresses, can still be private.
See [SECURITY.md](SECURITY.md). Legacy Agnes credential aliases remain supported.

## What actually leaves your machine

- The writer sends your question, selected schema context, clarification replies
  and error feedback to the configured model. Demo samples and any enabled
  uploaded samples or curated catalog values can also enter the prompt.
- Successful execution renders the answer locally from database values without
  another model call. The legacy non-executed summarization path can still send
  supplied result text to the model.
- Hosted providers receive this prompt context. Ollama is local only when its
  endpoint runs on your machine; the application also accepts remote HTTPS
  Ollama endpoints.

## What remains on disk

Saved sessions retain questions and answer text, which can contain result
values. Pending approval retains questions, clarifications and unapproved SQL;
approved-run records retain SQL, including literals. Structured row and CSV
payloads are excluded, but this does not remove values already present in text.
Audit JSONL uses separate question hashing and SQL-literal redaction. Protect
the state file, audit log, temporary upload workspace and backups.

## You are responsible for the data and database you connect

You, and only you, are responsible for:

- Deciding whether the database you point this at may have its schema and query results sent to a third-party LLM provider. This includes proprietary business data, customer records, or anything under a confidentiality or compliance obligation.
- Understanding and accepting your chosen provider's own data-handling, retention, and training-use policies.
- Any costs your provider charges for API usage. UI estimates and budget alerts
  do not enforce a spending cap. The separate benchmark driver has a conservative
  persistent budget ledger; it does not cap ordinary CLI/UI calls or reimburse
  charges.
- The credentials and access scope of the database connection you provide. NL2SQL Agent enforces read-only query safety on its own side (see [ARCHITECTURE.md](ARCHITECTURE.md) and [SECURITY.md](SECURITY.md)), but a misconfigured connection string with write access is your responsibility, not the application's.

If your data must never leave your machine, use only the local Ollama provider.

## No warranty, no liability

This software is provided "as is," without warranty of any kind, as stated in the [MIT License](LICENSE). The author is not liable for any damage, data loss, unintended disclosure, API costs, or other consequences arising from your use of this tool. Use it at your own risk.

## No financial support wanted

This project is free, open-source, and does not want or accept donations, sponsorships, or any other form of financial contribution — see [SUPPORT.md](SUPPORT.md).
